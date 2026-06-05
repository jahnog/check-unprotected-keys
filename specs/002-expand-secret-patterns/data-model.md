# Data Model: Expand Secret Patterns

## BaselinePatternCatalog

**Purpose**: Defines the shipped folder and filename entries that make up the
default scan scope before any operator customization.

**Fields**:

- `source_file`: path to the shipped example configuration that documents the
  baseline catalog
- `folder_entries`: ordered list of `PatternEntry` values for default folder
  scope
- `filename_entries`: ordered list of `PatternEntry` values for default
  filename scope
- `excluded_families`: ordered list of `ExcludedPatternFamily` values that are
  deliberately left out of the default catalog

**Validation Rules**:

- `folder_entries` MUST be non-empty.
- `filename_entries` MUST be non-empty.
- Entries MUST stay within the supported detection scope for the current
  product.
- The catalog MUST document at least one operator-visible rationale for each
  category of included and excluded patterns.

## PatternEntry

**Purpose**: Represents one shipped folder or filename pattern and the category
that justifies its presence.

**Fields**:

- `pattern_text`: literal glob or path pattern stored in configuration
- `pattern_kind`: `folder` or `filename`
- `category`: logical grouping such as `user-home-ssh`, `repo-key-root`,
  `config-subtree`, `deployment-root`, `vpn-text-container`, or
  `embedded-key-text-container`
- `supports_expanduser`: whether `~` expansion is expected for this entry
- `notes`: short operator-facing explanation of why the entry is included

**Validation Rules**:

- `pattern_text` MUST be non-empty and trimmed.
- `supports_expanduser` may be true only for folder entries.
- `category` MUST map to a documented rationale in the catalog.
- The same literal `pattern_text` may appear at most once within the same
  `pattern_kind` list in the shipped baseline.

## ExcludedPatternFamily

**Purpose**: Documents a family of patterns intentionally omitted from the
default catalog to keep scope bounded.

**Fields**:

- `family_name`: short name such as `generic-token-globs`, `public-only-files`,
  `unsupported-keystores`, or `broad-system-roots`
- `representative_patterns`: representative examples for the excluded family
- `reason`: operator-facing explanation of why the family is excluded

**Validation Rules**:

- `representative_patterns` MUST contain at least one example.
- `reason` MUST describe either unsupported detection scope, false-positive
  risk, or excessive traversal/noise.

## SearchConfiguration

**Purpose**: Captures the operator-visible configuration actually loaded at
runtime after the shipped baseline is copied or edited.

**Fields**:

- `config_file_path`: canonical path to `.check-unprotected-keys.toml`
- `execution_root`: canonical path used as the default scan root
- `folder_patterns`: ordered list of effective folder patterns
- `filename_patterns`: ordered list of effective filename patterns

**Validation Rules**:

- `folder_patterns` MUST contain at least one entry.
- `filename_patterns` MUST contain at least one entry.
- Relative folder patterns are resolved from `execution_root`.
- `~`-prefixed folder patterns are expanded against the active user home.

## EffectiveScope

**Purpose**: Represents the root directories and filename rules actually used
for a scan after applying configuration and optional start-folder narrowing.

**Fields**:

- `root_directories`: canonical folder roots selected by the catalog and config
- `filename_patterns`: unchanged filename patterns from configuration
- `canonical_root_set`: deduplicated set of canonical roots

**Validation Rules**:

- Each root directory MUST be canonical and absolute.
- Overlapping folder patterns MUST collapse to one canonical root set.
- A start-folder override MAY narrow roots but MUST NOT alter
  `filename_patterns`.

## CatalogValidationScenario

**Purpose**: Describes a fixture-backed validation slice used to prove the
expanded baseline behaves correctly.

**Fields**:

- `scenario_name`: descriptive name such as `default-expanded-scope`,
  `start-folder-narrowing`, `noise-boundary`, or `overlap-dedup`
- `fixture_roots`: directories used to represent one or more pattern categories
- `expected_finding_paths`: files that must be reported
- `expected_clean_paths`: in-scope files that must not be reported
- `expected_summary_counts`: malformed and unreadable counts expected for the
  scenario

**Validation Rules**:

- `expected_finding_paths` MUST contain only files supported by the current
  classification engine.
- `expected_clean_paths` SHOULD cover public-only, protected, unsupported, or
  intentionally excluded examples.
