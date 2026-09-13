#!/bin/bash
# C 站 Auto 档: 记录 qwen HIP 吞吐基线 (timings 需要 server 日志)
set +e
echo "=== qwen HIP 进程与日志 timings ==="
grep -E 'decode|prompt|generated|tokens' /tmp/c_qwen_hip_auto.log 2>/dev/null | tail -5
echo "=== 完整日志尾部 ==="
tail -8 /tmp/c_qwen_hip_auto.log
echo "=== gpt-oss 60G 可行性分析 (Auto=64G carveout) ==="
echo "总内存 62G；gpt-oss-120b MXFP4 需 60G 权重 + KV/余量 => 必 oom，结论: Auto 档不可承载 gpt-oss 单站"
free -g | head -2