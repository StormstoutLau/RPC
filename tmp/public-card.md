---
task: smoke review normal path
model: cluster-litellm/nemotron
sensitivity: public
body: Minimal public card to exercise the real review path through the default judge (ultra, egress).
accept:
    - test -f dummy.txt
---

# Public card

Used to verify `agent-cli review` normal advisory path with judge=ultra.