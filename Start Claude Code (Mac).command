#!/bin/bash
# Plain Congress: double-click me to open this folder in Claude Code.
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:$HOME/.claude/local/bin:$PATH"
echo "Plain Congress kit: $(pwd)"
echo
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python is not installed yet. Opening the download page..."
  open "https://www.python.org/downloads/"
  echo "Install Python (click Continue until it finishes), then double-click this file again."
  read -r -p "Press Return to close. "
  exit 1
fi
if ! command -v claude >/dev/null 2>&1; then
  echo "Installing Claude Code (one time, about a minute)..."
  curl -fsSL https://claude.ai/install.sh | bash
  export PATH="$HOME/.local/bin:$HOME/.claude/local/bin:$PATH"
  hash -r 2>/dev/null
fi
if ! command -v claude >/dev/null 2>&1; then
  echo "Claude Code did not install. Open START_HERE.txt and follow Step 3 by hand."
  read -r -p "Press Return to close. "
  exit 1
fi
echo "Starting Claude Code."
echo "  1. If it asks whether you trust this folder: press Return for Yes."
echo "  2. Paste everything from KICKOFF_PROMPT.txt and press Return."
echo
claude
