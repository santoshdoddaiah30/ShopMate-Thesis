"""ShopMate N24M2 trusted catalogue attribute truth layer.

This additive N24-only layer replaces self-validating derived catalogue labels
with provenance-aware evidence sourced directly from raw production fields.
Frozen N23 functions, model artefacts, hybrid weights, and training outputs are
never mutated here.
"""

from __future__ import annotations

import json as _n24m2_json
import math as _n24m2_math
import re as _n24m2_re
import time as _n24m2_time
from collections import Counter as _N24M2Counter
from copy import deepcopy as _n24m2_deepcopy
from enum import Enum as _N24M2Enum
from typing import Any as _N24M2Any


N24M2_SECTION_VERSION = "n24m2_trusted_catalogue_truth_v2"
N24M2_PROVENANCE_CONTRACT_VERSION = "n24m2_trusted_attribute_evidence_v1"
N24M2_ELIGIBILITY_ENGINE_VERSION = "n24m2_trusted_taxonomy_eligibility_v2"
N24M2_COLOUR_CONTRACT_VERSION = "n24m2_structured_ordered_colour_v1"
N24M2_AUDIENCE_CONTRACT_VERSION = "n24m2_structural_audience_v1"


# Keep rating units out of the historical-price parser. The N24M parser accepts
# currency-less budget language, so unit-bearing rating clauses must be masked
# generically before price extraction.
if "N24M2_BASE_PRICE_OPERATIONS" not in globals():
    N24M2_BASE_PRICE_OPERATIONS = _n24m_price_operations


def _n24m_price_operations(text: str):
    without_ratings = _n24m2_re.sub(
        r"(?i)\b(?:rating\s*(?:of|at\s+least|above|over)?|rated\s*(?:at\s+least|above|over)?|at\s+least|above|over)\s*\d(?:\.\d+)?\s*stars?\b",
        " ", str(text or ""),
    )
    without_ratings = _n24m2_re.sub(
        r"(?i)\b\d(?:\.\d+)?\s+stars?\s+(?:or\s+higher|minimum|and\s+above)\b",
        " ", without_ratings,
    )
    return N24M2_BASE_PRICE_OPERATIONS(without_ratings)


# Preserve the search portion of an utterance that also carries a mixed-colour
# relaxation. Standalone relaxation language continues down the saved N24M
# path and operates on the current request state.
if "N24M2_BASE_DETERMINISTIC_INTERPRETER" not in globals():
    N24M2_BASE_DETERMINISTIC_INTERPRETER = interpret_n24m_deterministic_turn


def interpret_n24m_deterministic_turn(raw_message: str, context, state, active_result_set):
    text = " ".join(str(raw_message or "").strip().split())
    mixed_pattern = r"(?i)\bmixed\s+colou?rs?\s+(?:are\s+)?(?:fine|okay|ok|allowed)\b"
    if _n24m2_re.search(mixed_pattern, text):
        product_clause = _n24m2_re.sub(mixed_pattern, " ", text)
        product_clause = _n24m2_re.sub(r"\s*[;,]\s*", " ", product_clause).strip(" .")
        if _n24m_extract_categories(product_clause) or _n24m_extract_colours_from_request(product_clause)[0]:
            parsed = N24M2_BASE_DETERMINISTIC_INTERPRETER(
                product_clause, context, state, active_result_set
            )
            if parsed is not None:
                delta, guard, updates = parsed
                updates = dict(updates or {})
                updates["allow_mixed_colours"] = True
                guard = dict(guard or {})
                guard["semantic_guard"] = "n24m2_compound_mixed_colour_request"
                return delta, guard, updates
    return N24M2_BASE_DETERMINISTIC_INTERPRETER(
        raw_message, context, state, active_result_set
    )


class N24TrustedSourceType(str, _N24M2Enum):
    STRUCTURED = "STRUCTURED"
    VARIANT = "VARIANT"
    TITLE_EXPLICIT = "TITLE_EXPLICIT"
    TITLE_VARIANT_PATTERN = "TITLE_VARIANT_PATTERN"
    TITLE_GENERIC = "TITLE_GENERIC"
    BRAND = "BRAND"
    MODEL_NAME = "MODEL_NAME"
    DESCRIPTION = "DESCRIPTION"
    FEATURE = "FEATURE"
    DERIVED = "DERIVED"
    UNKNOWN = "UNKNOWN"


class N24TrustedAttributeEvidence(N24StrictModel):
    contract_version: str = N24M2_PROVENANCE_CONTRACT_VERSION
    attribute: str
    canonical_value: _N24M2Any = None
    source_field: str | None = None
    source_type: N24TrustedSourceType
    raw_value: _N24M2Any = None
    confidence: float
    match_level: N24AttributeMatch
    reason: str


class N24TrustedEligibilityResult(N24StrictModel):
    product_id: str
    eligible: bool
    attribute_evidence: dict[str, N24TrustedAttributeEvidence]
    hard_constraint_count: int
    exact_constraint_count: int
    partial_constraint_count: int
    unknown_constraint_count: int
    violation_count: int
    match_score: float
    engine_version: str = N24M2_ELIGIBILITY_ENGINE_VERSION


_N24M2_STRUCTURED_COLOUR_FIELDS = (
    "Color", "Colour", "Color Name", "Band Color", "Stone Color", "Lens Color",
)
_N24M2_STRUCTURED_AUDIENCE_FIELDS = (
    "Department", "Suggested Users", "Target Audience", "Target gender",
)
_N24M2_STRUCTURED_AGE_FIELDS = ("Age Range (Description)", "Age Range")
_N24M2_STRUCTURED_MATERIAL_FIELDS = (
    "Material", "Fabric Type", "Inner Material", "Outer Material",
    "Material Type", "material_composition", "Material Composition",
)
_N24M2_STRUCTURED_STYLE_FIELDS = (
    "Style", "Sport Type", "Sport", "Occasion", "Recommended Uses For Product",
)
_N24M2_COLOUR_WORDS = {
    "white", "black", "red", "blue", "green", "orange", "brown", "gold",
    "silver", "pink", "purple", "yellow", "grey", "gray", "tan", "beige",
    "khaki", "navy", "burgundy", "violet", "multicolor", "multicolour",
}
_N24M2_MATERIAL_WORDS = {
    "leather", "cotton", "polyester", "nylon", "suede", "silk", "wool",
    "linen", "rubber", "synthetic", "canvas", "mesh", "metal", "plastic",
}


