#!/usr/bin/env python3
# A3a: TCP echo server (A 站, 10.10.10.1:50061) — 供 B 站测 TCP 小消息 RTT
import socket

host, port = '10.10.10.1', 50061
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind((host, port))
s.listen(1)
print('READY', flush=True)
while True:
    c, a = s.accept()
    c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    while True:
        d = c.recv(65536)
        if not d:
            break
        c.sendall(d)
    c.close()
