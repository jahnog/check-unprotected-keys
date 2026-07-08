# Internal Contract: Detection Extension Points

**Feature**: `specs/010-code-quality-audit` | **Date**: 2026-07-08

Maintainer-facing seams (not a runtime plugin API). Enforced by unit tests in
`tests/unit/test_detection_registries.py`. Shapes are defined in
[data-model.md](../data-model.md).

## Key-format recognizers — `adapters/key_parsers.KEY_RECOGNIZERS`

- Ordered tuple; **first `matches(blob)` wins**; later entries are not
  consulted. Registry order is the compatibility surface — new formats append
  unless they must shadow a broader prefix.
- A recognizer's `inspect` must return a `ProtectionAssessment` and must not
  raise for arbitrary bytes accepted by its `matches`.
- Adding a format = one new recognizer object + one registry entry; existing
  entries untouched (SC-003 is demonstrated by a dummy recognizer test that
  registers, scans, and unregisters).

## Usage categories — `domain/remediation.USAGE_CATEGORY_DEFINITIONS`

- Ordered tuple evaluated first-match; the `UNKNOWN` definition is last and
  matches everything (mandatory catch-all).
- Invariants (unit-tested): every `UsageCategory` enum member has exactly one
  definition; every definition carries a complete
  `RemediationRecommendation` (title, summary, rationale, next-step hint).
- Adding a category = new enum member + one definition entry; reporting and
  classification pick it up with no other edits (FR-005).

## Properties assessment rules — `adapters/properties_inspector.ASSESSMENT_RULES`

- Ordered tuple; each rule returns `RuleOutcome(finding, stop)`;
  the pipeline stops at the first outcome with `stop=True` or a finding.
- The shipped order replicates the historical pipeline exactly:
  `inline-key-material`, `value-signature`, `message-bundle-gate`,
  `value-kind-gate`, `placeholder-default`, `tier-gate`, `reference-follow`,
  `literal-credential`.
- Adding a detection layer = one rule inserted at an explicit position;
  existing rules are not edited (FR-006).
- Rules must never place a property *value* in a finding — key names only.
