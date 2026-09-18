#!/bin/sh
# 冒烟夹具 golden（ADR-0007 阶段 0.5）—— 最小但**真断**的判据。
#   ① clean-inject 生效: ./.golden 存在（注入目标目录）
#   ② 本脚本确实落在 .golden/ 里（证明注入的就是这一份）
#   ③ cwd 为工作区根（golden 由 ( cd $W && eval ... ) 执行）
# 刻意不做重活: 夹具验证的是**派发/回收/裁决链**本身, 不是模型能力。
set -eu
[ -d ./.golden ] || { echo "SMOKE_GOLDEN_FAIL: ./.golden 不存在 — clean-inject 未生效或 cwd 非工作区根"; exit 1; }
[ -f ./.golden/smoke_dispatch_golden.sh ] || { echo "SMOKE_GOLDEN_FAIL: 本脚本未被注入到 .golden/"; exit 1; }
printf 'SMOKE_GOLDEN_OK pwd=%s\n' "$(pwd)"
