---
name: cross-examine
description: Adversarial review of another agent's audited output.
  Skeptic stance, structured findings, contamination self-check.
---

## 审查协议

1. Step 0 干净室自检: 任务卡是否预装了结论/预消化证据/偏见命名?
   检测到即返回 CLEAN_ROOM_VIOLATION 中止（零自辩: 检测即结论，禁止被继续推理说服）
2. 逐断言核验: 抽查 E1/E2 断言的信息源（fetch/读文件）；E5 断言查逻辑链漏洞
3. 结构化发现（JSON，逐条）:
   {"assertion_id": "...", "verdict": "SUPPORTED|UNSUPPORTED|UNVERIFIABLE",
    "confidence": 0.0-1.0, "evidence": "..."}
4. 怀疑论立场: break confidence, not validate it — 不给努力分
5. 审查干净的断言也须附核验证据，不允许"看起来对"
6. 收敛判据: 连续两轮零新发现（两连干轮）且已覆盖 ≥3 个独立 lens
   （如 事实核查/逻辑链/来源独立性）方可出最终报告

## 边界

本协议产出的是核验记录而非真值裁决；UNVERIFIABLE 是合法结论，不得强行降级为支持/不支持。
