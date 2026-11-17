"""Loopback PostgreSQL wire relay to Supabase's certificate-verified /v2 WSS proxy.

The PostgreSQL client still negotiates its own required TLS inside the WSS
connection. This module forwards bytes and never parses/logs SQL or credentials.
"""
import logging
import re
import socket
import socketserver
import ssl
import threading
import struct
from websockets.sync.client import connect
from websockets.exceptions import WebSocketException
from sqlalchemy.engine import make_url
from .db_url import validate_database_url

def websocket_endpoint(database_url):
    url=make_url(validate_database_url(database_url))
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*\.pooler\.supabase\.com',url.host or ''):
        raise ValueError('WebSocket transport requires a Supabase shared pooler hostname from the Connect dialog.')
    if url.port not in (None,5432,6543):
        raise ValueError('WebSocket transport supports the Supabase shared pooler only.')
    # The documented proxy is same-host /v2 on TLS port 443. No URL credentials.
    return 'wss://'+url.host+'/v2'

def _shutdown(sock):
    try:sock.shutdown(socket.SHUT_RDWR)
    except OSError:pass
    try:sock.close()
    except OSError:pass

def _read_exact(sock,length,allow_eof=False):
    data=bytearray()
    while len(data)<length:
        chunk=sock.recv(length-len(data))
        if not chunk:
            if allow_eof and not data:return None
            raise OSError('Truncated PostgreSQL transport frame')
        data.extend(chunk)
    return bytes(data)

def _read_initial_packet(sock):
    header=_read_exact(sock,4)
    length=struct.unpack('!I',header)[0]
    if length<8 or length>65536:raise OSError('Invalid PostgreSQL startup frame length')
    return header+_read_exact(sock,length-4)

def _read_tls_record(sock):
    header=_read_exact(sock,5,allow_eof=True)
    if header is None:return None
    length=struct.unpack('!H',header[3:5])[0]
    if header[0] not in (20,21,22,23) or header[1]!=3 or length>18432:
        raise OSError('Invalid TLS record in PostgreSQL transport')
    return header+_read_exact(sock,length)

class _Server(socketserver.ThreadingTCPServer):
    daemon_threads=True
    block_on_close=False
    allow_reuse_address=False

class _Handler(socketserver.BaseRequestHandler):
    def handle(self):
        relay=self.server.relay
        if not relay.slots.acquire(blocking=False):return
        client=self.request
        with relay.lock:relay.clients.add(client)
        try:
            # Hostname and chain verification stay enabled. No insecure context,
            # HTTP endpoint, arbitrary destination, or plaintext remote fallback.
            with connect(relay.endpoint,ssl=ssl.create_default_context(),proxy=None,compression=None,open_timeout=7,close_timeout=2,ping_interval=20,ping_timeout=20,max_size=8*1024*1024,max_queue=4) as websocket:
                with relay.lock:relay.peers.add(websocket)
                def upload():
                    try:
                        initial=_read_initial_packet(client)
                        if initial!=struct.pack('!II',8,80877103):raise OSError('PostgreSQL TLS is required')
                        websocket.send(initial)
                        # Supabase's WS proxy expects whole startup packets. TLS
                        # records are framed separately so fragmented TCP reads
                        # cannot be mistaken for another PG startup packet.
                        while (data:=_read_tls_record(client)) is not None:websocket.send(data)
                    except (OSError,WebSocketException):pass
                    finally:websocket.close()
                sender=threading.Thread(target=upload,daemon=True,name='ictroot-pg-wss-upload')
                sender.start()
                try:
                    for data in websocket:
                        if not isinstance(data,bytes):raise OSError('Expected binary PostgreSQL transport')
                        client.sendall(data)
                finally:
                    _shutdown(client)
                    websocket.close()
                    sender.join(timeout=3)
                    with relay.lock:relay.peers.discard(websocket)
        except (OSError,WebSocketException,TimeoutError) as error:
            # Only a class name, never messages, payloads, SQL or connection URLs.
            logging.getLogger(__name__).debug('Supabase WebSocket transport closed (%s)',type(error).__name__)
        finally:
            _shutdown(client)
            with relay.lock:relay.clients.discard(client)
            relay.slots.release()

class PostgresWebSocketRelay:
    def __init__(self,database_url,max_connections=10):
        self.endpoint=websocket_endpoint(database_url)
        self.lock=threading.RLock()
        self.slots=threading.BoundedSemaphore(max_connections)
        self.clients=set()
        self.peers=set()
        self.server=None
        self.thread=None

    def start(self):
        with self.lock:
            if self.server is None:
                server=_Server(('127.0.0.1',0),_Handler)
                server.relay=self
                self.server=server
                self.thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':0.1},daemon=True,name='ictroot-pg-wss-listener')
                self.thread.start()
            return self.server.server_address[1]

    def stop_listener(self):
        with self.lock:
            server=self.server;thread=self.thread
            self.server=None;self.thread=None
        if server:
            server.shutdown();server.server_close()
            if thread:thread.join(timeout=2)

    def close(self):
        self.stop_listener()
        with self.lock:
            clients=list(self.clients);peers=list(self.peers)
        for client in clients:_shutdown(client)
        for peer in peers:peer.close()
