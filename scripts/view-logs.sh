#!/bin/bash
# Helper script to view logs from the Steam Deck

DECK_HOST="deck@192.168.0.241"

echo "=== Viewing logs from Steam Deck ==="
echo ""

# Check if we want to follow logs or view recent
if [ "$1" == "-f" ] || [ "$1" == "--follow" ]; then
    echo "Following logs in real-time (Ctrl+C to stop)..."
    ssh "$DECK_HOST" "journalctl --user -f | grep -E 'hogp|bt-controller|python3 -m src.hogp'"
else
    echo "Recent logs (last 100 lines):"
    echo "=============================="
    ssh "$DECK_HOST" "journalctl --user -n 100 | grep -E 'hogp|bt-controller|python3 -m src.hogp' || echo 'No recent logs found'"
    echo ""
    echo "To follow logs in real-time, run: $0 --follow"
fi
