#!/usr/bin/env bash
# Download a Gemma 4 GGUF variant from Hugging Face.
#
# Usage:
#   ./scripts/download-gemma4.sh [variant] [quant]
#
# Variants:
#   e2b    ~2B effective params (smallest, fastest)
#   e4b    ~4B effective params (sweet spot for fast scoring)
#   26b    26B total / 4B active MoE (best quality for 48GB Macs)
#
# Quant (defaults to Q4_K_M; pass another tag like Q5_K_M, Q8_0 to override):
#   Q4_K_M  4-bit, recommended for larger models
#   Q5_K_M  5-bit, larger but higher quality
#   Q8_0    8-bit, recommended for the small E2B/E4B models
#
# Output directory: ~/models/llm/gemma-4-<variant>/

set -euo pipefail

VARIANT="${1:-26b}"
QUANT="${2:-Q4_K_M}"
DEST_ROOT="${GEMMA4_DEST:-/Users/davidloor/models/llm}"

case "$VARIANT" in
  e2b)  REPO="unsloth/gemma-4-E2B-it-GGUF" ;;
  e4b)  REPO="unsloth/gemma-4-E4B-it-GGUF" ;;
  26b)  REPO="unsloth/gemma-4-26B-A4B-it-GGUF" ;;
  *)    echo "Unknown variant: $VARIANT (expected: e2b, e4b, 26b)" >&2; exit 1 ;;
esac

DEST="$DEST_ROOT/gemma-4-$VARIANT"
mkdir -p "$DEST"

echo "Downloading $REPO ($QUANT) -> $DEST"
echo "(This is a large download; expect 1-15 minutes depending on bandwidth and variant size.)"
echo

exec huggingface-cli download "$REPO" \
  --include "*${QUANT}*" \
  --local-dir "$DEST"
