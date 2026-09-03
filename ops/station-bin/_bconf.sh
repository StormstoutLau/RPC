#!/bin/bash
echo "== 更新 gpt-oss-120b conf (CTX 131072, 与 A 站一致) =="
sudo sed -i 's/^CTX=.*/CTX=131072/' /etc/llama-instances/gpt-oss-120b.env
grep -E "CTX|PORT|MODEL_PATH" /etc/llama-instances/gpt-oss-120b.env