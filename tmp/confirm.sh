#!/bin/bash
echo "=== 进程 ==="
ps -eo pid,etime,args | grep -E "dl_ms_enhanced|wget" | grep -v grep | cut -c1-110
echo "=== 分片3 size (两次 20s 间隔) ==="
stat -c %s ~/.lmstudio/models/lmstudio-community/Qwen3.8-Flash-Next-GGUF/UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00003-of-00003.gguf
sleep 20
stat -c %s ~/.lmstudio/models/lmstudio-community/Qwen3.8-Flash-Next-GGUF/UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00003-of-00003.gguf
echo "=== pid 文件 ==="
cat ~/dl-ms.pid 2>/dev/null; echo " (alive: $(kill -0 $(cat ~/dl-ms.pid 2>/dev/null) 2>/dev/null && echo yes || echo no))"