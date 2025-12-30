#!/bin/bash
# Launcher wrapper that shows errors
# This runs with pkexec and captures any errors

LOG_FILE="/tmp/bt-controller-emulator.log"

echo "=== BT Controller Emulator Log ===" > "$LOG_FILE"
echo "Started at: $(date)" >> "$LOG_FILE"
echo "User: $USER" >> "$LOG_FILE"
echo "Display: $DISPLAY" >> "$LOG_FILE"
echo "---" >> "$LOG_FILE"

# Allow GTK to run as root (needed for Bluetooth access)
export GDK_BACKEND=x11
export GTK_CSD=0

# Run the GUI and capture output
python3 "$@" 2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=$?
echo "---" >> "$LOG_FILE"
echo "Exit code: $EXIT_CODE" >> "$LOG_FILE"

if [ $EXIT_CODE -ne 0 ]; then
    # Show error dialog if available
    if command -v zenity &> /dev/null; then
        zenity --error --text="BT Controller Emulator failed to start.\nCheck log: $LOG_FILE" --width=400
    elif command -v kdialog &> /dev/null; then
        kdialog --error "BT Controller Emulator failed to start.\nCheck log: $LOG_FILE"
    fi
fi

exit $EXIT_CODE
