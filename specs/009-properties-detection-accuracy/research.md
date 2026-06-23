# Phase 0 Research: Precise `.properties` Secret Detection

This feature refines the 008 detection decision logic. The spec fixed the *shape*
of the solution (token-aware matching, confidence tiers, an unconditional
value-signature layer, conservative value-shape exclusions, expanded
externalization recognition, a labeled corpus) and deferred the concrete
catalogs, thresholds, and patterns to planning. The decisions below pin those
down, each chosen so that **recall on plausible secrets is preserved while
precision rises sharply**. Every value-based exclusion is backstopped by the
unconditional value-signature layer (Decision 3), so a genuine secret wearing a
benign shape is still caught if it matches any known signature.

All decisions are deterministic and dependency-free (stdlib `re`/`math` plus the
existing `cryptography` reuse), so the corpus (Decision 9) has a fixed baseline.

## Decision 1 — Token-aware key matching (FR-001)

- **Decision**: Replace the substring `matches_secret_name` with token-aware
  matching. Tokenize the key by splitting on `.`, `_`, `-`, `/`, whitespace, and
  camelCase boundaries (insert a split between a lowercase/digit and an uppercase
  letter, and between an acronym run and a following word — e.g. `dbPassword` →
  `db`,`Password`; `APIKey` → `API`,`Key`), then lowercase each token. Match the
  secret catalog in two classes:
  - **Substring-safe patterns** (long, low collision): matched as a
    case-insensitive substring of any single token. Catalog: `password`,
    `passwd`, `passphrase`, `credential`, `credentials`, `secret`, `apikey`,
    `privatekey`, `secretkey`, `accesskey`, `clientsecret`. These rarely occur
    inside unrelated words, so substring-within-token keeps run-together names
    (`dbpassword`, `mypassphrase`) matchable without the old false matches.
  - **Token-exact patterns** (short, high collision): matched only when they
    equal a whole token. Catalog: `pass`, `pwd`, `key`, `token`, `private`,
    `secrets`, `keys`, `tokens`, `passwords`.
- **Rationale**: The old substring match flagged `compass`/`bypass` (`pass`),
  `monkey`/`keyboard` (`key`), `tokenizer` (`token`), `secret.rotation` was fine
  but `secretariat`-style words were not. Token-exact on the short patterns kills
  the entire container-word false-positive class; substring-within-token on the
  long patterns preserves recall on glued names. This is the single biggest
  precision win.
- **Alternatives considered**: Pure token-equality for all patterns (rejected:
  misses `dbpassword`, `myapikey` — false negatives). Keeping substring but adding
  a container-word denylist (rejected: fragile, unbounded, must enumerate every
  English word containing `pass`/`key`).

## Decision 2 — Key-name strength tiers and qualifier demotion (FR-002)

- **Decision**: Introduce `KeyNameTier = STRONG | WEAK | NONE`.
  - **STRONG**: the key matched a clearly-credential pattern — any
    substring-safe pattern except bare `key`-family, plus token-exact `pass` /
    `pwd` — AND the matched secret token is **not** immediately followed by a
    qualifier from the denylist.
  - **WEAK**: the key matched only a broad/ambiguous token (`key`, `token`,
    `private`) used alone, OR a strong match that was demoted because the secret
    token is immediately qualified by a non-secret descriptor.
  - **NONE**: no secret token matched.
  - **Qualifier denylist** (the token immediately after the matched secret token):
    `alias`, `id`, `name`, `type`, `kind`, `algorithm`, `alg`, `store`,
    `storetype`, `provider`, `header`, `prefix`, `suffix`, `enabled`, `disabled`,
    `required`, `optional`, `length`, `len`, `size`, `count`, `max`, `min`,
    `ttl`, `timeout`, `interval`, `expiry`, `expiration`, `rotation`, `policy`,
    `format`, `encoding`, `charset`, `class`, `classname`, `strategy`,
    `location`, `path`, `dir`, `directory`, `pattern`, `regex`, `serializer`,
    `deserializer`, `resolver`, `url`, `uri`, `endpoint`, `host`, `port`,
    `version`, `mode`, `label`, `field`, `column`, `param`, `attribute`,
    `default`, `example`, `placeholder`, `count`, `index`, `order`, `public`.
