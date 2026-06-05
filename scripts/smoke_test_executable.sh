#!/usr/bin/env bash
set -euo pipefail

python -m build
pyinstaller --noconfirm --clean --onefile src/find_unencrypted_keys/cli.py --name check-unprotected-keys
./dist/check-unprotected-keys --help >/dev/null