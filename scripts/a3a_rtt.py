#!/usr/bin/env python3
# A3a: TCP-echo RTT 探针 (B 站 → A 站 10.10.10.1:50061)
# 小消息 1B 往返, 能感知 busy_read/busy_poll 的 socket 唤醒延迟 (ICMP ping 测不到)
import socket
import time
import statistics

host, port = '10.10.10.1', 50061
N = 5000

s = socket.create_connection((host, port), timeout=5)
s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

for _ in range(200):  # warmup
    s.sendall(b'x')
    s.recv(1)

lat = []
for _ in range(N):
    t0 = time.perf_counter_ns()
    s.sendall(b'x')
    r = s.recv(1)
    t1 = time.perf_counter_ns()
    if r != b'x':
        raise SystemExit('ECHO_MISMATCH')
    lat.append((t1 - t0) / 1000.0)  # us

lat.sort()
p50 = lat[int(len(lat) * 0.50) - 1]
p90 = lat[int(len(lat) * 0.90) - 1]
p99 = lat[int(len(lat) * 0.99) - 1]
print(f"TCPRTT n={len(lat)} min={lat[0]:.1f}us p50={p50:.1f}us p90={p90:.1f}us p99={p99:.1f}us avg={statistics.mean(lat):.1f}us")
s.close()
