#!/bin/bash
# Run ON B station: deploy B's OWN pubkey to C via pexpect (password scott-lau@C)
# Uses /tmp/deploy_key.py (which reads pubkey from argv)
B_PUB=$(cat ~/.ssh/id_ed25519.pub)
python3 /tmp/deploy_key.py "$B_PUB" 2>&1 | tail -5