- Each scenario MUST be runnable both as a default-scope validation and, when
  relevant, under a narrowed start-folder run.

## Relationships

- One `BaselinePatternCatalog` is documented through many `PatternEntry` and
  `ExcludedPatternFamily` values.
- One operator-edited `SearchConfiguration` is derived from the shipped
  `BaselinePatternCatalog`.
- One `SearchConfiguration` produces one `EffectiveScope` per scan invocation.
- One `EffectiveScope` is validated by one or more `CatalogValidationScenario`
  slices.# Data Model: Expand Secret Patterns

## BaselinePatternCatalog

**Purpose**: Defines the shipped default folder and filename catalog used as the
starting configuration for operators.

**Fields**:

- `source_path`: path to the shipped `.check-unprotected-keys.toml.example`
- `folder_categories`: ordered list of `PatternCategory` entries for folder
  roots
- `filename_categories`: ordered list of `PatternCategory` entries for filename
  matching
- `excluded_default_categories`: ordered list of intentionally unsupported
  default-scope categories

**Validation Rules**:

- Folder and filename category names MUST be unique within the catalog.
- Default-enabled patterns MUST be non-empty strings and retain stable order.
- Folder patterns MAY be relative to the execution root or `~`-prefixed for
  explicit user-home roots.
- Default categories MUST stay bounded to supported key-material storage
  conventions and MUST exclude whole-home, whole-system, and generic token
  hunting patterns.

## PatternCategory

**Purpose**: Groups related baseline patterns by operational intent.

**Fields**:

- `name`: human-readable category label such as `ssh-home`, `repo-pki`, or
  `embedded-key-text`
- `scope_kind`: `folder` or `filename`
- `patterns`: ordered list of glob or path patterns in the category
- `purpose`: operator-facing explanation of why the category exists
- `default_enabled`: whether the category is shipped enabled by default

**Validation Rules**:

- `patterns` MUST be deduplicated within the category.
- `purpose` MUST describe supported key-material coverage rather than generic
  secret detection.
- Disabled categories may appear in documentation, but only enabled categories
  belong in the shipped baseline example.

## SearchConfiguration

**Purpose**: Captures the operator-editable runtime configuration actually loaded
by the scanner.

**Fields**:

- `config_file_path`: canonical path to `.check-unprotected-keys.toml`
- `execution_root`: canonical path used as the default scan root
- `folder_patterns`: ordered list of active folder patterns
- `filename_patterns`: ordered list of active filename patterns

**Validation Rules**:

- Both pattern lists MUST contain at least one non-empty entry.
- Operator edits MAY remove or replace any shipped default category.
- The runtime configuration MAY diverge from the shipped baseline without code
  changes.

## EffectiveScope

**Purpose**: Represents the canonical folder roots and filename rules actually
applied for one scan after configuration loading and optional narrowing.

**Fields**:

- `root_directories`: resolved folder roots after `~` expansion, relative-path
  resolution, deduplication, and optional start-folder narrowing
- `filename_patterns`: unchanged filename pattern list from the active
  configuration
- `canonical_root_set`: deduplicated set of canonical root directories

**Validation Rules**:

- Start-folder narrowing MUST only affect `root_directories`.
- Duplicate folder patterns collapse to one canonical root.
- An empty `root_directories` result is a valid no-op scan when the supplied
  start folder narrows the active scope to nothing.

## CandidateFile

**Purpose**: Tracks an individual file selected for inspection under the broader
default catalog.

**Fields**:

- `canonical_path`: canonical absolute path to the file
- `display_path`: value emitted if the file becomes a finding
- `matched_folder_pattern`: resolved root that reached the file
- `matched_filename_pattern`: filename rule that admitted the file
- `category_hint`: optional logical category label derived from the baseline
  catalog for validation and documentation

**Validation Rules**:

- Each `canonical_path` appears at most once per scan.
- `display_path` MUST equal the canonical absolute path used for reporting.
- `matched_filename_pattern` MUST come from the unchanged active configuration,
  not from the start-folder override.

## Relationships

- One `BaselinePatternCatalog` defines the shipped default example and its
  documented categories.
- One operator `SearchConfiguration` may start from the baseline catalog and
  then diverge through local edits.
- One `SearchConfiguration` produces one `EffectiveScope` per scan.
- One `EffectiveScope` yields zero or more `CandidateFile` records that feed the
  existing classification and reporting pipeline.