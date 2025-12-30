#!/bin/bash
# Secure wrapper for btmgmt commands used by bt-controller-emulator
# This script provides a restricted interface to btmgmt to minimize security risk
# Only allows specific commands needed for setting BLE static address

set -euo pipefail

# Logging function
log() {
    logger -t "bt-controller-emulator-btmgmt" "$@"
    echo "[bt-controller-emulator-btmgmt] $@" >&2
}

# Validate adapter index (must be 0-9)
validate_adapter_index() {
    local index="$1"
    if ! [[ "$index" =~ ^[0-9]$ ]]; then
        log "ERROR: Invalid adapter index: $index (must be 0-9)"
        exit 1
    fi
}

# Validate BLE static random address format
# Must be a valid MAC with bit 1 set in the most significant byte (C, D, E, or F)
# Format: [CD][0-9A-F]:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}
validate_static_address() {
    local addr="$1"
    
    # Check basic MAC format
    if ! [[ "$addr" =~ ^[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}$ ]]; then
        log "ERROR: Invalid MAC address format: $addr"
        exit 1
    fi
    
    # Check that first octet has bit 1 set (required for BLE static random address)
    # This means the first hex digit must be C, D, E, or F (1100, 1101, 1110, or 1111)
    local first_char="${addr:0:1}"
    if ! [[ "$first_char" =~ ^[CDEFcdef]$ ]]; then
        log "ERROR: Invalid BLE static random address: $addr (first byte must start with C, D, E, or F)"
        exit 1
    fi
}

# Check that btmgmt exists
if ! command -v btmgmt &> /dev/null; then
    log "ERROR: btmgmt command not found"
    exit 1
fi

# Main command handling
case "${1:-}" in
    power)
        # Handle: power <index> <off|on>
        if [ $# -ne 3 ]; then
            log "ERROR: power command requires exactly 2 arguments: <index> <off|on>"
            exit 1
        fi
        
        validate_adapter_index "$2"
        
        if [ "$3" != "off" ] && [ "$3" != "on" ]; then
            log "ERROR: power state must be 'off' or 'on', got: $3"
            exit 1
        fi
        
        log "INFO: Executing: btmgmt --index $2 power $3"
        exec btmgmt --index "$2" power "$3"
        ;;
        
    static-addr)
        # Handle: static-addr <index> <address>
        if [ $# -ne 3 ]; then
            log "ERROR: static-addr command requires exactly 2 arguments: <index> <address>"
            exit 1
        fi
        
        validate_adapter_index "$2"
        validate_static_address "$3"
        
        log "INFO: Executing: btmgmt --index $2 static-addr $3"
        exec btmgmt --index "$2" static-addr "$3"
        ;;
        
    info)
        # Handle: info <index>
        # This is read-only and used to check if static address is already set
        if [ $# -ne 2 ]; then
            log "ERROR: info command requires exactly 1 argument: <index>"
            exit 1
        fi
        
        validate_adapter_index "$2"
        
        log "INFO: Executing: btmgmt --index $2 info"
        exec btmgmt --index "$2" info
        ;;
        
    *)
        log "ERROR: Invalid command: ${1:-<none>}"
        echo "Usage: $0 <command> [args...]" >&2
        echo "Allowed commands:" >&2
        echo "  power <index> <off|on>       - Power adapter off or on" >&2
        echo "  static-addr <index> <addr>   - Set BLE static random address" >&2
        echo "  info <index>                 - Get adapter info (read-only)" >&2
        exit 1
        ;;
esac
