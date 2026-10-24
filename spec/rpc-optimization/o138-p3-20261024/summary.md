# O-138 · P3 前置验证：halogen + 现有 GGUF + 现有 mtp.hgn ⇒ MTP 是否自动生效

- 日期：2026-10-24 · 站 C（192.168.10.37 · gfx1151 · 128 GB）
- 镜像：`ghcr.nju.edu.cn/peonist-ai/halogen-flash-server@sha256:2e98dc53…`（引擎自报 **version 0.18.13**）
- 权重：盘上既有 `UD-IQ4_XS` 三片 GGUF（93.7 GB）+ 同目录 `qwen38-flash-next-mtp.hgn`（1.52 GB）

## 结论

**MTP 默认开启、零开关**：draft head 放在 GGUF 旁边即被自动拾取（本次**未**设 `HALOGEN_MTP_HEAD`）。
⇒ **不需要给 llama.cpp 打 `#28243`，也不需要下载 115.55 GiB 原生主档**。

## 硬证据（逐字）

1) 启动日志：

```
checkpoint: 71.97 GiB in 1197 tensor(s) already resident (the repacked arena and the head file)
flash_serve: listening on 127.0.0.1:8730, 1 slots over ONE 8192-position KV pool, …
  MTP depth-2 (up to 7, confidence gate) selectable (drafter 1, speculates while alone)
halogen: engine listening after 26s
```

2) 响应 `timings.speculation`：

```json
"draft_n":15, "draft_n_accepted":15,
"speculation":{"drafter":"mtp","rounds":5,
  "head":{"rounds":2,"drafted":9,"accepted":9},
  "lookup":{"rounds":3,"drafted":6,"accepted":6}}
```

3) 引擎自报行：

```
serve_api: mtp 47 tok in 1.22s = 38.58 t/s | 5 rounds, commit 4.00/round |
  prompt 58, prefill 0.66s (58 new) | detok 17us/tok | 26 tok with the head off |
  pld 3 rounds, 2.00 acc/round | pool 256/8192 3% | think on, closed at 1 by answer room
```

## 本次容器参数

```
--device /dev/kfd --device /dev/dri --group-add 44 --group-add 992
--ipc=host --ulimit memlock=-1:-1 -p 127.0.0.1:8731:8731
-e HALOGEN_CHECKPOINT=/models/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf
-e HALOGEN_CTX=8192 -e HALOGEN_KV_SLOTS=1 -e HALOGEN_KV_POOL_POSITIONS=8192
-e HALOGEN_HOST_RESERVE_GIB=8 -e HALOGEN_CACHE_DIR=/cache
-e HALOGEN_DOWNLOAD=peonist-ai/halogen-qwen3.8-flash-next   # 只为拉 tokenizer/head（head 已在位）
-v /home/scott-lau/.lmstudio/models/lmstudio-community/Qwen3.8-Flash-Next-GGUF/UD-IQ4_XS:/models
```

⚠ **docker 不认 `--group-add keep-groups`**（那是 podman 语法）⇒ 用数字 GID（video=44 / render=992）。

## 内存读数（引擎自报）

weights 72.0 GiB locked · KV pool 0.2 GiB · working 10.1 GiB ⇒ **82.2 GiB**；
**lookup table 26.8 GiB 不入 RAM**，按请求从磁盘 file cache 读。

## 射程（如实）

- 单站 C、**短 prompt（58 tok）**、thinking on、greedy、ctx 8192 ⇒ **不是吞吐基准**，38.58 t/s **不可与 P1 的 27.55 直接并列**
- **未做**「关 MTP」对照臂：日志里的 `26 tok with the head off` 是引擎的混合统计，不是实验对照
- **未测**：长 ctx / 并发 / 质量锚
- 容器已停（是否作为常驻服务另定）