- **Rationale**: Tiering is the mechanism that lets US1 (no FP on benign config)
  and US2 (no FN on real secrets) coexist. Demotion captures the large class of
  metadata-about-a-secret keys (`signing.key.alias`, `secret.rotation.days`,
  `token.expiry.seconds`, `password.min.length`) without dropping them entirely:
  a demoted key stays WEAK, so a real high-entropy secret placed there is still
  caught by the strict gate or a value signature.
- **Alternatives considered**: Binary secret/not-secret (rejected: forces either
  the FP flood or FN risk). Dropping demoted keys entirely (rejected: a genuine
  random secret under `signing.key.alias` would be missed — violates the FN
  priority).

## Decision 3 — Unconditional value-signature layer (FR-003)

- **Decision**: Before the name gate, test every value against a curated
  high-confidence signature catalog; a match is a finding regardless of key name
  (origin `VALUE_SIGNATURE`). Catalog (all anchored, length-bounded for near-zero
  FP):
  - **Provider/service tokens**: AWS access key id
    `(?:AKIA|ASIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|A3T[A-Z0-9])[A-Z0-9]{16}`;
    GitHub `gh[pousr]_[A-Za-z0-9]{36,}` and `github_pat_[0-9A-Za-z_]{82}`;
    GitLab `glpat-[0-9A-Za-z_-]{20}`; Slack `xox[baprs]-[0-9A-Za-z-]{10,}`;
    Google API key `AIza[0-9A-Za-z_-]{35}`; Stripe `[sr]k_(?:live|test)_[0-9A-Za-z]{16,}`;
    Twilio `SK[0-9a-fA-F]{32}`; SendGrid `SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}`;
    npm `npm_[A-Za-z0-9]{36}`; OpenAI `sk-(?:proj-)?[A-Za-z0-9_-]{20,}`.
  - **JWT**: `eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+`.
  - **Embedded-credential URL/connection string**:
    `[A-Za-z][A-Za-z0-9+.-]*://[^/\s:@]+:(?P<pw>[^/\s:@]+)@` where the captured
    `pw` group contains none of `$ { }` and is non-empty (so `jdbc://${u}:${p}@`
    and `redis://host` do **not** match, but `jdbc:mysql://root:S3cr3t@db` does).
  - **Generic high-entropy blob**: a single base64/base64url/hex run of length
    ≥ 32 with Shannon entropy ≥ 4.0 bits/char and ≥ 3 character classes — catches
    random keys/secrets while excluding dotted identifiers, words, and versions.
  - PEM/OpenSSH/PuTTY **private** key material is already covered by the inline
    key-material branch (Decision 7) and is not duplicated here.
- **Rationale**: This is what makes "zero false negatives" achievable — it catches
  secrets hidden under benign key names (e.g. `datasource.url`,
  `notification.webhook`) that the name gate would miss, and it is the
  high-confidence anchor that lets the tiered value exclusions be aggressive
  without risking recall. Known formats give a clean yes/no, so they add almost
  no false positives.
- **Alternatives considered**: A large third-party signature ruleset (e.g. a
  full detect-secrets/gitleaks catalog) — rejected as a new dependency and FP
  surface; a curated, well-known subset covers the common providers with no
  dependency. Treating any 32+ char base64 as a secret regardless of entropy —
  rejected (flags long identifiers/hashes); the entropy+class floor fixes that.

## Decision 4 — Tiered credential gate (FR-004 / FR-005)

