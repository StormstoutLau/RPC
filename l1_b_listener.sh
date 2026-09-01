#!/bin/bash
# L1c-B: B 站 netconsole 监听服务 (python3 UDP, 零新依赖)
set -u
exec 2>&1

LISTENER=/usr/local/bin/netconsole-listen.py
SVC=/etc/systemd/system/netconsole-listen.service

sudo tee $LISTENER >/dev/null <<'EOF'
#!/usr/bin/env python3
# 接收 A 站 netconsole printk 镜像, 落盘带时间戳 (挂死最后遗言通道)
import socket, datetime
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("10.10.10.2", 6665))
sock.settimeout(None)
with open("/var/log/netconsole-a.log", "ab", buffering=0) as f:
    while True:
        data, addr = sock.recvfrom(8192)
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        try:
            f.write(f"{ts} {data.decode(errors='replace')}".encode() + b"\n")
        except Exception:
            pass
EOF
sudo chmod 755 $LISTENER

sudo tee $SVC >/dev/null <<'EOF'
[Unit]
Description=netconsole listener for station A printk mirror
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/bin/python3 /usr/local/bin/netconsole-listen.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now netconsole-listen.service
sleep 1
echo "--- 服务状态 ---"
systemctl is-active netconsole-listen.service
ss -ulnp | grep 6665 || echo "!! UDP 6665 未监听"
echo "DONE_L1C_B"
