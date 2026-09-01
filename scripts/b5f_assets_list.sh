#!/bin/bash
# b5f_assets_list.sh — 列出 beszel 最新 release 全部资产 (B 站)
curl -s --max-time 20 https://api.github.com/repos/henrygd/beszel/releases/latest | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('tag:', d['tag_name'])
for a in d['assets']:
    print(a['name'], a['size'])
"