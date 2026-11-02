#!/usr/bin/env bash
# _worker_entry.sh - D6 worker fixed entry (ADR-0013 D6-6 #1 / D167)
# WORKER_ENTRY_VERSION: 1
# Usage: bash _worker_entry.sh --expect-version 1 --exec <body.sh> [args...]
# Contract v1: argv only; stdout/stderr = body's, unmodified; exit = body's;
# entry-own errors = 64; no sandbox/lock/chdir/cleanup; version must match.
set -euo pipefail

WORKER_ENTRY_VERSION=1
EXPECT_VERSION=""
BODY=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --expect-version)
      [ "$#" -ge 2 ] || { echo "WORKER_ENTRY_BAD_REQUEST: --expect-version needs a value" >&2; exit 64; }
      EXPECT_VERSION="$2"
      shift 2
      ;;
    --exec)
      [ "$#" -ge 2 ] || { echo "WORKER_ENTRY_BAD_REQUEST: --exec needs a path" >&2; exit 64; }
      BODY="$2"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    *)
      break
      ;;
  esac
done

if [ -z "$EXPECT_VERSION" ]; then
  echo "WORKER_ENTRY_BAD_REQUEST: missing --expect-version" >&2
  exit 64
fi
if [ "$EXPECT_VERSION" != "$WORKER_ENTRY_VERSION" ]; then
  echo "WORKER_ENTRY_VERSION_MISMATCH: master expects $EXPECT_VERSION, worker is $WORKER_ENTRY_VERSION" >&2
  exit 64
fi
if [ -z "$BODY" ]; then
  echo "WORKER_ENTRY_BAD_REQUEST: missing --exec <body.sh>" >&2
  exit 64
fi
if [ ! -r "$BODY" ]; then
  echo "WORKER_ENTRY_BAD_REQUEST: body not readable: $BODY" >&2
  exit 64
fi

exec bash "$BODY" "$@"
