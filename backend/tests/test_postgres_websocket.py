"""Offline tests for the byte relay; no Supabase connection is made here."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import logging
import queue
import socket
import ssl
import struct
import threading

import pytest

from app import postgres_websocket as relay_module
from app.database import build_engine


HOST='aws-0-ap-south-1.pooler.supabase.com'
URL=f'postgresql://postgres.example:TEST-ONLY-NOT-A-REAL-SECRET@{HOST}:5432/postgres?sslmode=require'
SSL_REQUEST=struct.pack('!II',8,80877103)


@pytest.fixture(autouse=True)
def no_cloud_connections(monkeypatch):
    def forbidden(*args,**kwargs):
        raise AssertionError('Automatic relay tests must replace the WebSocket connection')
    monkeypatch.setattr(relay_module,'connect',forbidden)


class FragmentedSocket:
    """A TCP recv stand-in preserving unread bytes across arbitrary chunks."""
    def __init__(self,*chunks):
        self.chunks=deque(chunks)

    def recv(self,length):
        if not self.chunks:
            return b''
        chunk=self.chunks.popleft()
        if len(chunk)>length:
            self.chunks.appendleft(chunk[length:])
        return chunk[:length]


def tls_record(payload=b'opaque-test-payload',kind=22,version=0x0303):
    return struct.pack('!BHH',kind,version,len(payload))+payload


def test_endpoint_uses_only_same_supabase_hostname_and_documented_path():
    endpoint=relay_module.websocket_endpoint(URL)
    assert endpoint==f'wss://{HOST}/v2'
    assert 'TEST-ONLY' not in endpoint and 'postgres.example' not in endpoint


@pytest.mark.parametrize('port',[5432,6543])
def test_supported_pooler_ports_share_tls_websocket_endpoint(port):
    assert relay_module.websocket_endpoint(URL.replace(':5432/',f':{port}/'))==f'wss://{HOST}/v2'


@pytest.mark.parametrize('value',[
    'postgresql://user:secret@database.example/postgres?sslmode=require',
    'postgresql://user:secret@db.example.supabase.co/postgres?sslmode=require',
    f'postgresql://user:secret@{HOST}.evil.example/postgres?sslmode=require',
    f'postgresql://user:secret@{HOST}:12345/postgres?sslmode=require',
    f'postgresql://user:secret@{HOST}:5432/postgres?sslmode=disable',
    f'postgresql://user:secret@{HOST}:5432/postgres',
])
def test_unapproved_destination_or_insecure_connection_is_rejected(value):
    with pytest.raises(ValueError):relay_module.websocket_endpoint(value)


def test_initial_ssl_request_survives_tcp_fragmentation():
    stream=FragmentedSocket(SSL_REQUEST[:1],SSL_REQUEST[1:3],SSL_REQUEST[3:6],SSL_REQUEST[6:])
    assert relay_module._read_initial_packet(stream)==SSL_REQUEST


def test_concatenated_tcp_input_preserves_initial_and_tls_frame_boundaries():
    first=tls_record(b'first')
    second=tls_record(b'second',kind=23)
    stream=FragmentedSocket(SSL_REQUEST+first+second)
    assert relay_module._read_initial_packet(stream)==SSL_REQUEST
    assert relay_module._read_tls_record(stream)==first
    assert relay_module._read_tls_record(stream)==second
    assert relay_module._read_tls_record(stream) is None


@pytest.mark.parametrize('value',[
    b'',b'\x00',b'\x00\x00\x00',
    struct.pack('!I',7),struct.pack('!I',65537),SSL_REQUEST[:-1],
])
def test_missing_truncated_or_oversized_initial_packet_fails_closed(value):
    with pytest.raises(OSError):relay_module._read_initial_packet(FragmentedSocket(value))


def test_tls_record_survives_fragmented_header_and_payload():
    record=tls_record(b'\x00\x01\x02opaque')
    stream=FragmentedSocket(*(record[i:i+1] for i in range(len(record))))
    assert relay_module._read_tls_record(stream)==record


def test_tls_clean_eof_is_distinct_from_a_truncated_frame():
    assert relay_module._read_tls_record(FragmentedSocket()) is None
    for partial in (b'\x16',b'\x16\x03\x03',tls_record()[:-1]):
        with pytest.raises(OSError):relay_module._read_tls_record(FragmentedSocket(partial))


@pytest.mark.parametrize('header',[
    struct.pack('!BHH',0,0x0303,0),
    struct.pack('!BHH',22,0x0403,0),
    struct.pack('!BHH',23,0x0303,18433),
])
def test_invalid_tls_type_version_or_oversized_length_fails_closed(header):
    with pytest.raises(OSError):relay_module._read_tls_record(FragmentedSocket(header))


def test_lazy_listener_binds_only_loopback_and_lifecycle_is_idempotent():
    relay=relay_module.PostgresWebSocketRelay(URL,max_connections=2)
    assert relay.server is None and relay.thread is None
    relay.close()
    try:
        port=relay.start()
        assert 0<port<65536
        assert relay.server.server_address==('127.0.0.1',port)
        assert relay.start()==port
        thread=relay.thread
        assert thread.is_alive()
    finally:
        relay.close()
        relay.close()
    assert relay.server is None and not thread.is_alive()


def test_listener_can_restart_after_a_complete_close():
    relay=relay_module.PostgresWebSocketRelay(URL)
    try:
        relay.start();first_thread=relay.thread
        relay.close()
        relay.start()
        assert relay.thread is not first_thread
        assert relay.server.server_address[0]=='127.0.0.1'
        assert relay.thread.is_alive()
    finally:relay.close()


def test_concurrent_first_connections_share_one_lazy_listener():
    relay=relay_module.PostgresWebSocketRelay(URL)
    try:
        with ThreadPoolExecutor(max_workers=8) as workers:
            ports=list(workers.map(lambda _:relay.start(),range(8)))
        assert len(set(ports))==1
        assert relay.server.server_address==('127.0.0.1',ports[0])
    finally:relay.close()


class FakeWebSocket:
    def __init__(self):
        self.messages=[]
        self.incoming=queue.Queue()
        self.received_tls=threading.Event()

    def __enter__(self):return self
    def __exit__(self,*args):self.close()

    def send(self,data):
        self.messages.append(data)
        if data==SSL_REQUEST:self.incoming.put(b'S')
        else:
            self.received_tls.set()
            self.incoming.put(None)

    def __iter__(self):
        while True:
            data=self.incoming.get(timeout=3)
            if data is None:return
            yield data

    def close(self):self.incoming.put(None)


def test_relay_preserves_complete_frames_and_verifies_outer_tls(monkeypatch):
    websocket=FakeWebSocket()
    connection_options={}
    def connected(endpoint,**kwargs):
        connection_options.update(endpoint=endpoint,**kwargs)
        return websocket
    monkeypatch.setattr(relay_module,'connect',connected)
    relay=relay_module.PostgresWebSocketRelay(URL)
    record=tls_record(b'private-opaque-TLS-ciphertext',kind=23)
    try:
        with socket.create_connection(('127.0.0.1',relay.start()),timeout=3) as client:
            client.sendall(SSL_REQUEST)
            assert client.recv(1)==b'S'
            client.sendall(record)
            assert websocket.received_tls.wait(3)
        assert websocket.messages==[SSL_REQUEST,record]
        assert connection_options['endpoint']==f'wss://{HOST}/v2'
        context=connection_options['ssl']
        assert context.verify_mode==ssl.CERT_REQUIRED and context.check_hostname
        assert connection_options['proxy'] is None
    finally:relay.close()


def test_plain_postgres_startup_is_not_forwarded(monkeypatch):
    websocket=FakeWebSocket()
    monkeypatch.setattr(relay_module,'connect',lambda *args,**kwargs:websocket)
    relay=relay_module.PostgresWebSocketRelay(URL)
    try:
        with socket.create_connection(('127.0.0.1',relay.start()),timeout=3) as client:
            client.sendall(struct.pack('!II',8,196608))
            try:assert client.recv(1)==b''
            except ConnectionResetError:pass
        assert websocket.messages==[]
    finally:relay.close()


def test_stopping_listener_preserves_an_existing_transport(monkeypatch):
    websocket=FakeWebSocket()
    monkeypatch.setattr(relay_module,'connect',lambda *args,**kwargs:websocket)
    relay=relay_module.PostgresWebSocketRelay(URL)
    record=tls_record(b'existing-checked-out-connection',kind=23)
    try:
        with socket.create_connection(('127.0.0.1',relay.start()),timeout=3) as client:
            client.sendall(SSL_REQUEST)
            assert client.recv(1)==b'S'
            relay.stop_listener()
            assert relay.server is None
            client.sendall(record)
            assert websocket.received_tls.wait(3)
        assert websocket.messages==[SSL_REQUEST,record]
    finally:relay.close()


def test_connection_failure_logs_only_class_name(monkeypatch,caplog):
    secret='PRIVATE-DUMMY-CREDENTIAL-DO-NOT-LOG'
    def failed(*args,**kwargs):raise OSError(secret)
    monkeypatch.setattr(relay_module,'connect',failed)
    relay=relay_module.PostgresWebSocketRelay(URL)
    with caplog.at_level(logging.DEBUG,logger=relay_module.__name__):
        try:
            with socket.create_connection(('127.0.0.1',relay.start()),timeout=3) as client:
                try:assert client.recv(1)==b''
                except ConnectionResetError:pass
        finally:relay.close()
    assert 'OSError' in caplog.text
    assert secret not in caplog.text and 'TEST-ONLY' not in caplog.text


def test_engine_websocket_mode_is_lazy_and_keeps_postgres_identity_and_tls(monkeypatch):
    relays=[]
    class FakeRelay:
        def __init__(self,url,max_connections):
            self.url=url;self.limit=max_connections;self.starts=0
            relays.append(self)
        def start(self):self.starts+=1;return 61234
        def stop_listener(self):pass
        def close(self):pass
    monkeypatch.setattr(relay_module,'PostgresWebSocketRelay',FakeRelay)
    engine=build_engine(URL,pool_size=2,max_overflow=3,transport='supabase_websocket')
    try:
        assert len(relays)==1 and relays[0].limit==5 and relays[0].starts==0
        args,params=engine.dialect.create_connect_args(engine.url)
        original=params.copy()
        for hook in engine.dialect.dispatch.do_connect:hook(engine.dialect,None,args,params)
        assert relays[0].starts==1
        for key in ('host','user','password','dbname','sslmode'):assert params[key]==original[key]
        assert params['hostaddr']=='127.0.0.1' and params['port']==61234
        assert params['gssencmode']=='disable'
        assert params['sslmode']=='require'
    finally:engine.dispose()


def test_direct_engine_never_creates_a_relay(monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('Direct transport must not start a relay')
    monkeypatch.setattr(relay_module,'PostgresWebSocketRelay',forbidden)
    engine=build_engine(URL)
    engine.dispose()


def test_unknown_transport_fails_instead_of_falling_back():
    with pytest.raises(ValueError):build_engine(URL,transport='untrusted_proxy')


def test_engine_dispose_stops_listener_and_future_connections_restart_it(monkeypatch):
    relays=[]
    actual_relay=relay_module.PostgresWebSocketRelay
    class RecordedRelay(actual_relay):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            relays.append(self)
    monkeypatch.setattr(relay_module,'PostgresWebSocketRelay',RecordedRelay)
    engine=build_engine(URL,transport='supabase_websocket')
    relay=relays[0]
    try:
        args,params=engine.dialect.create_connect_args(engine.url)
        for hook in engine.dialect.dispatch.do_connect:hook(engine.dialect,None,args,params)
        first_server=relay.server
        first_thread=relay.thread
        assert first_server.server_address[0]=='127.0.0.1'
        engine.dispose()
        assert relay.server is None and not first_thread.is_alive()
        for hook in engine.dialect.dispatch.do_connect:hook(engine.dialect,None,args,params)
        assert relay.server is not first_server
        assert relay.thread.is_alive()
        assert params['hostaddr']=='127.0.0.1'
        assert params['sslmode']=='require'
    finally:
        engine.dispose()
        relay.close()
