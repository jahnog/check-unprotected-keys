# Phase 1 Data Model: Precise `.properties` Secret Detection

All new types are pure-domain (in `domain/properties.py`) or small additions to
existing adapter/model types. No value is ever stored on a finding. Types are
frozen dataclasses / `StrEnum`, consistent with the existing codebase.

## New / changed domain types (`domain/properties.py`)

### `KeyNameTier` (new `StrEnum`)

The confidence tier of a property key, governing how much value evidence is
required (research Decision 2).

| Member | Meaning |
| --- | --- |
| `STRONG` | Unambiguous credential key (e.g. `*.password`, `db.pwd`, `apikey`), not qualifier-demoted. Base value gate applies. |
| `WEAK` | Broad/ambiguous token (`key`, `token`, `private`) alone, or a strong match demoted by a non-secret qualifier. Strict gate or a value signature required. |
| `NONE` | No secret token in the key. Only an unconditional value signature can flag it. |

### `PropertyValueKind` (existing `StrEnum`, extended semantics)

Unchanged members (`EMPTY`, `PLACEHOLDER`, `ENCRYPTED`, `PATH_LIKE`, `LITERAL`),
but `PLACEHOLDER` and `ENCRYPTED` recognition is widened (research Decision 7):

- `PLACEHOLDER` now also covers `{{…}}`, `$ENV{…}`, `$(…)`, `%(…)s`, defaulted
  `${VAR:-default}` / `${VAR:default}`, and reference schemes (`vault:`,
  `awskms:`, `sops:`, `secret:`, `secretref:`, `env:`).
- `ENCRYPTED` now also covers `{cipher}…` and brace-wrapped `{ENC(…)}`.

### `ValueSignature` (new `StrEnum`)

Identifies which high-confidence value signature matched (research Decision 3),
for the finding's origin/label only:
`AWS_ACCESS_KEY`, `GITHUB_TOKEN`, `GITLAB_TOKEN`, `SLACK_TOKEN`,
`GOOGLE_API_KEY`, `STRIPE_KEY`, `TWILIO_KEY`, `SENDGRID_KEY`, `NPM_TOKEN`,
`OPENAI_KEY`, `JWT`, `EMBEDDED_CREDENTIAL_URL`, `HIGH_ENTROPY_BLOB`.

### Pure functions (new / changed)

| Function | Signature | Role |
| --- | --- | --- |
| `tokenize_key` | `(key: str) -> tuple[str, ...]` | Split on `. _ - /` whitespace + camelCase; lowercase. |
| `classify_key_tier` | `(key, name_patterns) -> KeyNameTier` | Token-aware match + qualifier demotion → tier (replaces `matches_secret_name`). |
| `match_value_signature` | `(value: str) -> ValueSignature \| None` | Curated provider/JWT/URL/blob signatures. |
| `is_sample_placeholder` | `(value: str, extra_ignore: tuple[str,...]) -> bool` | Sample/mask vocabulary (Decision 5) + optional `property_value_ignore`. |
| `is_non_secret_shape` | `(value: str, tier: KeyNameTier) -> bool` | Tier-aware structured-shape exclusion (Decision 6). |
| `classify_value` | `(value) -> PropertyValueKind` | Existing; widened PLACEHOLDER/ENCRYPTED recognition. |
| `placeholder_default` | `(value: str) -> str \| None` | Extract the default segment of a defaulted placeholder (FR-009). |
| `is_credential_like` | `(value, tier: KeyNameTier) -> bool` | Tier-aware gate: STRONG base (len≥6, H≥2.5) / WEAK strict (len≥12, H≥3.0). |

`matches_secret_name` is removed (callers move to `classify_key_tier`); the old
substring helper is not retained (DRY).

### Constants (module-level, not config — research Decision 8)

`MIN_SECRET_LENGTH = 6`, `MIN_ENTROPY_BITS_PER_CHAR = 2.5` (existing, STRONG
base), `MIN_WEAK_LENGTH = 12`, `MIN_WEAK_ENTROPY = 3.0`, `BLOB_MIN_LENGTH = 32`,
`BLOB_MIN_ENTROPY = 4.0`; the substring-safe and token-exact catalogs, the
qualifier denylist, the sample/mask vocabulary, the algorithm/keystore enum set,
and the compiled signature patterns. All tuned against the corpus (Decision 9).

## Adapter types (`adapters/properties_inspector.py`)

### `PropertyFindingOrigin` (existing `StrEnum`, +1 member)

Adds `VALUE_SIGNATURE = "value-signature"` to the existing `PLAINTEXT_SECRET`,
`INLINE_KEY_MATERIAL`, `REFERENCED_KEY_FILE`.

### `PropertyFinding` (existing, unchanged fields)

`property_key`, `classification`, `origin`. Still carries **no value**. The new
decision order (research Decision 7) populates it; `_assess_entry` is rewritten,
`inspect_properties_file` / `_follow_reference` / `_decode` / `_within_scope`
are unchanged in shape. `inspect_properties_file` gains a `value_ignore`
parameter threaded from config.

## Key-material adapter (`adapters/key_parsers.py`)

`_inspect_key_blob` gains a `-----BEGIN CERTIFICATE-----` branch returning
`PUBLIC_ONLY` (DRY with existing public-key handling), so inline certificates are
non-findings (FR-010). No other change.

## Configuration types

- `ScanConfigSection` (`config/models.py`) and `SearchConfiguration`
  (`domain/models.py`): add `property_value_ignore: tuple[str, ...] = ()`
  (optional, omit/empty/replace), resolved in `config/loader.py` via the existing
  `_resolve_ignore_list` helper against a packaged default (empty by default).
- `property_name_patterns` is unchanged in type; only its matcher semantics change.

## Validation / corpus types (`tests/fixtures/properties_corpus/corpus.py`)

A labeled case is a tuple `(key: str, value: str, expect_flag: bool,
rationale: str)`. Two collections: `MUST_FLAG` and `MUST_NOT_FLAG`. The accuracy
test computes recall over `MUST_FLAG` and false-positive rate over
`MUST_NOT_FLAG`; assertions compare booleans only (no value is emitted).

## Relationships (per-entry flow)

```
PropertyEntry
  ├─ inline key material? ──► PropertyFinding(INLINE_KEY_MATERIAL)   [unconditional]
  ├─ match_value_signature ─► PropertyFinding(VALUE_SIGNATURE)       [unconditional]
  ├─ classify_value
  │     EMPTY/ENCRYPTED ─────► (stop)
  │     PLACEHOLDER ─────────► placeholder_default? → reassess default : (stop)
  ├─ classify_key_tier
  │     NONE ────────────────► (stop)
  │     PATH_LIKE ───────────► _follow_reference → PropertyFinding(REFERENCED_KEY_FILE)
  │     LITERAL
  │        is_sample_placeholder ─► (stop)
  │        is_non_secret_shape ───► (stop)
  │        is_credential_like(tier) ─► PropertyFinding(PLAINTEXT_SECRET) : (stop)
```

Maps to the spec's FR-001…FR-010 and the contract decision order.
