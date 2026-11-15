"""Optional real local AI check; no student data, no model downloads."""
import json
import time
import httpx

started=time.monotonic()
with httpx.Client(base_url='http://127.0.0.1:11434',timeout=120,trust_env=False) as client:
    tags=client.get('/api/tags');tags.raise_for_status()
    models=tags.json()['models']
    names=[m['name'] for m in models if not m.get('remote_host') and not m.get('remote_model') and not m['name'].endswith(':cloud')]
    print('Installed local models:',names)
    if 'qwen3:4b-instruct' not in names:raise SystemExit('Default instruction model missing. No downloads performed.')
    r=client.post('/api/chat',json={'model':'qwen3:4b-instruct','stream':False,'format':{'type':'object','properties':{'status':{'type':'string'}},'required':['status']},'options':{'num_predict':30},'messages':[{'role':'user','content':'Return JSON with status equal to local-ready.'}]})
    r.raise_for_status();value=json.loads(r.json()['message']['content'])
    if value.get('status')!='local-ready':raise SystemExit('Schema/content check failed: '+str(value))
    print('Local structured chat succeeded in',round(time.monotonic()-started,1),'seconds')
