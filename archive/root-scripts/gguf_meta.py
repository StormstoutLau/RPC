#!/usr/bin/env python3
# gguf_meta.py — 解析 GGUF shard1 元数据 (nemotron_h_moe 架构参数)
import struct, sys

path = "/data/models/gguf/lmstudio-community/NVIDIA-Nemotron-3-Super-120B-A12B-GGUF/NVIDIA-Nemotron-3-Super-120B-A12B-Q4_K_M-00001-of-00003.gguf"
f = open(path, "rb")
assert f.read(4) == b"GGUF", "not gguf"
ver = struct.unpack("<I", f.read(4))[0]
n_tensors = struct.unpack("<Q", f.read(8))[0]
n_kv = struct.unpack("<Q", f.read(8))[0]
print(f"gguf v{ver}, tensors={n_tensors}, kv={n_kv}")

def rd_str():
    n = struct.unpack("<Q", f.read(8))[0]
    return f.read(n).decode("utf-8", errors="replace")

def rd_val(t):
    if t == 0: return struct.unpack("<B", f.read(1))[0]
    if t == 1: return struct.unpack("<b", f.read(1))[0]
    if t == 2: return struct.unpack("<H", f.read(2))[0]
    if t == 3: return struct.unpack("<h", f.read(2))[0]
    if t == 4: return struct.unpack("<I", f.read(4))[0]
    if t == 5: return struct.unpack("<i", f.read(4))[0]
    if t == 6: return struct.unpack("<f", f.read(4))[0]
    if t == 7: return struct.unpack("<B", f.read(1))[0]
    if t == 8: return rd_str()
    if t in (9, 10):
        et = struct.unpack("<I", f.read(4))[0]
        n = struct.unpack("<Q", f.read(8))[0]
        if et == 8:
            return [rd_str() for _ in range(n)]
        f.read(n * {0:1,1:1,2:2,3:2,4:4,5:4,6:4,7:1}[et]); return f"<array {n}x{et}>"
    if t == 11: return struct.unpack("<Q", f.read(8))[0]
    if t == 12: return struct.unpack("<q", f.read(8))[0]
    if t == 13: return struct.unpack("<d", f.read(8))[0]
    raise ValueError(f"type {t}")

kvs = {}
for _ in range(n_kv):
    k = rd_str()
    t = struct.unpack("<I", f.read(4))[0]
    v = rd_val(t)
    kvs[k] = v

# 输出关键架构参数
interesting = [k for k in kvs if any(s in k for s in
    ("arch", "context", "block_count", "embedding", "head_count", "head_dim",
     "feed_forward", "expert", "mamba", "attention.layer", "hybrid", "linear",
     "sliding", "layer_interval", "rope", "quant", "size_label", "name"))]
for k in sorted(interesting):
    print(f"{k} = {kvs[k]}")
