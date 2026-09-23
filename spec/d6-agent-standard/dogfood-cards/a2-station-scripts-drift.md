---
proj: dogfood
task: 列出本站脚本落点 ~/scripts 下每个文件的 sha256 / mtime / 大小，写入 out/station-scripts.tsv；只写这一个新文件
model: ultra
cli: opencode
sensitivity: public
readonly: false
timeout_s: 600
accept:
  - test -f out/station-scripts.tsv
  - test "$(wc -l < out/station-scripts.tsv)" -ge 3
  - grep -q 'sha256' out/station-scripts.tsv
---
## 任务描述

你是**只做采集**的取证 agent。**不要分析、不要比对、不要判断"哪个文件是新的"** —— 比对由**主控**做，你只提供站上原始事实。

> ⚠ **你拿不到任何"应该有哪些文件"的清单** —— 这是刻意的。**不要猜**、不要补齐、不要按常识推断"标准应有几个"。

### 第一步：确认工作目录可写

```bash
mkdir -p out && echo ok > out/.write-test && cat out/.write-test
```

失败则停止，stdout 打印 `DOGFOOD_A2_BLOCKED`（之后不要输出别的）。

### 唯一产物：`out/station-scripts.tsv`（相对工作目录根）

- **第 1 行固定为表头**：`sha256<TAB>mtime_epoch<TAB>size<TAB>relpath`
- 其后**每行一个文件**，四个字段用 **TAB** 分隔（不是空格）
- `relpath` 用**相对路径**（如 `scripts/b5k_sync.sh`），**不要写用户目录的绝对路径**
- 采集范围：`~/scripts/` 下的**普通文件**（含隐藏文件，**不含**子目录递归）
- 哈希用 `sha256sum`；`mtime_epoch` 用 `stat -c %Y`；`size` 用 `stat -c %s`
- **目录不存在** ⇒ 仍然写文件（只有表头一行），并把该情况记进 stdout 以外的**不产生额外文件**（见下 `A2_NOTE`）

### 格式化提示（等价命令，可自行等价实现）

```bash
cd ~/scripts 2>/dev/null || true
printf 'sha256\tmtime_epoch\tsize\trelpath\n' > "$OLDPWD/out/station-scripts.tsv"
for f in * .[!.]*; do [ -f "$f" ] || continue; printf '%s\t%s\t%s\t%s\n' \
  "$(sha256sum "$f" | cut -d' ' -f1)" "$(stat -c %Y "$f")" "$(stat -c %s "$f")" "scripts/$f" \
  >> "$OLDPWD/out/station-scripts.tsv"; done
```

（**若你的实现与上例不同，只要产物格式一致即可**；**不要**为了跑通上例而修改任何既有文件。）

### 硬性要求

1. **不许编造**：取不到的文件**不要写进表**；查不到 `~/scripts/` ⇒ 只写表头。
2. **不要修改、不要移动、不要删除**任何站上文件 —— 本卡是**只读取证**（虽然 `readonly` 为 false，仅因为要落 `out/` 产物）。
3. **不读取文件内容**（只算哈希），**不要** cat/grep 脚本内容。
4. **stdout 只输出一行**：`DOGFOOD_A2_OK`
5. 除 `out/station-scripts.tsv` 与探针 `out/.write-test` 外**不产生任何文件**。
