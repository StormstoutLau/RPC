#!/bin/bash
set -e
OC=/home/scott-lau/.config/opencode/opencode.jsonc
cp "$OC" "$OC.bak-20260904-b"
python3 - "$OC" <<'PY'
import sys,json,re
p=sys.argv[1]
s=open(p).read()
# 去注释(简单) + 去 trailing comma -> 解析
def strip_jsonc(s):
    # 去 // 注释 (排除字符串内)
    out=[];i=0;n=len(s);in_str=False
    while i<n:
        c=s[i]
        if c=='"':
            out.append(c);i+=1
            # consume string
            while i<n:
                if s[i]=='\\': out.append(s[i:i+2]);i+=2;continue
                if s[i]=='"': out.append(s[i]);i+=1;break
                out.append(s[i]);i+=1
            continue
        if c=='/' and i+1<n and s[i+1]=='/':
            while i<n and s[i]!='\n': i+=1
            continue
        out.append(c);i+=1
    t=''.join(out)
    # 去 trailing comma before } ]
    t=re.sub(r',\s*([}\]])', r'\1', t)
    return t
try:
    d=json.loads(strip_jsonc(s))
except Exception as e:
    print("PARSE FAIL:",e); sys.exit(2)
prov=d.setdefault('provider',{})
if 'cluster-local' in prov:
    print("already present, skip"); sys.exit(0)
prov['cluster-local']={
  "name":"B 站本地 unsloth gpt-oss",
  "npm":"@ai-sdk/openai-compatible",
  "options":{
    "baseURL":"http://127.0.0.1:8080/v1",
    "apiKey":"sk-unsloth-f5ec3cebea66f627889ae59edd8df5e3"
  },
  "models":{
    "gpt-oss":{
      "name":"GPT-OSS 120B MXFP4 (B 站 unsloth q8_0)",
      "limit":{"context":120000,"output":16384}
    }
  }
}
json.dump(d,open(p,'w'),indent=2,ensure_ascii=False)
print("cluster-local provider inserted correctly via json re-write")
PY
echo "== provider keys after =="
python3 -c "import json,re;s=open('/home/scott-lau/.config/opencode/opencode.jsonc').read();d=json.loads(re.sub(r',\s*([}\]])',r'\1',s).replace('//',''));print(list(d['provider'].keys()))"