# Phase 0 Research: Scan Java `.properties` Files for Unprotected Secrets

All spec clarifications were resolved during `/speckit-clarify` (see spec
Clarifications, Session 2026-06-22). The remaining decisions below pin the
planning-level details the spec deferred (heuristic bounds, default catalog,
parsing depth) plus the integration choices needed to keep the change within the
existing architecture.

## Decision 1 — Make `.properties` files candidates via existing discovery

- **Decision**: Add `*.properties` to packaged `filename_patterns`. Discovery
  (`filesystem.discover_candidate_files`) then selects them like any candidate,
  honoring `ignore_directories`, `ignore_filename_patterns`, canonical-path
  dedupe, and the directory-visit cap with no changes.
- **Rationale**: Reuses the entire authorized-traversal and ignore stack (DRY,
  KISS); satisfies FR-001 and FR-011 for free.
- **Alternatives considered**: A separate discovery pass for properties files —
  rejected (duplicate walk, extra traversal, violates SC-005).

## Decision 2 — Route by file type in the service, inspect content in an adapter

- **Decision**: In `ScanService.run`, branch on `candidate.canonical_path.suffix
  == ".properties"`. Properties candidates go to
  `properties_inspector.inspect_properties_file(...)`; all others keep the
  existing `key_parsers.inspect_candidate_file(...)` path.
- **Rationale**: A normal `.properties` file is not key material; the existing
  parser would classify it `MALFORMED`. Routing keeps the two responsibilities
  separate (SRP) and leaves file-level key classification untouched (Open/Closed).
- **Alternatives considered**: Teaching `inspect_candidate_file` about properties
  — rejected (mixes two unrelated responsibilities, returns a single
  file-level classification which cannot express multiple per-property findings).

## Decision 3 — Value-assessment decision order (FR-004/005/006/007)

For each parsed `PropertyEntry`:

1. **Inline key material** (unconditional, per FR-006): if the value contains a
   `-----BEGIN` marker, unescape `\n`, reuse `key_parsers` to classify; report
   when `UNPROTECTED`. This runs regardless of the key name because embedded key
   material is the tool's core competency.
2. The remaining rules apply **only when the key name matches** the secret-name
   catalog (FR-003):
   a. `EMPTY` / `PLACEHOLDER` (`${...}`, `@...@`, `#{...}`) / `ENCRYPTED`
      (`ENC(...)`) → never a finding (FR-005).
   b. `PATH_LIKE` → resolve and follow (Decision 5), report if the referenced
      key file is `UNPROTECTED` (FR-007).
   c. `LITERAL` that is credential-like (Decision 4) → report as a plaintext
      secret (FR-004).
   d. otherwise → not a finding.

- **Rationale**: Honors FR-006 as an unconditional MUST while gating the
  name-driven heuristics (FR-003/004/007) on the key name, matching the user's
  framing ("a property called password, pass, private…"). Cheap `-----BEGIN`
  pre-check keeps the unconditional branch O(1) for normal values.
- **Alternatives considered**: Gating inline key material on the name too —
  rejected as it could miss an embedded key under an unconventional key name,
  weakening the tool's primary guarantee.

## Decision 4 — Credential-likeness gate (length + entropy)

- **Decision**: A literal value is credential-like when **both** hold:
  - `len(value) >= MIN_SECRET_LENGTH` with `MIN_SECRET_LENGTH = 6`
  - Shannon entropy `H = -Σ p·log2(p)` over its characters
    `>= MIN_ENTROPY_BITS_PER_CHAR` with `MIN_ENTROPY_BITS_PER_CHAR = 2.5`

  Pure booleans (`true/false/yes/no/on/off`, case-insensitive) and pure
  integers/floats are rejected before the entropy check. Thresholds are module
  constants in `domain/properties.py` (not config surface).
- **Rationale**: Deterministic and dependency-free (stdlib `math` only), so
  acceptance tests have a fixed baseline (SC-001/SC-002). Worked examples:
  `hunter2` (len 7, H≈2.81) → flagged; `changeme` (len 8, H≈2.75) → flagged;
  `true` (len 4) → rejected on length; `8` → rejected (pure int); `localhost`
  (len 9, H≈2.73) → flagged on these bounds — acceptable since it sits under a
  secret-named key only when misconfigured, and recall is preferred per
  SC-001.
- **Alternatives considered**: Length-only (too many false positives on short
  config tokens); entropy-only (flags long low-entropy non-secrets, misses short
  random secrets). Combined gate chosen per the clarify decision.

## Decision 5 — Key-file reference resolution (FR-007 / FR-013)

