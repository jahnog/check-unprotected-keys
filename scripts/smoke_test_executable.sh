#!/usr/bin/env bash
set -euo pipefail

python -m build
pyinstaller --noconfirm --clean --onefile src/find_unencrypted_keys/cli.py --name find-unencrypted-keys
./dist/find-unencrypted-keys --help >/dev/null
#!/usr/bin/env bash
set -euo pipefail

python -m build
pyinstaller --noconfirm --clean --onefile src/find_unencrypted_keys/cli.py --name find-unencrypted-keys
./dist/find-unencrypted-keys --help >/dev/null