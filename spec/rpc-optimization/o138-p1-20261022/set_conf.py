#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rewrite C station qwen3.8-flash-next conf for O-138 parameter arms."""
import base64
import os
import re
import pathlib

conf = pathlib.Path("/etc/llama-instances/qwen3.8-flash-next.env")
text = conf.read_text(encoding="utf-8")
ncm = os.environ["NCM"]
ctx = os.environ["CTX"]
flags = base64.b64decode(os.environ["FLAGS_B64"]).decode("utf-8")
text = re.sub(r"^N_CPU_MOE=.*$", "N_CPU_MOE=%s" % ncm, text, flags=re.M)
text = re.sub(r"^CTX=.*$", "CTX=%s" % ctx, text, flags=re.M)
text = re.sub(r"^EXTRA_FLAGS=.*$", 'EXTRA_FLAGS="%s"' % flags, text, flags=re.M)
conf.write_text(text, encoding="utf-8")
print("CONF_SET ncm=%s ctx=%s flags=%s" % (ncm, ctx, flags))