- **Decision**: After name/shape filtering, apply a tier-specific gate to a
  `LITERAL` value:
  - **STRONG base gate** (unchanged floor, preserves recall on human passwords):
    `len >= MIN_SECRET_LENGTH (6)` AND Shannon entropy `>= MIN_ENTROPY (2.5)`,
    rejecting pure booleans/numbers. Catches `hunter2` (H≈2.81), `Summer2024`
    (H≈3.1), `changeit`-style real weak passwords.
  - **WEAK strict gate** (requires random-secret-like evidence):
    `len >= MIN_WEAK_LENGTH (12)` AND entropy `>= MIN_WEAK_ENTROPY (3.0)`, OR a
    value signature (Decision 3). All thresholds are module constants, tuned
    against the corpus (Decision 9).
- **Rationale**: Under a strong, unambiguous credential key, even a weak password
  must be reported (FN priority), so the base gate stays loose. Under a broad
  token like `routing.key`, a value must look like real secret material to fire;
  ordinary short/structured config tokens fall below the strict gate. Worked
  examples: `api.key=A1b2C3d4E5f6G7h8` (WEAK, len 16, H≈3.9) → flagged;
  `routing.key=order.created.event` (WEAK) → excluded as a dotted identifier
  (Decision 6) before the gate; `cache.key.prefix=user:` (WEAK, len 5) → below
  strict length → not flagged.
- **Alternatives considered**: Raising the single global threshold (rejected:
  loses `hunter2`/`Summer2024` under strong keys — false negatives). Entropy-only
  for weak keys (rejected: dotted identifiers can score high entropy — handled by
  shape exclusion instead).

## Decision 5 — Sample / placeholder / mask vocabulary (FR-006)

- **Decision**: Exclude (all tiers) literal values that are unambiguous
  documentation defaults or masks — values that are essentially never a live
  secret:
  - Exact, case-insensitive: `changeme`, `change-me`, `change_me`, `changeit`...
    NO — keep `changeit` flaggable (real Java keystore default password).
    Final exact set: `changeme`, `change-me`, `change_me`, `tochange`,
    `replaceme`, `your_password_here`, `yourpasswordhere`, `your-password`,
    `your_password`, `your_secret`, `your-secret`, `yoursecret`, `mysecret`...
    NO — `mysecret` is a plausible real password; exclude only the templated
    `your*` forms. Final: `changeme`/`change-me`/`change_me`, `replaceme`,
    `your_password_here`, `yourpasswordhere`, `your-password`, `your_password`,
    `your-secret`, `your_secret`, `example`, `sample`, `dummy`, `placeholder`,
    `tbd`, `todo`, `fixme`, `redacted`, `none`, `null`, `nil`, `na`, `n/a`,
    `notset`, `not-set`, `unset`, `undefined`, `xxxx`.
  - Patterns: `^[xX]{4,}$`, `^\*{4,}$`, `^•{3,}$`, `^<[^>]+>$` (angle template),
    `^\[[^\]]+\]$` (square template), `^\.{3,}$`.
- **Rationale**: These tokens are documentation noise; flagging them is pure
  false positive. The list is deliberately conservative — plausibly-real weak
  passwords (`changeit`, `password123`, `admin`, `secret`, `mysecret`) are **not**
  excluded, honoring the FN priority. A real credential is never literally
  `changeme` or `<password>`.
- **Alternatives considered**: A large weak-password dictionary (rejected: many
  weak-but-real passwords are exactly what we must flag — excluding them creates
  false negatives).

## Decision 6 — Structured non-secret value shapes (FR-007 / FR-010)

