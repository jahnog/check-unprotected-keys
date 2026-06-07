# Research: Expand Secret Patterns

## Scope Boundary and Detection Model

**Decision**: Keep the feature strictly focused on expanding the shipped folder
and filename pattern catalog while preserving the current detection engine for
supported key material, including supported key blocks embedded in matched text
files.

**Rationale**:

- The current product already distinguishes supported key parsing from generic
  secret hunting, and the clarification decision for this feature keeps that
  boundary intact.
- Existing adapters, contracts, and tests already support PEM, OpenSSH, PuTTY,
  and embedded key blocks in text containers without adding a new classifier
  family.
- Treating this feature as pattern expansion keeps planning, validation, and
  operator expectations aligned with the current CLI.

**Alternatives considered**:

- Add generic API-key or token detection: rejected because it would create a new
  secret-scanning subsystem, widen false-positive risk, and exceed the accepted
  scope for this feature.
- Restrict the feature to raw key files only: rejected because the current
  product already supports key material embedded in matched text files such as
  `.env`, and removing that from the expanded catalog would unnecessarily reduce
  real-world coverage.

## Default Folder Pattern Catalog

**Decision**: Ship a curated Linux-first folder catalog that includes the
user-home SSH root and repo-local key, certificate, configuration, deployment,
IaC, container, orchestration, and VPN directories where supported key material
is commonly stored.

**Recommended categories and representative patterns**:

- User-home SSH roots: `~/.ssh`, `.ssh`
- Repo-local key and PKI roots: `keys`, `private`, `certs`, `certificates`,
  `tls`, `ssl`, `pki`, `secrets`
- Curated config subtrees: `config/keys`, `config/certs`, `config/tls`,
  `config/secrets`, `.config/keys`, `.config/certs`, `.config/tls`,
  `.config/secrets`
- Deployment and IaC roots: `deploy`, `deployment`, `infra`, `ansible`,
  `terraform`
- Container, orchestration, and VPN roots: `docker`, `helm`, `k8s`,
  `kubernetes`, `vpn`, `openvpn`

**Rationale**:

- `Path.expanduser()` support already exists in folder-pattern expansion, so a
  curated home-directory SSH entry is implementable without changing CLI
  semantics.
- Repo-local key and PKI roots are common places for deploy keys, service keys,
  TLS material, and test credentials in Linux-first projects.
- Curated subtrees keep defaults understandable while avoiding recursive
  catch-all roots that would balloon candidate discovery.
- Container, IaC, and VPN directories often carry PEM, KEY, or embedded-key
  text containers without requiring support for generic token formats.

**Alternatives considered**:

- Repo-local directories only: rejected because it misses the most common
  user-home SSH storage convention and weakens out-of-the-box operator value.
- Whole-home or system-root scanning by default: rejected because it is noisy,
  privacy-sensitive, and unnecessary for the bounded default catalog.
- User-home cloud or kube directories by default: rejected because they mainly
  store JSON, YAML, or token formats outside the current supported detection
  engine.

## Default Filename Pattern Catalog

**Decision**: Expand the shipped filename catalog to cover raw key filenames,
generic PEM/KEY containers, PuTTY files, SSH host key names, and a small set of
high-signal text-container names that commonly embed supported key blocks.

**Recommended patterns**:

- Raw key names and extensions: `id_*`, `identity`, `ssh_host_*_key`, `*.ppk`,
  `*.pem`, `*.key`
- High-signal text containers with embedded-key support: `.env`, `.env.*`,
  `*.env`, `*.env.*`, `*.ovpn`, `*.tfvars`

**Explicit default exclusions**:

- Public-only and certificate-only artifacts: `*.pub`, `authorized_keys`,
  `known_hosts`, `*.crt`, `*.cer`, `*.csr`
- Unsupported keystore families: `*.p12`, `*.pfx`, `*.jks`, `*.keystore`,
  `*.der`, `*.pk8`
- Generic config or token-hunting patterns: `*.json`, `*.yaml`, `*.yml`,
  `*.toml`, `*.ini`, `*.cfg`, `*.conf`, `*.properties`, `*secret*`, `*token*`,
  `*credential*`, `*password*`, `*apikey*`, `*api_key*`, broad `*key*`

**Rationale**:

- `*.pem` and `*.key` provide the largest bounded recall improvement for
  currently supported parsers, especially when paired with curated folder roots.
- `.env`, `*.ovpn`, and `*.tfvars` are strong candidates for literal embedded
  PEM/OpenSSH blocks that the current engine can actually classify.
- Excluding structured text, public-only material, and unsupported keystores
  prevents the feature from drifting into generic secret detection or noisy
  certificate inventory scanning.

**Alternatives considered**:

- Keep only the original minimal filename list: rejected because it misses many
  common PEM/KEY naming conventions and weakens the feature's value.
- Add generic text and token patterns: rejected because the current engine does
  not classify them reliably and the user explicitly rejected that direction.

## Validation and Documentation Strategy

**Decision**: Validate the catalog with contract, integration, and unit tests
that exercise expanded defaults, start-folder narrowing, deduplication, and
noise boundaries; update the shipped configuration example, quickstart, README,
and contracts to explain the categories and non-goals.

**Rationale**:

- The feature changes operator-visible behavior through configuration defaults,
  so tests and docs must move together.
- Existing config loader, scope resolution, and discovery surfaces are already
  pattern-driven, making fixture-led validation the right level of proof.
