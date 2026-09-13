#!/bin/bash
# start unsloth studio on C with UNSLOTH_LLAMA_CPP_PATH from studio.conf
source "$HOME/.local/share/unsloth/studio.conf"
exec "$UNSLOTH_EXE" studio -p 8888