# Research: Remediation Guidance Logging

## Output Channel Separation

**Decision**: Keep the machine-readable finding stream unchanged on stdout and
emit malformed-file paths plus remediation guidance on stderr as operator-facing
console output.

**Rationale**:

- The current CLI contract already emits only canonical affected-file paths to
  stdout and safe summaries to stderr.
- Preserving stdout avoids breaking scripts, contract tests, and downstream
  consumers that parse finding lines directly.
- Malformed-file paths and recommendation text are meant for human review, not
  machine ingestion.

**Alternatives considered**:

- Add metadata to stdout: rejected because it would break the established
  one-path-per-line contract.
- Write a separate report file: rejected because the feature request is about
  console visibility during the scan itself.

## Malformed File Reporting Model

**Decision**: Store malformed file paths explicitly in the scan result and
derive the malformed count from that structured data instead of keeping only an
aggregate count.

**Rationale**:

- The current reporting surface only knows the malformed count, which is
  insufficient to print the exact files the operator must inspect.
- The scan service already has access to the candidate path at the moment a
  classification returns `MALFORMED`, making this the narrowest place to retain
  safe path metadata.
- A structured list supports both summary counts and deterministic unit or
  integration assertions.

**Alternatives considered**:

- Reconstruct malformed paths from stderr formatting only: rejected because it
  hides state in presentation code and weakens testability.
- Re-scan files later to rebuild malformed lists: rejected because it adds
  unnecessary work and duplicate logic.

## Usage Category Inference

**Decision**: Infer a finding's likely usage category from existing safe
metadata already available during scanning: canonical file path, matched folder
pattern, matched filename pattern, and whether the finding came from an
embedded-key text container.

**Recommended categories**:

- `interactive-user-key`: keys under `~/.ssh`, `.ssh`, `id_*`, or `identity`
  patterns that are likely used by a human through SSH tooling.
- `ssh-host-key`: `ssh_host_*_key` files used by SSH servers for host identity.
- `automation-or-deployment-key`: keys under infrastructure, deployment,
  repository key, CI, VPN, or service-oriented paths where an unattended prompt
  would be operationally disruptive.
- `embedded-config-secret`: supported private-key material embedded inside text
  containers such as `.env`, `*.ovpn`, or `*.tfvars`.
- `unknown`: ambiguous findings where the safest outcome is a conservative,
  generic recommendation.

**Rationale**:

- The scanner already records matched folder and filename patterns in
  `CandidateFile`, so inference can stay local and deterministic without
  reading or interpreting additional secret content.
- The user explicitly wants recommendations tied to normal usage of each file;
  path and naming conventions are the safest available proxy for that purpose.
- Keeping inference rule-based avoids a speculative or opaque recommendation
  engine.

**Alternatives considered**:

- Inspect raw file contents for richer semantics: rejected because the feature
  must remain secret-safe and avoid broad semantic parsing.
- Use only the filename or only the folder: rejected because mixed signals such
  as `identity` in repo roots or embedded keys in text files need both pieces of
  context.

## Remediation Guidance Mapping

**Decision**: Emit category-specific advisory guidance that prioritizes the
least disruptive secure workflow for the likely usage type rather than a single
generic "add a passphrase" message.

**Guidance map**:

- `interactive-user-key`: recommend adding a passphrase and loading the key
  into a session-oriented agent or system keychain once per login session, such
  as `ssh-agent` plus `ssh-add`, so repeated interactive prompts are avoided.
- `ssh-host-key`: recommend rotating or reprovisioning the host key under
  root-only ownership and strict permissions, and prefer certificate-based or
  platform-managed host identity workflows where available; do not recommend a
  passphrase because OpenSSH host keys are expected to remain usable without an
  interactive prompt.
- `automation-or-deployment-key`: recommend moving the key into a managed
  secret store or platform vault and injecting it into the workload at runtime,
  or replacing the file-based key with a managed identity or equivalent
  non-interactive credential path.
- `embedded-config-secret`: recommend removing the embedded private key from
  the file and storing it in an external secret manager or OS/application vault,
  with the file retaining only a reference or lookup key.
- `unknown`: recommend classifying the file's operational role first, then
  choosing either a session-scoped passphrase workflow for human use or a
  managed secret store for unattended use.

**Rationale**:

- OpenSSH documentation states that user identity files are commonly protected
  with a passphrase and used through `ssh-agent` or `ssh-add`, which supports a
  once-per-session workflow for interactive users.
- OpenSSH documentation also states that host keys must have an empty
  passphrase, so host-key advice must avoid recommending a human prompt.
- Cloud-secret-store guidance from AWS Secrets Manager and Azure Key Vault
  reinforces that embedded or automation-oriented secrets are better handled by
  managed secret services with controlled retrieval and caching rather than by
  checked-in plaintext files.

**Alternatives considered**:

- Recommend passphrases for every unprotected key: rejected because it is wrong
  for host keys and often impractical for unattended automation.
- Recommend cloud-specific services only: rejected because the scanner should
  stay platform-agnostic and advisory.

## Validation Strategy

**Decision**: Prove the feature with unit tests for category inference and
guidance mapping, contract tests for stdout/stderr separation, and integration
tests for end-to-end malformed-path and recommendation behavior.

**Rationale**:

- The highest risk is output regression, not parsing accuracy.
- Unit tests keep the category map deterministic and easy to evolve.
- Contract and integration coverage ensure the operator guidance does not alter
  exit codes or machine-readable findings.

**Alternatives considered**:

- Documentation-only rollout: rejected because the changed CLI behavior is
  operator-visible and needs executable proof.