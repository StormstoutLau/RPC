# -*- coding: utf-8 -*-
import json, glob, os
for model, d in [('Q3.8F(B)', r'd:\RPC\tmp\res_q38f'), ('M2.7(C)', r'd:\RPC\tmp\res_m27')]:
    print('=' * 10, model, '=' * 10)
    for f in sorted(glob.glob(os.path.join(d, '*.jsonl'))):
        r = json.load(open(f, encoding='utf-8'))
        rk = r.get('reasoning') or ''
        n = r.get('answer') or ''
        u = r.get('usage') or {}
        print(f"{r['id']}: ans={len(n.split())}tok reason={len(rk.split())}tok "
              f"elapsed={r.get('elapsed',0)}s comp={u.get('completion_tokens')} prompt={u.get('prompt_tokens')}")