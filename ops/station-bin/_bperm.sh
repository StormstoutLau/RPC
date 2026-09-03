#!/bin/bash
echo "== sudo 免密? =="
sudo -n true 2>&1 && echo "sudo OK" || echo "sudo NEEDS PASSWORD"
echo "== /usr/local/bin 可写? =="
test -w /usr/local/bin && echo "writable" || echo "NOT writable (need sudo)"
echo "== infer-load 当前版本哈希 =="
md5sum /usr/local/bin/infer-load /usr/local/bin/infer-list /usr/local/bin/infer-unload