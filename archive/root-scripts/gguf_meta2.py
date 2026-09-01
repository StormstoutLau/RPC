#!/usr/bin/env python3
# dump head_count_kv 数组 (88 层, 混合架构中 mamba 层应为 0)
import struct

path = "/data/models/gguf/lmstudio-community/NVIDIA-Nemotron-3-Super-120B-A12B-GGUF/NVIDIA-Nemotron-3-Super-120B-A12B-Q4_K_M-00001-of-00003.gguf"
f = open(path, "rb")
assert f.read(4) == b"GGUF"
f.read(4); f.read(8)
n_kv = struct.unpack("<Q", f.read(8))[0]

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
        if et == 8: return [rd_str() for _ in range(n)]
        sz = {0:1,1:1,2:2,3:2,4:4,5:4,6:4,7:1}[et]
        vals = struct.unpack(f"<{n}{ {0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'B'}[et] }", f.read(n*sz))
        return list(vals)
    if t == 11: return struct.unpack("<Q", f.read(8))[0]
    if t == 12: return struct.unpack("<q", f.read(8))[0]
    if t == 13: return struct.unpack("<d", f.read(8))[0]
    raise ValueError(t)

kvs = {}
for _ in range(n_kv):
    k = rd_str()
    t = struct.unpack("<I", f.read(4))[0]
    kvs[k] = rd_val(t)

hkv = kvs.get("nemotron_h_moe.attention.head_count_kv")
ffn = kvs.get("nemotron_h_moe.feed_forward_length")
print("head_count_kv 数组 (88 层):")
print(hkv)
print("feed_forward_length 数组:")
print(ffn)
attn = [i for i, v in enumerate(hkv) if v > 0]
print(f"attention 层数: {len(attn)}/88, 位置: {attn}")
print(f"mamba/linear 层数: {88 - len(attn)}/88")
hd = kvs["nemotron_h_moe.embedding_length"] // kvs["nemotron_h_moe.attention.head_count"]
print(f"head_dim = {hd}")
kv_per_tok = sum(hkv) * hd * 2 * 2  # K+V, f16
print(f"KV bytes/token = {kv_per_tok} ({kv_per_tok/1024:.1f} KB)")
for ctx in (32768, 131072, 262144, 524288, 1048576):
    print(f"  ctx {ctx//1024:>5}k: KV = {kv_per_tok*ctx/1024**3:.2f} GiB")
