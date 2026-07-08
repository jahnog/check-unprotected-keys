"""Detection of i18n/message resource bundles (research Decision 10).

An i18n bundle such as ``messages_es.properties`` holds natural-language text
*about* secrets ("Enter your password"), never secrets. Such files skip the
name-gated credential gate (the unconditional inline-key-material and
value-signature layers still apply, so a real embedded secret is never missed).
"""

from __future__ import annotations

from check_unprotected_keys.domain.properties.locales import (
    ISO_639_1_LANGUAGES,
    LOCALE_COLLISION_CODES,
    MESSAGE_BUNDLE_BASENAMES,
)


def is_message_bundle(filename: str) -> bool:
    """Return whether a ``.properties`` filename is an i18n/message bundle.

    True when the base name (after stripping a Java ResourceBundle locale suffix)
    is a known message-bundle name, or when the file carries a locale suffix whose
    language is an unambiguous ISO 639-1 code. Such files hold text *about*
    secrets, not secrets, so the name-gated credential gate is skipped for them.
    """

    stem = filename
    if stem.endswith(".properties"):
        stem = stem[: -len(".properties")]
    if not stem:
        return False
    base, language = _split_locale_suffix(stem)
    if base.lower() in MESSAGE_BUNDLE_BASENAMES:
        return True
    return language is not None and language not in LOCALE_COLLISION_CODES


def _split_locale_suffix(stem: str) -> tuple[str, str | None]:
    """Split a bundle stem into ``(base, language)`` at a trailing locale suffix.

    Returns ``(stem, None)`` when no valid trailing locale is present.
    """

    segments = stem.split("_")
    for index in range(1, len(segments)):
        language = segments[index]
        if (
            language.islower()
            and language in ISO_639_1_LANGUAGES
            and all(_is_locale_extra(segment) for segment in segments[index + 1 :])
        ):
            return "_".join(segments[:index]), language
    return stem, None


def _is_locale_extra(segment: str) -> bool:
    """Return whether a segment is a locale region / script / variant token."""

    if len(segment) == 2 and segment.isalpha() and segment.isupper():
        return True  # ISO 3166-1 country, e.g. US
    if len(segment) == 3 and segment.isdigit():
        return True  # UN M.49 region
    return (
        len(segment) == 4
        and segment.isalpha()
        and segment[0].isupper()
        and segment[1:].islower()
    )  # ISO 15924 script, e.g. Hant
