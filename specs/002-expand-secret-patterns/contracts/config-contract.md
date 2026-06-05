# Configuration Contract: Expand Secret Patterns

## File Location

`.check-unprotected-keys.toml` in the execution root.

The repository also ships `.check-unprotected-keys.toml.example` as the
documented baseline catalog for default usage.

## Schema

```toml
[scan]
folder_patterns = [
  "~/.ssh",
  ".ssh",
  "keys",
  "private",
  "certs",
  "certificates",
  "tls",
  "ssl",
  "pki",
  "secrets",
  "config/keys",
  "config/certs",
  "config/tls",
  "config/secrets",
  ".config/keys",
  ".config/certs",
  ".config/tls",
  ".config/secrets",
  "deploy",
  "deployment",
  "infra",
  "ansible",
  "terraform",
  "docker",
  "helm",
  "k8s",
  "kubernetes",
  "vpn",
  "openvpn"
]

filename_patterns = [
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
  "*.tfvars"
]
```

## Field Rules

### `scan.folder_patterns`

- Required.
- Array of non-empty strings.
- Entries may be relative to the execution root or absolute filesystem paths.
- `~`-prefixed entries expand against the active user home before canonical
  resolution.
- Entries define where the scanner may look for candidate files.
- The shipped baseline SHOULD stay limited to curated user-home and repo-local
  directories where supported key material is commonly stored.

### `scan.filename_patterns`

- Required.
- Array of non-empty glob strings.
- Entries are applied unchanged whether or not `--start-folder` is provided.
- Entries define which filenames are eligible once a folder match has been
  reached.
- The shipped baseline SHOULD include raw key filenames, PEM/KEY containers,
  PuTTY files, and high-signal text-container names that may embed supported
  key blocks.

## Default Pattern Categories

### Folder Categories

- `ssh-home`: explicit user-home SSH roots such as `~/.ssh` and `.ssh`
- `repo-key-roots`: `keys`, `private`, `certs`, `certificates`, `tls`, `ssl`,
  `pki`, `secrets`
- `config-subtrees`: `config/keys`, `config/certs`, `config/tls`,
  `config/secrets`, `.config/keys`, `.config/certs`, `.config/tls`,
  `.config/secrets`
- `deployment-and-iac`: `deploy`, `deployment`, `infra`, `ansible`, `terraform`
- `container-and-vpn`: `docker`, `helm`, `k8s`, `kubernetes`, `vpn`, `openvpn`

### Filename Categories

- `ssh-private-key-names`: `id_*`, `identity`, `ssh_host_*_key`
- `private-key-extensions`: `*.ppk`, `*.pem`, `*.key`
- `embedded-key-text-containers`: `.env`, `.env.*`, `*.env`, `*.env.*`,
  `*.ovpn`, `*.tfvars`

## Validation Rules

- The configuration file MUST parse as TOML.
- Both arrays MUST contain at least one entry.
- Blank strings are invalid.
- Duplicate patterns are allowed but are collapsed during effective-scope
  resolution through canonical-path deduplication.
- The shipped baseline MUST NOT rely on broad catch-all roots such as the whole
  execution root, whole user home, or recursive `**` patterns.
- The shipped baseline MUST NOT imply support for generic plaintext API keys,
  tokens, public-only files, or unsupported keystore families.

## Semantics

- The effective scope is the intersection of configured folder matches and
  configured filename matches.
- A start-folder override narrows only the reachable folder matches beneath the
  supplied path.
- Filename matching remains exactly the same after start-folder narrowing.
- Files matched through the expanded catalog are still classified only by the
  current supported key-detection engine.

## Bounded Default Exclusions

The shipped baseline excludes these families by default even though operators
may opt into them explicitly:

- Broad system or home roots such as `/etc`, `/var`, the whole execution root,
  or the whole user home
- Generic text or structured config formats such as `*.json`, `*.yaml`,
  `*.yml`, `*.toml`, `*.ini`, `*.cfg`, `*.conf`, and `*.properties`
- Public-only artifacts such as `*.pub`, `authorized_keys`, `known_hosts`, and
  certificate-only outputs such as `*.crt`, `*.cer`, and `*.csr`
- Unsupported keystore families such as `*.p12`, `*.pfx`, `*.jks`,
  `*.keystore`, `*.der`, and `*.pk8`
- Generic token or secret-hunting globs such as `*token*`, `*secret*`,
  `*credential*`, `*password*`, and broad `*key*`

## Effective Scope Example

```toml
[scan]
folder_patterns = [
  "~/.ssh",
  "tests/fixtures/expanded-patterns/repo-keys",
  "/absolute/path/to/repo/tests/fixtures/expanded-patterns/repo-keys"
]

filename_patterns = [
  "id_*",
  "*.pem",
  "*.key",
  ".env",
  "*.ovpn"
]
```

With this configuration, the next scan evaluates the expanded SSH and repo-key
roots, collapses overlapping relative and absolute folder matches to one
canonical root set, and applies the same filename patterns regardless of
whether `--start-folder` is supplied.