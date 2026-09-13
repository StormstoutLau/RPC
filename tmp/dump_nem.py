# -*- coding: utf-8 -*-
import json, glob, os
d='/tmp/res_nem120b'
ids=['A1','A2','A3','B1','B2','C1','C2','D1','D2','E1','E2','F1','G1','G2','H1','H2','I1','I2','J1','J2']
out=[]
for q in ids:
    f=os.path.join(d,q+'.jsonl')
    if not os.path.exists(f):
        out.append('# '+q+' - MISSING\n'); continue
    r=json.load(open(f,encoding='utf-8'))
    out.append('# '+q+' - '+(r.get('title') or q)+'\n')
    out.append((r.get('answer') or '')+'\n\n---\n')
open('/tmp/nem120b_answers.md','w',encoding='utf-8').write('\n'.join(out))
print('Wrote /tmp/nem120b_answers.md')