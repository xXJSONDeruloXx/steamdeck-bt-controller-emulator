#!/bin/bash
# Launcher wrapper - now runs as normal user
# Kept for compatibility but simplified

cd "$(dirname "$0")"
exec python3 -m src.hogp.gui
