"""Guard the hexagonal ports boundary (spec 010 FR-007)."""

from __future__ import annotations

import ast
from pathlib import Path


def test_ports_module_does_not_import_adapters() -> None:
    ports_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "check_unprotected_keys"
        / "services"
        / "ports.py"
    )
    tree = ast.parse(ports_path.read_text(encoding="utf-8"), filename=str(ports_path))
    adapter_imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if "adapters" in node.module.split("."):
                adapter_imports.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if "adapters" in alias.name.split("."):
                    adapter_imports.append(alias.name)
    assert adapter_imports == [], f"ports.py imports adapters: {adapter_imports}"