- Category-based docs reduce the chance that operators misread the feature as a
  generic secret scanner.

**Alternatives considered**:

- Documentation-only change: rejected because changed defaults need executable
  proof.
- Test-only change without contract or README updates: rejected because the
  catalog is an operator-facing interface, not just an internal implementation
  detail.# Research: Expand Secret Patterns

## Scope Boundary and Detection Model

**Decision**: Expand the shipped folder and filename catalog only; keep
findings limited to the current supported exposure detection model, including
supported private-key material embedded in matched text files, and do not add
generic plaintext API-key, token, or unsupported secret detection.

**Rationale**:

- The specification clarification explicitly keeps this feature as pattern
  expansion rather than a new generic secret scanner.
- Current runtime behavior already supports PEM, OpenSSH, and PuTTY private-key
  formats plus embedded recognized key blocks in matched text containers.
- Preserving the current detection engine keeps planning, testing, and release
  risk bounded to configuration and validation surfaces.

**Alternatives considered**:

- Generic token and user-secret heuristics: rejected because they require a new
  exposure model, higher false-positive risk, and broader product scope.
- Key-file-only expansion with no text-container support: rejected because the
  current product already supports embedded recognized key blocks in matched
  text files such as `.env`.

## Default Folder Catalog

**Decision**: Ship a curated Linux-first baseline that includes explicit
user-home and repo-local roots such as `~/.ssh`, `keys`, `private`, `secrets`,
`certs`, `tls`, `pki`, `vpn`, `openvpn`, `infra`, `infrastructure`,
`terraform`, `ansible`, `.github`, `.gitlab`, `.circleci`, `config/keys`,
`config/certs`, `config/tls`, `config/secrets`, `.config/keys`, `.config/certs`,
`.config/tls`, and `.config/secrets`.

**Rationale**:

- `Path.expanduser()` is already used for folder-pattern expansion, so
  `~/.ssh` is implementable without adding new runtime behavior.
- Repo-local key, PKI, VPN, IaC, CI, and explicit secret subtrees provide the
  biggest default-scan recall gains for supported key material without scanning
  the entire repository or home directory.
- The scanner already walks matched roots recursively and deduplicates
  canonical paths, so precise root names are preferable to broad recursive
  catch-all patterns.

**Alternatives considered**:

- Whole-home or whole-system roots such as `~`, `/home`, `/etc`, or `/etc/ssh`:
  rejected because they introduce too much traversal cost and operational
  surprise for default runs.
- Cloud and workstation tool roots such as `~/.aws`, `~/.azure`, `~/.kube`,
  `~/.docker`, or `~/.config/gcloud`: rejected because they mainly hold
  unsupported structured credentials rather than the currently supported raw key
  formats.
- Generic recursive roots such as `**`, `config/**`, or `secrets/**`: rejected
  because the existing scanner already recurses matched roots, making these
  patterns noisy and redundant.

## Default Filename Catalog

**Decision**: Expand the default filename list to high-signal conventions such
as `id_*`, `identity`, `ssh_host_*_key`, `*_rsa`, `*_ed25519`, `*_ecdsa`,
`*_dsa`, `*.ppk`, `*.pem`, `*.key`, `.env`, `.env.*`, `*.env`, `*.env.*`,
`*.ovpn`, and `*.tfvars`.

**Rationale**:

- These names cover common raw key files plus a small set of text containers
  that frequently embed literal armored key blocks.
- Broadening from `*_private.pem` and `*_private.key` to `*.pem` and `*.key`
  substantially improves recall inside bounded roots while keeping false
  positives manageable because non-findings are suppressed by the detection
  engine.
- `.ovpn` and `*.tfvars` are high-signal text containers for embedded key
  blocks in infrastructure workflows.

**Alternatives considered**:

- Generic structured config formats such as `*.json`, `*.yaml`, `*.yml`,
  `*.toml`, `*.ini`, `*.cfg`, or `*.conf`: rejected because the current engine
  does not reliably interpret escaped or wrapped key material in those files by
  default.
- Public and certificate-only names such as `*.pub`, `authorized_keys`,
  `known_hosts`, `*.crt`, `*.cer`, or `*.csr`: rejected because they mostly add
  public or certificate material that is not a finding.
- Unsupported keystore formats such as `*.p12`, `*.pfx`, `*.jks`, or
  `*.keystore`: rejected because parser support is not part of this feature.

## Validation and Documentation Strategy

**Decision**: Validate the broader default catalog through configuration
contract tests, default-scan and start-folder integration tests, and an updated
quickstart that uses deterministic repo fixtures plus a temporary `HOME` value
to exercise `~/.ssh` behavior.

**Rationale**:

- The current codebase is largely pattern-agnostic; the main regression risk is
  whether expanded defaults remain bounded, deduplicated, and compatible with
  start-folder narrowing.
- Using repo fixtures and a temporary `HOME` keeps the quickstart and automated
  validation deterministic without requiring access to a real user home
  directory.
- CLI packaging behavior does not change, so the executable smoke test only
  needs updated scenario coverage rather than a new delivery mechanism.

**Alternatives considered**:

- Manual-only validation against a developer's real home directory: rejected
  because it is not deterministic or CI-friendly.
- Documentation-only pattern expansion with no new fixtures: rejected because
  the constitution requires executable proof for changed behavior.