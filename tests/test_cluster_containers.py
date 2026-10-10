"""`cluster.py containers` 子命令的**纯函数夹具**（ADR-0012 D2 / ADR-0014 D2）。

为什么要有这条：
    `containers` 是**唯一**经统一管理面执行 docker 的入口（`ADR-0004` D2 不新增并列脚本），
    且**写动作默认 `--plan`、`--go` 才动手**。这些判据必须**离线可测**（不连站、零 ssh）——
    否则"计划与执行同一条命令"只能靠实跑碰运气。

射程（**只锁纯函数**）：
    · `parse_containers_probe`  站上探测块 → 结构
    · `parse_docker_ps`         `docker ps -a` 文本 → 行
    · `docker_published_ports`  端口串 → 宿主端口集合
    · `containers_plan`         动作 → 将下发的命令（**计划 = 执行**的同源真值）
    · `registered_host_ports`   ports.yaml 解析结果 → 已登记端口
    · `containers_port_audit`   容器已发布 vs 已登记 的对账
    · `format_containers_station` 单站渲染（**空集必须显式报「无容器」**，ADR-0012 D2）

用法（退出码 0 = 全过）：
    py tests\\test_cluster_containers.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))
import cluster as C                                    # noqa: E402

fails = []


def chk(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + extra if extra else ""))
    if not cond:
        fails.append(name)


# ── parse_containers_probe: 站上探测块 → 结构（docker 缺席也要可判）──────────
_p_absent = C.parse_containers_probe("DOCKER=absent\n")
chk("probe: 无 dockerd ⇒ docker=absent 且三段皆空",
    _p_absent["docker"] == "absent" and _p_absent["ps"] == []
    and _p_absent["images"] == [] and _p_absent["compose"] == [],
    str(_p_absent))

_probe = C.parse_containers_probe(
    "DOCKER=active\n"
    "===PS===\n"
    "halogen-flash\tghcr.io/peonist-ai/halogen-flash-server:v0.17.4\tUp 3 minutes\t"
    "127.0.0.1:8731->8731/tcp\n"
    "===IMG===\n"
    "ghcr.io/peonist-ai/halogen-flash-server:v0.17.4\t4.1GB\n"
    "===CMP===\n"
    "searxng\trunning(1)\n"
)
chk("probe: active ⇒ 三段各自解析",
    _probe["docker"] == "active" and len(_probe["ps"]) == 1
    and _probe["ps"][0]["name"] == "halogen-flash"
    and _probe["images"] == [{"ref": "ghcr.io/peonist-ai/halogen-flash-server:v0.17.4", "size": "4.1GB"}]
    and _probe["compose"] == ["searxng\trunning(1)"],
    str(_probe))

chk("probe: CMP 只有表头 ⇒ compose 为空（不许把 0 个栈误报成 1 个）",
    C.parse_containers_probe(
        "DOCKER=active\n===CMP===\n"
        "NAME                STATUS              CONFIG FILES\n"
    )["compose"] == [])

chk("probe: 无 DOCKER= 行 ⇒ unknown（不假装 absent）",
    C.parse_containers_probe("===PS===\n")["docker"] == "unknown",
    C.parse_containers_probe("===PS===\n")["docker"])

chk("probe: PS 段为空行 ⇒ 行数 0（而非 1 条空行）",
    len(C.parse_containers_probe("DOCKER=active\n===PS===\n\n===IMG===\n")["ps"]) == 0)


# ── parse_docker_ps: 4 列文本 → 行（短行/空行跳过）───────────────────────────
_rows = C.parse_docker_ps(
    "a\timg:1\tUp 2 hours\t127.0.0.1:8731->8731/tcp\n"
    "\n"
    "short\timg\n"
    "b\timg:2\tExited (0) 3 days ago\t\n"
)
chk("ps: 正常行解析出 name/image/status/ports_raw",
    _rows[0] == {"name": "a", "image": "img:1", "status": "Up 2 hours",
                 "ports_raw": "127.0.0.1:8731->8731/tcp", "host_ports": [8731]},
    str(_rows[0] if _rows else None))
chk("ps: 空行与短行（<4 列）被跳过 ⇒ 只剩 2 行",
    len(_rows) == 2, f"n={len(_rows)}")
chk("ps: 无发布端口 ⇒ host_ports 为空列表（不是 None/异常）",
    _rows[1]["host_ports"] == [], str(_rows[1]))
chk("ps: 空输入 ⇒ []（不抛）", C.parse_docker_ps("") == [])


# ── docker_published_ports: 端口串 → 宿主端口（多段 / 双栈 / 无 IP 前缀）─────
chk("ports: 单条 loopback",
    C.docker_published_ports("127.0.0.1:8731->8731/tcp") == [8731])
chk("ports: 多段（含 0.0.0.0 与 ::: 形态）逐条抽出",
    C.docker_published_ports("0.0.0.0:8888->8080/tcp, :::8888->8080/tcp") == [8888, 8888],
    str(C.docker_published_ports("0.0.0.0:8888->8080/tcp, :::8888->8080/tcp")))
chk("ports: 未发布（只有容器内口，无 ->）⇒ []",
    C.docker_published_ports("8080/tcp") == [], str(C.docker_published_ports("8080/tcp")))
chk("ports: 空串 ⇒ []", C.docker_published_ports("") == [])


# ── containers_plan: 计划 = 将下发的命令（写动作的**唯一**真值源）────────────
chk("plan: pull 只含 docker pull <image>",
    C.containers_plan("pull", station="A", image="ghcr.io/x/y:v1")
    == ["docker pull ghcr.io/x/y:v1"],
    str(C.containers_plan("pull", station="A", image="ghcr.io/x/y:v1")))
# ★ 实测教训(2026-10-10): `docker pull` 多 GB 镜像**远超** ssh exec 上界(timeout+30s),
#   两次实拉(900s/1800s)均 `TimeoutError`、镜像未落地 ⇒ 需要与 ssh 会话**解耦**的后台拉取。
#   `setsid ... </dev/null >/dev/null 2>&1 &` = 脱离会话、不占 stdout; 末尾 `echo DETACHED`
#   让 ssh_run(strict=True) 拿到 rc=0(否则 `&` 无输出会让调用方误判)。
chk("plan: pull --detach 产出自托管后台拉取(与 ssh 超时解耦, 可续传)",
    C.containers_plan("pull", station="A", image="img:v1", detach=True)
    == ["setsid sh -c 'docker pull img:v1 >>/tmp/cluster-docker-pull.log 2>&1' "
        "</dev/null >/dev/null 2>&1 & echo DETACHED"],
    str(C.containers_plan("pull", station="A", image="img:v1", detach=True)))
chk("plan: pull --detach --log <path> 可改日志落点",
    C.containers_plan("pull", station="A", image="img:v1", detach=True, log="/tmp/x.log")
    == ["setsid sh -c 'docker pull img:v1 >>/tmp/x.log 2>&1' "
        "</dev/null >/dev/null 2>&1 & echo DETACHED"],
    str(C.containers_plan("pull", station="A", image="img:v1", detach=True, log="/tmp/x.log")))
chk("plan: down 吃 detach 但不改命令（detach 只对 pull 有意义）",
    C.containers_plan("down", station="A", name="x", detach=True) == ["docker rm -f x"])
chk("plan: down 只含 docker rm -f <name>",
    C.containers_plan("down", station="A", name="halogen-flash")
    == ["docker rm -f halogen-flash"])
_up = C.containers_plan("up", station="A", image="ghcr.io/x/y:v1", name="halogen-flash",
                        publish=["127.0.0.1:8731:8731"], group_add=["video", "render"])
chk("plan: up 组合 -d/--name/--group-add/-p/image 齐全",
    _up == ["docker run -d --name halogen-flash --group-add video --group-add render "
            "-p 127.0.0.1:8731:8731 ghcr.io/x/y:v1"],
    str(_up))
chk("plan: 不传 device/ipc/ulimit/env/volume 时**不产生多余空格**（默认形态与旧版逐字一致）",
    C.containers_plan("up", station="A", image="i", name="n") == ["docker run -d --name n i"],
    str(C.containers_plan("up", station="A", image="i", name="n")))
# ADR-0014 D4 + 上游部署配方（docker-compose.yml / AGENTS.md）: halogen 起容器**必须**
#   带 --device /dev/kfd /dev/dri、--group-add video render、--ipc=host（load-bearing：
#   官方逐字"no shm_size substitutes"）、--ulimit memlock=-1:-1、-v <models>:/models:ro、
#   -e HALOGEN_CHECKPOINT=... ⇒ 这些 flag 是本仓"真部署"的最小充分集，须与配方同源。
_up_full = C.containers_plan(
    "up", station="A", image="ghcr.io/peonist-ai/halogen-flash-server:0.17.4",
    name="halogen-flash", publish=["127.0.0.1:8731:8731"],
    group_add=["video", "render"], device=["/dev/kfd", "/dev/dri"],
    volume=["/m:/models:ro"], env=["HALOGEN_CHECKPOINT=/models/x.gguf"],
    ipc="host", ulimit=["memlock=-1:-1"])
chk("plan: up 承载 halogen 配方（--device/--ipc/--ulimit/-v/-e 齐全且保序）",
    _up_full == ["docker run -d --name halogen-flash "
                 "--device /dev/kfd --device /dev/dri "
                 "--group-add video --group-add render --ipc=host --ulimit memlock=-1:-1 "
                 "-e HALOGEN_CHECKPOINT=/models/x.gguf -v /m:/models:ro "
                 "-p 127.0.0.1:8731:8731 ghcr.io/peonist-ai/halogen-flash-server:0.17.4"],
    str(_up_full))
chk("plan: pull/up 之外的动作**不**吃 device/volume（避免把 run 专属 flag 泄漏到 rm/down）",
    C.containers_plan("down", station="A", name="x") == ["docker rm -f x"])
for _bad, _kw in (
    (dict(act="pull", station="A"), "pull"),
    (dict(act="up", station="A", name="x"), "up"),
    (dict(act="up", station="A", image="i"), "up"),
    (dict(act="down", station="A"), "down"),
):
    try:
        C.containers_plan(_bad.pop("act"), **_bad)
        chk(f"plan: 缺参 {_kw} ⇒ ValueError", False, "未抛异常")
    except ValueError:
        chk(f"plan: 缺参 {_kw} ⇒ ValueError", True)
try:
    C.containers_plan("bogus", station="A")
    chk("plan: 未知动作 ⇒ ValueError", False, "未抛异常")
except ValueError:
    chk("plan: 未知动作 ⇒ ValueError", True)


# ── registered_host_ports / containers_port_audit: 与真值表对账 ─────────────
_table = {
    "managed": [{"port": 8731}, {"port": 8080}],
    "third_party": [{"port": 9095}],
    "unmanaged": [{"owner": "rpc.statd", "range": [512, 1023]}],   # 段位形态 ⇒ 非具体端口
}
_reg = C.registered_host_ports(_table)
chk("registered: 收 int 端口并记来源", set(_reg) == {8731, 8080, 9095}, str(_reg))
chk("registered: 段位形态（无 port 键）不进集合", 512 not in _reg and 1023 not in _reg)
chk("registered: 空表 ⇒ {}（不抛）", C.registered_host_ports({}) == {})

_iss = C.containers_port_audit({"A": [8731, 9999]}, _reg)
chk("audit: 未登记端口 **报出**、已登记不报",
    len(_iss) == 1 and "9999" in _iss[0] and "A" in _iss[0], str(_iss))
chk("audit: 全已登记 ⇒ 无问题行",
    C.containers_port_audit({"A": [8731]}, _reg) == [])


# ── format_containers_station: 空集必须**显式报「无容器」**（ADR-0012 D2）───
_lines_empty = C.format_containers_station("A", {"docker": "active", "ps": [], "images": [], "compose": []})
chk("渲染: docker active 且 0 容器 ⇒ 文本含「无容器」（**不许打印空**）",
    any("无容器" in ln for ln in _lines_empty), "\n".join(_lines_empty))

_lines_absent = C.format_containers_station("B", {"docker": "absent", "ps": [], "images": [], "compose": []})
chk("渲染: docker absent ⇒ 明示「未安装」（容器路径不适用）",
    any("未安装" in ln for ln in _lines_absent), "\n".join(_lines_absent))
chk("渲染: absent 时不报「无容器」（避免把'没 docker'读成'没起容器'）",
    not any("无容器" in ln for ln in _lines_absent), "\n".join(_lines_absent))

_lines_one = C.format_containers_station("A", {
    "docker": "active",
    "ps": [{"name": "halogen-flash", "image": "ghcr.io/x/y:v1",
            "status": "Up 3 minutes", "ports_raw": "127.0.0.1:8731->8731/tcp",
            "host_ports": [8731]}],
    "images": [{"ref": "ghcr.io/x/y:v1", "size": "4.1GB"}],
    "compose": [],
})
chk("渲染: 有容器 ⇒ 列出名字，且**不**出现「无容器」",
    any("halogen-flash" in ln for ln in _lines_one)
    and not any("无容器" in ln for ln in _lines_one), "\n".join(_lines_one))


print()
print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED -> {fails}")
sys.exit(1 if fails else 0)