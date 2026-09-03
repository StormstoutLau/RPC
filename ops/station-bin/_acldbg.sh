#!/bin/bash
echo "== claude --debug 抓真实错误 =="
timeout 60 claude --model gpt-oss-120b-MXFP4 --debug api -p "hi" < /dev/null 2>&1 | grep -iE 'unrecognized|model|base_url|127.0.0.1|messages|error|request|provider' | head -40