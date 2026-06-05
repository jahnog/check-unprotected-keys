"""Helpers for generating scan fixtures during tests."""

from __future__ import annotations

import stat
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa

PASSPHRASE = b"correct-horse-battery-staple"
DEFAULT_FILENAME_PATTERNS = (
    "id_*",
    "*.ppk",
    ".env",
    ".env.*",
    "*_private.pem",
    "*_private.key",
)


@dataclass(slots=True)
class ScanWorkspace:
    """A temporary workspace populated with representative key fixtures."""

    root: Path
    default_scope: Path
    clean_scope: Path
    unprotected_pem: Path
    protected_pem: Path
    unprotected_openssh: Path
    protected_openssh: Path
    unprotected_putty: Path
    protected_putty: Path
    public_key: Path
    malformed_key: Path
    unreadable_key: Path

    def restore_permissions(self) -> None:
        """Restore unreadable fixture permissions so tmp cleanup can succeed."""

        if self.unreadable_key.exists():
            self.unreadable_key.chmod(stat.S_IRUSR | stat.S_IWUSR)


@dataclass(slots=True)
class StartFolderWorkspace:
    """A temporary workspace with nested roots for start-folder tests."""

    root: Path
    scope_root: Path
    team_a_root: Path
    team_b_root: Path
    team_a_finding: Path
    team_a_protected: Path
    team_b_finding: Path


def create_scan_workspace(root: Path) -> ScanWorkspace:
    """Create a temporary workspace with mixed protected and unprotected files."""

    workspace_root = root.resolve()
    default_scope = workspace_root / "fixtures" / "default-scope"
    clean_scope = workspace_root / "fixtures" / "clean-scope"
    default_scope.mkdir(parents=True, exist_ok=True)
    clean_scope.mkdir(parents=True, exist_ok=True)

    unprotected_pem = default_scope / "id_rsa"
    protected_pem = clean_scope / "service_private.pem"
    unprotected_openssh = default_scope / "id_ed25519"
    protected_openssh = clean_scope / "id_ed25519"
    unprotected_putty = default_scope / "workstation.ppk"
    protected_putty = clean_scope / "workstation.ppk"
    public_key = default_scope / "id_rsa.pub"
    malformed_key = default_scope / "broken_private.key"
    unreadable_key = default_scope / "blocked_private.pem"

    write_pem_private_key(unprotected_pem, encrypted=False)
    write_pem_private_key(protected_pem, encrypted=True)
    write_openssh_private_key(unprotected_openssh, encrypted=False)
    write_openssh_private_key(protected_openssh, encrypted=True)
    write_putty_private_key(unprotected_putty, encrypted=False)
    write_putty_private_key(protected_putty, encrypted=True)
    write_public_key(public_key)
    malformed_key.write_text("not a valid private key\n", encoding="utf-8")
    write_pem_private_key(unreadable_key, encrypted=False)
    unreadable_key.chmod(0)

    return ScanWorkspace(
        root=workspace_root,
        default_scope=default_scope,
        clean_scope=clean_scope,
        unprotected_pem=unprotected_pem.resolve(),
        protected_pem=protected_pem.resolve(),
        unprotected_openssh=unprotected_openssh.resolve(),
        protected_openssh=protected_openssh.resolve(),
        unprotected_putty=unprotected_putty.resolve(),
        protected_putty=protected_putty.resolve(),
        public_key=public_key.resolve(),
        malformed_key=malformed_key.resolve(),
        unreadable_key=unreadable_key.resolve(),
    )


def create_start_folder_workspace(root: Path) -> StartFolderWorkspace:
    """Create a temporary workspace with nested fixture roots for US2 tests."""

    workspace_root = root.resolve()
    scope_root = workspace_root / "fixtures" / "default-scope"
    team_a_root = scope_root / "team-a"
    team_b_root = scope_root / "team-b"
    team_a_root.mkdir(parents=True, exist_ok=True)
    team_b_root.mkdir(parents=True, exist_ok=True)

    team_a_finding = team_a_root / "id_rsa"
    team_a_protected = team_a_root / "service_private.pem"
    team_b_finding = team_b_root / "workstation.ppk"

    write_pem_private_key(team_a_finding, encrypted=False)
    write_pem_private_key(team_a_protected, encrypted=True)
    write_putty_private_key(team_b_finding, encrypted=False)

    return StartFolderWorkspace(
        root=workspace_root,
        scope_root=scope_root.resolve(),
        team_a_root=team_a_root.resolve(),
        team_b_root=team_b_root.resolve(),
        team_a_finding=team_a_finding.resolve(),
        team_a_protected=team_a_protected.resolve(),
        team_b_finding=team_b_finding.resolve(),
    )


def write_scan_configuration(
    root: Path,
    *,
    folder_patterns: tuple[str, ...],
    filename_patterns: tuple[str, ...] = DEFAULT_FILENAME_PATTERNS,
) -> Path:
    """Write the scanner TOML configuration in the workspace root."""

    config_path = root / ".check-unprotected-keys.toml"
    folder_entries = "\n".join(f'  "{pattern}",' for pattern in folder_patterns)
    filename_entries = "\n".join(f'  "{pattern}",' for pattern in filename_patterns)

    config_path.write_text(
        dedent(
            f"""
            [scan]
            folder_patterns = [
            {folder_entries}
            ]

            filename_patterns = [
            {filename_entries}
            ]
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return config_path


def write_pem_private_key(path: Path, *, encrypted: bool) -> None:
    """Write a PEM private key fixture."""

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    encryption = (
        serialization.BestAvailableEncryption(PASSPHRASE)
        if encrypted
        else serialization.NoEncryption()
    )
    path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=encryption,
        )
    )


def write_public_key(path: Path) -> None:
    """Write a public key file fixture."""

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH,
        )
        + b"\n"
    )


def write_openssh_private_key(path: Path, *, encrypted: bool) -> None:
    """Write an OpenSSH private key fixture."""

    private_key = ed25519.Ed25519PrivateKey.generate()
    encryption = (
        serialization.BestAvailableEncryption(PASSPHRASE)
        if encrypted
        else serialization.NoEncryption()
    )
    path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.OpenSSH,
            encryption_algorithm=encryption,
        )
    )


def write_putty_private_key(path: Path, *, encrypted: bool) -> None:
    """Write a conservative PuTTY private key fixture."""

    encryption = "aes256-cbc" if encrypted else "none"
    path.write_text(
        dedent(
            f"""
            PuTTY-User-Key-File-3: ssh-ed25519
            Encryption: {encryption}
            Comment: test-key
            Public-Lines: 1
            AAAAC3NzaC1lZDI1NTE5AAAAIEhFTEwtd29ybGQtdGVzdC1wdWJsaWMta2V5
            Private-Lines: 1
            AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=
            Private-MAC: 0000000000000000000000000000000000000000
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
