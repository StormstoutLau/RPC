#!/bin/bash
echo "== claude --help 中 model/custom/api 相关（完整） =="
timeout 20 claude --help 2>&1 | grep -iE 'model|api|base|provider|ssl|insecure|debug|verbose' | head -40