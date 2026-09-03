#!/bin/bash
set -e
echo "== 语法检查 infer-load / infer-unload =="
bash -n /home/scott-lau/infer-load.new && echo "infer-load SYNTAX OK"
bash -n /home/scott-lau/infer-unload.new && echo "infer-unload SYNTAX OK"
echo "== 备份 =="
sudo cp /usr/local/bin/infer-load /usr/local/bin/infer-load.bak-unsloth2-20260904
sudo cp /usr/local/bin/infer-unload /usr/local/bin/infer-unload.bak-unsloth-20260904
echo "== 安装 =="
sudo cp /home/scott-lau/infer-load.new /usr/local/bin/infer-load
sudo cp /home/scott-lau/infer-unload.new /usr/local/bin/infer-unload
sudo chmod 755 /usr/local/bin/infer-load /usr/local/bin/infer-unload
md5sum /usr/local/bin/infer-load /usr/local/bin/infer-unload