- **Decision**: Recognize value shapes that are not credentials. Each is a
  deterministic predicate. **Always excluded** (every tier — implausible as a live
  secret): dotted identifier / class / package
  (`^[A-Za-z_$][\w$]*(\.[A-Za-z_$][\w$]*)+$`); enumerated algorithm / keystore /
  cipher-transformation constant (curated set incl. `RS256`, `HS512`, `ES256`,
  `PS256`, `PBKDF2`, `HmacSHA256`, `AES`, `AES256`, `RSA`, `EC`, `Ed25519`,
  `PKCS1`, `PKCS8`, `PKCS12`, `JKS`, `JCEKS`, `BCFKS`, `PEM`, `DER`, `BCRYPT`,
  `SCRYPT`, `ARGON2`, `NONE`, `PLAIN`, plus cipher transforms
  `^[A-Za-z0-9]+(/[A-Za-z0-9]+){1,2}$`); MIME type (`^[a-z]+/[a-z0-9.+-]+$`);
  HTTP header name (`^[A-Z][A-Za-z]+(-[A-Z][A-Za-z]+)+$`); semantic version
  (`^v?\d+\.\d+(\.\d+)?([-+][0-9A-Za-z.-]+)?$`); bare hostname / IP / URL with
  **no** embedded credential (URL whose authority lacks `user:pass@`, or a bare
  host like `localhost` / `db.internal` / `10.0.0.5`); public-key / certificate
  markers in the value (`-----BEGIN PUBLIC KEY-----`, `-----BEGIN CERTIFICATE-----`,
  `ssh-`/`ecdsa-`/`sk-` OpenSSH public prefixes). **Excluded under WEAK keys only**
  (could be a glued secret under a strong key, so not excluded there): generic
  kebab/snake identifier with all-word segments
  (`^[A-Za-z][A-Za-z0-9]*([._-][A-Za-z0-9]+)+$`) and short date/version-ish
  tokens.
- **Rationale**: This directly removes the documented `localhost` false positive
  and the class/enum/URL clusters. The split — aggressive shape exclusion under
  WEAK keys, only the implausible-as-secret subset under STRONG keys — preserves
  recall: a diceware passphrase `correct-horse-battery-staple` under
  `account.passphrase` (STRONG) is **not** shape-excluded and is caught by the
  base gate, while the same string under `routing.key` (WEAK) is treated as a
  benign identifier.
- **Certificates**: rather than a value-only rule, also teach `key_parsers` to
  classify `-----BEGIN CERTIFICATE-----` blocks as `PUBLIC_ONLY` (DRY with the
  existing public-key handling), so inline certs are non-findings at the
  key-material branch.
- **Alternatives considered**: Excluding all dotted/kebab values in every tier
  (rejected: risks FN on glued/hyphenated secrets under strong keys). No shape
  awareness, entropy-only (rejected: the documented status quo that produces the
  FP flood).

## Decision 7 — Decision order and defaulted placeholders (FR-008 / FR-009)

- **Decision**: New per-entry order in `_assess_entry`:
  1. **Inline key material** (unconditional): `-----BEGIN` present → parse via
     `key_parsers`; `UNPROTECTED` → finding (`INLINE_KEY_MATERIAL`);
     `PUBLIC_ONLY`/`PROTECTED`/`MALFORMED` → not a finding (stop).
  2. **Value signature** (unconditional, Decision 3) → finding (`VALUE_SIGNATURE`).
  3. **Classify value**: `EMPTY` → stop. `ENCRYPTED` → stop. `PLACEHOLDER` → if a
     defaulted placeholder (`${VAR:-default}` / `${VAR:default}`) with a non-empty
     default, recurse into steps 2/5/6/7 on the **default segment** using the
     key's tier (FR-009); otherwise stop.
  4. **Key tier** (Decision 2): `NONE` → stop (signatures already handled).
  5. `PATH_LIKE` → follow reference (unchanged 008 behavior).
  6. `LITERAL` → sample/mask (Decision 5) → stop; structured shape (Decision 6,
     tier-aware) → stop.
  7. **Tiered gate** (Decision 4): pass → finding (`PLAINTEXT_SECRET`); else stop.
- **Expanded externalization** (FR-008): `PLACEHOLDER` adds `{{...}}`, `$ENV{...}`,
  `$(...)`, `%(...)s`, and reference-scheme prefixes (case-insensitive)
  `vault:`, `vault://`, `awskms:`, `aws-kms:`, `sops:`, `secret:`, `secretref:`,
  `env:`. `ENCRYPTED` adds `{cipher}...` (Spring Cloud Config) and brace-wrapped
  `{ENC(...)}` alongside the existing `ENC(...)`.
- **Rationale**: Putting signatures before the name gate is the recall anchor;
  putting sample/shape exclusions before the gate is the precision win; assessing
  the placeholder default closes the `${VAR:-hunter2}` hardcoded-fallback FN.
