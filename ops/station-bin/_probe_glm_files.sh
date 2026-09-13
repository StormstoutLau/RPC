#!/bin/bash
# probe_glm_files.sh - locate GLM gguf across B; then caller checks A
echo "=== B: broad find glm ==="
find /home/scott-lau /data /srv /opt /models -iname '*glm*' 2>/dev/null | head -20
echo "=== B: any gguf listing dirs ==="
ls -lat /data/models/gguf/ 2>/dev/null | head -15
echo "=== B: lm-download style paths ==="
find / -maxdepth 5 -iname '*glm*' -not -path '*/proc/*' -not -path '*/sys/*' -not -path '*cache*' 2>/dev/null | head -20
echo PROBE_GLM_FILES_B_DONE