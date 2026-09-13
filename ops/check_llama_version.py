#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_llama_version.py — 三站 A/B/C llama.cpp 引擎版本一致性巡检 (主控站 paramiko 版)
依据: spec/vulkan-version-control/IMPLEMENTATION.md §4.3 + ops/check_llama_version.sh
用法: python check_llama_version.py [--deep]
退出: 0 一致 / 1 不一致 / 2 SSH 不可达
指纹: <symlink 目标>|<version>|<commit>|<rpc_protocol>|<md5ok>
依赖: paramiko (与 cluster.py 同环境: hermes venv Python 3.11)
运行: C:\\Users\\Peng\\.hermes\\hermes-agent\\venv\\Scripts\\python.exe
"""
import sys
import paramiko

HOSTS = [
    ("B", "scott-lau@scott-lau-GTR-Pro.local"),
    ("A", "scott-lau@scott-lau-NEX.local"),
    ("C", "scott-lau@192.168.1.37"),
]
SSH_TIMEOUT = 8

FP_CMD = r"""
D=/opt/llama.cpp
L=$(readlink "$D" 2>/dev/null || echo NO_SYMLINK)
M=$(readlink -f "$D")/MANIFEST
V=$(grep "^version" "$M" 2>/dev/null | cut -d= -f2 | tr -d ' ' || echo NO_MANIFEST)
C=$(grep "^commit" "$M" 2>/dev/null | cut -d= -f2 | tr -d ' ' || echo '?')
R=$(grep "^rpc_protocol" "$M" 2>/dev/null | cut -d= -f2 | tr -d ' ' || echo '?')
MD=$(cd "$(readlink -f "$D")" 2>/dev/null && tail -n +10 MANIFEST 2>/dev/null | md5sum -c 2>&1 | grep -c '成功' || echo 0)
echo "$L|$V|$C|$R|md5ok=$MD"
"""

MD5_CMD = r"cd /opt/llama.cpp && md5sum llama-* ggml-rpc-server libggml*.so* libllama*.so* libmtmd*.so* 2>/dev/null | sort"


def ssh_run(host_spec: str, cmd: str, timeout: int = SSH_TIMEOUT) -> str:
    user_host, _, hostname = host_spec.rpartition("@")
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        cli.connect(hostname, username=user_host, timeout=timeout, banner_timeout=timeout)
        _, out, _ = cli.exec_command(cmd, timeout=timeout + 30)
        return out.read().decode("utf-8", "replace").strip()
    except Exception as e:
        return f"__ERROR__:{type(e).__name__}:{e}"
    finally:
        cli.close()


def main() -> int:
    deep = "--deep" in sys.argv
    fps = {}
    any_error = False
    for label, host in HOSTS:
        text = ssh_run(host, FP_CMD)
        if not text or text.startswith("__ERROR__"):
            print(f"❌ {label}({host}) SSH 不可达: {text}")
            any_error = True
            continue
        fps[label] = text
        print(f"{label}({host}) → {text}")
    if any_error:
        return 2

    keys = {k: "|".join(v.split("|")[:4]) for k, v in fps.items()}
    base = keys["B"]
    mismatch = False
    for k in ("A", "C"):
        if keys[k] != base:
            print(f"❌ {k} 不一致: {keys[k]} vs base {base}")
            mismatch = True
    if not mismatch:
        print(f"✅ 三站指纹一致: {base}")

    if deep:
        print("== 深度模式: 三站文件集 md5 比对 ==")
        sets = {}
        for label, host in HOSTS:
            text = ssh_run(host, MD5_CMD)
            sets[label] = set(text.splitlines())
            print(f"{label} → {len(sets[label])} 文件")
        ref = sets["B"]
        for k in ("A", "C"):
            if sets[k] != ref:
                print(f"❌ {k} 与 B 文件集不一致 (差 {len(sets[k] ^ ref)} 条)")
                for line in sorted(sets[k] ^ ref)[:8]:
                    print(f"   diff: {line}")
                mismatch = True
            else:
                print(f"✅ {k} 与 B 文件集完全一致")
    return 1 if mismatch else 0


if __name__ == "__main__":
    sys.exit(main())