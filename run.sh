#!/usr/bin/env bash
#
# run.sh - one-command setup + launch for "Smarter Cities, Smoother Traffic".
#
# Usage:

#   ./run.sh            # set up (if needed) and open the dashboard
#   ./run.sh --setup    # only build the virtual environment, don't launch
#   ./run.sh --reset    # delete the virtual environment and rebuild from scratch
#
# Why this script exists:
#   The dashboard is a Tkinter GUI. Apple's built-in Python 3.9 ships with
#   Tk 8.5, which renders Tkinter windows blank on current macOS. This script
#   builds a virtual environment on a Python that has a working Tk (8.6) so the
#   window actually draws.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

VENV_DIR="$PROJECT_DIR/venv311"
PYBIN="$VENV_DIR/bin/python"

log()  { printf '\033[36m>>> %s\033[0m\n' "$*"; }
err()  { printf '\033[31m!!! %s\033[0m\n' "$*" >&2; }

# ---------------------------------------------------------------------------
# 1. Handle flags
# ---------------------------------------------------------------------------
SETUP_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --setup) SETUP_ONLY=1 ;;
    --reset) log "Removing $VENV_DIR"; rm -rf "$VENV_DIR" ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) err "Unknown option: $arg"; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# 2. Find a Python interpreter that has a working Tkinter
# ---------------------------------------------------------------------------
find_python_with_tk() {
  local candidates=(
    "$PYBIN"                              # our own venv, if already built
    "/opt/homebrew/bin/python3.12"
    "/opt/homebrew/bin/python3.11"
    "/opt/homebrew/bin/python3"
    "/usr/local/bin/python3"
    "python3"                             # whatever is on PATH (may be Tk 8.5)
  )
  for c in "${candidates[@]}"; do
    command -v "$c" >/dev/null 2>&1 || [ -x "$c" ] || continue
    if "$c" -c "import tkinter" >/dev/null 2>&1; then
      echo "$c"
      return 0
    fi
  done
  return 1
}

# ---------------------------------------------------------------------------
# 3. Build the virtual environment if it isn't there yet
# ---------------------------------------------------------------------------
if [ ! -x "$PYBIN" ]; then
  log "No virtual environment found - creating one."

  BASE_PY="$(find_python_with_tk || true)"

  if [ -z "${BASE_PY:-}" ]; then
    err "Could not find a Python with working Tkinter."
    err "Install one with Homebrew, then re-run this script:"
    err "    brew install python@3.11 python-tk@3.11"
    exit 1
  fi

  # If the only Tk-capable Python is Apple's system 3.9 (Tk 8.5), warn but continue.
  TKVER="$("$BASE_PY" -c 'import tkinter; print(tkinter.TkVersion)')"
  log "Using base interpreter: $BASE_PY (Tk $TKVER)"
  if [ "$TKVER" = "8.5" ]; then
    err "Warning: Tk 8.5 detected - the window may render blank."
    err "For a reliable GUI: brew install python@3.11 python-tk@3.11 && ./run.sh --reset"
  fi

  log "Creating virtual environment at $VENV_DIR"
  "$BASE_PY" -m venv "$VENV_DIR"

  log "Installing dependencies from requirements.txt"
  "$PYBIN" -m pip install --quiet --upgrade pip
  "$PYBIN" -m pip install --quiet -r "$PROJECT_DIR/requirements.txt"
  log "Setup complete."
else
  log "Using existing virtual environment: $VENV_DIR"
fi

# ---------------------------------------------------------------------------
# 4. Launch
# ---------------------------------------------------------------------------
if [ "$SETUP_ONLY" -eq 1 ]; then
  log "Setup only (--setup) - not launching. Start it later with:  ./run.sh"
  exit 0
fi

log "Launching the dashboard  (close the window to quit)"
exec "$PYBIN" "$PROJECT_DIR/main.py"
