# Steam Deck BLE HID Controller Emulator - Development Justfile

# Steam Deck SSH configuration
deck_host := "192.168.0.241"
deck_user := "deck"
deck_path := "~/steamdeck-bt-controller-emulator"

# Local paths
src_dir := "src"

# Default recipe - show help
default:
    @just --list

# ============================================
# Deployment
# ============================================

# Deploy source code to Steam Deck
deploy:
    @echo "📦 Deploying to {{deck_user}}@{{deck_host}}:{{deck_path}}"
    ssh {{deck_user}}@{{deck_host}} "mkdir -p {{deck_path}}/src"
    scp -r {{src_dir}}/hogp {{deck_user}}@{{deck_host}}:{{deck_path}}/src/
    scp README.md {{deck_user}}@{{deck_host}}:{{deck_path}}/ 2>/dev/null || true
    scp run-gui.sh install-deck.sh uninstall-deck.sh launcher-wrapper.sh bt-controller-emulator.desktop bt-controller-emulator-dbus.conf bt-controller-emulator-sudoers {{deck_user}}@{{deck_host}}:{{deck_path}}/
    @echo "✅ Deployment complete"

# Deploy only modified files (quick sync)
deploy-quick:
    @echo "⚡ Quick deploying modified files..."
    scp {{src_dir}}/hogp/gatt_app.py {{deck_user}}@{{deck_host}}:{{deck_path}}/src/hogp/
    scp {{src_dir}}/hogp/bluez.py {{deck_user}}@{{deck_host}}:{{deck_path}}/src/hogp/
    scp {{src_dir}}/hogp/gui.py {{deck_user}}@{{deck_host}}:{{deck_path}}/src/hogp/
    @echo "✅ Quick deployment complete"

# Deploy and run immediately
deploy-run: deploy run

# Deploy and run with physical input forwarding
deploy-run-input: deploy run-input

# ============================================
# Running on Steam Deck
# ============================================

# Run the HoG peripheral on Steam Deck (interactive)
run name="SteamDeckHoG" rate="10":
    @echo "🎮 Starting HoG peripheral on Steam Deck..."
    ssh -t {{deck_user}}@{{deck_host}} "cd {{deck_path}} && sudo python3 -m src.hogp --name '{{name}}' --rate {{rate}} --verbose"

# Run with physical input forwarding (auto-detect controller)
run-input name="SteamDeckHoG" rate="10" device="auto":
    @echo "🎮 Starting HoG peripheral with input forwarding..."
    ssh -t {{deck_user}}@{{deck_host}} "cd {{deck_path}} && sudo python3 -m src.hogp --name '{{name}}' --rate {{rate}} --input-device {{device}} --verbose"

# Run in background on Steam Deck
run-background name="SteamDeckHoG" rate="10":
    @echo "🎮 Starting HoG peripheral in background..."
    ssh {{deck_user}}@{{deck_host}} "cd {{deck_path}} && sudo nohup python3 -m src.hogp --name '{{name}}' --rate {{rate}} > /tmp/hogp.log 2>&1 &"
    @echo "✅ Started. Use 'just logs' to view output or 'just stop' to stop."

# Run with input forwarding in background
run-input-background name="SteamDeckHoG" rate="10" device="auto":
    @echo "🎮 Starting HoG peripheral with input forwarding in background..."
    ssh {{deck_user}}@{{deck_host}} "cd {{deck_path}} && sudo nohup python3 -m src.hogp --name '{{name}}' --rate {{rate}} --input-device {{device}} > /tmp/hogp.log 2>&1 &"
    @echo "✅ Started. Use 'just logs' to view output or 'just stop' to stop."

# Run the GUI on Steam Deck (interactive)
run-gui:
    @echo "🖥️  Starting GUI on Steam Deck..."
    ssh -t {{deck_user}}@{{deck_host}} "cd {{deck_path}} && sudo python3 -m hogp.gui"

# Deploy and run GUI
deploy-gui: deploy-quick run-gui

# Install desktop launcher on Steam Deck
install:
    @echo "📦 Installing desktop launcher on Steam Deck..."
    ssh -t {{deck_user}}@{{deck_host}} "cd {{deck_path}} && ./install-deck.sh"
    @echo "✅ Desktop launcher installed. Search for 'BT Controller Emulator' in app menu."

# Reinstall after deployment
deploy-install: deploy install

# Stop the HoG peripheral on Steam Deck
stop:
    @echo "🛑 Stopping HoG peripheral..."
    ssh -t {{deck_user}}@{{deck_host}} "sudo pkill -f 'python3 -m src.hogp' || true"
    @echo "✅ Stopped"

# Reset Bluetooth and static address on Steam Deck
reset-bt:
    @echo "🔄 Resetting Bluetooth on Steam Deck..."
    ssh -t {{deck_user}}@{{deck_host}} "sudo systemctl restart bluetooth"
    @echo "✅ Bluetooth restarted"

# Force set static BLE address
set-static-addr addr="C2:12:34:56:78:9A":
    @echo "🔧 Setting static BLE address on Steam Deck..."
    ssh -t {{deck_user}}@{{deck_host}} "sudo btmgmt --index 0 power off && sudo btmgmt --index 0 static-addr {{addr}} && sudo btmgmt --index 0 power on && sudo systemctl restart bluetooth"
    @echo "✅ Static address set to {{addr}}"

# ============================================
# Monitoring & Debugging
# ============================================

# View logs from background process
logs:
    ssh {{deck_user}}@{{deck_host}} "tail -f /tmp/hogp.log"