def _n24m2_normalize(value: _N24M2Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("&", " and ").replace("’", "'").casefold()
    text = _n24m2_re.sub(r"[^a-z0-9]+", " ", text)
    return _n24m2_re.sub(r"\s+", " ", text).strip()


def _n24m2_raw_details(value: _N24M2Any) -> dict:
    if isinstance(value, dict):
        return dict(value)
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = _n24m2_json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _n24m2_raw_categories(value: _N24M2Any) -> list[str]:
    if isinstance(value, list):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = _n24m2_json.loads(value)
        except Exception:
            parsed = []
    else:
        parsed = []
    return [str(item).strip() for item in parsed if str(item).strip()]


def mask_n24_canonical_brand_span(title: str, brand: str) -> str:
    """Remove exact canonical brand spans before any title fallback parsing."""
    title = str(title or "")
    brand = str(brand or "").strip()
    if not title or not brand:
        return title
    pieces = [piece for piece in _n24m2_re.split(r"\s+", brand) if piece]
    if not pieces:
        return title
    expression = r"(?<![A-Za-z0-9])" + r"\s+".join(
        _n24m2_re.escape(piece) for piece in pieces
    ) + r"(?![A-Za-z0-9])"
    return _n24m2_re.sub(expression, " ", title, count=0, flags=_n24m2_re.I).strip()


def _n24m2_evidence(
    attribute: str,
    canonical_value: _N24M2Any,
    source_field: str | None,
    source_type: N24TrustedSourceType,
    raw_value: _N24M2Any,
    confidence: float,
    match_level: N24AttributeMatch,
    reason: str,
) -> N24TrustedAttributeEvidence:
    if isinstance(raw_value, (_N24M2Enum,)):
        raw_value = raw_value.value
    if not isinstance(raw_value, (str, int, float, bool, list, dict, type(None))):
        raw_value = str(raw_value)
    return N24TrustedAttributeEvidence(
        attribute=attribute, canonical_value=canonical_value,
        source_field=source_field, source_type=source_type,
        raw_value=raw_value, confidence=float(confidence),
        match_level=match_level, reason=reason,
    )


def _n24m2_colour_tokens(raw_value: _N24M2Any) -> list[str]:
    """Canonicalize ordered tokens only after a source is independently trusted."""
    text = str(raw_value or "")
    if not text.strip():
        return []
    text = _n24m2_re.sub(r"(?i)\bwhite\s+gold\b", "", text)
    aliases = sorted(_N24M_COLOUR_ALIASES, key=len, reverse=True)
    pattern = r"(?<![a-z0-9])(" + "|".join(
        _n24m2_re.escape(item) for item in aliases
    ) + r")(?![a-z0-9])"
    return [
        _N24M_COLOUR_ALIASES[match.group(1).casefold()]
        for match in _n24m2_re.finditer(pattern, text, flags=_n24m2_re.I)
    ]


def _n24m2_title_attribute_tokens(text: str, vocabulary: set[str]) -> list[str]:
    normalized = _n24m2_normalize(text)
    return [
        token for token in sorted(vocabulary)
        if _n24m2_re.search(rf"\b{_n24m2_re.escape(_n24m2_normalize(token))}\b", normalized)
    ]


def _n24m2_resolve_colorway_slash_group(group: str) -> list[str] | None:
    """A "/"-joined group counts as a genuine colorway list only if EVERY
    part independently resolves to a known colour alias -- this is what
    separates it from an untrusted generic title colour word, so it cannot
    be triggered by a brand or model name, only by an actual
    structured-looking colour list.
    """
    if "/" not in group:
        return None
    parts = [part.strip() for part in group.split("/") if part.strip()]
    if len(parts) < 2:
        return None
    resolved = []
    for part in parts:
        alias = _N24M_COLOUR_ALIASES.get(_n24m2_normalize(part))
        if alias is None:
            return None
        resolved.append(alias)
    return resolved


def _n24m2_title_colorway_tokens(masked_title: str) -> list[str]:
    """Recover colour evidence from a genuine colorway list in the
    (brand-masked) title. Amazon titles encode this three ways -- a single
    comma-delimited slash-joined segment ("...Running Shoe, White/White/
    White, 10 US"), a run of consecutive comma segments that are each
    nothing but a colour word ("...Sneakers Shoes, Ftwr White, Ftwr White,
    Core Black, 5.5 M US"), or a standalone slash-joined whitespace token
    with no comma at all ("...Wide 4E Black/Black (416355 001)"). Every
    variant is governed by the same strict rule in
    `_n24m2_resolve_colorway_slash_group`: every part of the matched span
    must independently resolve to a known colour alias, never a bare
    occurrence of a colour word.
    """
    masked_title = str(masked_title or "")
    segments = [part.strip() for part in masked_title.split(",")]

    for segment in segments:
        resolved = _n24m2_resolve_colorway_slash_group(segment)
        if resolved:
            return list(dict.fromkeys(resolved))

    best_run: list[str] = []
    current_run: list[str] = []
    for segment in segments:
        alias = None if "/" in segment else _N24M_COLOUR_ALIASES.get(_n24m2_normalize(segment))
        if alias is not None:
            current_run.append(alias)
        else:
            if len(current_run) >= 2 and len(current_run) > len(best_run):
                best_run = current_run
            current_run = []
    if len(current_run) >= 2 and len(current_run) > len(best_run):
        best_run = current_run
    if best_run:
        return list(dict.fromkeys(best_run))

    for token in masked_title.split():
        token = token.strip(".,()[]")
        resolved = _n24m2_resolve_colorway_slash_group(token)
        if resolved:
            return list(dict.fromkeys(resolved))
    return []


def _n24m2_brand_matches(product_brand_norm: str, requested_norms: set[str]) -> bool:
    """A requested brand also matches a more specific catalogue sub-line of
    it (e.g. requesting "adidas" matches a product whose canonical brand is
    "adidas originals"), but never the reverse -- requesting a specific
    sub-line does not pull in the parent brand's unrelated listings.
    """
    if product_brand_norm in requested_norms:
        return True
    return any(
        requested and product_brand_norm.startswith(requested + " ")
        for requested in requested_norms
    )


def _n24m2_structural_audience(value: _N24M2Any) -> N24CanonicalAudience:
    text = _n24m2_normalize(value)
    if not text:
        return N24CanonicalAudience.UNKNOWN
    if _n24m2_re.search(r"\b(?:toddler|baby|infant)s?\b", text):
        return N24CanonicalAudience.TODDLER
    if _n24m2_re.search(r"\bunisex\s+(?:child|kids?|youth)\b", text):
        return N24CanonicalAudience.UNISEX_CHILD
    if _n24m2_re.search(r"\bunisex\s+adult\b", text) or text == "unisex":
        return N24CanonicalAudience.UNISEX_ADULT
    if _n24m2_re.search(r"\b(?:boys?|male child)\b", text):
        return N24CanonicalAudience.BOYS
    if _n24m2_re.search(r"\b(?:girls?|female child)\b", text):
        return N24CanonicalAudience.GIRLS
    if _n24m2_re.search(r"\b(?:kids?|children|child|youth)\b", text):
        return N24CanonicalAudience.KIDS
    if _n24m2_re.search(r"\b(?:mens?|man|male)\b", text):
        return N24CanonicalAudience.MEN
    if _n24m2_re.search(r"\b(?:womens?|woman|female|ladies)\b", text):
        return N24CanonicalAudience.WOMEN
    if text == "adult":
        return N24CanonicalAudience.UNISEX_ADULT
    return N24CanonicalAudience.UNKNOWN


def _n24m2_explicit_title_audience(masked_title: str) -> N24CanonicalAudience:
    text = str(masked_title or "")
    patterns = (
        (r"\bunisex[- ]child\b", N24CanonicalAudience.UNISEX_CHILD),
        (r"\bunisex[- ]adult\b", N24CanonicalAudience.UNISEX_ADULT),
        (r"\bmen(?:'|’)s\b", N24CanonicalAudience.MEN),
        (r"\bwomen(?:'|’)s\b", N24CanonicalAudience.WOMEN),
        (r"\bboys(?:'|’)?\b", N24CanonicalAudience.BOYS),
        (r"\bgirls(?:'|’)?\b", N24CanonicalAudience.GIRLS),
        (r"\b(?:toddler|baby|infant)s?\b", N24CanonicalAudience.TODDLER),
        (r"\bkids(?:'|’)?\b", N24CanonicalAudience.KIDS),
    )
    for pattern, canonical in patterns:
        if _n24m2_re.search(pattern, text, flags=_n24m2_re.I):
            return canonical
    return N24CanonicalAudience.UNKNOWN


def _n24m2_age_from_raw(value: _N24M2Any) -> str:
    text = _n24m2_normalize(value)
    if _n24m2_re.search(r"\b(?:toddler|baby|infant)\b", text):
        return "TODDLER"
    if _n24m2_re.search(r"\b(?:child|children|kid|kids|youth|boy|boys|girl|girls)\b", text):
        return "CHILD"
    if _n24m2_re.search(r"\b(?:adult|men|mens|women|womens)\b", text):
        return "ADULT"
    return "UNKNOWN"


def _n24m2_age_from_audience(audience: N24CanonicalAudience) -> str:
    if audience in {
        N24CanonicalAudience.MEN, N24CanonicalAudience.WOMEN,
        N24CanonicalAudience.UNISEX_ADULT,
    }:
        return "ADULT"
    if audience == N24CanonicalAudience.TODDLER:
        return "TODDLER"
    if audience in {
        N24CanonicalAudience.BOYS, N24CanonicalAudience.GIRLS,
        N24CanonicalAudience.KIDS, N24CanonicalAudience.UNISEX_CHILD,
    }:
        return "CHILD"
    return "UNKNOWN"


def _n24m2_structured_list(details: dict, fields: tuple[str, ...]) -> tuple[list[str], str | None, str | None]:
    for field in fields:
        raw = details.get(field)
        if raw is None or not str(raw).strip():
            continue
        values = [
            item.strip().casefold()
            for item in _n24m2_re.split(r"[,;/+]", str(raw))
            if item.strip()
        ]
        if values:
            return list(dict.fromkeys(values)), f"details.{field}", str(raw)
    return [], None, None


def _n24m2_numeric_evidence(attribute: str, source_field: str, value: _N24M2Any):
    numeric = safely_convert_to_float(value)
    if numeric is None or not _n24m2_math.isfinite(float(numeric)):
        return _n24m2_evidence(
            attribute, None, source_field, N24TrustedSourceType.UNKNOWN,
            None, 0.0, N24AttributeMatch.UNKNOWN,
            f"{source_field} has no valid numeric value",
        )
    return _n24m2_evidence(
        attribute, float(numeric), source_field, N24TrustedSourceType.STRUCTURED,
        float(numeric), 1.0, N24AttributeMatch.EXACT,
        f"validated numeric {source_field}",
    )


def _n24m2_build_product_evidence(row: dict) -> dict:
    product_id = str(row.get("product_id"))
    title = str(row.get("title") or "")
    brand = str(row.get("brand") or "").strip()
    masked_title = mask_n24_canonical_brand_span(title, brand)
    details = _n24m2_raw_details(row.get("details"))
    categories = _n24m2_raw_categories(row.get("categories"))

    category_evidence = _n24m2_evidence(
        "category", categories if categories else None, "categories",
        N24TrustedSourceType.STRUCTURED if categories else N24TrustedSourceType.UNKNOWN,
        row.get("categories"), 1.0 if categories else 0.0,
        N24AttributeMatch.EXACT if categories else N24AttributeMatch.UNKNOWN,
        "raw catalogue hierarchy" if categories else "no usable raw category hierarchy",
    )
    brand_evidence = _n24m2_evidence(
        "brand", brand if brand else None, "brand",
        N24TrustedSourceType.BRAND if brand else N24TrustedSourceType.UNKNOWN,
        brand if brand else None, 1.0 if brand else 0.0,
        N24AttributeMatch.EXACT if brand else N24AttributeMatch.UNKNOWN,
        "canonical structured brand field" if brand else "brand is missing",
    )

    colour_evidence = None
    colour_components = []
    colour_source = None
    colour_raw = None
    for field in _N24M2_STRUCTURED_COLOUR_FIELDS:
        raw = details.get(field)
        components = _n24m2_colour_tokens(raw)
        if components:
            colour_components = components
            colour_source = f"details.{field}"
            colour_raw = str(raw)
            match_level = N24AttributeMatch.EXACT
            reason = "explicit structured colour/variant field"
            # A structured colour field can itself be wrong relative to the
            # product's own title (seen in the raw catalogue: a listing
            # whose Color field says "White" while its own title says
            # "...Black"). When the title independently names a colour that
            # the structured field never mentions at all, don't silently
            # trust the structured value as EXACT -- downgrade instead of
            # excluding, since we don't know which side is right.
            title_words = {
                _N24M_COLOUR_ALIASES.get(word, word)
                for word in _n24m2_title_attribute_tokens(masked_title, _N24M2_COLOUR_WORDS)
            }
            if title_words and not (title_words & set(components)):
                match_level = N24AttributeMatch.PARTIAL
                reason = "structured colour field conflicts with an independent colour word in the title"
            colour_evidence = _n24m2_evidence(
                "colour", components, colour_source, N24TrustedSourceType.VARIANT,
                colour_raw, 1.0, match_level, reason,
            )
            break
    if colour_evidence is None:
        colorway = _n24m2_title_colorway_tokens(masked_title)
        if colorway:
            colour_components = colorway
            colour_evidence = _n24m2_evidence(
                "colour", colorway, "title_colorway_pattern", N24TrustedSourceType.TITLE_VARIANT_PATTERN,
                masked_title, 0.85, N24AttributeMatch.EXACT,
                "structured colorway segment recovered from title (comma/slash-delimited colour list)",
            )
        else:
            title_colours = _n24m2_title_attribute_tokens(masked_title, _N24M2_COLOUR_WORDS)
            title_source = N24TrustedSourceType.TITLE_GENERIC
            reason = "generic title/model colour token is not trusted for exact colour"
            if title_colours:
                colour_evidence = _n24m2_evidence(
                    "colour", title_colours, "title_after_brand_mask", title_source,
                    masked_title, 0.25, N24AttributeMatch.UNKNOWN, reason,
                )
            else:
                colour_evidence = _n24m2_evidence(
                    "colour", None, None, N24TrustedSourceType.UNKNOWN, None,
                    0.0, N24AttributeMatch.UNKNOWN,
                    "no independent structured colour evidence",
                )

    audience = N24CanonicalAudience.UNKNOWN
    audience_evidence = None
    for field in _N24M2_STRUCTURED_AUDIENCE_FIELDS:
        raw = details.get(field)
        canonical = _n24m2_structural_audience(raw)
        if canonical != N24CanonicalAudience.UNKNOWN:
            audience = canonical
            audience_evidence = _n24m2_evidence(
                "audience", canonical.value, f"details.{field}",
                N24TrustedSourceType.STRUCTURED, str(raw), 1.0,
                N24AttributeMatch.EXACT, "explicit structured audience field",
            )
            break
    if audience_evidence is None:
        for raw in categories:
            canonical = _n24m2_structural_audience(raw)
            if canonical != N24CanonicalAudience.UNKNOWN:
                audience = canonical
                audience_evidence = _n24m2_evidence(
                    "audience", canonical.value, "categories",
                    N24TrustedSourceType.STRUCTURED, raw, 0.95,
                    N24AttributeMatch.EXACT, "explicit audience node in category hierarchy",
                )
                break
    if audience_evidence is None:
        canonical = _n24m2_explicit_title_audience(masked_title)
        if canonical != N24CanonicalAudience.UNKNOWN:
            audience = canonical
            audience_evidence = _n24m2_evidence(
                "audience", canonical.value, "title_after_brand_mask",
                N24TrustedSourceType.TITLE_EXPLICIT, masked_title, 0.85,
                N24AttributeMatch.EXACT, "explicit structural audience form in brand-masked title",
            )
        else:
            audience_evidence = _n24m2_evidence(
                "audience", None, None, N24TrustedSourceType.UNKNOWN, None,
                0.0, N24AttributeMatch.UNKNOWN,
                "no structured or explicit structural audience evidence",
            )

    age_group = "UNKNOWN"
    age_evidence = None
    for field in _N24M2_STRUCTURED_AGE_FIELDS:
        raw = details.get(field)
        canonical_age = _n24m2_age_from_raw(raw)
        if canonical_age != "UNKNOWN":
            age_group = canonical_age
            age_evidence = _n24m2_evidence(
                "age_group", age_group, f"details.{field}",
                N24TrustedSourceType.STRUCTURED, str(raw), 1.0,
                N24AttributeMatch.EXACT, "explicit structured age field",
            )
            break
    if age_evidence is None and audience != N24CanonicalAudience.UNKNOWN:
        age_group = _n24m2_age_from_audience(audience)
        age_evidence = _n24m2_evidence(
            "age_group", age_group, audience_evidence.source_field,
            audience_evidence.source_type, audience_evidence.raw_value,
            audience_evidence.confidence, N24AttributeMatch.EXACT,
            "age compatibility proven by trusted audience evidence",
        )
    if age_evidence is None:
        age_evidence = _n24m2_evidence(
            "age_group", None, None, N24TrustedSourceType.UNKNOWN, None,
            0.0, N24AttributeMatch.UNKNOWN, "no trusted age evidence",
        )

    materials, material_source, material_raw = _n24m2_structured_list(
        details, _N24M2_STRUCTURED_MATERIAL_FIELDS
    )
    if materials:
        material_evidence = _n24m2_evidence(
            "material", materials, material_source, N24TrustedSourceType.STRUCTURED,
            material_raw, 0.9, N24AttributeMatch.EXACT,
            "structured historical material evidence; soft-match only",
        )
    else:
        title_materials = _n24m2_title_attribute_tokens(masked_title, _N24M2_MATERIAL_WORDS)
        material_evidence = _n24m2_evidence(
            "material", title_materials or None,
            "title_after_brand_mask" if title_materials else None,
            N24TrustedSourceType.TITLE_GENERIC if title_materials else N24TrustedSourceType.UNKNOWN,
            masked_title if title_materials else None, 0.2 if title_materials else 0.0,
            N24AttributeMatch.UNKNOWN,
            "generic title material token is not trusted" if title_materials else "no structured material evidence",
        )

    size_raw = details.get("Size")
    size_evidence = _n24m2_evidence(
        "size", str(size_raw) if size_raw not in (None, "") else None,
        "details.Size" if size_raw not in (None, "") else None,
        N24TrustedSourceType.STRUCTURED if size_raw not in (None, "") else N24TrustedSourceType.UNKNOWN,
        str(size_raw) if size_raw not in (None, "") else None,
        0.6 if size_raw not in (None, "") else 0.0,
        N24AttributeMatch.UNKNOWN,
        "historical listing size cannot prove current availability",
    )

    styles, style_source, style_raw = _n24m2_structured_list(
        details, _N24M2_STRUCTURED_STYLE_FIELDS
    )
    style_evidence = _n24m2_evidence(
        "style_activity", styles or None, style_source,
        N24TrustedSourceType.STRUCTURED if styles else N24TrustedSourceType.UNKNOWN,
        style_raw, 0.8 if styles else 0.0,
        N24AttributeMatch.EXACT if styles else N24AttributeMatch.UNKNOWN,
        "structured contextual style/activity evidence" if styles else "no structured style/activity evidence",
    )

    trusted = {
        "category": category_evidence, "brand": brand_evidence,
        "colour": colour_evidence, "audience": audience_evidence,
        "age_group": age_evidence,
        "historical_price": _n24m2_numeric_evidence("historical_price", "price", row.get("price")),
        "rating": _n24m2_numeric_evidence("rating", "average_rating", row.get("average_rating")),
        "review_count": _n24m2_numeric_evidence("review_count", "rating_number", row.get("rating_number")),
        "material": material_evidence, "size": size_evidence,
        "style_activity": style_evidence,
    }
    return {
        "product_id": product_id, "row": row, "details": details,
        "title": title, "masked_title": masked_title,
        "categories": categories,
        "category_norms": {_n24m2_normalize(item) for item in categories},
        "brand": brand, "brand_norm": _n24m2_normalize(brand),
        "colour_components": colour_components,
        "primary_colour": colour_components[0] if colour_components else None,
        "secondary_colours": colour_components[1:] if len(colour_components) > 1 else [],
        "colour_source": colour_source, "colour_raw": colour_raw,
        "colour_mode": (
            "STRICT_SINGLE_COLOUR" if colour_components and len(set(colour_components)) == 1
            else "MIXED_COLOUR" if colour_components else "UNKNOWN"
        ),
        "audience": audience.value,
        "audience_source": audience_evidence.source_field,
        "audience_raw": audience_evidence.raw_value,
        "age_group": age_group,
        "materials": materials, "size": None if size_raw in (None, "") else str(size_raw),
        "styles": styles,
        "price": trusted["historical_price"].canonical_value,
        "rating": trusted["rating"].canonical_value,
        "review_count": trusted["review_count"].canonical_value,
        "trusted_attributes": {
            key: value.model_dump(mode="python") for key, value in trusted.items()
        },
    }


def _n24m2_build_catalogue_index():
    started = _n24m2_time.perf_counter()
    index = {}
    source_counts = _N24M2Counter()
    audience_counts = _N24M2Counter()
    for row in application_request_metadata_df.drop_duplicates("product_id").to_dict("records"):
        product = _n24m2_build_product_evidence(row)
        index[product["product_id"]] = product
        colour_source_type = product["trusted_attributes"]["colour"]["source_type"]
        source_counts[getattr(colour_source_type, "value", str(colour_source_type))] += 1
        audience_counts[product["audience"]] += 1
    rows = len(index)
    return index, {
        "catalogue_rows": rows,
        "structured_colour_count": sum(bool(item["colour_components"]) for item in index.values()),
        "structured_colour_coverage": round(100 * sum(bool(item["colour_components"]) for item in index.values()) / rows, 2),
        "colour_source_types": dict(source_counts),
        "audience_counts": dict(audience_counts),
        "brand_mask_changed_titles": sum(item["masked_title"] != item["title"] for item in index.values()),
        "build_seconds": round(_n24m2_time.perf_counter() - started, 3),
    }


N24M2_TRUSTED_CATALOGUE_INDEX, N24M2_TRUSTED_CATALOGUE_AUDIT = _n24m2_build_catalogue_index()

# N24M downstream integrations intentionally consume this stricter index.
# N23 functions retain their own frozen globals and are never rebound here.
N24M_CATALOGUE_INDEX = N24M2_TRUSTED_CATALOGUE_INDEX
N24M_CATALOGUE_AUDIT = N24M2_TRUSTED_CATALOGUE_AUDIT


def _n24m2_requested_audience(value: _N24M2Any) -> N24CanonicalAudience:
    return _n24m2_structural_audience(value)


def _n24m2_audience_compatible(actual: str, requested: N24CanonicalAudience) -> bool:
    compatible = {
        N24CanonicalAudience.MEN: {"MEN", "UNISEX_ADULT"},
        N24CanonicalAudience.WOMEN: {"WOMEN", "UNISEX_ADULT"},
        N24CanonicalAudience.UNISEX_ADULT: {"UNISEX_ADULT"},
        N24CanonicalAudience.BOYS: {"BOYS", "UNISEX_CHILD"},
        N24CanonicalAudience.GIRLS: {"GIRLS", "UNISEX_CHILD"},
        N24CanonicalAudience.KIDS: {"BOYS", "GIRLS", "KIDS", "UNISEX_CHILD", "TODDLER"},
        N24CanonicalAudience.UNISEX_CHILD: {"UNISEX_CHILD"},
        N24CanonicalAudience.TODDLER: {"TODDLER"},
    }
    return actual in compatible.get(requested, set())


def _n24m2_match_evidence(base, match_level, reason, *, canonical_value=None):
    return _n24m2_evidence(
        base.attribute,
        base.canonical_value if canonical_value is None else canonical_value,
        base.source_field, base.source_type, base.raw_value,
        base.confidence, match_level, reason,
    )


# A category hierarchy can itself be contaminated when records are merged
# across Amazon datasets.  These independent product-family signals prevent a
# raw leaf such as "T-Shirts" from overruling a conflicting main category,
# title, or structured product detail.
N24_DECLARATIVE_TAXONOMY_VERSION = "n24_declarative_taxonomy_v1"

# One declarative family vocabulary shared by catalogue canonicalisation,
# request resolution and (through N24_OUTFIT_SLOT_FAMILIES below) outfit slot
# eligibility.  Accessories are represented explicitly and never promoted to
# their parent product merely because Amazon filed them below that hierarchy.
N24_DECLARATIVE_TAXONOMY = {
    "SHIRTS": {
        "parent": "CLOTHING", "aliases": ["shirt", "shirts", "t-shirt", "t-shirts", "tee", "tees", "polo", "blouse", "top", "tops"],
        "subtypes": ["T_SHIRT", "BUTTON_DOWN", "POLO", "BLOUSE", "TOP"],
        "accessory_terms": ["shirt stay", "collar extender", "cuff link"],
        "conflicts": ["BEAUTY", "SHOES", "WATCHES", "HANDBAGS", "JEWELRY"],
    },
    "DRESSES": {
        "parent": "CLOTHING", "aliases": ["dress", "dresses", "gown", "gowns"],
        "subtypes": ["CASUAL_DRESS", "FORMAL_DRESS", "GOWN"],
        "accessory_terms": ["dress cover", "garment bag"],
        "conflicts": ["SHOES", "WATCHES", "HANDBAGS", "JEWELRY", "BEAUTY"],
    },
    "JACKETS": {
        "parent": "CLOTHING", "aliases": ["jacket", "jackets", "coat", "coats", "blazer", "blazers", "outerwear"],
        "subtypes": ["JACKET", "COAT", "BLAZER"],
        "accessory_terms": ["jacket cover", "coat hanger"],
        "conflicts": ["SHOES", "WATCHES", "HANDBAGS", "JEWELRY", "BEAUTY"],
    },
    "PANTS": {
        "parent": "CLOTHING", "aliases": ["pants", "trousers", "jeans", "leggings", "chinos", "shorts", "skirt", "skirts"],
        "subtypes": ["PANTS", "JEANS", "LEGGINGS", "CHINOS", "SHORTS", "SKIRT"],
        "accessory_terms": ["waist extender", "pants hanger"],
        "conflicts": ["SHOES", "WATCHES", "HANDBAGS", "JEWELRY", "BEAUTY"],
    },
    "SHOES": {
        "parent": "FOOTWEAR", "aliases": ["shoe", "shoes", "sneaker", "sneakers", "boot", "boots", "sandal", "sandals", "slipper", "slippers", "loafer", "loafers", "footwear"],
        "subtypes": ["SNEAKERS", "SANDALS", "BOOTS", "SLIPPERS", "LOAFERS"],
        "accessory_terms": ["cleaner", "polish", "insole", "insert", "shoe bag", "shoe tree", "lace", "laces", "care kit"],
        "accessory_patterns": [r"\bshoe\s+(?:cleaner|polish|care\s+kit|bag|tree|insert)s?\b", r"\b(?:replacement\s+)?insoles?\b", r"\bshoe\s*laces?\b"],
        "conflicts": ["BEAUTY", "WATCHES", "HANDBAGS", "JEWELRY"],
    },
    "WATCHES": {
        "parent": "ACCESSORIES", "aliases": ["watch", "watches", "wristwatch", "wristwatches", "timepiece"],
        "subtypes": ["WRIST_WATCH", "SMART_WATCH"],
        "accessory_terms": ["strap", "band", "case", "cover", "protector", "repair", "tool", "charger"],
        "accessory_patterns": [r"\bwatch\s+(?:strap|band|case|cover|protector|repair\s+tool|charger)s?\b", r"\b(?:strap|band|case|cover|protector)\s+for\s+(?:a\s+)?watch\b"],
        "conflicts": ["BEAUTY", "SHIRTS", "SHOES", "HANDBAGS", "JEWELRY"],
    },
    "HANDBAGS": {
        "parent": "ACCESSORIES", "aliases": ["handbag", "handbags", "purse", "purses", "tote", "totes", "clutch", "clutches", "wallet", "wallets"],
        "subtypes": ["HANDBAG", "PURSE", "TOTE", "CLUTCH", "WALLET"],
        "accessory_terms": ["organizer", "insert", "divider", "storage", "dust bag", "strap replacement"],
        "accessory_patterns": [r"\b(?:handbag|purse|tote)\s+(?:organizer|insert|divider)s?\b", r"\b(?:organizer|insert)\s+for\s+(?:handbags?|purses?|totes?)\b", r"\breplacement\s+(?:handbag|purse)\s+strap\b"],
        "conflicts": ["BEAUTY", "SHIRTS", "SHOES", "WATCHES", "JEWELRY"],
    },
    "JEWELRY": {
        "parent": "ACCESSORIES", "aliases": ["jewelry", "jewellery", "ring", "rings", "necklace", "necklaces", "bracelet", "bracelets", "earring", "earrings"],
        "subtypes": ["RING", "NECKLACE", "BRACELET", "EARRING"],
        "accessory_terms": ["organizer", "cleaner", "display stand", "holder", "box", "tray"],
        "accessory_patterns": [r"\bjewel(?:ry|lery)\s+(?:organizer|cleaner|display\s+stand|holder|box|tray)s?\b", r"\b(?:organizer|display\s+stand|holder)\s+for\s+jewel(?:ry|lery)\b"],
        "conflicts": ["BEAUTY", "SHIRTS", "SHOES", "WATCHES", "HANDBAGS"],
    },
    "BEAUTY": {
        "parent": "BEAUTY_GROOMING", "aliases": ["beauty", "razor", "razors", "shaver", "shaving", "cosmetic", "cosmetics", "makeup", "lipstick", "mascara", "perfume", "fragrance", "skincare", "grooming"],
        "subtypes": ["RAZOR", "SHAVING", "COSMETICS", "FRAGRANCE", "SKINCARE"],
        "accessory_terms": ["case", "holder", "replacement head"],
        "conflicts": ["SHIRTS", "DRESSES", "JACKETS", "PANTS", "SHOES", "WATCHES", "HANDBAGS", "JEWELRY"],
        "unsupported": True,
    },
    "SPORTING_EQUIPMENT": {
        "parent": "UNSUPPORTED", "aliases": ["macebell", "dumbbell", "kettlebell", "barbell", "weight plate"],
        "subtypes": [], "accessory_terms": [], "conflicts": ["SHIRTS", "DRESSES", "JACKETS", "PANTS", "SHOES", "WATCHES", "HANDBAGS", "JEWELRY"],
        "unsupported": True,
    },
    "PHONE_ACCESSORY": {
        "parent": "UNSUPPORTED", "aliases": ["phone case", "iphone case", "smartphone case", "screen protector"],
        "subtypes": [], "accessory_terms": [], "conflicts": ["SHIRTS", "DRESSES", "JACKETS", "PANTS", "SHOES", "WATCHES", "HANDBAGS", "JEWELRY"],
        "unsupported": True,
    },
    "CLEANING_CARE": {
        "parent": "UNSUPPORTED", "aliases": ["cleaner", "cleaning kit", "polish", "care kit"],
        "subtypes": [], "accessory_terms": [], "conflicts": ["SHIRTS", "DRESSES", "JACKETS", "PANTS", "SHOES", "WATCHES", "HANDBAGS", "JEWELRY"],
        "unsupported": True,
    },
}

N24_OUTFIT_SLOT_FAMILIES = {
    "top": {"SHIRTS"}, "bottom": {"PANTS"}, "footwear": {"SHOES"},
    "outerwear": {"JACKETS"}, "accessory": {"WATCHES", "HANDBAGS", "JEWELRY"},
}

_N24M2_PRODUCT_FAMILY_PATTERNS = {
    "SHIRTS": r"\b(?:shirt|shirts|t[ -]?shirt|tee|tees|polo|blouse|button[ -]?down)\b",
    "SHOES": r"\b(?:shoe|shoes|sneaker|sneakers|boot|boots|sandal|sandals|slipper|slippers|loafer|loafers|footwear)\b",
    "WATCHES": r"\b(?:watch|watches|wristwatch|wristwatches|timepiece)\b",
    "HANDBAGS": r"\b(?:handbag|handbags|purse|purses|tote|totes|clutch|clutches|wallet|wallets|crossbody\s+bags?|shoulder\s+bags?|satchels?|backpack\s+purses?)\b",
    # "dress" is also a common formality adjective for other product types
    # ("dress shoes", "dress shirt", "dress watch", "dress code", "dress
    # pants/socks/belt/boots") -- those are not the Dresses category, so they
    # are excluded by lookahead rather than treated as a family match.
    "DRESSES": r"\bgowns?\b|\bdress(?:es)?\b(?!\s+(?:shoe|shoes|shirt|shirts|watch|watches|code|pants|sock|socks|belt|belts|boot|boots))",
    "JEWELRY": r"\b(?:jewelry|jewellery|ring|rings|necklace|necklaces|bracelet|bracelets|earring|earrings)\b",
    "BEAUTY": r"\b(?:beauty|razor|razors|shav(?:e|er|ing)|cosmetic|cosmetics|makeup|lipstick|mascara|perfume|fragrance|skincare|grooming)\b",
    "JACKETS": r"\b(?:jacket|jackets|coat|coats|blazer|blazers|outerwear)\b",
    "PANTS": r"\b(?:pants|trousers|jeans|leggings|chinos|shorts|skirts?)\b",
    "SPORTING_EQUIPMENT": r"\b(?:macebells?|dumbbells?|kettlebells?|barbells?|weight\s+plates?)\b",
    "PHONE_ACCESSORY": (
        r"\bscreen\s+protectors?\b"
        r"|(?=.*\b(?:phone|iphone|ipad|ipod|smartphone|galaxy|android)\b)(?=.*\bcase\b)"
    ),
    "CLEANING_CARE": r"\b(?:cleaners?|cleaning\s+kits?|polish(?:es)?|care\s+kits?)\b",
}

_N24M2_REQUEST_FAMILIES = {
    "shirts": "SHIRTS", "t shirts": "SHIRTS",
    "shoes": "SHOES", "walking": "SHOES", "running": "SHOES",
    "athletic": "SHOES", "fashion sneakers": "SHOES", "sandals": "SHOES",
    "boots": "SHOES", "slippers": "SHOES", "flip flops": "SHOES",
    "watches": "WATCHES", "wrist watches": "WATCHES",
    "handbags and wallets": "HANDBAGS", "dresses": "DRESSES",
    "rings": "JEWELRY", "earrings": "JEWELRY", "necklaces": "JEWELRY", "bracelets": "JEWELRY",
    "beauty": "BEAUTY", "razors": "BEAUTY",
    "jackets": "JACKETS", "coats": "JACKETS", "pants": "PANTS",
    "jeans": "PANTS", "leggings": "PANTS", "accessories": "ACCESSORIES",
}


def _n24m2_main_category_family(value):
    normalized = _n24m2_normalize(value)
    if any(token in normalized for token in ("beauty", "personal care")):
        return "BEAUTY"
    if "watch" in normalized:
        return "WATCHES"
    if any(token in normalized for token in ("jewelry", "jewellery")):
        return "JEWELRY"
    if any(token in normalized for token in ("clothing", "fashion")):
        return None
    for family in ("SHIRTS", "DRESSES", "JACKETS", "PANTS", "SHOES", "HANDBAGS"):
        aliases = N24_DECLARATIVE_TAXONOMY[family]["aliases"]
        if any(_n24m2_re.search(rf"\b{_n24m2_re.escape(alias)}\b", normalized) for alias in aliases):
            return family
    return None


def _n24m2_listing_families(product):
    row = product.get("row", {})
    details = _n24m2_raw_details(row.get("details"))
    text = " ".join([
        str(row.get("title") or ""),
        " ".join(str(value) for key, value in details.items()
                 if key in {"Item Type", "Product Type", "Number of Blades", "Style Name"}),
    ])
    return {
        family for family, pattern in _N24M2_PRODUCT_FAMILY_PATTERNS.items()
        if _n24m2_re.search(pattern, text, flags=_n24m2_re.I)
    }


def _n24m2_accessory_conflict(product, wanted_family: str | None) -> str | None:
    """Return explicit accessory evidence that contradicts a parent product.

    This is family-generic and declarative: the terms live in the taxonomy,
    not in per-ASIN exceptions.  It addresses contaminated hierarchy records
    such as watch bands under Watches or shoe cleaner under Shoes.
    """
    spec = N24_DECLARATIVE_TAXONOMY.get(str(wanted_family or ""))
    if not spec:
        return None
    row = product.get("row", {})
    details = _n24m2_raw_details(row.get("details"))
    text = _n24m2_normalize(" ".join([
        str(row.get("title") or ""),
        str(details.get("Item Type") or ""),
        str(details.get("Product Type") or ""),
    ]))
    patterns = list(spec.get("accessory_patterns") or [])
    hits = [pattern for pattern in patterns if _n24m2_re.search(pattern, text)]
    if hits:
        return "listing proves an accessory/care product rather than the requested parent: " + ", ".join(hits)
    return None


def _n24m2_category_decision(product, requested):
    direct_hierarchy_match = _n24m_category_matches(product, requested)
    wanted_family = _N24M2_REQUEST_FAMILIES.get(_n24m2_normalize(requested))
    if not wanted_family:
        return (
            (True, "requested hierarchy node proven") if direct_hierarchy_match
            else (False, "requested category is absent from the raw hierarchy")
        )
    if wanted_family == "ACCESSORIES":
        return (
            (True, "requested broad accessory hierarchy proven") if direct_hierarchy_match
            else (False, "requested category is absent from the raw hierarchy")
        )
    row = product.get("row", {})
    main_family = _n24m2_main_category_family(row.get("main_category"))
    listing_families = _n24m2_listing_families(product)
    # The leading node is always the broad department label (e.g. "Clothing,
    # Shoes & Jewelry"), present verbatim on every record in this dataset --
    # not a specific-product-family signal.  Its own substrings ("Shoes",
    # "Jewelry") would otherwise falsely register as a conflicting family on
    # every single product regardless of category, so it is excluded here.
    hierarchy_text = " > ".join(str(item) for item in product.get("categories", [])[1:])
    hierarchy_families = {
        family for family, pattern in _N24M2_PRODUCT_FAMILY_PATTERNS.items()
        if _n24m2_re.search(pattern, hierarchy_text, flags=_n24m2_re.I)
    }
    # Broad family requests are satisfied by a compatible subtype.  For
    # example, Jeans and Skirts are valid members of the Pants/bottom family
    # even if the raw hierarchy never contains the literal word "Pants".
    # Narrow subtype requests (Walking, T-Shirts, etc.) still require their
    # direct hierarchy node and cannot be widened by this rule.
    broad_family_terms = {
        "shirts", "shoes", "watches", "handbags and wallets", "dresses",
        "jackets", "coats", "pants", "accessories", "beauty",
    }
    family_proven = (
        _n24m2_normalize(requested) in broad_family_terms
        and wanted_family in (listing_families | hierarchy_families | ({main_family} if main_family else set()))
    )
    if not direct_hierarchy_match and not family_proven:
        return False, "requested category is absent from the raw hierarchy"
    contradictory = {
        family for family in (listing_families | hierarchy_families) if family != wanted_family
    }
    if main_family and main_family != wanted_family:
        return False, f"raw main_category proves conflicting {main_family} family"
    accessory_conflict = _n24m2_accessory_conflict(product, wanted_family)
    if accessory_conflict:
        return False, accessory_conflict
    if contradictory and wanted_family not in listing_families:
        return False, "independent title/details prove conflicting product family: " + ", ".join(sorted(contradictory))
    return True, (
        "compatible canonical family/subtype proven with no independent product-family contradiction"
        if family_proven and not direct_hierarchy_match
        else "raw hierarchy proven with no independent product-family contradiction"
    )


def evaluate_n24_trusted_eligibility(
    candidate: str | dict,
    request,
    sidecar: dict | None = None,
) -> N24TrustedEligibilityResult:
    if not isinstance(request, N24ValidatedRecommendationRequest):
        request = N24ValidatedRecommendationRequest.model_validate(request)
    product_id = str(candidate.get("product_id")) if isinstance(candidate, dict) else str(candidate)
    product = candidate if isinstance(candidate, dict) else N24M2_TRUSTED_CATALOGUE_INDEX.get(product_id)
    if not product:
        missing = _n24m2_evidence(
            "product_id", product_id, "product_id", N24TrustedSourceType.UNKNOWN,
            product_id, 0.0, N24AttributeMatch.VIOLATION,
            "product is absent from the processed catalogue",
        )
        return N24TrustedEligibilityResult(
            product_id=product_id, eligible=False, attribute_evidence={"product_id": missing},
            hard_constraint_count=1, exact_constraint_count=0, partial_constraint_count=0,
            unknown_constraint_count=0, violation_count=1, match_score=0.0,
        )
    sidecar = _n24m2_deepcopy(
        sidecar or N24M_REQUEST_SIDECARS.get(request.request_fingerprint)
        or _n24m_default_sidecar()
    )
    evaluated = {}
    trusted = {
        key: N24TrustedAttributeEvidence.model_validate(value)
        for key, value in product["trusted_attributes"].items()
    }

    if request.categories:
        base = trusted["category"]
        category_decisions = [_n24m2_category_decision(product, wanted) for wanted in request.categories]
        ok = base.match_level == N24AttributeMatch.EXACT and all(item[0] for item in category_decisions)
        level = N24AttributeMatch.EXACT if ok else (
            N24AttributeMatch.UNKNOWN if base.match_level == N24AttributeMatch.UNKNOWN
            else N24AttributeMatch.VIOLATION
        )
        evaluated["category"] = _n24m2_match_evidence(
            base, level,
            "all requested taxonomy nodes independently proven" if ok
            else "; ".join(item[1] for item in category_decisions if not item[0]),
        )

    if request.brands:
        base = trusted["brand"]
        wanted = {_n24m2_normalize(item) for item in request.brands}
        if base.match_level == N24AttributeMatch.UNKNOWN:
            level = N24AttributeMatch.UNKNOWN
        else:
            level = N24AttributeMatch.EXACT if _n24m2_brand_matches(product["brand_norm"], wanted) else N24AttributeMatch.VIOLATION
        evaluated["brand"] = _n24m2_match_evidence(
            base, level, "canonical structured brand equality" if level == N24AttributeMatch.EXACT else "structured brand does not match request",
        )

    if request.colours:
        base = trusted["colour"]
        wanted = [
            _N24M_COLOUR_ALIASES.get(_n24m2_normalize(item), _n24m2_normalize(item))
            for item in request.colours
        ]
        components = list(product["colour_components"])
        allow_mixed = bool(sidecar.get("allow_mixed_colours"))
        if not components or base.match_level != N24AttributeMatch.EXACT:
            level = N24AttributeMatch.UNKNOWN
            reason = "no independent structured colour evidence"
        elif len(wanted) == 1:
            if all(item == wanted[0] for item in components):
                level, reason = N24AttributeMatch.EXACT, "trusted components prove strict single colour"
            elif wanted[0] in components:
                level = N24AttributeMatch.EXACT if allow_mixed else N24AttributeMatch.PARTIAL
                reason = "trusted mixed colour explicitly allowed" if allow_mixed else "requested colour is only one mixed component"
            else:
                level, reason = N24AttributeMatch.VIOLATION, "trusted colour components do not contain request"
        else:
            requested_set, component_set = set(wanted), set(components)
            if component_set == requested_set:
                level, reason = N24AttributeMatch.EXACT, "trusted mixed components exactly match requested colours"
            elif requested_set.issubset(component_set):
                level, reason = N24AttributeMatch.PARTIAL, "trusted product contains additional unrequested colours"
            else:
                level, reason = N24AttributeMatch.VIOLATION, "trusted components do not prove every requested colour"
        evaluated["colour"] = _n24m2_match_evidence(
            base, level, reason,
            canonical_value={
                "primary_colour": product["primary_colour"],
                "secondary_colours": product["secondary_colours"],
                "colour_components": components,
                "mode": product["colour_mode"],
            },
        )

    if request.recipient:
        base = trusted["audience"]
        requested = _n24m2_requested_audience(request.recipient)
        if base.match_level == N24AttributeMatch.UNKNOWN or product["audience"] == "UNKNOWN":
            level = N24AttributeMatch.UNKNOWN
        else:
            level = N24AttributeMatch.EXACT if _n24m2_audience_compatible(product["audience"], requested) else N24AttributeMatch.VIOLATION
        evaluated["audience"] = _n24m2_match_evidence(
            base, level, "trusted audience is compatible" if level == N24AttributeMatch.EXACT else "trusted audience is unknown or incompatible",
        )
        age_base = trusted["age_group"]
        requested_age = (
            "ADULT" if requested in {N24CanonicalAudience.MEN, N24CanonicalAudience.WOMEN, N24CanonicalAudience.UNISEX_ADULT}
            else "TODDLER" if requested == N24CanonicalAudience.TODDLER else "CHILD"
        )
        if age_base.match_level == N24AttributeMatch.UNKNOWN or product["age_group"] == "UNKNOWN":
            age_level = N24AttributeMatch.UNKNOWN
        else:
            age_ok = product["age_group"] == requested_age or (
                requested == N24CanonicalAudience.KIDS and product["age_group"] == "TODDLER"
            )
            age_level = N24AttributeMatch.EXACT if age_ok else N24AttributeMatch.VIOLATION
        evaluated["age_group"] = _n24m2_match_evidence(
            age_base, age_level, "trusted age is compatible" if age_level == N24AttributeMatch.EXACT else "trusted age is unknown or incompatible",
        )

    if request.minimum_price is not None or request.maximum_price is not None:
        base = trusted["historical_price"]
        price = product["price"]
        if base.match_level == N24AttributeMatch.UNKNOWN or price is None:
            level = N24AttributeMatch.UNKNOWN
        else:
            ok = (
                (request.minimum_price is None or price >= request.minimum_price)
                and (request.maximum_price is None or price <= request.maximum_price)
            )
            level = N24AttributeMatch.EXACT if ok else N24AttributeMatch.VIOLATION
        evaluated["historical_price"] = _n24m2_match_evidence(
            base, level, "numeric historical price satisfies request" if level == N24AttributeMatch.EXACT else "historical price is unknown or outside request",
        )

    minimum_rating = sidecar.get("minimum_rating")
    if minimum_rating is not None:
        base = trusted["rating"]
        rating = product["rating"]
        if base.match_level == N24AttributeMatch.UNKNOWN or rating is None:
            level = N24AttributeMatch.UNKNOWN
        else:
            ok = rating > float(minimum_rating) if sidecar.get("rating_exclusive") else rating >= float(minimum_rating)
            level = N24AttributeMatch.EXACT if ok else N24AttributeMatch.VIOLATION
        evaluated["rating"] = _n24m2_match_evidence(
            base, level, "numeric historical rating satisfies request" if level == N24AttributeMatch.EXACT else "rating is unknown or below threshold",
        )

    if request.excluded_product_ids:
        forbidden = {str(item).casefold() for item in request.excluded_product_ids}
        level = N24AttributeMatch.VIOLATION if product_id.casefold() in forbidden else N24AttributeMatch.EXACT
        evaluated["excluded_product"] = _n24m2_evidence(
            "excluded_product", product_id, "product_id", N24TrustedSourceType.STRUCTURED,
            product_id, 1.0, level,
            "product is not excluded" if level == N24AttributeMatch.EXACT else "product ID is explicitly excluded",
        )
    if request.excluded_brands:
        base = trusted["brand"]
        forbidden = {_n24m2_normalize(item) for item in request.excluded_brands}
        if base.match_level == N24AttributeMatch.UNKNOWN:
            level = N24AttributeMatch.UNKNOWN
        else:
            level = N24AttributeMatch.VIOLATION if _n24m2_brand_matches(product["brand_norm"], forbidden) else N24AttributeMatch.EXACT
        evaluated["excluded_brand"] = _n24m2_match_evidence(base, level, "trusted brand exclusion evaluated")
    if request.excluded_categories:
        base = trusted["category"]
        if base.match_level == N24AttributeMatch.UNKNOWN:
            level = N24AttributeMatch.UNKNOWN
        else:
            violates = any(_n24m_category_matches(product, item) for item in request.excluded_categories)
            level = N24AttributeMatch.VIOLATION if violates else N24AttributeMatch.EXACT
        evaluated["excluded_category"] = _n24m2_match_evidence(base, level, "trusted category exclusion evaluated")
    if request.excluded_colours:
        base = trusted["colour"]
        forbidden = {
            _N24M_COLOUR_ALIASES.get(_n24m2_normalize(item), _n24m2_normalize(item))
            for item in request.excluded_colours
        }
        if base.match_level != N24AttributeMatch.EXACT or not product["colour_components"]:
            level = N24AttributeMatch.UNKNOWN
        else:
            level = N24AttributeMatch.VIOLATION if set(product["colour_components"]) & forbidden else N24AttributeMatch.EXACT
        evaluated["excluded_colour"] = _n24m2_match_evidence(base, level, "trusted colour exclusion evaluated")
    excluded_audiences = [_n24m2_requested_audience(item) for item in sidecar.get("excluded_audiences", [])]
    if excluded_audiences:
        base = trusted["audience"]
        if base.match_level == N24AttributeMatch.UNKNOWN or product["audience"] == "UNKNOWN":
            level = N24AttributeMatch.UNKNOWN
        else:
            violates = any(_n24m2_audience_compatible(product["audience"], item) for item in excluded_audiences)
            level = N24AttributeMatch.VIOLATION if violates else N24AttributeMatch.EXACT
        evaluated["excluded_audience"] = _n24m2_match_evidence(base, level, "trusted audience exclusion evaluated")

    levels = [item.match_level for item in evaluated.values()]
    exact = sum(item == N24AttributeMatch.EXACT for item in levels)
    partial = sum(item == N24AttributeMatch.PARTIAL for item in levels)
    unknown = sum(item == N24AttributeMatch.UNKNOWN for item in levels)
    violation = sum(item == N24AttributeMatch.VIOLATION for item in levels)
    eligible = bool(levels) and exact == len(levels) and partial == unknown == violation == 0
    score = 0.0 if not levels else round(100.0 * exact / len(levels), 2)
    return N24TrustedEligibilityResult(
        product_id=product_id, eligible=eligible, attribute_evidence=evaluated,
        hard_constraint_count=len(levels), exact_constraint_count=exact,
        partial_constraint_count=partial, unknown_constraint_count=unknown,
        violation_count=violation, match_score=score,
    )


def evaluate_n24_product_eligibility(product_id: str, request, sidecar: dict | None = None):
    trusted_result = evaluate_n24_trusted_eligibility(product_id, request, sidecar)
    return N24ProductEligibilityEvidence(
        product_id=trusted_result.product_id, eligible=trusted_result.eligible,
        attribute_matches={
            key: evidence.match_level for key, evidence in trusted_result.attribute_evidence.items()
        },
        attribute_evidence={
            key: evidence.model_dump(mode="json")
            for key, evidence in trusted_result.attribute_evidence.items()
        },
        hard_constraint_count=trusted_result.hard_constraint_count,
        exact_constraint_count=trusted_result.exact_constraint_count,
        partial_constraint_count=trusted_result.partial_constraint_count,
        unknown_constraint_count=trusted_result.unknown_constraint_count,
        violation_count=trusted_result.violation_count,
        match_score=trusted_result.match_score,
        engine_version=N24M2_ELIGIBILITY_ENGINE_VERSION,
    )


def _n24m2_level(value) -> N24AttributeMatch:
    return value if isinstance(value, N24AttributeMatch) else N24AttributeMatch(value)


def _n24m2_fast_exact(product: dict, product_id: str, request, sidecar: dict) -> bool:
    trusted = product["trusted_attributes"]
    if request.categories:
        if _n24m2_level(trusted["category"]["match_level"]) != N24AttributeMatch.EXACT:
            return False
        if not all(_n24m2_category_decision(product, wanted)[0] for wanted in request.categories):
            return False
    if request.brands:
        if _n24m2_level(trusted["brand"]["match_level"]) != N24AttributeMatch.EXACT:
            return False
        if not _n24m2_brand_matches(product["brand_norm"], {_n24m2_normalize(item) for item in request.brands}):
            return False
    if request.colours:
        if _n24m2_level(trusted["colour"]["match_level"]) != N24AttributeMatch.EXACT:
            return False
        components = product["colour_components"]
        wanted = [
            _N24M_COLOUR_ALIASES.get(_n24m2_normalize(item), _n24m2_normalize(item))
            for item in request.colours
        ]
        if not components:
            return False
        if len(wanted) == 1:
            if all(item == wanted[0] for item in components):
                pass
            elif sidecar.get("allow_mixed_colours") and wanted[0] in components:
                pass
            else:
                return False
        elif set(components) != set(wanted):
            return False
    if request.recipient:
        if _n24m2_level(trusted["audience"]["match_level"]) != N24AttributeMatch.EXACT:
            return False
        requested = _n24m2_requested_audience(request.recipient)
        if not _n24m2_audience_compatible(product["audience"], requested):
            return False
        if _n24m2_level(trusted["age_group"]["match_level"]) != N24AttributeMatch.EXACT:
            return False
        requested_age = (
            "ADULT" if requested in {N24CanonicalAudience.MEN, N24CanonicalAudience.WOMEN, N24CanonicalAudience.UNISEX_ADULT}
            else "TODDLER" if requested == N24CanonicalAudience.TODDLER else "CHILD"
        )
        if product["age_group"] != requested_age and not (
            requested == N24CanonicalAudience.KIDS and product["age_group"] == "TODDLER"
        ):
            return False
    price = product["price"]
    if request.minimum_price is not None and (price is None or price < request.minimum_price):
        return False
    if request.maximum_price is not None and (price is None or price > request.maximum_price):
        return False
    minimum_rating = sidecar.get("minimum_rating")
    if minimum_rating is not None:
        rating = product["rating"]
        if rating is None:
            return False
        if sidecar.get("rating_exclusive"):
            if rating <= float(minimum_rating):
                return False
        elif rating < float(minimum_rating):
            return False
    if request.excluded_product_ids and product_id.casefold() in {
        str(item).casefold() for item in request.excluded_product_ids
    }:
        return False
    if request.excluded_brands:
        if _n24m2_level(trusted["brand"]["match_level"]) != N24AttributeMatch.EXACT:
            return False
        if _n24m2_brand_matches(product["brand_norm"], {_n24m2_normalize(item) for item in request.excluded_brands}):
            return False
    if request.excluded_categories:
        if _n24m2_level(trusted["category"]["match_level"]) != N24AttributeMatch.EXACT:
            return False
        if any(_n24m_category_matches(product, item) for item in request.excluded_categories):
            return False
    if request.excluded_colours:
        if _n24m2_level(trusted["colour"]["match_level"]) != N24AttributeMatch.EXACT:
            return False
        forbidden = {
            _N24M_COLOUR_ALIASES.get(_n24m2_normalize(item), _n24m2_normalize(item))
            for item in request.excluded_colours
        }
        if set(product["colour_components"]) & forbidden:
            return False
    excluded_audiences = [_n24m2_requested_audience(item) for item in sidecar.get("excluded_audiences", [])]
    if excluded_audiences:
        if _n24m2_level(trusted["audience"]["match_level"]) != N24AttributeMatch.EXACT:
            return False
        if any(_n24m2_audience_compatible(product["audience"], item) for item in excluded_audiences):
            return False
    return True


def _n24m_fast_eligible(product: dict, product_id: str, request, sidecar: dict) -> bool:
    return _n24m2_fast_exact(product, product_id, request, sidecar)


def _n24m_eligible_ids(request, sidecar: dict) -> set[str]:
    return {
        product_id for product_id, product in N24M2_TRUSTED_CATALOGUE_INDEX.items()
        if _n24m2_fast_exact(product, product_id, request, sidecar)
    }


if "N24M2_FROZEN_RANK_CACHE" not in globals():
    N24M2_FROZEN_RANK_CACHE = {}


def get_n24_recommendations_from_validated_state(
    request,
    top_n=10,
    candidate_pool_size=REQUEST_AWARE_DEFAULT_CANDIDATE_POOL_SIZE,
):
    """Gate on trusted exact eligibility, then preserve frozen ranking order."""
    request = N24ValidatedRecommendationRequest.model_validate(request.model_dump(mode="python"))
    if not isinstance(top_n, int) or top_n < 1:
        raise ValueError("top_n must be a positive integer")
    sidecar = _n24m2_deepcopy(
        N24M_REQUEST_SIDECARS.get(request.request_fingerprint)
        or _n24m_sidecar(N24M_CURRENT_CHAT_ID.get())
    )
    gate_started = _n24m2_time.perf_counter()
    eligible_ids = _n24m_eligible_ids(request, sidecar)
    gate_seconds = _n24m2_time.perf_counter() - gate_started

    ranking_request = request.model_copy(deep=True)
    ranking_request.excluded_categories = []
    ranking_request.excluded_brands = []
    ranking_request.excluded_colours = []
    ranking_request.excluded_materials = []
    ranking_request.excluded_sizes = []
    ranking_request.excluded_product_ids = []
    depth = 750 if request.brands and request.categories else 2500 if request.categories else 3000
    depth = max(depth, top_n * 40)
    cache_payload = {
        "truth_version": N24M2_ELIGIBILITY_ENGINE_VERSION,
        "profile_id": request.profile_id, "categories": request.categories,
        "brands": request.brands, "colours": request.colours,
        "materials": request.materials, "sizes": request.sizes,
        "minimum_price": request.minimum_price, "maximum_price": request.maximum_price,
        "occasions": request.occasions, "recipient": request.recipient, "depth": depth,
    }
    cache_key = _n24m2_json.dumps(cache_payload, sort_keys=True, default=str)
    frozen = N24M2_FROZEN_RANK_CACHE.get(cache_key)
    if eligible_ids and frozen is None:
        frozen = _n24c_run_frozen_ranking(
            ranking_request, depth, max(candidate_pool_size, depth)
        )
        N24M2_FROZEN_RANK_CACHE[cache_key] = {
            **frozen, "recommendations": frozen["recommendations"].copy(deep=True),
        }
        while len(N24M2_FROZEN_RANK_CACHE) > 48:
            N24M2_FROZEN_RANK_CACHE.pop(next(iter(N24M2_FROZEN_RANK_CACHE)))
    elif frozen is not None:
        frozen = {**frozen, "recommendations": frozen["recommendations"].copy(deep=True)}

    if not eligible_ids or frozen is None:
        ranked = application_request_metadata_df.head(0).copy()
    else:
        ranked = frozen["recommendations"].copy()
        if not ranked.empty:
            ranked = ranked.loc[
                ranked["product_id"].astype(str).isin(eligible_ids)
            ].drop_duplicates("product_id").copy()
    selected = ranked.head(top_n).reset_index(drop=True)
    eligibility = {}
    if not selected.empty:
        eligibility = {
            product_id: evaluate_n24_product_eligibility(product_id, request, sidecar)
            for product_id in selected["product_id"].astype(str)
        }
        selected["request_rank"] = _n24l_np.arange(1, len(selected) + 1, dtype=_n24l_np.int32)
        selected["n24m_match_score"] = selected["product_id"].astype(str).map(
            lambda item: eligibility[item].match_score
        )
        selected["n24m_match_evidence"] = selected["product_id"].astype(str).map(
            lambda item: eligibility[item].model_dump(mode="json")
        )
        selected["matched_request_categories"] = ", ".join(request.categories)
        selected["matched_request_brands"] = ", ".join(request.brands)
        selected["matched_request_colors"] = selected["product_id"].astype(str).map(
            lambda item: ", ".join(N24M2_TRUSTED_CATALOGUE_INDEX[item]["colour_components"])
        )
        selected["matched_request_materials"] = ", ".join(request.materials)
        selected["matched_request_sizes"] = ", ".join(request.sizes)
        selected["matched_request_occasions"] = ", ".join(request.occasions)
        selected["request_explanation"] = selected["product_id"].astype(str).map(
            lambda item: "Matches your requested " + ", ".join(
                key.replace("historical_price", "price").replace("age_group", "age group").replace("_", " ")
                for key, value in eligibility[item].attribute_matches.items()
                if value == N24AttributeMatch.EXACT
            ) + "."
        )
    parsed = _n24c_structured_parsed_request(request)
    parsed["n24m2_provenance_contract_version"] = N24M2_PROVENANCE_CONTRACT_VERSION
    parsed["n24m2_sidecar"] = sidecar
    count = int(len(selected))
    return {
        "profile_id": request.profile_id, "parsed_request": parsed,
        "validated_request": request, "recommendations": selected,
        "recommendation_count": count, "requested_result_count": top_n,
        "exact_match_count": count, "eligible_catalogue_count": len(eligible_ids),
        "exact_match_shortfall": count < top_n, "no_exact_match": count == 0,
        "result_mode": "no_exact_matches" if count == 0 else "partial_exact_matches" if count < top_n else "complete_exact_matches",
        "constraints_relaxed": False,
        "hard_constraints_applied": {
            "categories": request.categories, "brands": request.brands,
            "colours": request.colours, "recipient": request.recipient,
            "minimum_price": request.minimum_price, "maximum_price": request.maximum_price,
            "minimum_rating": sidecar.get("minimum_rating"),
        },
        "exclusions_applied": {
            "categories": request.excluded_categories, "brands": request.excluded_brands,
            "colours": request.excluded_colours, "product_ids": request.excluded_product_ids,
            "audiences": sidecar.get("excluded_audiences", []),
        },
        "relaxation_candidates": _n24m_relaxation_options(request, sidecar) if count < top_n else [],
        "clarification_needed": False, "clarification_question": None,
        "category_constraint_mode": "n24m2_trusted_taxonomy_with_contradiction_guard",
        "engine_version": N24M2_ELIGIBILITY_ENGINE_VERSION,
        "eligibility_overhead_seconds": round(gate_seconds, 6),
        "ranking_started_after_trusted_gate": True,
    }


if "n24m2_pre_match_score" not in globals():
    n24m2_pre_match_score = calculate_product_match_score


def calculate_product_match_score(product_row, parsed_request):
    score = getattr(product_row, "n24m_match_score", None)
    evidence = getattr(product_row, "n24m_match_evidence", None)
    if score is not None and not (
        isinstance(score, float) and _n24m2_math.isnan(score)
    ) and isinstance(evidence, dict) and evidence.get("engine_version") == N24M2_ELIGIBILITY_ENGINE_VERSION:
        names = [
            key.replace("historical_price", "price").replace("age_group", "age group").replace("_", " ")
            for key, value in (evidence.get("attribute_matches") or {}).items()
            if value == "EXACT"
        ]
        phrase = "Matches your requested " + ", ".join(names) if names else "Trusted catalogue match"
        return round(float(score), 2), phrase
    return n24m2_pre_match_score(product_row, parsed_request)


if "n24m2_pre_card_builder" not in globals():
    n24m2_pre_card_builder = build_final_recommendation_cards


def build_final_recommendation_cards(request_result: dict, top_n=FINAL_PRODUCT_CARD_DEFAULT_TOP_N):
    built = n24m2_pre_card_builder(request_result, top_n=top_n)
    cards = built.get("cards")
    if cards is None or cards.empty:
        return built
    cards = cards.copy()
    records = cards.to_dict("records")
    if not any(
        isinstance(row.get("eligibility_evidence"), dict)
        and row["eligibility_evidence"].get("engine_version") == N24M2_ELIGIBILITY_ENGINE_VERSION
        for row in records
    ):
        return built
    cards["trusted_eligibility_evidence"] = cards.get("eligibility_evidence")
    cards["matched_attributes"] = [[] for _ in range(len(cards))]
    explanations = []
    for row in records:
        evidence = row.get("eligibility_evidence")
        evidence = evidence if isinstance(evidence, dict) else {}
        names = [
            key.replace("historical_price", "price").replace("age_group", "age group").replace("_", " ")
            for key, value in (evidence.get("attribute_matches") or {}).items()
            if value == "EXACT"
        ]
        natural = "Matches your requested " + (
            ", ".join(names) if names else "catalogue criteria"
        ) + "."
        old = str(row.get("recommendation_explanation") or "")
        if "Trust evidence:" in old:
            natural += " Trust evidence:" + old.split("Trust evidence:", 1)[1]
        explanations.append(natural)
    cards["recommendation_explanation"] = explanations
    built["cards"] = cards
    built["product_card_version"] = "n24m2_trusted_provenance_cards_v1"
    return built


N24_SUPPORTED_CAPABILITY_MANIFEST = {
    **N24_SUPPORTED_CAPABILITY_MANIFEST,
    "trusted_provenance_contract": N24M2_PROVENANCE_CONTRACT_VERSION,
    "trusted_eligibility_engine": N24M2_ELIGIBILITY_ENGINE_VERSION,
    "title_generic_exact_colour": False,
    "brand_masking": True,
    "unknown_exact": False,
    "additional_llm_calls_for_truth": 0,
}


def run_n24m2_contract_tests():
    tests = {}
    diagnostics = {
        "B007IFWHRY": "WHITE MOUNTAIN Carly",
        "B01DQCBHT6": "WHITE MOUNTAIN Helga",
        "B08R7FKZ5Q": "WHITE MOUNTAIN Hayleigh",
        "B0C62MD9JY": "Timberland White Ledge",
    }
    profile = N24A_GOLDEN_PROFILE_ID
    white_request = build_n24_validated_recommendation_request(
        profile, N24HardRequestState(categories=["Shoes"], colours=["white"]),
        N24ExclusionState(),
    )
    diagnostic_results = {}
    for product_id, label in diagnostics.items():
        product = N24M2_TRUSTED_CATALOGUE_INDEX.get(product_id)
        result = evaluate_n24_trusted_eligibility(product_id, white_request)
        diagnostic_results[label] = {
            "product_id": product_id,
            "raw_colour_source": None if product is None else product["colour_source"],
            "trusted_source_type": None if product is None else getattr(product["trusted_attributes"]["colour"]["source_type"], "value", str(product["trusted_attributes"]["colour"]["source_type"])),
            "trusted_match": None if product is None else getattr(product["trusted_attributes"]["colour"]["match_level"], "value", str(product["trusted_attributes"]["colour"]["match_level"])),
            "eligible": result.eligible,
        }
    tests["brand_masking_generic"] = mask_n24_canonical_brand_span(
        "WHITE MOUNTAIN Women's Carly Footbed Sandal", "WHITE MOUNTAIN"
    ) == "Women's Carly Footbed Sandal"
    tests["diagnostics_not_false_white"] = all(not item["eligible"] for item in diagnostic_results.values())
    tests["unknown_not_exact"] = all(
        item["trusted_match"] == "UNKNOWN" for item in diagnostic_results.values()
    )
    tests["registry_preserved"] = bool(N24_CATALOGUE_CAPABILITY_REGISTRY)
    tests["n23_callable_preserved"] = callable(n24l_n23_workspace_controller)
    tests["engine_n24"] = get_shopmate_engine() == "n24"
    return {
        "tests": tests, "all_passed": all(tests.values()),
        "diagnostic_products": diagnostic_results,
    }


N24M2_CONTRACT_TEST_REPORT = run_n24m2_contract_tests()
set_shopmate_engine("n24")
N24M2_INTEGRATION_STATUS = {
    "section_version": N24M2_SECTION_VERSION,
    "provenance_contract": N24M2_PROVENANCE_CONTRACT_VERSION,
    "eligibility_engine": N24M2_ELIGIBILITY_ENGINE_VERSION,
    "catalogue_rows": len(N24M2_TRUSTED_CATALOGUE_INDEX),
    "catalogue_audit": N24M2_TRUSTED_CATALOGUE_AUDIT,
    "contract_tests": N24M2_CONTRACT_TEST_REPORT,
    "engine": get_shopmate_engine(),
    "n23_preserved": callable(n24l_n23_workspace_controller),
    "additional_llm_calls": 0,
}

print("SECTION 153E7N24M2 - TRUSTED CATALOGUE ATTRIBUTE TRUTH LAYER ready")
print(_n24m2_json.dumps(N24M2_INTEGRATION_STATUS, indent=2, default=str))


# ============================================================
# SECTION 153E7N24M2X - CANONICAL PRODUCT SEMANTICS + CONSTRAINT EVALUATION
# Consolidation migration, Stage 1 + Stage 2. Additive only: nothing above
# this point is modified or removed. Reuses the already-computed N24M2
# trusted-attribute evidence (_n24m2_build_product_evidence) rather than
# recomputing it, and formally names evaluate_n24_trusted_eligibility as the
# one ConstraintEvaluation entry point that eligibility, Match %, cards, and
# (from Stage 5) outfits are meant to consume. Does not touch N23.
# ============================================================

N24_CANONICAL_CONTRACT_VERSION = "n24_canonical_semantics_v1"

# The outfit runtime (notebook cell 394, N13-N18) has always kept its own,
# disconnected slot-category vocabulary. This does not replace it yet
# (Stage 5 does that) -- it makes the same vocabulary reachable from one
# place alongside the already-load-bearing _N24M_CATEGORY_ALIASES table that
# _n24m_category_matches (and therefore N24M2's own category decision) uses.
N24_OUTFIT_SLOT_CATEGORY_TERMS = {
    "top": ["T-Shirts", "Shirts", "Casual Button-Down Shirts", "Polos", "Dress Shirts", "Blouses", "Tops"],
    "bottom": ["Jeans", "Pants", "Casual", "Chinos", "Skirts", "Shorts"],
    "footwear": ["Fashion Sneakers", "Loafers & Slip-Ons", "Oxfords", "Flats", "Pumps", "Sandals", "Shoes"],
    "outerwear": ["Casual Jackets", "Blazers", "Lightweight Jackets", "Denim Jackets", "Sport Coats & Blazers"],
    "accessory": ["Belts", "Wrist Watches", "Sunglasses", "Wallets", "Necklaces", "Bracelets",
                  "Handbags & Shoulder Bags", "Crossbody Bags"],
}


def n24_canonical_categories_for(phrase) -> list[str]:
    """One lookup for 'what raw catalogue categories does this phrase mean',
    covering both ordinary search vocabulary (_N24M_CATEGORY_ALIASES) and
    outfit slot vocabulary (N24_OUTFIT_SLOT_CATEGORY_TERMS). Existing callers
    of _n24m_category_matches / _N24M_CATEGORY_ALIASES are unaffected.
    """
    normalized = _n24m2_normalize(phrase)
    if normalized in _N24M_CATEGORY_ALIASES:
        return list(_N24M_CATEGORY_ALIASES[normalized])
    if normalized in N24_OUTFIT_SLOT_CATEGORY_TERMS:
        return list(N24_OUTFIT_SLOT_CATEGORY_TERMS[normalized])
    return []


def _n24m2_category_hierarchy_families(categories) -> set[str]:
    """Which of the 7 sensitive keyword families (_N24M2_PRODUCT_FAMILY_PATTERNS)
    the product's OWN raw category hierarchy text evidences. Reuses the exact
    same patterns _n24m2_listing_families applies to title/details, so the two
    are directly comparable: a family present in listing text but absent from
    the category hierarchy is a genuine self-consistency conflict, not merely
    "some keyword family was mentioned somewhere".
    """
    text = " > ".join(str(item) for item in (categories or []))
    return {
        family for family, pattern in _N24M2_PRODUCT_FAMILY_PATTERNS.items()
        if _n24m2_re.search(pattern, text, flags=_n24m2_re.I)
    }


class N24CanonicalProductSemantics(N24StrictModel):
    """The one per-product semantics record. Values are taken directly from
    the existing, already-tested N24M2 trusted-attribute evidence -- nothing
    here recomputes colour/audience/brand/etc. It only reorganises those
    values into one typed, versioned schema and adds explicit product-family
    conflict evidence as a first-class field, so a raw-hierarchy
    contamination (e.g. a razor filed under Shirts) is visible on the
    product record itself rather than only inside one eligibility call.
    """
    contract_version: str = N24_CANONICAL_CONTRACT_VERSION
    product_id: str
    source_dataset: str | None = None
    title: str
    masked_title: str
    brand: str
    raw_main_category: str | None = None
    raw_category_hierarchy: list[str] = []
    categories: list[str]
    canonical_family: str | None = None
    canonical_subtype: str | None = None
    category_provenance: list[str] = []
    category_conflicts: list[str] = []
    product_semantic_confidence: float = 0.0
    main_category_family: str | None = None
    listing_conflict_families: list[str] = []
    audience: str
    age_group: str
    colour_components: list[str] = []
    colour_mode: str
    materials: list[str] = []
    styles: list[str] = []
    historical_price: _N24M2Any = None
    rating: _N24M2Any = None
    review_count: _N24M2Any = None
    trusted_attributes: dict[str, _N24M2Any]
    visual_colour_evidence: dict[str, _N24M2Any] | None = None

    @property
    def has_conflict_evidence(self) -> bool:
        return bool(self.listing_conflict_families)


def n24_build_canonical_semantics(product: dict) -> "N24CanonicalProductSemantics":
    row = product.get("row", {})
    listing_families = _n24m2_listing_families(product)
    hierarchy_families = _n24m2_category_hierarchy_families(product.get("categories"))
    # A genuine conflict requires an independent signal (title/details) naming
    # a family the category hierarchy itself does not evidence at all -- not
    # merely "a keyword family was mentioned somewhere". A product whose title
    # says nothing distinctive (listing_families empty) is not flagged either
    # way: absence of listing evidence is not evidence of a contradiction.
    main_family = _n24m2_main_category_family(row.get("main_category"))
    if main_family:
        hierarchy_families = hierarchy_families | {main_family}
    conflict_families = sorted(listing_families - hierarchy_families) if hierarchy_families else []
    family_candidates = set(listing_families)
    if main_family:
        family_candidates.add(main_family)
    if not family_candidates:
        family_candidates = set(hierarchy_families)
    canonical_family = next(iter(family_candidates)) if len(family_candidates) == 1 else None
    subtype = None
    if canonical_family:
        title_norm = _n24m2_normalize(row.get("title"))
        for candidate in N24_DECLARATIVE_TAXONOMY.get(canonical_family, {}).get("subtypes", []):
            if _n24m2_normalize(candidate) in title_norm:
                subtype = candidate
                break
    provenance = []
    if hierarchy_families:
        provenance.append("categories")
    if listing_families:
        provenance.append("title_or_structured_product_type")
    if main_family:
        provenance.append("main_category")
    semantic_confidence = 0.0 if conflict_families else 1.0 if canonical_family and len(provenance) >= 2 else 0.6 if canonical_family else 0.0
    return N24CanonicalProductSemantics(
        product_id=product["product_id"], source_dataset=str(row.get("source_dataset") or "") or None,
        title=product["title"], masked_title=product["masked_title"],
        brand=product["brand"], categories=list(product["categories"]),
        raw_main_category=str(row.get("main_category") or "") or None,
        raw_category_hierarchy=list(product["categories"]), canonical_family=canonical_family,
        canonical_subtype=subtype, category_provenance=provenance,
        category_conflicts=conflict_families,
        product_semantic_confidence=semantic_confidence,
        main_category_family=main_family, listing_conflict_families=conflict_families,
        audience=product["audience"], age_group=product["age_group"],
        colour_components=list(product["colour_components"]), colour_mode=product["colour_mode"],
        materials=list(product["materials"]), styles=list(product["styles"]),
        historical_price=product["price"], rating=product["rating"], review_count=product["review_count"],
        trusted_attributes=product["trusted_attributes"],
    )


N24_CANONICAL_SEMANTICS_INDEX = {
    product_id: n24_build_canonical_semantics(product)
    for product_id, product in N24M2_TRUSTED_CATALOGUE_INDEX.items()
}


def n24_canonical_semantics_for(product_id: str):
    return N24_CANONICAL_SEMANTICS_INDEX.get(str(product_id))


# ------------------------------------------------------------------
# Stage 2 -- ConstraintEvaluation is a name for what already exists, not a
# new computation. evaluate_n24_trusted_eligibility is already the single
# per-product, per-request evaluation consumed for eligibility filtering
# (get_n24_recommendations_from_validated_state) AND for Match %/explanations
# (calculate_product_match_score and build_final_recommendation_cards both
# read n24m_match_evidence, which is this same function's own output attached
# to each candidate row upstream). N24ConstraintEvaluation names that shared
# result type explicitly and adds accessors so new consumers (outfits, tests)
# don't need N24M2's internal history to find "the" evaluator.
# ------------------------------------------------------------------

N24ConstraintEvaluation = N24TrustedEligibilityResult


def n24_constraint_evaluation_badges(evaluation: "N24TrustedEligibilityResult") -> list[str]:
    return sorted(
        key for key, evidence in evaluation.attribute_evidence.items()
        if evidence.match_level == N24AttributeMatch.EXACT
    )


def n24_constraint_evaluation_explanation(evaluation: "N24TrustedEligibilityResult") -> str:
    badges = n24_constraint_evaluation_badges(evaluation)
    readable = [item.replace("historical_price", "price").replace("age_group", "age group").replace("_", " ") for item in badges]
    if readable:
        return "Matches your requested " + ", ".join(readable) + "."
    if evaluation.violation_count:
        reasons = [
            evidence.reason for evidence in evaluation.attribute_evidence.values()
            if evidence.match_level == N24AttributeMatch.VIOLATION
        ]
        return "Does not satisfy: " + "; ".join(reasons) if reasons else "Does not satisfy the requested constraints."
    return "Trusted catalogue match."


def evaluate_n24_constraint(product_id: str, request, sidecar: dict | None = None):
    """Canonical entry point: same computation as evaluate_n24_trusted_eligibility,
    given a stable, intention-revealing name for new call sites (outfit
    integration in Stage 5, the independent test suite in Stage 7)."""
    return evaluate_n24_trusted_eligibility(product_id, request, sidecar)


N24_OUTFIT_SLOT_REQUEST_CATEGORY = {
    "top": "Shirts", "bottom": "Pants", "footwear": "Shoes",
    "outerwear": "Jackets", "accessory": "Accessories",
}


def n24_filter_outfit_candidates_with_canonical_truth(
    candidate_result: dict, *, profile_id: str, slot: str, recipient: str | None,
    colours: list[str] | None = None,
) -> dict:
    """Apply the same ConstraintEvaluation used by ordinary search to an
    outfit slot while preserving the legacy outfit rank/order and coordination
    data.  Slot assembly remains unchanged; product-family and audience truth
    are no longer a parallel universe.
    """
    category = N24_OUTFIT_SLOT_REQUEST_CATEGORY.get(str(slot))
    if category is None:
        raise ValueError(f"Unsupported outfit slot: {slot}")
    request = build_n24_validated_recommendation_request(
        profile_id,
        N24HardRequestState(
            categories=[category], recipient=recipient,
            colours=list(colours or []),
        ),
        N24ExclusionState(),
    )
    output = dict(candidate_result or {})
    accepted, rejected, evidence = [], 0, {}
    for product in list(output.get("products") or []):
        product_id = str(product.get("product_id") or product.get("id") or "")
        evaluation = evaluate_n24_constraint(product_id, request)
        evidence[product_id] = evaluation.model_dump(mode="json")
        if evaluation.eligible:
            accepted.append(product)
        else:
            rejected += 1
    output["products"] = accepted
    output["canonical_constraint_evidence"] = evidence
    output["canonical_rejected_count"] = rejected
    output["canonical_semantics_version"] = N24_CANONICAL_CONTRACT_VERSION
    return output


N24_CANONICAL_STATUS = {
    "contract_version": N24_CANONICAL_CONTRACT_VERSION,
    "canonical_semantics_rows": len(N24_CANONICAL_SEMANTICS_INDEX),
    "products_with_conflict_evidence": sum(
        semantics.has_conflict_evidence for semantics in N24_CANONICAL_SEMANTICS_INDEX.values()
    ),
    "canonical_evaluator": "evaluate_n24_constraint (same computation as evaluate_n24_trusted_eligibility)",
    "n23_modified": False,
}
print("N24 canonical product semantics + constraint evaluation layer ready.")
print(_n24m2_json.dumps(N24_CANONICAL_STATUS, indent=2, default=str))
