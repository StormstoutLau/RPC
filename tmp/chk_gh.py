# -*- coding: utf-8 -*-
import json
for qid in ['G2','H1']:
    r=json.load(open('/tmp/res_nem120b/%s.jsonl'%qid,encoding='utf-8'))
    if 'error' in r:
        print(qid,'ERR',r['error'][:40]); continue
    a=r.get('answer') or ''
    print('{} [{}] ans={}tok comp={} el={}s'.format(qid,'OK' if len(a.split())>40 else 'EMPTY',len(a.split()),r.get('usage') and r['usage'].get('completion_tokens'),r.get('elapsed')))