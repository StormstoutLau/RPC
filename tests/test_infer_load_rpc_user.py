"""`infer-load` / `infer-unload` 的 **worker 通道身份**契约（O-181，2026-10-29）。

为什么必须钉死
--------------
2026-10-29 实测（B 站）：`infer-unload` 由 `sudo` 执行 ⇒ `id -un = root`
⇒ 原实现 `RPC_USER="${RPC_USER:-$(id -un)}"` 取到 root，而 root 的 `~/.ssh`
只有 0 字节 `authorized_keys`、没有 known_hosts ⇒ 远端一律
`Host key verification failed:`。调用点又写着 `2>/dev/null`，把真因吞成
一句「不可达」——同一句告警既可能是网络故障、也可能是身份错，无法分诊。

判据
----
1. 两个脚本都**不再**用 `$(id -un)` 作为 root 下的默认身份；
2. 解析顺序含 **nodes.env 的 `RPC_USER=`**；
3. root 且无显式配置时，探测「本机首个持有 `id_ed25519`/`id_rsa` 的非系统用户」；
4. 解析结果**打进日志**（可诊断：这次到底用谁连的）；
5. 远端 ssh 失败时**保留并打印 stderr**（不再全 `2>/dev/null`）；
6. 仓库真值 `ops/nodes.env` 声明 `RPC_USER`。

用法: py tests\\test_infer_load_rpc_user.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "ops" / "station-bin"
fails = []


def chk(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


def main() -> int:
    un = (BIN / "infer-unload").read_text(encoding="utf-8", errors="replace")
    ld = (BIN / "infer-load").read_text(encoding="utf-8", errors="replace")
    env = (ROOT / "ops" / "nodes.env").read_text(encoding="utf-8", errors="replace")
    # 只看代码行：注释里会引用旧写法作为说明，不该算违规。
    un_code = "\n".join(l for l in un.splitlines() if not l.lstrip().startswith("#"))
    ld_code = "\n".join(l for l in ld.splitlines() if not l.lstrip().startswith("#"))

    chk("infer-unload 不再直取 $(id -un) 作为身份",
        'RPC_USER="${RPC_USER:-$(id -un)}"' not in un_code,
        "root 下会取到 root ⇒ 无密钥 ⇒ 所有远端『不可达』")
    chk("infer-unload 从 nodes.env 解析 RPC_USER",
        "s/^RPC_USER=//p" in un)
    chk("infer-unload 在 root 下探测持钥用户",
        "id_ed25519" in un and "id_rsa" in un and "getent passwd" in un)
    chk("infer-unload 打印解析出的通道用户（可诊断）",
        "worker 通道用户" in un)
    chk("infer-unload 远端 ssh 失败时保留 stderr",
        "mktemp" in un and "原始错误" in un,
        "`2>/dev/null` 会把 Host key verification failed 吞成『不可达』")

    chk("infer-load 不再直取 ${RPC_USER:-$(id -un)}",
        "${RPC_USER:-$(id -un)}" not in ld_code)
    chk("infer-load 同样从 nodes.env 解析 RPC_USER",
        "s/^RPC_USER=//p" in ld)
    chk("infer-load 同样在 root 下探测持钥用户",
        "id_ed25519" in ld and "id_rsa" in ld)

    chk("ops/nodes.env 声明 RPC_USER",
        "RPC_USER=" in env,
        "节点清单是节点侧真值，身份应与清单同源")

    print("\nRESULT: " + ("ALL PASS" if not fails else f"FAIL ({len(fails)} 项) · " + ", ".join(fails)))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
