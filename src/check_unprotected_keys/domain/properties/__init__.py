"""Pure parsing and secret heuristics for Java ``.properties`` content.

This package is I/O-free: it turns decoded text into property entries and
classifies values. Byte reading, key-file reference following, and reuse of the
key-material parser live in the adapter layer.

Detection is a layered, confidence-tiered classifier (feature 009):

1. Token-aware key matching (:func:`tokenize_key`, :func:`classify_key_tier`,
   :mod:`.tiers`) replaces substring matching so container words like
   ``compass``/``tokenizer`` no longer match.
2. Key-name strength tiers (:class:`KeyNameTier`) with qualifier demotion decide
   how much value evidence is required.
3. An unconditional value-signature layer (:func:`match_value_signature`,
   :mod:`.signatures`) catches provider tokens, JWTs, embedded-credential URLs,
   and high-entropy blobs regardless of the key name.
4. Conservative, tier-aware value-shape and sample/mask exclusions
   (:func:`is_sample_placeholder`, :func:`is_non_secret_shape`, :mod:`.shapes`)
   remove the benign-config false positives.
5. A tier-aware credential gate (:func:`is_credential_like`).

Reference data tables live in :mod:`.reference_data` and :mod:`.locales`,
separated from the logic that consumes them (spec 010 FR-010). This
``__init__`` re-exports the public API so existing imports keep working.
"""

from check_unprotected_keys.domain.properties.bundles import is_message_bundle
from check_unprotected_keys.domain.properties.parser import (
    PropertyEntry,
    parse_properties,
)
from check_unprotected_keys.domain.properties.shapes import (
    PropertyValueKind,
    classify_value,
    is_credential_like,
    is_non_secret_shape,
    is_sample_placeholder,
    placeholder_default,
)
from check_unprotected_keys.domain.properties.signatures import (
    ValueSignature,
    match_value_signature,
)
from check_unprotected_keys.domain.properties.tiers import (
    KeyNameTier,
    classify_key_tier,
    tokenize_key,
)

__all__ = [
    "KeyNameTier",
    "PropertyEntry",
    "PropertyValueKind",
    "ValueSignature",
    "classify_key_tier",
    "classify_value",
    "is_credential_like",
    "is_message_bundle",
    "is_non_secret_shape",
    "is_sample_placeholder",
    "match_value_signature",
    "parse_properties",
    "placeholder_default",
    "tokenize_key",
]
