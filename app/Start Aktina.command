#!/bin/zsh
set -e
cd "$(dirname "$0")"
node build.mjs
printf '%s\n' 'Open http://127.0.0.1:8527/ in your browser. Press Ctrl+C to stop.'
python3 -m http.server 8527 --bind 127.0.0.1 --directory dist
