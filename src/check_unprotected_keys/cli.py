"""CLI entry point for the scanner."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from find_unencrypted_keys import __version__
from find_unencrypted_keys.adapters.reporting import emit_error, emit_scan_result
from find_unencrypted_keys.config.loader import (
    ConfigurationError,
    load_search_configuration,
)
from find_unencrypted_keys.domain.models import ScanRequest
from find_unencrypted_keys.domain.scope import resolve_start_folder
from find_unencrypted_keys.services.scan_service import ScanService


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""

    parser = argparse.ArgumentParser(
        prog="check-unprotected-keys",
        description=(
            "Scan configured folders and filename patterns for unprotected "
            "private keys."
        ),
    )
    parser.add_argument(
        "--start-folder",
        dest="start_folder",
        help=(
            "Optional directory that narrows configured folder matches while "
            "keeping filename patterns unchanged."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""

    parser = build_argument_parser()
    args = parser.parse_args(argv)

    execution_root = Path.cwd().resolve()

    try:
        start_folder = resolve_start_folder(execution_root, args.start_folder)
        configuration = load_search_configuration(execution_root)
    except (ConfigurationError, ValueError) as exc:
        emit_error(str(exc))
        return 2

    request = ScanRequest(
        execution_root=execution_root,
        configuration=configuration,
        start_folder=start_folder,
    )
    result = ScanService().run(request)
    emit_scan_result(result)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
