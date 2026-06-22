# Feature Specification: Symlink-Following, Cycle-Safe Folder Traversal

**Feature Branch**: `006-symlink-safe-traversal`

**Created**: 2026-06-22

**Status**: Draft

**Input**: User description: "when navigating through folders recursively searching for files to verify, make two changes. the first is to follow symbolic links. the second is to implement some kind of data structure to avoid circles (due to the symbolic links) so we scan each final folder only one time."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Discover keys stored behind symbolic links (Priority: P1)

A security operator scans a workspace where a sensitive directory (for example a home `.ssh` folder, a shared secrets vault, or a deployment credentials directory) is not a real subfolder but a **symbolic link** pointing elsewhere. Today the scan steps over that link and silently misses any unprotected keys behind it. With this feature, the scanner follows the link, descends into the linked directory, and reports the unprotected keys it contains.

**Why this priority**: This is the core value of the feature. Symlinked key directories are common (dotfile managers, mounted vaults, shared team folders), and missing them is a false sense of security — the tool's entire purpose is to find exposed keys, so a blind spot here directly undermines trust in a clean result.

**Independent Test**: Create a real directory containing an unprotected private key in a location that is *not* under the configured search base. Create a symbolic link inside the search base that points to that directory. Run a scan and confirm the unprotected key is discovered and reported. This is independently testable and delivers the headline value on its own.

**Acceptance Scenarios**:

1. **Given** a symbolic link inside the search base that points to a directory holding an unprotected key, **When** a scan runs, **Then** the unprotected key is reported as a finding.
2. **Given** a symbolic link inside the search base that points directly to an unprotected key file (not a directory), **When** a scan runs, **Then** the linked file is evaluated against the configured filename patterns and reported if unprotected.
3. **Given** a symbolic link pointing to a directory that contains only properly protected keys, **When** a scan runs, **Then** those keys are inspected and counted as non-findings (no false positive).

---

### User Story 2 - Scan each final folder exactly once, even with cycles (Priority: P1)

The same operator scans a tree where symbolic links create **cycles** (a link that points back to an ancestor, two folders that link to each other, or a link to itself) or **aliases** (two different links that resolve to the same real directory). With this feature, the scan terminates promptly, never loops infinitely, and visits each real ("final") directory at most once — so results and runtime stay correct and bounded.

**Why this priority**: Following symbolic links is unsafe without cycle protection. A single circular link can make a naive recursive walk loop forever or exhaust resources. This guarantee is what makes User Story 1 safe to ship, so it is equally critical.

**Independent Test**: Build a directory tree containing a symbolic-link cycle (e.g., `a/link -> ../a`) plus at least one unprotected key. Run a scan and confirm it terminates in bounded time, reports the key exactly once, and does not error. Separately, create two distinct links resolving to the same real directory and confirm its keys are reported once, not twice.

**Acceptance Scenarios**:

1. **Given** a self-referential symbolic link (a directory link pointing to itself), **When** a scan runs, **Then** the scan terminates and reports findings without looping.
2. **Given** a mutual cycle (directory A links into B and B links back into A), **When** a scan runs, **Then** each real directory is traversed at most once and the scan terminates.
3. **Given** a symbolic link pointing to an ancestor of itself, **When** a scan runs, **Then** the scan terminates without re-descending the ancestor subtree.
4. **Given** two distinct symbolic links that resolve to the same real directory, **When** a scan runs, **Then** the keys in that directory are reported exactly once (no duplicate findings) and the directory is walked only once.

---

### User Story 3 - Tolerate broken and inaccessible links without failing (Priority: P2)

The operator scans a real-world tree that contains dangling symbolic links (targets deleted or unmounted) and links whose targets cannot be read due to permissions. With this feature, the scan skips those links gracefully and completes, reporting all other findings.

**Why this priority**: Robustness matters but does not block the headline value. Production filesystems routinely contain broken or permission-restricted links; the scan must not abort or crash, but this can layer on top of the core traversal behavior.

**Independent Test**: Create a dangling symbolic link (pointing to a non-existent path) and a link to a directory with read permission removed, alongside a valid unprotected key elsewhere in the tree. Run a scan and confirm it completes, skips the broken/inaccessible links, and still reports the valid finding.

**Acceptance Scenarios**:

1. **Given** a dangling symbolic link, **When** a scan runs, **Then** the link is skipped and the scan continues to completion.
2. **Given** a symbolic link to a directory the process cannot read, **When** a scan runs, **Then** the inaccessible target is skipped and all other reachable findings are still reported.

---

### Edge Cases

