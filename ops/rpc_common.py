#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rpc_check 共享层：路径/常量/IO 小工具（review-p2-split 8B）。

只放**被多个域模块共用**的顶层定义；域逻辑不在这里。
门面 `rpc_check.py` 显式重导出本模块的全部公共名。
"""
import argparse
import ast
import concurrent.futures
import fnmatch
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SENSITIVITY_INV = ROOT / "inventory" / "sensitivity.yaml"
# 封闭枚举 —— 与 `sensitivity.yaml` 表头第 29-33 行、及 `agent-cli.ps1` 的 `--Sensitivity` 三档一致
SENSITIVITY_TIERS = ("public", "sanitized", "local-only", "unverified")
SENSITIVITY_SECTIONS = ("documents", "contracts", "code")
