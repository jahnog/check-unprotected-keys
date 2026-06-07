#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
workspace_dir="$(mktemp -d)"
team_a_root="$repo_root/tests/fixtures/default-scope/team-a"
stdout_file="$workspace_dir/stdout.txt"
stderr_file="$workspace_dir/stderr.txt"
expected_file="$workspace_dir/expected.txt"

cleanup() {
	rm -rf "$workspace_dir"
}

trap cleanup EXIT

cat >"$workspace_dir/.check-unprotected-keys.toml" <<EOF
[scan]
folder_patterns = ["$repo_root/tests/fixtures/default-scope"]
filename_patterns = ["id_*", "*_private.pem", "*.ppk"]
EOF

python -m build
python -m PyInstaller --noconfirm --clean check-unprotected-keys.spec

./dist/check-unprotected-keys --help | grep -q -- "--start-folder"
./dist/check-unprotected-keys --version | grep -Eq '^check-unprotected-keys [0-9]+\.[0-9]+\.[0-9]+$'

set +e
(
	cd "$workspace_dir"
	"$repo_root/dist/check-unprotected-keys" --start-folder "$team_a_root" >"$stdout_file" 2>"$stderr_file"
)
status=$?
set -e

if [[ "$status" -ne 1 ]]; then
	echo "expected exit code 1 from standalone scan, got $status" >&2
	exit 1
fi

printf '%s\n' \
	"$team_a_root/id_rsa" | sort >"$expected_file"
sort "$stdout_file" -o "$stdout_file"

diff -u "$expected_file" "$stdout_file"
grep -q "Found 1 violation(s)." "$stderr_file"
grep -q "Recommended protection for $team_a_root/id_rsa:" "$stderr_file"