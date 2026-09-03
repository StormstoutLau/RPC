#!/bin/bash
echo "== A -> B ssh 连通 =="
ssh -o BatchMode=yes -o ConnectTimeout=6 scott-lau-GTR-Pro.local 'echo A_TO_B_OK' 2>&1 | head -2
echo "rc=$?"