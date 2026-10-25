#!/bin/bash
# usage: bash code/utilities/grab_download.sh <filename>
# Copies <filename> from the Downloads folder ($DOWNLOADS if set, otherwise ~/Downloads) to data/raw/unit_prices/.
D=${DOWNLOADS:-$HOME/Downloads}
T="$(cd "$(dirname "$0")/../.." && pwd)/data/raw/unit_prices"
[ -f "$D/$1" ] || { echo "File not found: $D/$1 (set DOWNLOADS=...)"; exit 1; }
cp "$D/$1" "$T/$1" && ls -la "$T/$1" && head -2 "$T/$1"
