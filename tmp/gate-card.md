---
task: smoke review gate test
model: cluster-litellm/nemotron
sensitivity: local-only
body: Veria task body for gate test. This is a minimal card to exercise the review sensitivity gate.
accept:
    - test -f dummy.txt
---

# Gate test card

Minimal card used only to verify `agent-cli review` sensitivity/reject/normal paths.