#!/usr/bin/env python3
# Deploy pubkey to C station (192.168.1.37, user seaviv) via pexpect password auth.
# Run ON B station (has pexpect + reachable to C over LAN).
import pexpect, sys

HOST = "192.168.1.37"
USER = "scott-lau"
PASS = "860129"
PUBKEY = open("/home/scott-lau/.ssh/id_ed25519.pub").read().strip() if False else None
# pubkey content fetched from forwarded var; read from stdin arg
if len(sys.argv) > 1:
    PUBKEY = sys.argv[1]
else:
    print("USAGE: deploy_key.py '<pubkey-line>'")
    sys.exit(2)

cmd = (f'ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no -o NumberOfPasswordPrompts=1 '
       f'{USER}@{HOST} "umask 077; mkdir -p ~/.ssh; echo \'{PUBKEY}\' >> ~/.ssh/authorized_keys; '
       f'chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys; echo KEY_INSTALLED_OK_MARKER"')

child = pexpect.spawn("/bin/bash", ["-c", cmd], timeout=30, encoding="utf-8")
child.logfile_read = sys.stdout
i = child.expect([r"[Pp]assword:", r"\(yes/no\)", pexpect.EOF, pexpect.TIMEOUT])
if i == 0:
    child.sendline(PASS)
    child.expect(pexpect.EOF, timeout=20)
    print("\n[DONE] exit")
elif i == 1:
    child.sendline("yes")
    child.expect(r"[Pp]assword:")
    child.sendline(PASS)
    child.expect(pexpect.EOF, timeout=20)
    print("\n[DONE] exit")
elif i == 2:
    print("EOF before password prompt")
else:
    print("TIMEOUT waiting password")
    sys.exit(1)