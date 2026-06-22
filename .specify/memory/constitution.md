<!--
Sync Impact Report
Version change: 1.0.0 -> 1.1.0
Modified principles:
- I. Pythonic SOLID Architecture -> I. SOLID Architecture (explicit SOLID tenets)
- II. Clean Code, Types, and Intentional Patterns -> II. Clean Code, DRY, and KISS
- III. Tests and Coverage Are Release Gates -> III. Tests, Coverage, and Post-Implementation Verification
Added sections:
- None (existing principles expanded; no new top-level sections)
Removed sections:
- None
Templates requiring updates:
- ✅ .specify/templates/plan-template.md
- ✅ .specify/templates/spec-template.md
- ✅ .specify/templates/tasks-template.md
Related guidance reviewed:
- ✅ .github/copilot-instructions.md (Spec Kit context pointer only; no principle enumeration — no change needed)
- ✅ CLAUDE.md (Spec Kit context pointer only — no change needed)
- ✅ README.md (no principle enumeration — no change needed)
Follow-up TODOs:
- None
-->
# Find Unencrypted Keys Constitution

## Core Principles

### I. SOLID Architecture
Production code MUST be organized into explicit layers for CLI entrypoints,
application services, domain logic, and infrastructure adapters, and MUST obey
the five SOLID tenets:

- **Single Responsibility**: each class, function, and module has one reason to
	change and one clear responsibility.
- **Open/Closed**: behavior is extended through new abstractions rather than by
	editing stable, tested units.
- **Liskov Substitution**: implementations are substitutable for the
	abstractions they fulfill without surprising callers.
- **Interface Segregation**: seams expose narrow, purpose-built interfaces, not
	broad catch-all contracts.
- **Dependency Inversion**: high-level domain logic depends on abstractions at
	I/O seams, never directly on concrete platform or filesystem details, and
	hidden global state is avoided.

Design patterns MAY be introduced only when they reduce coupling, simplify
extension points, or protect domain logic from platform details; every
non-trivial pattern choice MUST be named and justified in the implementation
plan.

Rationale: A standalone executable stays maintainable only when business logic
remains isolated from command-line plumbing and operating-system concerns, and
SOLID seams are what keep that isolation enforceable over time.

### II. Clean Code, DRY, and KISS
All generated and hand-written production code MUST comply with Clean Code, DRY,
and KISS as non-negotiable principles:

- **Clean Code**: prefer small, cohesive units; descriptive, intention-revealing
	names; explicit types on public interfaces; and side-effect-aware functions.
	Public modules, service boundaries, and data transfer objects MUST be
	type-annotated. A pattern is compliant only when it makes control flow easier
	to understand for the next maintainer.
- **DRY (Don't Repeat Yourself)**: each piece of knowledge or logic has a single
	authoritative source. Duplication MUST be removed at the right abstraction
	level rather than copy-pasted — and rather than hidden behind premature or
	speculative indirection.
- **KISS (Keep It Simple)**: the simplest design that satisfies the requirement
	wins. Accidental complexity, speculative generality, and cleverness that
	obscures intent MUST be rejected; complexity that remains MUST be justified by
	a concrete, present need.

Rationale: Clean, non-duplicated, simple code reduces accidental complexity and
makes security-sensitive scanning behavior safer to evolve and review.

### III. Tests, Coverage, and Post-Implementation Verification
Every feature and bug fix MUST ship with unit tests that validate the new or
changed behavior and MUST produce a coverage report on every validation path.
Integration or contract tests MUST be added when a change crosses process
boundaries, packaging boundaries, filesystem boundaries, or other infrastructure
seams. Configured minimum coverage gates MUST fail the build when unmet.

After implementing or changing behavior, the full unit-test suite AND the
coverage report MUST be run before the change is considered complete. A change
with unrun tests, failing tests, or an unmet coverage gate is NOT done.

When a test fails, the failure MUST be root-caused before any fix is applied:
the engineer MUST first determine whether the **test's** logic is incorrect or
the **implementation's** logic is incorrect, record that determination (in the
PR, commit, or task notes), and only then modify the test or the code
accordingly. Editing a test merely to make it pass — without first establishing
that the test's expectation was actually wrong — is prohibited.