- **Self-referential link** (`dir -> .` or `dir -> dir`): traversal must visit the directory once and stop, never recurse into the link.
- **Mutual / multi-hop cycles** (A → B → A, or longer chains): every real directory in the chain is visited at most once.
- **Ancestor loop** (a link pointing to one of its own parents): the ancestor subtree is not re-walked.
- **Aliasing / diamond** (two or more links to the same real directory): the directory is walked once and its keys reported once.
- **Link to a regular file**: treated as a candidate file and matched against filename patterns like any other file.
- **Broken / dangling link**: skipped without aborting the scan.
- **Inaccessible target** (permissions, unmounted, or other OS error): skipped without aborting the scan.
- **Ignored-name reached via a link** (e.g., a link named or resolving to `node_modules`, `.git`): existing ignored-directory pruning still applies.
- **Link target outside the configured search base** (including a link to a high-level directory such as a home or root): followed per the documented scope assumption, while ignored-name pruning and single-visit protection still bound the work.
- **A real directory and a link both reaching the same final directory**: the directory is still visited only once across the whole scan.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST follow symbolic links that resolve to directories during recursive discovery, descending into the linked directory's contents as if it were a real subdirectory.
- **FR-002**: System MUST follow symbolic links that resolve to regular files and evaluate the linked file as a discovery candidate, subject to the same filename-pattern matching applied to non-linked files.
- **FR-003**: System MUST visit each distinct final (canonical) directory at most once per scan, regardless of how many symbolic-link paths lead to it.
- **FR-004**: System MUST detect and break symbolic-link cycles — including self-referential links, mutual cycles, and ancestor loops — so that every scan terminates.
- **FR-005**: System MUST report each discovered key file at most once, even when the file is reachable through multiple symbolic-link paths (no duplicate findings).
- **FR-006**: System MUST skip broken or dangling symbolic links without aborting the scan and continue traversal.
- **FR-007**: System MUST skip symbolic-link targets that cannot be accessed (permissions or other operating-system errors) without aborting the scan, consistent with existing traversal error handling.
- **FR-008**: System MUST continue to honor configured ignored-directory names and the optional start-folder narrowing when traversal proceeds through symbolic links.
- **FR-009**: The symlink-following and single-visit (cycle-avoidance) behavior MUST apply consistently to every recursive traversal pass the scan performs, including directory-hint promotion discovery and candidate-file discovery.
- **FR-010**: System MUST preserve correct provenance attribution for findings reached via symbolic links, so reporting continues to identify why and where each candidate was discovered.
- **FR-011**: System MUST follow symbolic links by default without requiring the operator to enable a configuration flag (see Assumptions for the rationale and the scope-containment trade-off).

### Non-Functional Requirements *(mandatory)*

- **NFR-001**: Feature MUST preserve explicit boundaries between CLI entrypoints, application services, domain logic, and infrastructure concerns. The traversal change is confined to the filesystem infrastructure adapter; the single-visit/cycle-avoidance data structure lives at the traversal seam and MUST NOT leak filesystem mechanics into domain or service layers.
- **NFR-002**: Feature MUST describe required unit tests (cycle detection and single-visit logic) and integration tests using real temporary filesystems with symbolic links (linked directories, cycles, aliases, broken and inaccessible links). New traversal branches MUST be covered by the automated coverage report and keep the project at or above its configured coverage gate.
- **NFR-003**: Feature MUST remain compliant with the project's linting, formatting, and static analysis gates.
- **NFR-004**: Feature MUST NOT change standalone packaging, entry points, release artifacts, or deployment documentation; user-facing documentation is updated only to note the new symlink-following behavior.

### Key Entities *(include if feature involves data)*

- **Symbolic Link**: A filesystem reference encountered during traversal whose target may be a directory or a regular file, may lie inside or outside the configured search base, and may be valid, dangling, or inaccessible.
- **Final (Canonical) Directory**: The real directory that a possibly-symlinked path resolves to. The unit of "scan once" — a scan visits each final directory at most once.
- **Visited-Directory Record**: The data structure that remembers which final directories have already been entered during the current scan, enabling cycle detection and the single-visit guarantee. Conceptually a set keyed on a stable directory identity (canonical location).
- **Candidate File**: An existing concept — a file discovered during traversal (now also reachable via symbolic links) that is matched against filename patterns and assessed for protection.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of unprotected keys located behind in-scope symbolic-linked directories or files are reported, where previously 0% were (these keys were skipped entirely).
- **SC-002**: A scan over a filesystem containing one or more symbolic-link cycles always terminates; it never hangs or loops, and its runtime stays within the same order of magnitude as an equivalent cycle-free tree of the same number of distinct directories.
- **SC-003**: Each real/final directory is entered at most once: for a tree exposing N distinct directories through any mix of links and real paths, the number of directory visits does not exceed N.
- **SC-004**: Each unique key file is reported exactly once even when reachable via multiple link paths — zero duplicate findings in scans containing aliasing links.
- **SC-005**: Broken or inaccessible symbolic links never cause a scan to fail; a scan containing such links completes and still reports every other discoverable finding.

## Assumptions

- **Symlinks are followed by default, with no new toggle.** The user asked to "follow symbolic links" as a behavior change, so following becomes the standard traversal behavior rather than an opt-in flag. No new configuration key is introduced.
- **Symbolic links are followed even when their canonical target lies outside the originally configured search bases** (for example a link to a home directory or a mounted volume). The user's stated intent is to find key material wherever a link leads, and the tool's purpose is exposure detection. Scope is still bounded by existing ignored-directory pruning, optional start-folder narrowing, and the single-visit guarantee. Operators who need strict containment can rely on `ignore_directories`; a dedicated scope-containment option is out of scope for this feature.
- **Directory identity for the single-visit guarantee is based on the canonical/real location** of a directory (consistent with the tool's existing canonical-path resolution for files). Two paths that resolve to the same real directory are treated as the same directory.
- **Existing file-level deduplication is retained**; this feature adds directory-level single-visit on top of it, so both duplicate findings and redundant directory walks are prevented.
- **Existing default and configured ignored-directory names continue to be pruned**, including when those names are encountered through a symbolic link.
- **POSIX symlink semantics are the primary target.** On platforms where symbolic links or directory junctions behave differently, behavior follows the standard library's path-resolution semantics; no platform-specific handling is added beyond that.
- **Reporting format and finding/non-finding counting semantics are unchanged**; only which files are discoverable (and that each is counted once) changes.
