<!--
Sync Impact Report
Version change: template -> 1.0.0
Modified principles:
- Template Principle 1 -> I. Pythonic SOLID Architecture
- Template Principle 2 -> II. Clean Code, Types, and Intentional Patterns
- Template Principle 3 -> III. Tests and Coverage Are Release Gates
- Template Principle 4 -> IV. Automated Quality Enforcement
- Template Principle 5 -> V. Reproducible Standalone Delivery
Added sections:
- Engineering Standards
- Delivery Workflow & Quality Gates
Removed sections:
- None
Templates requiring updates:
- ✅ .specify/templates/plan-template.md
- ✅ .specify/templates/spec-template.md
- ✅ .specify/templates/tasks-template.md
Follow-up TODOs:
- None
Related guidance updated:
- ✅ .github/copilot-instructions.md
-->
# Find Unencrypted Keys Constitution

## Core Principles

### I. Pythonic SOLID Architecture
Production code MUST be organized into explicit layers for CLI entrypoints,
application services, domain logic, and infrastructure adapters. Classes,
functions, and modules MUST have one clear responsibility, depend on
abstractions at I/O seams, and avoid hidden global state. Design patterns MAY be
introduced only when they reduce coupling, simplify extension points, or
protect domain logic from platform details; every non-trivial pattern choice
MUST be named and justified in the implementation plan.

Rationale: A standalone executable stays maintainable only when business logic
remains isolated from command-line plumbing and operating-system concerns.

### II. Clean Code, Types, and Intentional Patterns
Code MUST prefer small, cohesive units; descriptive names; explicit types on
public interfaces; and side-effect-aware functions. Public modules, service
boundaries, and data transfer objects MUST be type-annotated. Duplication MUST
be removed at the right abstraction level rather than hidden behind premature
indirection. A pattern is compliant only when it makes control flow easier to
understand for the next maintainer.

Rationale: Clean, typed code reduces accidental complexity and makes
security-sensitive scanning behavior safer to evolve.

### III. Tests and Coverage Are Release Gates
Every feature and bug fix MUST ship with unit tests for new or changed
behavior. Integration or contract tests MUST be added when a change crosses
process boundaries, packaging boundaries, filesystem boundaries, or other
infrastructure seams. The project MUST produce an automated coverage report on
every validation path, and configured minimum coverage gates MUST fail the build
when unmet.

Rationale: This application inspects sensitive material; regression-safe changes
require executable proof, not manual confidence.

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
- Dependency additions MUST be justified in the plan or pull request, and
	unused dependencies MUST be removed promptly.
- The default quality stack MUST include unit testing, coverage reporting,
	linting, formatting, and static analysis aligned with current Python best
	practices.
- Error messages MUST be actionable, and operational logs MUST avoid printing
	secrets, raw private keys, or other sensitive material.

## Delivery Workflow & Quality Gates

- Every spec and implementation plan MUST document architecture boundaries,
	test strategy, coverage expectations, quality commands, and executable
	packaging impact before implementation starts.
- Pull requests and review checklists MUST confirm compliance with SOLID
	boundaries, Clean Code expectations, required tests, coverage reporting, and
	standalone packaging rules.
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

**Version**: 1.0.0 | **Ratified**: 2026-06-04 | **Last Amended**: 2026-06-04
