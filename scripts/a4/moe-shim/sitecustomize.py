# sitecustomize.py — MoE device-name shim for gfx1151 vLLM.
#
# WHY: this vLLM build mocks `amdsmi` with a MagicMock, so
#   RocmPlatform.get_device_name() returns a mock, not a string. vLLM builds the
#   tuned-MoE config filename from that name, gets a per-process-random garbage
#   filename, and silently falls back to the DEFAULT MoE config. Forcing a real,
#   stable device name makes VLLM_TUNED_CONFIG_FOLDER work.
#
# HOW: install a meta_path finder that wraps the loader for `vllm.platforms.rocm`
#   and applies the override immediately after that module executes (before any
#   MoE config lookup during model load). Must be on PYTHONPATH for BOTH ranks,
#   because the fused-MoE GEMM (and thus the lookup) runs on both.
#
# INSTALL: place this dir on PYTHONPATH for the head vLLM process AND the Ray
#   worker. Python auto-imports `sitecustomize` at interpreter startup from any
#   sys.path entry, so no explicit import is needed.
#
# Source: ayysasha/Strix-halo-dual-optimized (MIT), adapted verbatim for A4.
import importlib.util
import sys

_TARGET = "vllm.platforms.rocm"


def _apply_override(module):
    try:
        import torch  # resolved only inside the vLLM/ROCm container
        real_name = torch.cuda.get_device_name(0)

        def _get_device_name(cls, device_id: int = 0, _n=real_name):
            return _n

        module.RocmPlatform.get_device_name = classmethod(_get_device_name)
        print(f"[moe-shim] patched RocmPlatform.get_device_name -> {real_name!r}",
              file=sys.stderr, flush=True)
    except Exception as exc:  # never break startup
        print(f"[moe-shim] FAILED to patch get_device_name: {exc!r}",
              file=sys.stderr, flush=True)


class _WrappedLoader:
    def __init__(self, orig):
        self._orig = orig

    def create_module(self, spec):
        return self._orig.create_module(spec)

    def exec_module(self, module):
        self._orig.exec_module(module)
        _apply_override(module)


class _Finder:
    _busy = False

    def find_spec(self, fullname, path=None, target=None):
        if fullname != _TARGET or _Finder._busy:
            return None
        _Finder._busy = True
        try:
            spec = importlib.util.find_spec(fullname)
        finally:
            _Finder._busy = False
        if spec is not None and spec.loader is not None:
            setattr(spec, "loader", _WrappedLoader(spec.loader))
        return spec


sys.meta_path.insert(0, _Finder())
