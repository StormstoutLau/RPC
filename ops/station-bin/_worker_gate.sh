#!/usr/bin/env bash
# _worker_gate.sh - worker-side egress/sensitivity/scrub gate (ADR-0013 D6-6 #3 / D170)
# WORKER_GATE_VERSION: 1
# Usage: bash _worker_gate.sh --expect-version 1 --sensitivity S --backend-egress 0|1
#          --prompt-file P [--rules-b64 R]
# Exit: 0 pass / 4 reject / 64 usage. Reject tokens: WORKER_GATE_REJECT ...
# Scope: re-checks the gates on the worker side so a foreign master cannot bypass them.
#   Rules are DATA (name<TAB>regex lines, block=$true only) generated from Get-ScrubRules.
#   Block rules must stay POSIX-ERE compatible; a new non-ERE rule needs an explicit mapping here.
set -euo pipefail

GATE_VERSION=1
EXPECT_VERSION=""
SENS=""
EGRESS=""
PROMPT=""
RULES_B64=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --expect-version)
      [ "$#" -ge 2 ] || { echo "WORKER_GATE_BAD_REQUEST: --expect-version needs a value" >&2; exit 64; }
      EXPECT_VERSION="$2"; shift 2 ;;
    --sensitivity)
      [ "$#" -ge 2 ] || { echo "WORKER_GATE_BAD_REQUEST: --sensitivity needs a value" >&2; exit 64; }
      SENS="$2"; shift 2 ;;
    --backend-egress)
      [ "$#" -ge 2 ] || { echo "WORKER_GATE_BAD_REQUEST: --backend-egress needs 0|1" >&2; exit 64; }
      EGRESS="$2"; shift 2 ;;
    --prompt-file)
      [ "$#" -ge 2 ] || { echo "WORKER_GATE_BAD_REQUEST: --prompt-file needs a path" >&2; exit 64; }
      PROMPT="$2"; shift 2 ;;
    --rules-b64)
      [ "$#" -ge 2 ] || { echo "WORKER_GATE_BAD_REQUEST: --rules-b64 needs a value" >&2; exit 64; }
      RULES_B64="$2"; shift 2 ;;
    --)
      shift; break ;;
    *)
      break ;;
  esac
done

if [ -z "$EXPECT_VERSION" ]; then
  echo "WORKER_GATE_BAD_REQUEST: missing --expect-version" >&2
  exit 64
fi
if [ "$EXPECT_VERSION" != "$GATE_VERSION" ]; then
  echo "WORKER_GATE_VERSION_MISMATCH: master expects $EXPECT_VERSION, worker is $GATE_VERSION" >&2
  exit 64
fi
case "$SENS" in
  public|sanitized|local-only) ;;
  *) echo "WORKER_GATE_REJECT unknown-sensitivity:${SENS:-<empty>}"; exit 4 ;;
esac
case "$EGRESS" in
  0|1) ;;
  *) echo "WORKER_GATE_BAD_REQUEST: --backend-egress must be 0|1" >&2; exit 64 ;;
esac
if [ "$SENS" = "local-only" ] && [ "$EGRESS" = "1" ]; then
  echo "WORKER_GATE_REJECT sensitivity-local-only:egress"
  exit 4
fi
if [ "$SENS" = "sanitized" ]; then
  if [ -z "$RULES_B64" ]; then
    echo "WORKER_GATE_BAD_REQUEST: sanitized requires --rules-b64" >&2
    exit 64
  fi
  if [ ! -r "$PROMPT" ]; then
    echo "WORKER_GATE_BAD_REQUEST: prompt file not readable: $PROMPT" >&2
    exit 64
  fi
  rules="$(mktemp)"
  trap 'rm -f "$rules"' EXIT
  printf '%s' "$RULES_B64" | base64 -d > "$rules"
  while IFS=$'\t' read -r name re || [ -n "${name:-}" ]; do
    [ -z "${name:-}" ] && continue
    if grep -Eq -- "$re" "$PROMPT"; then
      echo "WORKER_GATE_REJECT scrub-unsafe:$name"
      exit 4
    fi
  done < "$rules"
fi
echo "WORKER_GATE_OK sensitivity=$SENS backend_egress=$EGRESS"
exit 0
