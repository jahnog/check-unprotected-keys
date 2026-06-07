"""Classification helpers for file-level protection assessments."""

from __future__ import annotations

from collections.abc import Iterable

from check_unprotected_keys.domain.models import (
    ProtectionAssessment,
    ProtectionClassification,
)

FINDING_CLASSIFICATIONS = frozenset({ProtectionClassification.UNPROTECTED})
CLASSIFICATION_PRIORITY = {
    ProtectionClassification.UNPROTECTED: 50,
    ProtectionClassification.PROTECTED_WITH_PASSPHRASE: 40,
    ProtectionClassification.PUBLIC_ONLY: 30,
    ProtectionClassification.MALFORMED: 20,
    ProtectionClassification.UNREADABLE: 10,
}


def build_assessment(
    classification: ProtectionClassification,
    *,
    format_hint: str,
    message: str,
) -> ProtectionAssessment:
    """Create a typed protection assessment."""

    return ProtectionAssessment(
        classification=classification,
        format_hint=format_hint,
        message=message,
    )


def select_file_assessment(
    assessments: Iterable[ProtectionAssessment],
) -> ProtectionAssessment:
    """Select the strongest file-level assessment from one or more key blobs."""

    return max(
        assessments,
        key=lambda assessment: CLASSIFICATION_PRIORITY[assessment.classification],
    )


def is_finding(assessment: ProtectionAssessment) -> bool:
    """Return whether the assessment should be emitted as a violation."""

    return assessment.classification in FINDING_CLASSIFICATIONS