- **Decision**: When a secret-named value is `PATH_LIKE`, build the path; if
  relative, resolve it against the **directory of the `.properties` file**
  (`candidate.canonical_path.parent`). Resolve to a canonical path; the reference
  is followed only when (a) the file exists and (b) the canonical path is within
  `scope.canonical_root_set` (equal to or under an authorized root). A missing or
  out-of-scope reference is skipped without a finding and without aborting.
  Assessment reuses `key_parsers.inspect_candidate_file`.
- **`files_scanned` accounting**: The service seeds a `set[Path]` with all
  candidate canonical paths. A followed reference increments `files_scanned` only
  if its canonical path is not already in that set, then is added to it — so a
  file both referenced and directly discovered, or referenced twice, counts once
  (FR-013).
- **`PATH_LIKE` heuristic**: a value is path-like when it contains a path
  separator or ends in a key-material extension (`.pem`, `.key`, `.ppk`, `id_*`),
  and is not a placeholder/encrypted form. A path-like value that cannot be
  followed (missing or out of scope) is **not** reported — it is a path, not a
  secret (FR-007); only `LITERAL` values are subject to the credential gate. (An
  earlier draft fell through to the literal rule for recall; that was dropped
  during implementation because it contradicted FR-007 and produced false
  positives on path strings.)
- **Rationale**: Matches common Java/Spring config-relative resource semantics
  (clarify decision); the scope check upholds "never read outside authorized
  scope" (Principle V, FR-007).
- **Alternatives considered**: CWD-relative resolution (depends on invocation
  dir) and following absolute paths only (misses relative refs) — both rejected
  per the clarify decision.

## Decision 6 — Per-property output contract (FR-008/009)

- **Decision**: Each offending property yields one `KeyFinding` with
  `property_key` set; `KeyFinding.output_line` returns `f"{file_path}#{property_key}"`.
  `reporting.emit_scan_result` prints `output_line` to stdout. Secret values are
  never stored on the finding nor printed; stderr remediation reuses the
  `EMBEDDED_CONFIG_SECRET` category.
- **Rationale**: Keeps the established "stdout = canonical paths" stream while
  making each finding independently greppable (clarify decision); guarantees
  SC-003 (zero secret-value emissions) by construction.
- **Alternatives considered**: One finding per file (loses which property);
  emitting values inline (violates the no-leak guarantee). Both rejected.

## Decision 7 — Parsing depth & encoding

- **Decision**: Implement the common Java `.properties` subset: leading-whitespace
  trim, `#`/`!` comment lines, blank-line skip, first unescaped `=`/`:`/whitespace
  as key/value separator, backslash line continuation, and escapes `\=`, `\:`,
  `\t`, `\n`, `\\`. Decode bytes as UTF-8, falling back to Latin-1 (never fails)
  so values remain assessable; an OSError on read is reported as unreadable via
  the existing path. Full `\uXXXX` unescaping is out of scope (values we assess
  are credential strings, paths, or PEM blocks — all ASCII-representable).
- **Rationale**: Covers real-world Spring/Java config while staying KISS; latin-1
  fallback guarantees the parser is total over readable bytes.
- **Alternatives considered**: Using `java.util.Properties` semantics in full
  (over-engineered) or a third-party properties library (new dependency,
  rejected per constitution dependency rule).

## Decision 8 — Default secret-name catalog

- **Decision**: Ship `password`, `passwd`, `pwd`, `pass`, `secret`, `private`,
  `key`, `token`, `credential`, `apikey`, `passphrase` as packaged
  `property_name_patterns`, matched case-insensitively as substrings so dotted
  keys (`spring.datasource.password`) match. Configurable via omit/empty/replace,
  reusing `_resolve_ignore_list`.
- **Rationale**: Covers the names called out by the user plus the most common
  credential conventions; substring matching handles namespaced keys (FR-003).
  `key` as a substring is broad but paired with the value gate (Decision 4) and
  path-following (Decision 5), which suppress benign `*.key`-named non-secrets.
- **Alternatives considered**: Exact-match names (misses dotted keys); glob-only
  (more config ceremony). Substring chosen per the spec assumption.

## Cross-cutting: tests, quality gates, packaging

- **Testing**: new unit suites for parsing, secret heuristics, and the inspector;
  extended loader and reporting unit tests; a new integration workflow test;
  updated `files_scanned` expectations in the existing default-scan integration
  test. Coverage gate ≥ 85% enforced by `pytest` addopts.
- **Quality gates**: `pytest`, `ruff check src/ tests/`,
  `ruff format --check src/ tests/`, `pyright src/`.
- **Packaging**: only the bundled example TOML changes; entry points and build
  process unchanged. Smoke `--print-example-config` after the resource edit.
