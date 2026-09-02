---
name: assertion-audit
description: Produce audit-ready output. Every factual claim must carry
  (a) evidence class E1-E5, (b) source link/path, (c) inference chain.
  Use when tasked with research, review, or any deliverable whose
  claims will be cross-checked by another agent.
---

## 输出契约

1. 断言表（交付物内所有可核查断言入表）:
   | 断言 | 证据等级 E1-E5 | 信息源 (URL/文件路径/命令输出) | 逻辑链 (前提→推理→结论) |
2. 证据等级: E1 一手直验(本会话 fetch/读文件/跑命令) / E2 一手转述(引用原始
   页面或日志原文) / E3 二手(他人对来源的转述) / E4 一手但有时效风险 / E5 推断(无源)
3. 无源断言必须显式标 E5 并给验证方法
4. 引用他人的判断须与自己的核验分开标注（二手 vs 一手）
5. 结论只允许从表中断言推出 — 表外无断言

## 证明力边界声明（强制字段，不得删除）

本断言表是结构过滤而非溯源保证：信息源存在且被引用不等于内容为真；
E1/E2 抽查通过不等于全表通过。交叉核验须由独立审查方（cross-examine）执行。
