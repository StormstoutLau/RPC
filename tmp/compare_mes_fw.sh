#!/bin/bash
# 对比本机与 B 站的 MES/GC firmware 关键文件 (B 站经环网 10.10.11.1)
set +e
echo "=== C 本机 MES/GC firmware md5 ==="
for f in gc_11_0_0_mes.bin.zst gc_11_0_0_mes1.bin.zst gc_11_0_0_mes_2.bin.zst gc_11_0_0_pfp.bin.zst gc_11_0_0_me.bin.zst gc_11_0_0_mec.bin.zst gc_11_0_0_imu.bin.zst; do
  h=$(md5sum /lib/firmware/amdgpu/$f 2>/dev/null | cut -d' ' -f1)
  printf "%-24s %s\n" "$f" "${h:-MISSING}"
done
echo ""
echo "=== B 站 (环网) 同文件 md5 ==="
ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=no scott-lau@10.10.11.1 'for f in gc_11_0_0_mes.bin.zst gc_11_0_0_mes1.bin.zst gc_11_0_0_mes_2.bin.zst gc_11_0_0_pfp.bin.zst gc_11_0_0_me.bin.zst gc_11_0_0_mec.bin.zst gc_11_0_0_imu.bin.zst; do h=$(md5sum /lib/firmware/amdgpu/$f 2>/dev/null | cut -d" " -f1); printf "%-24s %s\n" "$f" "${h:-MISSING}"; done'