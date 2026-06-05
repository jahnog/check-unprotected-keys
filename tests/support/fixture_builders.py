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
HOME_EXPANDED_FOLDER_PATTERN = "~/.ssh"
EXPANDED_FIXTURE_ROOT = "fixtures/expanded-patterns"
EXPANDED_FOLDER_PATTERNS = (
    HOME_EXPANDED_FOLDER_PATTERN,
    f"{EXPANDED_FIXTURE_ROOT}/repo-keys",
    f"{EXPANDED_FIXTURE_ROOT}/config-secrets",
    f"{EXPANDED_FIXTURE_ROOT}/infra",
    f"{EXPANDED_FIXTURE_ROOT}/vpn",
)
EXPANDED_FILENAME_PATTERNS = (
    "id_*",
    "identity",
    "ssh_host_*_key",
    "*.ppk",
    "*.pem",
    "*.key",
    ".env",
    ".env.*",
    "*.env",
    "*.env.*",
    "*.ovpn",
    "*.tfvars",
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


@dataclass(slots=True)
class ExpandedPatternWorkspace:
    """A temporary workspace with expanded default-scope coverage scenarios."""

    root: Path
    home_root: Path
    home_ssh_root: Path
    fixture_root: Path
    repo_keys_root: Path
    config_secrets_root: Path
    infra_root: Path
    vpn_root: Path
    noise_root: Path
    home_ssh_finding: Path
    repo_key_finding: Path
    repo_key_protected: Path
    config_secret_finding: Path
    infra_secret_finding: Path
    vpn_secret_finding: Path
    noise_public_key: Path
    noise_certificate: Path
    noise_keystore: Path
    noise_config: Path
    repo_public_only: Path | None = None
    repo_malformed_key: Path | None = None
    repo_excluded_certificate: Path | None = None
    repo_excluded_keystore: Path | None = None
    config_excluded_json: Path | None = None


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


def create_expanded_pattern_workspace(root: Path) -> ExpandedPatternWorkspace:
    """Create expanded-scope fixtures for home, repo, infra, and noise tests."""

    workspace_root = root.resolve()
    fixture_root = workspace_root / EXPANDED_FIXTURE_ROOT
    home_root = workspace_root / "home"
    home_ssh_root = home_root / ".ssh"
    repo_keys_root = fixture_root / "repo-keys"
    config_secrets_root = fixture_root / "config-secrets"
    infra_root = fixture_root / "infra"
    vpn_root = fixture_root / "vpn"
    noise_root = fixture_root / "noise"

    for directory in (
        home_ssh_root,
        repo_keys_root,
        config_secrets_root,
        infra_root,
        vpn_root,
        noise_root,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    home_ssh_finding = home_ssh_root / "id_ed25519"
    repo_key_finding = repo_keys_root / "deploy.pem"
    repo_key_protected = repo_keys_root / "service_private.pem"
    config_secret_finding = config_secrets_root / "service.env"
    infra_secret_finding = infra_root / "terraform.tfvars"
    vpn_secret_finding = vpn_root / "client.ovpn"
    noise_public_key = noise_root / "id_ed25519.pub"
    noise_certificate = noise_root / "tls.crt"
    noise_keystore = noise_root / "bundle.p12"
    noise_config = noise_root / "service-account.json"

    write_openssh_private_key(home_ssh_finding, encrypted=False)
    write_pem_private_key(repo_key_finding, encrypted=False)
    write_pem_private_key(repo_key_protected, encrypted=True)
    write_embedded_private_key(config_secret_finding, encrypted=False)
    write_embedded_private_key(infra_secret_finding, encrypted=False)
    write_embedded_private_key(vpn_secret_finding, encrypted=False)
    write_public_key(noise_public_key)
    noise_certificate.write_text(
        "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n",
        encoding="utf-8",
    )
    noise_keystore.write_bytes(b"not-a-supported-keystore\n")
    noise_config.write_text('{"token": "example"}\n', encoding="utf-8")

    return ExpandedPatternWorkspace(
        root=workspace_root,
        home_root=home_root.resolve(),
        home_ssh_root=home_ssh_root.resolve(),
        fixture_root=fixture_root.resolve(),
        repo_keys_root=repo_keys_root.resolve(),
        config_secrets_root=config_secrets_root.resolve(),
        infra_root=infra_root.resolve(),
        vpn_root=vpn_root.resolve(),
        noise_root=noise_root.resolve(),
        home_ssh_finding=home_ssh_finding.resolve(),
        repo_key_finding=repo_key_finding.resolve(),
        repo_key_protected=repo_key_protected.resolve(),
        config_secret_finding=config_secret_finding.resolve(),
        infra_secret_finding=infra_secret_finding.resolve(),
        vpn_secret_finding=vpn_secret_finding.resolve(),
        noise_public_key=noise_public_key.resolve(),
        noise_certificate=noise_certificate.resolve(),
        noise_keystore=noise_keystore.resolve(),
        noise_config=noise_config.resolve(),
    )


def create_expanded_noise_workspace(root: Path) -> ExpandedPatternWorkspace:
    """Create expanded fixtures plus mixed noise inside scanned categories."""

    workspace = create_expanded_pattern_workspace(root)
    repo_public_only = workspace.repo_keys_root / "identity"
    repo_malformed_key = workspace.repo_keys_root / "unsupported.key"
    repo_excluded_certificate = workspace.repo_keys_root / "tls.crt"
    repo_excluded_keystore = workspace.repo_keys_root / "bundle.p12"
    config_excluded_json = workspace.config_secrets_root / "credentials.json"

    write_public_key(repo_public_only)
    repo_malformed_key.write_text("not a supported private key\n", encoding="utf-8")
    repo_excluded_certificate.write_text(
        "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n",
        encoding="utf-8",
    )
    repo_excluded_keystore.write_bytes(b"unsupported keystore fixture\n")
    config_excluded_json.write_text(
        '{"credential": "not-a-supported-key"}\n',
        encoding="utf-8",
    )

    workspace.repo_public_only = repo_public_only.resolve()
    workspace.repo_malformed_key = repo_malformed_key.resolve()
    workspace.repo_excluded_certificate = repo_excluded_certificate.resolve()
    workspace.repo_excluded_keystore = repo_excluded_keystore.resolve()
    workspace.config_excluded_json = config_excluded_json.resolve()
    return workspace


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


def write_expanded_scan_configuration(
    root: Path,
    *,
    folder_patterns: tuple[str, ...] = EXPANDED_FOLDER_PATTERNS,
    filename_patterns: tuple[str, ...] = EXPANDED_FILENAME_PATTERNS,
) -> Path:
    """Write the expanded-catalog configuration used by later feature tests."""

    return write_scan_configuration(
        root,
        folder_patterns=folder_patterns,
        filename_patterns=filename_patterns,
    )


def write_pem_private_key(path: Path, *, encrypted: bool) -> None:
    """Write a PEM private key fixture."""

    path.write_bytes(_serialize_pem_private_key(encrypted=encrypted))


def write_embedded_private_key(path: Path, *, encrypted: bool) -> None:
    """Write a text container that embeds a PEM private key block."""

    key_text = _serialize_pem_private_key(encrypted=encrypted).decode("utf-8")
    path.write_text(
        f"# embedded key fixture\nfixture = true\n{key_text}",
        encoding="utf-8",
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


def _serialize_pem_private_key(*, encrypted: bool) -> bytes:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    encryption = (
        serialization.BestAvailableEncryption(PASSPHRASE)
        if encrypted
        else serialization.NoEncryption()
    )
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=encryption,
    )