# View recent logs
logs-recent lines="50":
    ssh {{deck_user}}@{{deck_host}} "tail -n {{lines}} /tmp/hogp.log"

# Check if advertisement is active
check-adv:
    @echo "📡 Checking advertisement status..."
    ssh {{deck_user}}@{{deck_host}} "busctl --system get-property org.bluez /org/bluez/hci0 org.bluez.LEAdvertisingManager1 ActiveInstances"

# Check BlueZ adapter status
check-adapter:
    @echo "🔌 Checking Bluetooth adapter..."
    ssh {{deck_user}}@{{deck_host}} "busctl --system get-property org.bluez /org/bluez/hci0 org.bluez.Adapter1 Powered && \
        busctl --system get-property org.bluez /org/bluez/hci0 org.bluez.Adapter1 Discoverable && \
        busctl --system get-property org.bluez /org/bluez/hci0 org.bluez.Adapter1 Address"

# Find python3 D-Bus unique name and query GATT objects
check-gatt:
    @echo "🔍 Finding Python D-Bus name and querying GATT objects..."
    ssh {{deck_user}}@{{deck_host}} 'PYNAME=$$(busctl --system list | grep python3 | head -1 | awk "{print \$$1}") && \
        if [ -n "$$PYNAME" ]; then \
            echo "Python D-Bus name: $$PYNAME" && \
            busctl --system call $$PYNAME /com/steamdeck/hogp org.freedesktop.DBus.ObjectManager GetManagedObjects | head -c 2000; \
        else \
            echo "No python3 process found on D-Bus"; \
        fi'

# Monitor D-Bus signals (useful for debugging)
monitor-dbus:
    @echo "👀 Monitoring BlueZ D-Bus signals (Ctrl+C to stop)..."
    ssh {{deck_user}}@{{deck_host}} "sudo dbus-monitor --system 'sender=org.bluez'"

# Monitor our application's D-Bus signals
monitor-hogp:
    @echo "👀 Monitoring HoG D-Bus signals (Ctrl+C to stop)..."
    ssh {{deck_user}}@{{deck_host}} "sudo dbus-monitor --system 'path=/com/steamdeck/hogp'"

# Check BlueZ journal logs
bluez-logs:
    ssh {{deck_user}}@{{deck_host}} "journalctl -u bluetooth -f"

# Check BlueZ recent logs
bluez-logs-recent lines="50":
    ssh {{deck_user}}@{{deck_host}} "journalctl -u bluetooth -n {{lines}}"

# ============================================
# Bluetooth Management
# ============================================

# Power cycle the Bluetooth adapter
bt-restart:
    @echo "🔄 Restarting Bluetooth adapter..."
    ssh {{deck_user}}@{{deck_host}} "bluetoothctl power off && sleep 1 && bluetoothctl power on"
    @echo "✅ Bluetooth adapter restarted"

# Show paired devices
bt-paired:
    ssh {{deck_user}}@{{deck_host}} "bluetoothctl paired-devices"

# Remove all paired devices (use with caution!)
bt-unpair-all:
    @echo "⚠️  Removing all paired devices..."
    ssh {{deck_user}}@{{deck_host}} 'bluetoothctl paired-devices | while read -r line; do mac=$$(echo $$line | awk "{print \$$2}"); bluetoothctl remove $$mac; done'

# Show Bluetooth adapter info
bt-info:
    ssh {{deck_user}}@{{deck_host}} "bluetoothctl show"

# ============================================
# SSH Helpers
# ============================================

# Open SSH shell to Steam Deck
ssh:
    ssh {{deck_user}}@{{deck_host}}

# Copy SSH key to Steam Deck (run once for passwordless access)
ssh-copy-id:
    ssh-copy-id {{deck_user}}@{{deck_host}}

# Test SSH connection
ssh-test:
    @echo "🔗 Testing SSH connection..."
    ssh {{deck_user}}@{{deck_host}} "echo 'Connected to $$(hostname)' && uname -a"

# ============================================
# Development Helpers
# ============================================

# Format Python code with black
format:
    black {{src_dir}}/hogp/

# Type check with mypy
typecheck:
    mypy {{src_dir}}/hogp/

# Lint with ruff
lint:
    ruff check {{src_dir}}/hogp/

# Run all checks
check: format lint typecheck

# Clean up Python cache files
clean:
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true

# ============================================
# Research Submodules
# ============================================

# Initialize research submodules
research-init:
    @echo "📚 Initializing research submodules..."
    git submodule update --init --recursive

# Add all research repositories as submodules
research-add:
    @echo "📚 Adding research repositories as submodules..."
    mkdir -p research
    git submodule add https://github.com/Alkaid-Benetnash/EmuBTHID.git research/EmuBTHID || true
    git submodule add https://github.com/007durgesh219/BTGamepad.git research/BTGamepad || true
    git submodule add https://github.com/rafikel/diyps3controller.git research/diyps3controller || true
    git submodule add https://github.com/matlo/GIMX.git research/GIMX || true
    @echo "✅ Research submodules added. Run 'git submodule update --init --recursive' to clone them."

# Update all research submodules
research-update:
    git submodule update --remote --merge

# ============================================
# Full Workflow
# ============================================

# Full deployment and run cycle
full: deploy run

# Full check, deploy, and run
all: check deploy run

# Quick test: deploy and check if everything registers
test: deploy
    @echo "🧪 Running quick test..."
    @just run-background
    @sleep 3
    @just check-adv
    @just check-gatt
    @just stop
    @echo "✅ Quick test complete"
