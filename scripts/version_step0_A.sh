#!/bin/bash
# version_step0_A.sh — A 站 (scott-lau-NEX / Worker) 第 0 步版本化迁移
# 用法: 经主控站 scp 到 /tmp 后 ssh 执行: bash /tmp/version_step0_A.sh
# 效果: /opt/llama.cpp → /opt/llama.cpp-9859 (实体) + /opt/llama.cpp (symlink)
# 退出: 0 成功 / 1 前置不满足 / 2 操作失败
set -euo pipefail
VER="9859"
TARGET="/opt/llama.cpp-${VER}"
LINK="/opt/llama.cpp"
STATION="A站(NEX/Worker)"

echo "=== [1/5] 前置检查 ($STATION) ==="
if test -L "$LINK"; then
    CUR=$(readlink "$LINK")
    if [[ "$CUR" == "llama.cpp-${VER}" ]]; then
        echo "✅ 已是受控状态: $LINK -> $CUR (幂等跳过)"
        "$LINK/llama-cli" --version | head -1
        exit 0
    fi
    echo "❌ symlink 指向非 ${VER}: $CUR"; exit 1
fi
if ! test -d "$LINK"; then echo "❌ $LINK 不存在"; exit 1; fi
if pgrep -x llama-server >/dev/null 2>&1 || pgrep -x ggml-rpc-server >/dev/null 2>&1; then
    echo "❌ 有推理进程在运行，先终止"; exit 1
fi
VOUT=$("$LINK/llama-cli" --version 2>&1 | head -1 || true)
echo "$VOUT" | grep -q "version: ${VER}" || { echo "❌ 版本号不匹配: $VOUT"; exit 1; }
echo "   版本确认: $VOUT"

echo "=== [2/5] 关键 MD5 基线核对 ==="
md5sum "$LINK/llama-cli" "$LINK/libggml-vulkan.so" "$LINK/libggml-rpc.so" "$LINK/libggml-cpu-zen4.so" | tee /tmp/step0_md5_check.txt
grep -q "^126494d96363e8feb5c36568be7ee522" /tmp/step0_md5_check.txt \
    || echo "⚠️ llama-cli MD5 与会话基线不符（继续，MANIFEST 记录实际值）"

echo "=== [3/5] mv（同文件系统原子 rename） ==="
sudo mv "$LINK" "$TARGET"

echo "=== [4/5] 建立相对 symlink ==="
sudo ln -sfn "llama.cpp-${VER}" "$LINK"

echo "=== [5/5] 冒烟：经 symlink 解析二进制 ==="
"$LINK/llama-cli" --version | head -1
ls -ld "$LINK"
echo "✅ $STATION 第 0 步完成: $LINK -> $(readlink "$LINK")"
echo "   下一步: bash /tmp/gen_manifest.sh ${TARGET}"
