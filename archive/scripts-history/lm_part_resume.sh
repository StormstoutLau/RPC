#!/bin/bash
# lm_part_resume.sh — LM Studio .part 断点续传 (hf-mirror + aria2 -c)
# 依据: spec/lm-download/DESIGN.md (2026-08-29)
# 用法: lm_part_resume.sh [--dry-run] [任务号 1-8, 缺省=全部]
# 日志: /tmp/lm_resume.log (由调用方 nohup 重定向)
set -uo pipefail

MODE="/data"  # 默认实际目录在下方 task 定义里
MODELS=/home/scott-lau/.lmstudio/models
LOG_TAG="[lm-resume]"

log() { echo "$LOG_TAG $(date '+%m-%d %H:%M:%S') $*"; }

# --- task 定义: url|save_path|sha256|total_bytes ---
TASKS=(
  "https://hf-mirror.com/lmstudio-community/DeepSeek-V4-Flash-0731-GGUF/resolve/main/DeepSeek-V4-Flash-0731-MXFP4-00001-of-00004.gguf|$MODELS/lmstudio-community/DeepSeek-V4-Flash-0731-GGUF/DeepSeek-V4-Flash-0731-MXFP4-00001-of-00004.gguf|810cb08cd6b6a2d53c7dee42666e1021a95412b27236911d4bbc52c1d76b9780|39944333888"
  "https://hf-mirror.com/lmstudio-community/DeepSeek-V4-Flash-0731-GGUF/resolve/main/DeepSeek-V4-Flash-0731-MXFP4-00003-of-00004.gguf|$MODELS/lmstudio-community/DeepSeek-V4-Flash-0731-GGUF/DeepSeek-V4-Flash-0731-MXFP4-00003-of-00004.gguf|b3456e914dd112d14d06681e7e7fdcf260e21c86e1d0f501b2e5b4463a0cf481|39929776800"
  "https://hf-mirror.com/chatqaq/Qwen3.6-27B-Claude-Mythos-Distilled-MTP-GGUF/resolve/main/Qwen3.6-27B-Claude-Mythos-Distilled.Q8_0.gguf|$MODELS/chatqaq/Qwen3.6-27B-Claude-Mythos-Distilled-MTP-GGUF/Qwen3.6-27B-Claude-Mythos-Distilled.Q8_0.gguf|f8fcdd9300a775eed42cf42542f600b1e127af1394721a9e0fa5b7d226d2d920|29047083136"
  "https://hf-mirror.com/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF/resolve/main/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-Q8_K_P.gguf|$MODELS/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-Q8_K_P.gguf|4e7735df4d1e2ec721f2551f531b815702a2f89123238c564797eda4b0304bc2|31457990784"
  "https://hf-mirror.com/unsloth/GLM-5.3-Flash-GGUF/resolve/main/UD-IQ4_XS/GLM-5.3-Flash-UD-IQ4_XS-00002-of-00005.gguf|$MODELS/unsloth/GLM-5.3-Flash-GGUF/GLM-5.3-Flash-UD-IQ4_XS-00002-of-00005.gguf|7d64cf0395672c4322012841abec502ea7e20518299bb5e3069003f06f9e6de9|49989334176"
  "https://hf-mirror.com/unsloth/GLM-5.3-Flash-GGUF/resolve/main/UD-IQ4_XS/GLM-5.3-Flash-UD-IQ4_XS-00003-of-00005.gguf|$MODELS/unsloth/GLM-5.3-Flash-GGUF/GLM-5.3-Flash-UD-IQ4_XS-00003-of-00005.gguf|7c2c63c9c30f8060428fdf2ac935dbf2ee9ad8f771d62b6ae47a7f7f2c1520e7|49607025280"
  "https://hf-mirror.com/unsloth/GLM-5.3-Flash-GGUF/resolve/main/UD-IQ4_XS/GLM-5.3-Flash-UD-IQ4_XS-00004-of-00005.gguf|$MODELS/unsloth/GLM-5.3-Flash-GGUF/GLM-5.3-Flash-UD-IQ4_XS-00004-of-00005.gguf|06c90f191871317c92dd9d25a353b687aed44c50f3ac6c713e9fe410bc2d26dd|49486530144"
  "https://hf-mirror.com/unsloth/GLM-5.3-Flash-GGUF/resolve/main/UD-IQ4_XS/GLM-5.3-Flash-UD-IQ4_XS-00005-of-00005.gguf|$MODELS/unsloth/GLM-5.3-Flash-GGUF/GLM-5.3-Flash-UD-IQ4_XS-00005-of-00005.gguf|66ebf9ec85e04d3f44af674ae4f694acbc89cc53db75e42f2f4d3646bf321c0d|7729791616"
)

DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1 && shift
ONLY="${1:-}"

# --- pre-flight ---
# 写冲突判据: .part 文件是否被进程占用 (fuser) — 比进程名匹配精确
# (pgrep "lm.?studio" 会误匹配 llama-server 的 .lmstudio 模型路径)
if command -v fuser >/dev/null 2>&1; then
  BUSY=0
  for t in "${TASKS[@]}"; do
    IFS='|' read -r _url _save _sha _total <<< "$t"
    _part="$(dirname "$_save")/downloading_$(basename "$_save").part"
    [ -f "$_part" ] || continue
    if fuser "$_part" >/dev/null 2>&1; then
      log "ABORT: $_part 被进程占用 (LM Studio 下载器在写?) — 先关闭 GUI"
      BUSY=1
    fi
  done
  [ "$BUSY" = "1" ] && exit 1
else
  log "WARN: fuser 不可用, 跳过占用检查 (执行期间勿开 LM Studio GUI)"
fi
NEED_GB=209
AVAIL_KB=$(df -k "$MODELS" | awk 'NR==2{print $4}')
AVAIL_GB=$((AVAIL_KB / 1048576))
log "磁盘: $MODELS 可用 ${AVAIL_GB}GB, 需要 ~${NEED_GB}GB"
if [ "$AVAIL_GB" -lt "$NEED_GB" ]; then log "ABORT: 空间不足"; exit 1; fi
command -v aria2c >/dev/null || { log "ABORT: aria2c 未安装 (sudo apt install -y aria2)"; exit 1; }

resume_one() {
  local idx="$1" line="$2"
  local url save sha total
  IFS='|' read -r url save sha total <<< "$line"
  local dir part final_name
  dir=$(dirname "$save")
  final_name=$(basename "$save")
  part="$dir/downloading_${final_name}.part"

  # 已收编则跳过
  if [ -f "$save" ]; then log "[$idx] SKIP: 已存在 FINAL $final_name"; return 0; fi
  if [ ! -f "$part" ]; then log "[$idx] WARN: .part 不存在, 从零下载"; fi

  local have=0
  [ -f "$part" ] && have=$(stat -c%s "$part")
  local remain=$((total - have))
  log "[$idx] START $final_name: $have/$total B (剩 $((remain/1048576))MB)"

  if [ "$DRY" = "1" ]; then
    log "[$idx] DRY-RUN: aria2c -c -x16 -s16 --file-allocation=none -d '$dir' -o '$(basename "$part")' '$url'"
    return 0
  fi

  local t0=$(date +%s)
  aria2c -c -x16 -s16 --file-allocation=none \
    --max-tries=10 --retry-wait=5 --connect-timeout=20 \
    --auto-file-renaming=false --allow-overwrite=false \
    --summary-interval=60 --console-log-level=warn \
    -d "$dir" -o "$(basename "$part")" "$url" >> /tmp/aria2_task$idx.log 2>&1
  local rc=$?
  local t1=$(date +%s)

  # 校验 1: 字节数
  local got=0; [ -f "$part" ] && got=$(stat -c%s "$part")
  if [ "$got" != "$total" ]; then
    log "[$idx] FAIL: 字节不符 got=$got want=$total rc=$rc — 不收编, 保留 .part"
    return 1
  fi
  # 校验 2: sha256
  local s=$(sha256sum "$part" | awk '{print $1}')
  if [ "$s" != "$sha" ]; then
    log "[$idx] FAIL: sha256 不匹配 — 不收编, 保留 .part (人工决断是否删part重下)"
    return 1
  fi
  # 收编: 原子 mv
  mv "$part" "$save"
  log "[$idx] DONE $final_name: +$((remain/1048576))MB in $((t1-t0))s ($((remain/1048576/(t1-t0+1)))MB/s avg) sha256 OK"
  return 0
}

log "=== 开始: 8 任务, DRY=$DRY, ONLY=${ONLY:-all} ==="
FAIL=0
i=0
for t in "${TASKS[@]}"; do
  i=$((i+1))
  [ -n "$ONLY" ] && [ "$ONLY" != "$i" ] && continue
  resume_one "$i" "$t" || FAIL=$((FAIL+1))
done
log "=== 结束: 失败 $FAIL/8 ==="
exit $FAIL
