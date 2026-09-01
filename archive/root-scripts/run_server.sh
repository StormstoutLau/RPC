#!/bin/bash
# run_server.sh - 启动 OpenAI 兼容 API 服务 (llama-server + RPC 分布式推理)
# 部署位置: B 站 (Master) ~/llama-distributed/run_server.sh
# 用法: bash ~/llama-distributed/run_server.sh [端口]
# 前置: A 站 (Worker) 已运行 /llama-distributed/start_rpc.sh

PORT="${1:-8080}"
CONFIG_FILE="/llama-distributed/inference.conf"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ 配置文件不存在: $CONFIG_FILE"
    exit 1
fi
source "$CONFIG_FILE"

if [ -z "$MODEL_PATH" ] || [ ! -f "$MODEL_PATH" ]; then
    echo "❌ 模型文件不存在或未指定: $MODEL_PATH"
    exit 1
fi

# 检查 RPC Worker (A 站) 可达
RPC_HOST=$(echo "$RPC_ADDR" | cut -d':' -f1)
RPC_PORT=$(echo "$RPC_ADDR" | cut -d':' -f2)
if ! nc -z "$RPC_HOST" "$RPC_PORT" 2>/dev/null; then
    echo "❌ 无法连接 RPC Worker $RPC_ADDR，请先在 A 站运行 /llama-distributed/start_rpc.sh"
    exit 1
fi

# 避免重复启动
if pgrep -f "llama-server.*--port $PORT" > /dev/null; then
    echo "⚠️ llama-server 已在端口 $PORT 运行，PID: $(pgrep -f "llama-server.*--port $PORT")"
    exit 0
fi

LOG_DIR="$HOME/llama-distributed/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/server_$(date +%Y%m%d_%H%M%S).log"

# 构建命令 (与 run_inference.sh 同源参数, 仅将 llama-cli 换成 llama-server)
CMD="/opt/llama.cpp/llama-server -m \"$MODEL_PATH\""
CMD="$CMD --rpc $RPC_ADDR"
CMD="$CMD -ngl $GPU_LAYERS"
CMD="$CMD -c $CTX_SIZE"
CMD="$CMD -t $THREADS"
CMD="$CMD -b $BATCH_SIZE"
if [ -n "$N_CPU_MOE" ]; then
    CMD="$CMD --n-cpu-moe $N_CPU_MOE"
fi
if [ "$FLASH_ATTN" = "true" ]; then
    CMD="$CMD -fa on"
fi
CMD="$CMD --host 0.0.0.0 --port $PORT"

echo "🚀 启动 API 服务: $CMD"
echo "   日志: $LOG_FILE"
nohup bash -c "$CMD" > "$LOG_FILE" 2>&1 &
SERVER_PID=$!

# 等待模型加载完成 (大模型经 RPC 分发需数分钟)
echo "⏳ 等待模型加载 (每10秒探测一次, 最长15分钟)..."
for i in $(seq 1 90); do
    sleep 10
    if curl -s --max-time 3 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '"ok"'; then
        echo "✅ 服务就绪: B站本机 http://127.0.0.1:$PORT  |  主控站 http://192.168.1.15:$PORT"
        echo "   OpenAI 兼容端点: /v1/chat/completions  |  模型名: $(basename "$MODEL_PATH" .gguf)"
        exit 0
    fi
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo "❌ 进程已退出，最后日志:"
        tail -20 "$LOG_FILE"
        exit 1
    fi
done
echo "⚠️ 15分钟未就绪 (仍在加载?)，请手动检查: curl http://127.0.0.1:$PORT/health"
echo "   进程 PID: $SERVER_PID, 日志: $LOG_FILE"