- **Alternatives considered**: Assessing only the variable name of a placeholder
  (rejected: misses hardcoded defaults). Treating every `{...}` as encrypted
  (rejected: over-broad, would hide real values).

## Decision 8 — Configuration surface (FR-013)

- **Decision**: Keep the single existing `property_name_patterns` config key
  (omit/empty/replace), now interpreted by the token-aware matcher; user-supplied
  patterns are treated as STRONG by default (the operator chose them explicitly),
  still subject to qualifier demotion, signatures, exclusions, and the gate. The
  tier lists, qualifier denylist, sample vocabulary, signature catalog, shape
  predicates, and numeric thresholds ship as **internal module constants**
  (KISS — not new config surface), mirroring the existing `MIN_SECRET_LENGTH` /
  `MIN_ENTROPY_BITS_PER_CHAR` precedent. Add one optional, documented config key
  `property_value_ignore` (omit/empty/replace) — extra exact value tokens an
  organization wants treated as benign — for site-specific FP suppression without
  code changes.
- **Rationale**: Satisfies FR-013 (name catalog + an exclusion override remain
  configurable; defaults work with zero config) while avoiding a sprawl of
  knobs. Numeric thresholds stay constants so corpus tuning has one source of
  truth.
- **Alternatives considered**: Exposing every list/threshold as config (rejected:
  KISS violation, huge surface, undermines the curated near-zero-FP guarantee).

## Decision 9 — Labeled accuracy corpus and enforced thresholds (FR-014)

- **Decision**: Add `tests/fixtures/properties_corpus/corpus.py` defining a list
  of labeled cases — `(key, value, expect_flag, rationale)` — partitioned into
  **MUST-FLAG** (true secrets across: strong/weak/none key names; literal
  passwords; every signature family; embedded-credential URLs; inline PEM;
  referenced key files; hardcoded placeholder defaults) and **MUST-NOT-FLAG**
  (benign secret-named config across every FP class above: container words,
  qualified keys, identifiers, enums, hosts/URLs, durations, MIME, headers,
  versions, placeholders, encrypted wrappers, sample/mask tokens, public keys,
  certificates). A parametrized test `tests/unit/test_properties_accuracy.py`
  runs each case through the inspector (in a tmp scope for reference/inline
  cases) and asserts: **recall == 100%** on MUST-FLAG and **false-positive rate
  ≤ target (2%, 0 on the curated core)** on MUST-NOT-FLAG, failing the build on
  breach. The test asserts only booleans, never printing values (SC-004).
- **Rationale**: Turns the "near-zero FP / zero FN" claim into an enforced,
  regression-proof gate (SC-001/002/006). The labeled list doubles as the tuning
  oracle for the Decision 4 thresholds.
- **Alternatives considered**: Ad-hoc fixtures without metrics (rejected: the
  accuracy claim would be unverifiable and would silently regress).

## Cross-cutting: tests, quality gates, packaging

- **Testing**: new unit suites for tokenization/tiering, value signatures, shape
  and sample exclusions, expanded placeholder/encrypted recognition, defaulted
  default assessment, and the tiered gate; the labeled accuracy test; an
  integration test (a benign secret-named `.properties` yields zero findings; a
  `datasource.url` with embedded credentials and a `db.password` are reported).
  Existing `test_property_secrets.py` / `test_properties_inspector.py` cases that
  encode the *old* loose behavior (e.g. `is_credential_like("localhost") is True`,
  substring name matches) are updated — and each such change is triaged as
  "test encoded the defect being fixed" per NFR-002/Constitution III before
  editing. Coverage gate ≥ 85% (pytest addopts).
- **Quality gates**: `pytest`, `ruff check src/ tests/`,
  `ruff format --check src/ tests/`, `pyright src/`.
- **Packaging**: bundled example TOML comment updated (token-aware semantics,
  tiering, signatures, the optional `property_value_ignore` key); no new runtime
  dependency; entry points unchanged. Smoke `--print-example-config` after the
  resource edit.
