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

# Deploy source code to Steam Deck
deploy:
    @echo "Deploying to {{deck_user}}@{{deck_host}}:{{deck_path}}"
    ssh {{deck_user}}@{{deck_host}} "mkdir -p {{deck_path}}/src {{deck_path}}/scripts {{deck_path}}/config"
    scp -r {{src_dir}}/hogp {{deck_user}}@{{deck_host}}:{{deck_path}}/src/
    scp scripts/*.sh {{deck_user}}@{{deck_host}}:{{deck_path}}/scripts/
    scp config/* {{deck_user}}@{{deck_host}}:{{deck_path}}/config/
    @echo "Deployment complete"

# Install desktop launcher on Steam Deck
install:
    ssh -t {{deck_user}}@{{deck_host}} "cd {{deck_path}} && ./install.sh"
    @echo "Installed. Search for 'BT Controller Emulator' in app menu."

# Open SSH shell to Steam Deck
ssh:
    ssh {{deck_user}}@{{deck_host}}

# Copy SSH key to Steam Deck (run once for passwordless access)
ssh-copy-id:
    ssh-copy-id {{deck_user}}@{{deck_host}}


# Clean up Python cache files
clean:
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