Rationale: This application inspects sensitive material; regression-safe changes
require executable proof, not manual confidence, and a disciplined failure
triage prevents masking real defects by "fixing" correct tests.

### IV. Automated Quality Enforcement
Linting, formatting, and static analysis MUST run from project tooling and MUST
be deterministic in local and CI execution. The default toolchain MUST be
declared in `pyproject.toml` and MUST include a formatter, a linter, and a
static analysis or type-check step consistent with modern Python standards. A
change is not merge-ready until these checks pass without manual exceptions.

Rationale: Automated quality gates keep code style debates out of reviews and
prevent low-signal defects from reaching packaged builds.

### V. Reproducible Standalone Delivery
The application MUST remain deployable as a standalone Python executable through
a documented, repeatable build process. Packaging metadata, entry points,
runtime dependencies, and build commands MUST live in version-controlled project
configuration. Each release candidate MUST be smoke-tested from the produced
artifact, and logs or reports MUST redact sensitive key material by default.

Rationale: A security-oriented command-line tool is only trustworthy when its
packaged artifact is reproducible, reviewable, and safe to operate.

## Engineering Standards

- The repository MUST use `pyproject.toml` as the single source of truth for
	project metadata, dependency constraints, and Python tooling configuration.
- Source code MUST live under `src/`, tests MUST live under `tests/`, and
	executable entrypoints MUST be thin adapters over application services.
- Code MUST satisfy SOLID, Clean Code, DRY, and KISS; reviewers MUST reject
	duplicated logic, needless complexity, and broken layer boundaries.
- Dependency additions MUST be justified in the plan or pull request, and
	unused dependencies MUST be removed promptly.
- The default quality stack MUST include unit testing, coverage reporting,
	linting, formatting, and static analysis aligned with current Python best
	practices.
- After implementing a change, the full unit-test suite and coverage report MUST
	be executed locally before the change is proposed for review.
- Error messages MUST be actionable, and operational logs MUST avoid printing
	secrets, raw private keys, or other sensitive material.

## Delivery Workflow & Quality Gates

- Every spec and implementation plan MUST document architecture boundaries,
	test strategy, coverage expectations, quality commands, and executable
	packaging impact before implementation starts.
- Pull requests and review checklists MUST confirm compliance with SOLID
	boundaries, Clean Code / DRY / KISS expectations, required tests, coverage
	reporting, and standalone packaging rules.
- After implementation, the full unit-test suite and coverage report MUST be run;
	any failing test MUST be triaged (test logic vs. implementation logic) and the
	conclusion recorded before the test or the code is changed.
- CI MUST run the project's formatter check, linter, static analysis, test
	suite, and coverage reporting before merge; release automation MUST
	additionally build and smoke-test the standalone executable.
- Documentation for new commands, configuration, or packaging behavior MUST be
	updated in the same change that introduces them.

## Governance

This constitution overrides conflicting local conventions and serves as the
default quality bar for all planning, implementation, review, and release work
in this repository.

Amendments MUST be proposed in the same change set as any impacted templates,
guidance files, or automation updates. Versioning follows semantic intent:
MAJOR for removed or fundamentally redefined principles, MINOR for new
principles or materially expanded governance, and PATCH for clarifications that
do not change engineering obligations.

Compliance MUST be checked in every implementation plan through the Constitution
Check section, in every pull request review, and before every release artifact
is published. Any approved exception MUST be time-boxed, documented with
rationale, and tracked to removal.

**Version**: 1.1.0 | **Ratified**: 2026-06-04 | **Last Amended**: 2026-06-22
