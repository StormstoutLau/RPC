#!/bin/bash
# 诊断: B 站谁占着 10.10.10.2:44288 → A:50052
echo '--- B: 44288 连接归属 ---'
ss -tnp '( sport = :44288 )' 2>/dev/null || sudo ss -tnp '( sport = :44288 )'
echo '--- B: 所有到 10.10.10.1 的连接 ---'
sudo ss -tnp 'dst 10.10.10.1' | head -10
