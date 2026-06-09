# Specification Quality Checklist: Search Bases and Directory Hints (Broad Discovery)

**Purpose**: Validate specification completeness and quality before proceeding to detailed planning and implementation
**Created**: 2026-06-09
**Feature**: [spec.md](spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) leaked into the primary user-facing sections
- [x] Focused on user value (broader discovery with low maintenance) and operator control
- [x] Written so that a security operator or developer can understand the benefit and the controls without reading source
- [x] All mandatory sections completed (User Stories with independent tests, Requirements, Success Criteria, Edge Cases, Assumptions)

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous (FR-001 through FR-008, NFR-001 through NFR-006)
- [x] Success criteria are measurable (SC-001 through SC-008) and include concrete observable outcomes (files discovered at depth, no **/ required, pruning works, compat, start-folder, coverage, gates)
- [x] Success criteria are technology-agnostic where possible (they describe observable scanner behavior)
- [x] All acceptance scenarios are defined per user story
- [x] Edge cases are identified (overlapping bases, promotion inside ignored trees, start-folder + broad bases, legacy configs, provenance, noise, symlinks, permissions, etc.)
- [x] Scope is clearly bounded (what is in vs. future work such as .gitignore respect, content-only discovery, hard budgets)
- [x] Dependencies and assumptions are called out (relationship to 001 and 004, the role of existing filename_patterns + classification as the noise valve, operator responsibility for choosing bases)

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria tied back to the user stories
- [x] User scenarios cover the primary flows (broad bases, automatic promotion via hints, pruning, compat/migration, start-folder narrowing)
- [x] Feature meets the measurable outcomes defined in Success Criteria
- [x] The design is an evolution that reuses the existing candidate enumeration, classification, and reporting pipeline; only the "where do we look?" phase is extended
- [x] No implementation details leak into the specification itself (plan.md, research.md, tasks.md, and contracts/ contain the tactical and technical choices)

## Cross-Feature Consistency

- [x] Preserves the stdout-only-for-findings contract and stderr-only-for-summaries/guidance/malformed paths
- [x] Preserves the existing `--start-folder` contract (spec 004) — validation timing, narrowing semantics for the location side, filename patterns never change
- [x] Compatible with the original 001 intent ("starting from the root folder" is now achievable in a controlled way via bases) while keeping the operator-controlled, auditable character of the tool
- [x] The dead duplicate package cleanup (`src/find_unencrypted_keys/`) is noted as housekeeping performed as part of this feature

## Notes

- Items marked incomplete would require spec updates before planning or implementation.
- Initial validation performed at creation time (2026-06-09). All core checklist items pass.
- The specification directly addresses the user's request for an alternative design that delivers broader discovery without a large `**/foo` maintenance burden.
- Pruning is treated as a P1 enabler (not an afterthought) because broad bases are otherwise impractical.
- Backward compatibility via legacy key acceptance + auto-contribution of bare names to hints is explicitly required so that existing user configs do not regress on upgrade.
- The checklist will be re-run after research.md, data-model.md, and the contracts supplement are complete, and again before the implementation phase begins in earnest.