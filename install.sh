#!/usr/bin/env bash
# install.sh — Set up the Discord Music Bot on a Linux/macOS system.
set -euo pipefail

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
info()    { echo "[INFO]  $*"; }
success() { echo "[OK]    $*"; }
warn()    { echo "[WARN]  $*"; }
error()   { echo "[ERROR] $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1. Check for Python 3.12+
# ---------------------------------------------------------------------------
info "Checking Python version..."
if ! command -v python3 &>/dev/null; then
    error "python3 not found. Please install Python 3.12 or newer."
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 12 ]; }; then
    error "Python 3.12+ is required (found $PYTHON_VERSION)."
fi
success "Python $PYTHON_VERSION found."

# ---------------------------------------------------------------------------
# 2. Check for ffmpeg
# ---------------------------------------------------------------------------
info "Checking for ffmpeg..."
if ! command -v ffmpeg &>/dev/null; then
    error "ffmpeg not found. Please install ffmpeg before running this script."
fi
success "ffmpeg found: $(ffmpeg -version 2>&1 | head -1)"

# ---------------------------------------------------------------------------
# 3. Create virtual environment
# ---------------------------------------------------------------------------
VENV_DIR=".venv"
if [ -d "$VENV_DIR" ]; then
    info "Virtual environment '$VENV_DIR' already exists, skipping creation."
else
    info "Creating virtual environment in '$VENV_DIR'..."
    python3 -m venv "$VENV_DIR"
    success "Virtual environment created."
fi

# ---------------------------------------------------------------------------
# 4. Install Python dependencies
# ---------------------------------------------------------------------------
info "Installing Python dependencies from requirements.txt..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r requirements.txt
success "Dependencies installed."

# ---------------------------------------------------------------------------
# 5. Create .env from .env.example if not present
# ---------------------------------------------------------------------------
if [ -f ".env" ]; then
    info ".env already exists, skipping copy."
else
    info "Copying .env.example → .env..."
    cp .env.example .env
    success ".env created."
fi

# ---------------------------------------------------------------------------
# 6. Configure environment
# ---------------------------------------------------------------------------
# Helper: read the current value of a key from .env (strips surrounding quotes)
_get_env_val() {
    grep -E "^$1=" .env 2>/dev/null | cut -d= -f2- | sed "s/^['\"]//;s/['\"]$//"
}

# Helper: set/replace a key=value line in .env (Linux + macOS portable)
_set_env_var() {
    local key="$1" value="$2"
    # Escape characters that are special in sed replacement (\, &, |)
    local escaped
    escaped=$(printf '%s' "$value" | sed 's/[\\&|]/\\&/g')
    if grep -qE "^${key}=" .env; then
        sed -i.bak "s|^${key}=.*|${key}=${escaped}|" .env && rm -f .env.bak
    else
        printf '%s=%s\n' "$key" "$value" >> .env
    fi
}

# Helper: prompt for a variable; pass "secret" as 3rd arg to mask input
_prompt_env() {
    local key="$1" label="$2" secret="${3:-}" current
    current=$(_get_env_val "$key")
    if [ -n "$secret" ]; then
        if [ -n "$current" ]; then
            read -rsp "  ${label} [already set, Enter to keep]: " input
        else
            read -rsp "  ${label} [not set]: " input
        fi
        echo  # newline after hidden input
    else
        read -rp "  ${label} [${current}]: " input
    fi
    if [ -n "$input" ]; then
        _set_env_var "$key" "$input"
    fi
}

info "Configuring environment variables..."
echo "  Press Enter to keep the current value. Secret fields are masked."
echo ""
_prompt_env "DISCORD_TOKEN"          "Discord bot token            (required)" secret
_prompt_env "DISCORD_CLIENT_ID"      "Discord application client ID (required)"
_prompt_env "DISCORD_CLIENT_SECRET"  "Discord OAuth2 client secret (dashboard)" secret
_prompt_env "DISCORD_CALLBACK_URL"   "Discord OAuth2 callback URL  (dashboard)"
_prompt_env "SPOTIFY_CLIENT_ID"      "Spotify client ID            (optional)"
_prompt_env "SPOTIFY_CLIENT_SECRET"  "Spotify client secret        (optional)" secret
_prompt_env "SESSION_SECRET"         "Dashboard session secret     (dashboard)" secret
echo ""
success "Environment configured. Values saved to .env."

# ---------------------------------------------------------------------------
# 7. Create required data directories
# ---------------------------------------------------------------------------
info "Creating data directories..."
mkdir -p data/sfx
success "data/sfx directory is ready."

# ---------------------------------------------------------------------------
# 8. Deploy slash commands
# ---------------------------------------------------------------------------
echo ""
read -r -p "Deploy slash commands to Discord now? [y/N]: " _deploy
if [[ "$_deploy" =~ ^[Yy]$ ]]; then
    info "Deploying slash commands..."
    "$VENV_DIR/bin/python" deploy_commands.py
    success "Slash commands deployed."
else
    info "Skipping slash command deployment."
    echo "  You can deploy later with:  .venv/bin/python deploy_commands.py"
fi

echo ""
echo "-----------------------------------------------------"
echo " Setup complete!"
echo "-----------------------------------------------------"
echo ""
echo "Next steps:"
echo "  1. Start the bot:"
echo "       .venv/bin/python -m bot.main"
echo "  2. (Optional) Start the web dashboard:"
echo "       .venv/bin/python -m bot.dashboard.app"
echo ""
