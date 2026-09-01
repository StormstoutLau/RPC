#!/bin/bash
# glm_cold_move.sh — GLM-5.3-Flash 146G 冷移 B 站 → A 站 (USB4 rsync)
# 源: /home/scott-lau/.lmstudio/models/unsloth/GLM-5.3-Flash-GGUF
# 目标: A 站同路径 (LM Studio 语义不变)
SRC="/home/scott-lau/.lmstudio/models/unsloth/GLM-5.3-Flash-GGUF"
DST_HOST="scott-lau@10.10.10.1"
DST_DIR="/home/scott-lau/.lmstudio/models/unsloth/GLM-5.3-Flash-GGUF"
LOG="/tmp/glm_move.log"

echo "=== 源清单 ===" > $LOG
ls -lh $SRC/ >> $LOG 2>&1
echo "源大小: $(du -sh $SRC | cut -f1)" >> $LOG

# A 站建目录
ssh $DST_HOST "mkdir -p $DST_DIR" >> $LOG 2>&1

# 源端 sha256 (权威元数据, 供接收端校验 — 65G 级 sha ~2min, 146G 约 5min, 必做)
echo "=== 源端 sha256 计算中 ===" >> $LOG
sha256sum $SRC/*.gguf > /tmp/glm_source.sha256 2>>$LOG
cat /tmp/glm_source.sha256 >> $LOG

echo "=== rsync 传输 (USB4) ===" >> $LOG
rsync -a --info=progress2,stats1 -e "ssh -o StrictHostKeyChecking=no" \
  $SRC/ $DST_HOST:$DST_DIR/ >> $LOG 2>&1
RC=$?
echo "rsync rc=$RC" >> $LOG

if [ $RC -eq 0 ]; then
  echo "=== 接收端 sha256 校验 ===" >> $LOG
  ssh $DST_HOST "cd $DST_DIR && sha256sum *.gguf" > /tmp/glm_dest.sha256 2>>$LOG
  echo "--- 源 ---" >> $LOG; cat /tmp/glm_source.sha256 >> $LOG
  echo "--- 目标 ---" >> $LOG; cat /tmp/glm_dest.sha256 >> $LOG
  # 比较: 只比对 hash 列 (文件名同)
  if diff <(awk '{print $1}' /tmp/glm_source.sha256) <(awk '{print $1}' /tmp/glm_dest.sha256) >/dev/null; then
    echo "VERIFY_OK — 目标端 sha256 全一致" >> $LOG
    echo "=== 目标端最终状态 ===" >> $LOG
    ssh $DST_HOST "ls -lh $DST_DIR/ && df -h / | tail -1" >> $LOG 2>&1
    echo "READY_TO_DELETE_SOURCE" >> $LOG
  else
    echo "VERIFY_MISMATCH — 源端未删, 人工检查" >> $LOG
  fi
else
  echo "RSYNC_FAILED — 源端未删" >> $LOG
fi
tail -5 $LOG
