"""Usage-category classification rules and remediation guidance registry.

Each ``UsageCategory`` has exactly one ``UsageCategoryDefinition`` pairing its
classification rule with its remediation prose (spec 010 FR-005): adding a
category means adding one enum member and one definition entry — nothing else
is edited. Definitions are evaluated in tuple order, first match wins, and the
``UNKNOWN`` catch-all is always last
(specs/010-code-quality-audit/contracts/extension-points.md).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from check_unprotected_keys.domain.models import (
    CandidateFile,
    RemediationRecommendation,
    UsageCategory,
)

EMBEDDED_CONFIG_PATTERNS = frozenset(
    {
        ".env",
        ".env.*",
        "*.env",
        "*.env.*",
        "*.ovpn",
        "*.tfvars",
    }
)
INTERACTIVE_USER_PATTERNS = frozenset({"id_*", "identity", "*.ppk"})
AUTOMATION_PATH_HINTS = (
    "repo-keys",
    "deploy",
    "deployment",
    "infra",
    "ci",
    "cd",
    "runner",
    "pipeline",
    "vpn",
    "k8s",
    "kubernetes",
)


@dataclass(frozen=True, slots=True)
class CandidateFacts:
    """Lower-cased candidate metadata shared by all classification rules."""

    matched_filename_pattern: str
    file_name: str
    path_parts: frozenset[str]
    folder_pattern: str
    automation_hint: bool

    @classmethod
    def from_candidate(cls, candidate: CandidateFile) -> CandidateFacts:
        directory_text = str(candidate.canonical_path.parent).lower()
        folder_pattern = candidate.matched_folder_pattern.lower()
        return cls(
            matched_filename_pattern=candidate.matched_filename_pattern.lower(),
            file_name=candidate.canonical_path.name.lower(),
            path_parts=frozenset(
                part.lower() for part in candidate.canonical_path.parts
            ),
            folder_pattern=folder_pattern,
            automation_hint=any(
                hint in directory_text or hint in folder_pattern
                for hint in AUTOMATION_PATH_HINTS
            ),
        )


@dataclass(frozen=True, slots=True)
class UsageCategoryDefinition:
    """Single authoritative record for one usage category."""

    category: UsageCategory
    matches: Callable[[CandidateFacts], bool]
    remediation: RemediationRecommendation


def _matches_ssh_host_key(facts: CandidateFacts) -> bool:
    return facts.matched_filename_pattern == "ssh_host_*_key" or (
        facts.file_name.startswith("ssh_host_")
    )


def _matches_embedded_config(facts: CandidateFacts) -> bool:
    return facts.matched_filename_pattern in EMBEDDED_CONFIG_PATTERNS


def _matches_interactive_user(facts: CandidateFacts) -> bool:
    if ".ssh" in facts.path_parts or ".ssh" in facts.folder_pattern:
        return True
    return (
        facts.matched_filename_pattern in INTERACTIVE_USER_PATTERNS
        and not facts.automation_hint
    )


def _matches_automation(facts: CandidateFacts) -> bool:
    return facts.automation_hint


def _matches_any(facts: CandidateFacts) -> bool:
    return True


USAGE_CATEGORY_DEFINITIONS: tuple[UsageCategoryDefinition, ...] = (
    UsageCategoryDefinition(
        category=UsageCategory.SSH_HOST_KEY,
        matches=_matches_ssh_host_key,
        remediation=RemediationRecommendation(
            usage_category=UsageCategory.SSH_HOST_KEY,
            title="Reprovision as a managed host key",
            summary=(
                "Keep host startup non-interactive by rotating the key "
                "under root-only control or moving to certificate-based "
                "host identity."
            ),
            rationale=(
                "SSH host keys must stay available during service startup, "
                "so interactive passphrase prompts are not appropriate."
            ),
            next_step_hint=(
                "Rotate the host key with strict ownership and evaluate "
                "host certificates or platform-managed host identity."
            ),
        ),
    ),
    UsageCategoryDefinition(
        category=UsageCategory.EMBEDDED_CONFIG_SECRET,
        matches=_matches_embedded_config,
        remediation=RemediationRecommendation(
            usage_category=UsageCategory.EMBEDDED_CONFIG_SECRET,
            title="Externalize the embedded secret",
            summary=(
                "Remove the secret from the config file and load it "
                "from a vault, secret manager, or OS/application key store."
            ),
            rationale=(
                "Embedded secrets are hard to rotate and spread plaintext "
                "secret material through config distribution."
            ),
            next_step_hint=(
                "Delete the embedded secret from the file and leave only a "
                "reference or lookup identifier."
            ),
        ),
    ),
    UsageCategoryDefinition(
        category=UsageCategory.INTERACTIVE_USER_KEY,
        matches=_matches_interactive_user,
        remediation=RemediationRecommendation(
            usage_category=UsageCategory.INTERACTIVE_USER_KEY,
            title="Passphrase plus session agent",
            summary=(
                "Add a passphrase and load the key into ssh-agent or a "
                "system keychain once per session."
            ),
            rationale=(
                "Interactive SSH workflows can tolerate one unlock per "
                "login session without repeated prompts."
            ),
            next_step_hint=(
                "Re-save the key with a passphrase, then load it once per "
                "session with ssh-add or your platform keychain."
            ),
        ),
    ),
    UsageCategoryDefinition(
        category=UsageCategory.AUTOMATION_OR_DEPLOYMENT_KEY,
        matches=_matches_automation,
        remediation=RemediationRecommendation(
            usage_category=UsageCategory.AUTOMATION_OR_DEPLOYMENT_KEY,
            title="Move to a managed secret or identity",
            summary=(
                "Replace the file-based key with a vault-managed secret or "
                "workload identity that can be retrieved non-interactively."
            ),
            rationale=(
                "Automation and deployment workflows break when they depend "
                "on manual unlock prompts."
            ),
            next_step_hint=(
                "Store the key in your secret manager or switch the "
                "workload to a managed identity path."
            ),
        ),
    ),
    UsageCategoryDefinition(
        category=UsageCategory.UNKNOWN,
        matches=_matches_any,
        remediation=RemediationRecommendation(
            usage_category=UsageCategory.UNKNOWN,
            title="Classify usage before choosing a protection path",
            summary=(
                "Confirm whether this key is used by a human or an "
                "unattended workload before picking passphrase or vault "
                "guidance."
            ),
            rationale=(
                "The safest remediation depends on whether an interactive "
                "prompt is acceptable."
            ),
            next_step_hint=(
                "Identify the consuming process, then choose session-agent "
                "protection for human use or managed secret storage for "
                "unattended use."
            ),
        ),
    ),
)

_REMEDIATION_BY_CATEGORY: dict[UsageCategory, RemediationRecommendation] = {
    definition.category: definition.remediation
    for definition in USAGE_CATEGORY_DEFINITIONS
}


def infer_usage_category(candidate: CandidateFile) -> UsageCategory:
    """Infer a safe usage category from path and matched-pattern metadata."""

    facts = CandidateFacts.from_candidate(candidate)
    for definition in USAGE_CATEGORY_DEFINITIONS:
        if definition.matches(facts):
            return definition.category
    return UsageCategory.UNKNOWN  # pragma: no cover - UNKNOWN catch-all is last


def build_remediation_recommendation(
    usage_category: UsageCategory,
) -> RemediationRecommendation:
    """Return the least-disruptive safe recommendation for a usage category."""

    return _REMEDIATION_BY_CATEGORY[usage_category]
