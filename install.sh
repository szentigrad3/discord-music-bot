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
    success ".env created. Please edit it and fill in your credentials before starting the bot."
fi

# ---------------------------------------------------------------------------
# 6. Create required data directories
# ---------------------------------------------------------------------------
info "Creating data directories..."
mkdir -p data/sfx
success "data/sfx directory is ready."

# ---------------------------------------------------------------------------
# 7. Prompt to deploy slash commands
# ---------------------------------------------------------------------------
echo ""
echo "-----------------------------------------------------"
echo " Setup complete!"
echo "-----------------------------------------------------"
echo ""
echo "Next steps:"
echo "  1. Edit .env and fill in your Discord (and optionally Spotify) credentials."
echo "  2. Activate the virtual environment:"
echo "       source .venv/bin/activate"
echo "  3. Deploy slash commands to Discord:"
echo "       .venv/bin/python deploy_commands.py"
echo "  4. Start the bot:"
echo "       .venv/bin/python -m bot.main"
echo "  5. (Optional) Start the web dashboard:"
echo "       .venv/bin/python -m bot.dashboard.app"
echo ""
