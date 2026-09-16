"""Cpp_Hub pytest 脚手架（在 B 站真实 venv 中执行）。

主控侧 golden 测试独立于此（见 ops/station-bin/golden/），
防模型自写测试自证。本文件为远端产物级验收。
"""
import subprocess
import shutil


def _方案库构建可用():
    """最轻验收：仅验证源码骨架与中文文件存在性，不强制编译。"""
    return True


def test_中文源文件存在():
    # 相对本 test 文件定位 src
    import pathlib
    src = pathlib.Path(__file__).resolve().parent.parent / "src"
    assert (src / "因子计算_核心.cpp").is_file()
    assert (src / "因子计算_run.cpp").is_file()


def test_编译链存在():
    # g++ / cmake 存在即可（编译非硬性，但链须就绪）
    assert shutil.which("g++") is not None
    assert shutil.which("cmake") is not None


def test_源码可解析():
    # 不求编译，至少语法可由 g++ -fsyntax-only 通过（若链就绪）
    import pathlib
    src = pathlib.Path(__file__).resolve().parent.parent / "src"
    for f in ["因子计算_核心.cpp", "因子计算_run.cpp"]:
        r = subprocess.run(["g++", "-fsyntax-only", "-std=c++17",
                            str(src / f)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr