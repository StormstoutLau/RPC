#!/bin/bash
set -e
NEW=/home/scott-lau/infer-load.new
echo "== 语法检查 =="
bash -n "$NEW" && echo "SYNTAX OK"
echo "== 备份现行 =="
sudo cp /usr/local/bin/infer-load /usr/local/bin/infer-load.bak-20260904
echo "== 安装 =="
sudo cp "$NEW" /usr/local/bin/infer-load
sudo chmod 755 /usr/local/bin/infer-load
echo "== 版本哈希 =="
md5sum /usr/local/bin/infer-load
echo "== 冒烟: infer-list 仍正常 =="
/usr/local/bin/infer-list 2>&1 | head -8