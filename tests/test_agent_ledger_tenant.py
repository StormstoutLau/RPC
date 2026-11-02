"""台账分租户的**只读聚合**行为（ADR-0013 D6⑥④，2026-11-02）。

守的是什么：
  `ops/cluster_agent.py` 的 `_agent_ledger_rows` 必须同时读
  ① 存量单文件 `agent-runs.log`（默认形态）
  ② 分租户目录 `agent-runs.d/*.log`（D6⑥④ 后的形态）
  并按 ts 重排后取尾部 N 条 —— **只读**，不建目录、不写索引。

⚠ 本测试只碰临时目录里的常量副本，不读真实台账（避免受运行时数据影响）。

用法: py tests\\test_agent_ledger_tenant.py
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))
import cluster_agent as CA  # noqa: E402

fails = []


def chk(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


def _rows():
    return [("20260101000000000000", "legacy", "m1", "public", "0", "0", "1"),
            ("20260102000000000000", "tenant-b", "m1", "public", "0", "0", "2"),
            ("20260103000000000000", "tenant-a", "m1", "public", "0", "0", "3")]


def _write_ledger(path, rows):
    lines = ["RPC_LEDGER_TEST 2026-09-06"]
    lines += [",".join(r) for r in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    old_file, old_dir = CA.AGENT_LEDGER, CA.AGENT_LEDGER_DIR
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        legacy = base / "agent-runs.log"
        ledger_dir = base / "agent-runs.d"
        legacy_rows, tenant_b, tenant_a = _rows()

        # ① 默认形态：只有单文件 ⇒ 行为与分租户前一致
        _write_ledger(legacy, [legacy_rows])
        CA.AGENT_LEDGER, CA.AGENT_LEDGER_DIR = legacy, ledger_dir
        only_legacy = CA._agent_ledger_rows(10)
        chk("单文件形态只读 1 条（目录不存在不报错）",
            len(only_legacy) == 1 and only_legacy[0]["proj"] == "legacy", only_legacy)

        # ② 双形态：单文件 + 租户目录 ⇒ 聚合 3 条
        ledger_dir.mkdir()
        _write_ledger(ledger_dir / "tenant-b.log", [tenant_b])
        _write_ledger(ledger_dir / "tenant-a.log", [tenant_a])
        merged = CA._agent_ledger_rows(10)
        chk("单文件 + 租户目录只读合并 3 条", len(merged) == 3,
            [r["proj"] for r in merged])
        chk("跨文件按 ts 升序重排",
            [r["ts"] for r in merged] == sorted(r[0] for r in _rows()),
            [r["ts"] for r in merged])
        chk("租户列保留（proj 不被覆盖）",
            [r["proj"] for r in merged] == ["legacy", "tenant-b", "tenant-a"],
            [r["proj"] for r in merged])

        # ③ 尾部 limit 在聚合后生效
        tail = CA._agent_ledger_rows(2)
        chk("limit 取聚合后的尾部 2 条",
            [r["proj"] for r in tail] == ["tenant-b", "tenant-a"],
            [r["proj"] for r in tail])

        # ④ 只读：调用不创建目录、不新增文件
        before = sorted(p.name for p in ledger_dir.iterdir())
        CA._agent_ledger_rows(10)
        after = sorted(p.name for p in ledger_dir.iterdir())
        chk("聚合读取是只读（不建索引/不改文件）", before == after, after)

    CA.AGENT_LEDGER, CA.AGENT_LEDGER_DIR = old_file, old_dir

    print(f"\nRESULT: {'ALL PASS' if not fails else f'FAIL ({len(fails)} 项)'}"
          f" · 失败: {', '.join(fails) if fails else '无'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
