"""测试专用：`cluster` 门面的**可打桩代理**（评审 #8 拆 `cluster.py` 的配套）。

为什么需要：拆分后判据本体按域住进 `cluster_runtime / _catalog / _flow / _agent / _ops`，
函数读的是**自己模块的全局** ⇒ 测试里 `C.ssh_run = ...` 这种"只打门面"的桩会**静默落空**。
实测代价（2026-10-28）：`test_cluster_pure` 的桩全落空 ⇒ 真的向 B 站派发了 `infer-load`。

用法（替代 `import cluster as C`）：
    from _cluster_proxy import cluster_proxy
    C = cluster_proxy()

语义：**读**走门面（对外契约不变）；**写**同时落到"门面 + 所有已绑定该名字的域模块"，
      使 `hasattr`/`getattr` 与真实读取点一致。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

DOMAIN_MODULES = ("cluster_const", "cluster_console", "cluster_ssh", "cluster_model",
                  "cluster_secrets", "cluster_egress", "cluster_catalog", "cluster_runtime",
                  "cluster_flow", "cluster_agent", "cluster_ops")


class _Proxy:
    """只做"属性赋值传播"的门面代理；不做任何其他魔法。"""

    def __init__(self, facade):
        object.__setattr__(self, "_facade", facade)
        mods = [facade]
        for name in DOMAIN_MODULES:
            try:
                mods.append(__import__(name))
            except Exception:              # 某域尚未拆出/不可导入 ⇒ 跳过（不影响其余）
                pass
        object.__setattr__(self, "_mods", mods)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_facade"), name)

    def __setattr__(self, name, value):
        """★ 关键：写到**所有**已绑定该名字的模块（否则函数读不到桩）。"""
        for m in object.__getattribute__(self, "_mods"):
            if hasattr(m, name):
                setattr(m, name, value)
        setattr(object.__getattribute__(self, "_facade"), name, value)

    def __delattr__(self, name):
        """对称语义：删也删所有模块里的（`_swap` 的"原本不存在"还原路径要用）。"""
        for m in object.__getattribute__(self, "_mods"):
            if hasattr(m, name):
                try:
                    delattr(m, name)
                except AttributeError:
                    pass


def cluster_proxy():
    import cluster
    return _Proxy(cluster)
