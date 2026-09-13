#!/bin/bash
python3 - <<'PY'
import json, glob
for f in sorted(glob.glob('/tmp/res_nem120b/*.jsonl')):
    id=f.split('/')[-1][:-6]
    r=json.load(open(f,encoding='utf-8'))
    if 'error' in r:
        print('{} [ERR] {}'.format(id, r['error'][:30]))
        continue
    a=r.get('answer') or ''
    u=r.get('usage') or {}
    fl='OK' if len(a.split())>40 else 'EMPTY'
    print('{} [{}] ans={}tok comp={} el={}s'.format(id,fl,len(a.split()),u.get('completion_tokens'),r.get('elapsed')))
PY