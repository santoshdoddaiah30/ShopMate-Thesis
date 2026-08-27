"""ShopMate N24M deterministic catalogue semantics and eligibility hardening.

Executed by SECTION 153E7N24M in the existing notebook namespace.  This module
is additive to N24A-L.  It does not redefine or mutate any frozen N23 model,
weight, artefact, or database schema.
"""

from __future__ import annotations

import contextvars as _n24m_contextvars
import json as _n24m_json
import math as _n24m_math
import re as _n24m_re
import time as _n24m_time
from collections import Counter as _N24MCounter
from copy import deepcopy as _n24m_deepcopy
from enum import Enum as _N24MEnum
from typing import Any as _N24MAny


N24M_SECTION_VERSION = "n24m_complete_product_semantics_v1"
N24M_CAPABILITY_REGISTRY_VERSION = "n24m_catalogue_capabilities_v1"
N24M_ELIGIBILITY_ENGINE_VERSION = "n24m_deterministic_eligibility_v1"
N24M_STATE_VERSION = "n24m_semantic_sidecar_v1"
N24M_COLOUR_CONTRACT_VERSION = "n24m_ordered_colour_components_v1"
N24M_AUDIENCE_CONTRACT_VERSION = "n24m_canonical_audience_v1"


# Stable pre-N24M application entry points.  These functions are defined by
# the authoritative notebook before this module is first executed.  Earlier
# versions captured whichever object happened to be bound during every warm
# reload.  If that object was an older N24M wrapper, the wrapper captured
# itself and recursed forever.  Preserve the genuine pre-layer objects once
# and always recover the corresponding base guards from this registry.
if "N24_APPLICATION_BASES" not in globals():
    N24_APPLICATION_BASES = {}

for _n24m_base_name in (
    "get_n24_recommendations_from_validated_state",
    "calculate_product_match_score",
    "build_final_recommendation_cards",
    "build_n24_validated_recommendation_request",
    "show_more_n24_results",
):
    _n24m_base_candidate = globals().get(_n24m_base_name)
    _n24m_base_file = str(
        getattr(getattr(_n24m_base_candidate, "__code__", None), "co_filename", "")
    ).casefold()
    if callable(_n24m_base_candidate) and "shopmate_n24" not in _n24m_base_file:
        N24_APPLICATION_BASES.setdefault(_n24m_base_name, _n24m_base_candidate)


class N24CatalogueCapability(str, _N24MEnum):
    HARD_FILTER_SUPPORTED = "HARD_FILTER_SUPPORTED"
    SOFT_MATCH_SUPPORTED = "SOFT_MATCH_SUPPORTED"
    CONTEXT_ONLY = "CONTEXT_ONLY"
    RANKING_SUPPORTED = "RANKING_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"


class N24AttributeMatch(str, _N24MEnum):
    EXACT = "EXACT"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    VIOLATION = "VIOLATION"


class N24ColourMatchMode(str, _N24MEnum):
    STRICT_SINGLE_COLOUR = "STRICT_SINGLE_COLOUR"
    MIXED_COLOUR = "MIXED_COLOUR"
    NO_COLOUR_MATCH = "NO_COLOUR_MATCH"
    UNKNOWN = "UNKNOWN"


class N24CanonicalAudience(str, _N24MEnum):
    MEN = "MEN"
    WOMEN = "WOMEN"
    UNISEX_ADULT = "UNISEX_ADULT"
    BOYS = "BOYS"
    GIRLS = "GIRLS"
    KIDS = "KIDS"
    UNISEX_CHILD = "UNISEX_CHILD"
    TODDLER = "TODDLER"
    UNKNOWN = "UNKNOWN"


class N24CatalogueCapabilityEntry(N24StrictModel):
    attribute: str
    classification: N24CatalogueCapability
    reliability: str
    sources: list[str]
    coverage_percentage: float | None = None
    notes: str


class N24ProductEligibilityEvidence(N24StrictModel):
    product_id: str
    eligible: bool
    attribute_matches: dict[str, N24AttributeMatch]
    attribute_evidence: dict[str, _N24MAny]
    hard_constraint_count: int
    exact_constraint_count: int
    partial_constraint_count: int
    unknown_constraint_count: int
    violation_count: int
    match_score: float
    engine_version: str = N24M_ELIGIBILITY_ENGINE_VERSION


N24_CATALOGUE_CAPABILITY_REGISTRY = {
    "category": N24CatalogueCapabilityEntry(
        attribute="category", classification=N24CatalogueCapability.HARD_FILTER_SUPPORTED,
        reliability="HIGH", sources=["categories"], coverage_percentage=100.0,
        notes="Exact canonical hierarchy membership; broad catalogue roots are not product types.",
    ),
    "subcategory_product_type": N24CatalogueCapabilityEntry(
        attribute="subcategory_product_type", classification=N24CatalogueCapability.HARD_FILTER_SUPPORTED,
        reliability="HIGH", sources=["categories"], coverage_percentage=100.0,
        notes="Exact normalized category-path membership with documented aliases.",
    ),
    "brand": N24CatalogueCapabilityEntry(
        attribute="brand", classification=N24CatalogueCapability.HARD_FILTER_SUPPORTED,
        reliability="HIGH", sources=["brand"], coverage_percentage=100.0,
        notes="Exact canonical brand equality; arbitrary title substrings are never brands.",
    ),
    "colour": N24CatalogueCapabilityEntry(
        attribute="colour", classification=N24CatalogueCapability.HARD_FILTER_SUPPORTED,
        reliability="MEDIUM", sources=["details.Color", "details.Band Color", "title variant text"],
        coverage_percentage=None,
        notes="Ordered explicit colour components only; unknown evidence is excluded from strict colour results.",
    ),
    "audience_gender": N24CatalogueCapabilityEntry(
        attribute="audience_gender", classification=N24CatalogueCapability.HARD_FILTER_SUPPORTED,
        reliability="HIGH", sources=["details.Department", "details.Suggested Users", "categories"],
        coverage_percentage=92.92,
        notes="Canonical audience with structured metadata first and category fallback.",
    ),
    "age_group": N24CatalogueCapabilityEntry(
        attribute="age_group", classification=N24CatalogueCapability.HARD_FILTER_SUPPORTED,
        reliability="MEDIUM", sources=["details.Department", "details.Age Range (Description)", "categories"],
        coverage_percentage=None,
        notes="Adult/child/toddler compatibility derived conservatively from explicit metadata.",
    ),
    "historical_price": N24CatalogueCapabilityEntry(
        attribute="historical_price", classification=N24CatalogueCapability.HARD_FILTER_SUPPORTED,
        reliability="HIGH", sources=["price"], coverage_percentage=100.0,
        notes="Numeric historical catalogue price only; never a live price claim.",
    ),
    "rating": N24CatalogueCapabilityEntry(
        attribute="rating", classification=N24CatalogueCapability.HARD_FILTER_SUPPORTED,
        reliability="HIGH", sources=["average_rating"], coverage_percentage=100.0,
        notes="Numeric historical catalogue rating.",
    ),
    "review_count": N24CatalogueCapabilityEntry(
        attribute="review_count", classification=N24CatalogueCapability.RANKING_SUPPORTED,
        reliability="HIGH", sources=["rating_number", "application_trust_metadata_df"],
        coverage_percentage=100.0,
        notes="Deterministic ranking/comparison evidence; not an invented popularity claim.",
    ),
    "material": N24CatalogueCapabilityEntry(
        attribute="material", classification=N24CatalogueCapability.SOFT_MATCH_SUPPORTED,
        reliability="LOW", sources=["details.Material", "details.Fabric Type", "details.Inner Material", "details.Outer Material"],
        coverage_percentage=6.90,
        notes="Sparse historical metadata; may inform a soft match but cannot guarantee material eligibility.",
    ),
    "size": N24CatalogueCapabilityEntry(
        attribute="size", classification=N24CatalogueCapability.UNSUPPORTED,
        reliability="LOW", sources=["details.Size", "title historical variant text"],
        coverage_percentage=2.82,
        notes="Cannot confirm current size availability; title size text is historical listing text only.",
    ),
    "style": N24CatalogueCapabilityEntry(
        attribute="style", classification=N24CatalogueCapability.CONTEXT_ONLY,
        reliability="LOW", sources=["details.Style", "categories", "title"],
        coverage_percentage=5.31,
        notes="General style words are context unless represented by an exact structured subcategory.",
    ),
    "activity_use_case": N24CatalogueCapabilityEntry(
        attribute="activity_use_case", classification=N24CatalogueCapability.CONTEXT_ONLY,
        reliability="MEDIUM", sources=["categories", "details.Sport Type", "details.Sport"],
        coverage_percentage=None,
        notes="Running, walking, basketball and other exact category-path values are enforced as subcategories; free-form use cases remain context.",
    ),
    "occasion": N24CatalogueCapabilityEntry(
        attribute="occasion", classification=N24CatalogueCapability.CONTEXT_ONLY,
        reliability="LOW", sources=["details.Occasion"], coverage_percentage=0.64,
        notes="Too sparse for universal hard filtering.",
    ),
    "department": N24CatalogueCapabilityEntry(
        attribute="department", classification=N24CatalogueCapability.CONTEXT_ONLY,
        reliability="HIGH", sources=["details.Department"], coverage_percentage=92.92,
        notes="Source evidence for canonical audience; the raw value is not exposed as a free-form filter.",
    ),
    "recipient_evidence": N24CatalogueCapabilityEntry(
        attribute="recipient_evidence", classification=N24CatalogueCapability.CONTEXT_ONLY,
        reliability="MEDIUM", sources=["audience_gender", "age_group"], coverage_percentage=None,
        notes="Gift recipient language is contextual unless it explicitly states a supported audience.",
    ),
    "title_description_features": N24CatalogueCapabilityEntry(
        attribute="title_description_features", classification=N24CatalogueCapability.CONTEXT_ONLY,
        reliability="MEDIUM", sources=["title", "description", "features"], coverage_percentage=100.0,
        notes="Grounding/context evidence; broad text is never a substitute for a supported structured hard attribute.",
    ),
    "variant_information": N24CatalogueCapabilityEntry(
        attribute="variant_information", classification=N24CatalogueCapability.CONTEXT_ONLY,
        reliability="MEDIUM", sources=["details.Color", "details.Size", "title"], coverage_percentage=None,
        notes="Historical listing variant evidence, not live availability.",
    ),
    "historical_availability": N24CatalogueCapabilityEntry(
        attribute="historical_availability", classification=N24CatalogueCapability.CONTEXT_ONLY,
        reliability="LOW", sources=["details.Is Discontinued By Manufacturer", "details.Date First Available"],
        coverage_percentage=None,
        notes="Historical metadata only; never current stock or delivery evidence.",
    ),
    "live_stock_delivery_coupon_current_price": N24CatalogueCapabilityEntry(
        attribute="live_stock_delivery_coupon_current_price", classification=N24CatalogueCapability.UNSUPPORTED,
        reliability="UNSUPPORTED", sources=[], coverage_percentage=0.0,
        notes="No live commerce feed exists in the processed catalogue.",
    ),
}


_N24M_CATEGORY_ALIASES = {
    "walking shoes": ["Shoes", "Walking"], "walking shoe": ["Shoes", "Walking"],
    "running shoes": ["Shoes", "Running"], "running shoe": ["Shoes", "Running"],
    "basketball shoes": ["Shoes", "Basketball"], "basketball shoe": ["Shoes", "Basketball"],
    "sports shoes": ["Shoes", "Athletic"], "sport shoes": ["Shoes", "Athletic"],
    "athletic shoes": ["Shoes", "Athletic"], "athletic shoe": ["Shoes", "Athletic"],
    "fashion sneakers": ["Shoes", "Fashion Sneakers"],
    "sneakers": ["Shoes"], "sneaker": ["Shoes"], "sneekers": ["Shoes"],
    "kicks": ["Shoes"], "shoes": ["Shoes"], "shoe": ["Shoes"],
    "sandals": ["Shoes", "Sandals"], "sandal": ["Shoes", "Sandals"],
    "boots": ["Shoes", "Boots"], "boot": ["Shoes", "Boots"],
    "slippers": ["Shoes", "Slippers"], "slipper": ["Shoes", "Slippers"],
    "flip flops": ["Shoes", "Flip-Flops"], "flip-flops": ["Shoes", "Flip-Flops"],
    "t-shirts": ["T-Shirts"], "t shirt": ["T-Shirts"], "tshirt": ["T-Shirts"],
    "tshirts": ["T-Shirts"], "tee shirts": ["T-Shirts"], "tees": ["T-Shirts"],
    "jackets": ["Jackets & Coats"], "jacket": ["Jackets & Coats"],
    "watches": ["Watches"], "watch": ["Watches"],
    "handbags": ["Handbags & Wallets"], "handbag": ["Handbags & Wallets"],
    "accessories": ["Accessories"], "accessory": ["Accessories"],
    "dresses": ["Dresses"], "dress": ["Dresses"],
    "jeans": ["Jeans"], "pants": ["Pants"], "leggings": ["Leggings"],
    "rings": ["Rings"], "ring": ["Rings"], "earrings": ["Earrings"],
    "earring": ["Earrings"], "necklaces": ["Necklaces"], "necklace": ["Necklaces"],
    "bracelets": ["Bracelets"], "bracelet": ["Bracelets"],
    "shirts": ["Shirts"], "shirt": ["Shirts"],
}

_N24M_COLOUR_ALIASES = {
    "footwear white": "white", "ftwr white": "white", "core white": "white",
    "cloud white": "white", "off white": "white", "off-white": "white", "white": "white",
    "core black": "black", "jet black": "black", "black": "black",
    "grey two": "grey", "gray": "grey", "grey": "grey", "silver": "silver",
    "navy blue": "blue", "navy": "blue", "royal blue": "blue", "blue": "blue",
    "wine red": "red", "burgundy": "red", "red": "red",
    "pink tint": "pink", "rose pink": "pink", "pink": "pink",
    "forest green": "green", "olive green": "green", "green": "green",
    "purple": "purple", "violet": "purple", "yellow": "yellow", "orange": "orange",
    "dark brown": "brown", "brown": "brown", "tan": "tan", "beige": "beige",
    "khaki": "khaki", "gold": "gold", "rose gold": "gold", "multicolor": "multicolour",
    "multi-color": "multicolour", "multi coloured": "multicolour", "multi": "multicolour",
}

_N24M_MATERIAL_TERMS = {
    "leather", "faux leather", "cotton", "polyester", "nylon", "suede", "silk",
    "wool", "linen", "rubber", "synthetic", "canvas", "mesh", "metal", "plastic",
}

_N24M_STYLE_TERMS = {
    "casual", "formal", "work", "office", "running", "walking", "sports", "sport",
    "basketball", "classic", "modern", "vintage", "elegant", "minimalist",
}

_N24M_BRAND_TYPOS = {
    "adiddas": "adidas", "addidas": "adidas", "adidias": "adidas",
    "nikke": "Nike", "nkie": "Nike", "skecher": "Skechers",
    "newbalance": "New Balance",
}

_N24M_INVALID_BRAND_VALUES = {
    "", "unknown", "which is", "which", "none", "n a", "na", "generic",
}

# A small number of real catalogue brands normalize to ordinary shopping
# verbs.  They require an explicit brand/source construction so commands such
# as "help me find shoes" cannot become accidental hard brand constraints.
_N24M_AMBIGUOUS_BRAND_TOKENS = {"find"}


def _n24m_reliable_brand_value(value: _N24MAny) -> bool:
    normalized = _n24m_normalize(value)
    if normalized in _N24M_INVALID_BRAND_VALUES:
        return False
    if any(token in normalized for token in (" author", "illustrator", "paperback", "hardcover")):
        return False
    words = normalized.split()
    return bool(normalized) and len(normalized) <= 60 and len(words) <= 7


def _n24m_normalize(value: _N24MAny) -> str:
    text = "" if value is None else str(value)
    text = text.replace("&", " and ").replace("’", "'").casefold()
    text = _n24m_re.sub(r"[^a-z0-9]+", " ", text)
    return _n24m_re.sub(r"\s+", " ", text).strip()


def _n24m_json_object(value: _N24MAny) -> dict:
    if isinstance(value, dict):
        return dict(value)
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = _n24m_json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _n24m_category_path(value: _N24MAny) -> list[str]:
    try:
        parsed = parse_application_categories(value)
    except Exception:
        parsed = []
    return [str(item).strip() for item in parsed if str(item).strip()]


def _n24m_colour_tokens(value: _N24MAny) -> list[str]:
    text = str(value or "")
    if not text.strip():
        return []
    text = _n24m_re.sub(r"(?i)\bwhite\s+gold\b", "", text)
    aliases = sorted(_N24M_COLOUR_ALIASES, key=len, reverse=True)
    pattern = r"(?<![a-z0-9])(" + "|".join(_n24m_re.escape(item) for item in aliases) + r")(?![a-z0-9])"
    return [_N24M_COLOUR_ALIASES[match.group(1).casefold()] for match in _n24m_re.finditer(pattern, text, flags=_n24m_re.I)]


def _n24m_extract_colours(title: str, details: dict) -> tuple[list[str], str | None, str | None]:
    for key in ("Color", "Colour", "Color Name", "Band Color", "Stone Color", "Lens Color"):
        raw = details.get(key)
        components = _n24m_colour_tokens(raw)
        if components:
            return components, key, str(raw)
    segments = [segment.strip() for segment in str(title or "").split(",")]
    variant_components = []
    variant_text = []
    for segment in segments[1:]:
        found = _n24m_colour_tokens(segment)
        if found:
            variant_components.extend(found)
            variant_text.append(segment)
    if variant_components:
        return variant_components, "title_variant", " | ".join(variant_text)
    components = _n24m_colour_tokens(title)
    if components:
        return components, "title", str(title)
    return [], None, None


def _n24m_canonical_audience_text(value: _N24MAny) -> N24CanonicalAudience:
    text = _n24m_normalize(value)
    if not text:
        return N24CanonicalAudience.UNKNOWN
    if "toddler" in text or "baby" in text or "infant" in text:
        return N24CanonicalAudience.TODDLER
    adult = "adult" in text
    child = any(token in text for token in ("child", "kid", "youth"))
    men = bool(_n24m_re.search(r"\b(men|mens|man|male)\b", text))
    women = bool(_n24m_re.search(r"\b(women|womens|woman|female|ladies)\b", text))
    boys = bool(_n24m_re.search(r"\b(boy|boys)\b", text))
    girls = bool(_n24m_re.search(r"\b(girl|girls)\b", text))
    unisex = "unisex" in text or (men and women) or (boys and girls)
    if unisex and (child or boys or girls):
        return N24CanonicalAudience.UNISEX_CHILD
    if unisex and (adult or men or women):
        return N24CanonicalAudience.UNISEX_ADULT
    if boys:
        return N24CanonicalAudience.BOYS
    if girls:
        return N24CanonicalAudience.GIRLS
    if men:
        return N24CanonicalAudience.MEN
    if women:
        return N24CanonicalAudience.WOMEN
    if child:
        return N24CanonicalAudience.KIDS
    if adult:
        return N24CanonicalAudience.UNISEX_ADULT
    return N24CanonicalAudience.UNKNOWN


def _n24m_extract_audience(details: dict, categories: list[str]) -> tuple[N24CanonicalAudience, str, str | None]:
    for key in ("Department", "Suggested Users", "Target Audience", "Target gender"):
        raw = details.get(key)
        audience = _n24m_canonical_audience_text(raw)
        if audience != N24CanonicalAudience.UNKNOWN:
            return audience, key, str(raw)
    for category in categories:
        audience = _n24m_canonical_audience_text(category)
        if audience != N24CanonicalAudience.UNKNOWN:
            return audience, "categories", category
    return N24CanonicalAudience.UNKNOWN, "none", None


def _n24m_material_components(details: dict) -> list[str]:
    values = []
    for key in ("Material", "Fabric Type", "Inner Material", "Outer Material", "Material Type", "material_composition", "Material Composition"):
        if details.get(key):
            values.extend(part.strip().casefold() for part in _n24m_re.split(r"[,;/+]", str(details[key])) if part.strip())
    return list(dict.fromkeys(values))


def _n24m_style_components(details: dict, categories: list[str]) -> list[str]:
    values = []
    for key in ("Style", "Sport Type", "Sport", "Occasion", "Recommended Uses For Product"):
        if details.get(key):
            values.extend(part.strip().casefold() for part in _n24m_re.split(r"[,;/]", str(details[key])) if part.strip())
    values.extend(_n24m_normalize(item) for item in categories if _n24m_normalize(item))
    return list(dict.fromkeys(values))


def _n24m_build_catalogue_index():
    started = _n24m_time.perf_counter()
    index = {}
    audience_counts = _N24MCounter()
    colour_source_counts = _N24MCounter()
    material_count = 0
    size_count = 0
    style_count = 0
    category_nonempty = 0
    for row in application_request_metadata_df.drop_duplicates("product_id").to_dict("records"):
        product_id = str(row.get("product_id"))
        details = _n24m_json_object(row.get("details"))
        categories = _n24m_category_path(row.get("categories"))
        if categories:
            category_nonempty += 1
        colours, colour_source, colour_raw = _n24m_extract_colours(str(row.get("title") or ""), details)
        audience, audience_source, audience_raw = _n24m_extract_audience(details, categories)
        materials = _n24m_material_components(details)
        styles = _n24m_style_components(details, categories)
        size_raw = details.get("Size")
        material_count += bool(materials)
        size_count += bool(size_raw)
        style_count += bool(styles)
        audience_counts[audience.value] += 1
        colour_source_counts[colour_source or "UNKNOWN"] += 1
        index[product_id] = {
            "row": row,
            "categories": categories,
            "category_norms": {_n24m_normalize(item) for item in categories},
            "brand": str(row.get("brand") or "").strip(),
            "brand_norm": _n24m_normalize(row.get("brand")),
            "colour_components": colours,
            "primary_colour": colours[0] if colours else None,
            "secondary_colours": colours[1:] if len(colours) > 1 else [],
            "colour_source": colour_source,
            "colour_raw": colour_raw,
            "audience": audience.value,
            "audience_source": audience_source,
            "audience_raw": audience_raw,
            "age_group": (
                "ADULT" if audience in {N24CanonicalAudience.MEN, N24CanonicalAudience.WOMEN, N24CanonicalAudience.UNISEX_ADULT}
                else "TODDLER" if audience == N24CanonicalAudience.TODDLER
                else "CHILD" if audience in {N24CanonicalAudience.BOYS, N24CanonicalAudience.GIRLS, N24CanonicalAudience.KIDS, N24CanonicalAudience.UNISEX_CHILD}
                else "UNKNOWN"
            ),
            "materials": materials,
            "size": None if size_raw in (None, "") else str(size_raw),
            "styles": styles,
            "price": safely_convert_to_float(row.get("price")),
            "rating": safely_convert_to_float(row.get("average_rating")),
            "review_count": safely_convert_to_float(row.get("rating_number")),
        }
    rows = len(index)
    audit = {
        "catalogue_rows": rows,
        "fields": {
            "product_id": {"non_null": rows, "coverage_percentage": 100.0, "reliability": "HIGH"},
            "title": {"non_null": rows, "coverage_percentage": 100.0, "reliability": "HIGH"},
            "brand": {"non_null": rows, "coverage_percentage": 100.0, "reliability": "HIGH"},
            "categories": {"non_null": category_nonempty, "coverage_percentage": round(100 * category_nonempty / rows, 2), "reliability": "HIGH"},
            "price": {"non_null": sum(item["price"] is not None for item in index.values()), "coverage_percentage": 100.0, "reliability": "HIGH"},
            "average_rating": {"non_null": sum(item["rating"] is not None for item in index.values()), "coverage_percentage": 100.0, "reliability": "HIGH"},
            "rating_number": {"non_null": sum(item["review_count"] is not None for item in index.values()), "coverage_percentage": 100.0, "reliability": "HIGH"},
            "audience": {"non_null": rows - audience_counts["UNKNOWN"], "coverage_percentage": round(100 * (rows - audience_counts["UNKNOWN"]) / rows, 2), "reliability": "HIGH"},
            "colour_evidence": {"non_null": rows - colour_source_counts["UNKNOWN"], "coverage_percentage": round(100 * (rows - colour_source_counts["UNKNOWN"]) / rows, 2), "reliability": "MEDIUM"},
            "material_evidence": {"non_null": material_count, "coverage_percentage": round(100 * material_count / rows, 2), "reliability": "LOW"},
            "size_evidence": {"non_null": size_count, "coverage_percentage": round(100 * size_count / rows, 2), "reliability": "LOW"},
            "style_activity_evidence": {"non_null": style_count, "coverage_percentage": round(100 * style_count / rows, 2), "reliability": "MEDIUM"},
        },
        "audience_counts": dict(audience_counts),
        "colour_source_counts": dict(colour_source_counts),
        "build_seconds": round(_n24m_time.perf_counter() - started, 3),
    }
    return index, audit


N24M_CATALOGUE_INDEX, N24M_CATALOGUE_AUDIT = _n24m_build_catalogue_index()


_N24M_BRAND_CANONICAL = {}
for _n24m_brand in application_request_metadata_df["brand"].dropna().astype(str).str.strip().unique():
    if _n24m_reliable_brand_value(_n24m_brand):
        _N24M_BRAND_CANONICAL.setdefault(_n24m_normalize(_n24m_brand), _n24m_brand)
for _n24m_typo, _n24m_canonical in _N24M_BRAND_TYPOS.items():
    _N24M_BRAND_CANONICAL[_n24m_normalize(_n24m_typo)] = _N24M_BRAND_CANONICAL.get(_n24m_normalize(_n24m_canonical), _n24m_canonical)


def _n24m_default_sidecar() -> dict:
    return {
        "state_version": N24M_STATE_VERSION,
        "minimum_rating": None,
        "rating_exclusive": False,
        "allow_mixed_colours": False,
        "excluded_audiences": [],
        "soft_materials": [],
        "style_context": [],
        "limitations": [],
    }


N24_CANONICAL_REQUEST_STATE_VERSION = "n24_canonical_request_state_v1"


class N24CanonicalRequestState(N24StrictModel):
    """Single persisted request-state contract for the post-N23 application.

    The in-memory dictionaries remain compatibility caches for existing call
    sites, but they are projections of this record rather than independent
    persisted sources of truth.
    """
    state_version: str = N24_CANONICAL_REQUEST_STATE_VERSION
    hard_request: N24HardRequestState
    exclusions: N24ExclusionState
    colour_mode: str = "STRICT"
    minimum_rating: float | None = None
    rating_exclusive: bool = False
    excluded_audiences: list[str] = []
    soft_materials: list[str] = []
    style_context: list[str] = []
    limitations: list[str] = []
    active_result_set_id: str | None = None
    pending_offer_id: str | None = None


def _n24m_canonical_request_state(state, sidecar: dict, pending_offer=None):
    return N24CanonicalRequestState(
        hard_request=state.hard_request.model_copy(deep=True),
        exclusions=state.exclusions.model_copy(deep=True),
        colour_mode=str(sidecar.get("colour_mode") or (
            "MIXED_ALLOWED" if sidecar.get("allow_mixed_colours") else "STRICT"
        )),
        minimum_rating=sidecar.get("minimum_rating"),
        rating_exclusive=bool(sidecar.get("rating_exclusive")),
        excluded_audiences=list(sidecar.get("excluded_audiences") or []),
        soft_materials=list(sidecar.get("soft_materials") or []),
        style_context=list(sidecar.get("style_context") or []),
        limitations=list(sidecar.get("limitations") or []),
        active_result_set_id=(
            None if state.active_result_set is None else state.active_result_set.result_set_id
        ),
        pending_offer_id=(
            pending_offer.get("offer_id") if isinstance(pending_offer, dict) else None
        ),
    )


def _n24m_sidecar_from_canonical(canonical: N24CanonicalRequestState) -> dict:
    return {
        "state_version": N24M_STATE_VERSION,
        "minimum_rating": canonical.minimum_rating,
        "rating_exclusive": canonical.rating_exclusive,
        "allow_mixed_colours": canonical.colour_mode == "MIXED_ALLOWED",
        "colour_mode": canonical.colour_mode,
        "excluded_audiences": list(canonical.excluded_audiences),
        "soft_materials": list(canonical.soft_materials),
        "style_context": list(canonical.style_context),
        "limitations": list(canonical.limitations),
    }


if "N24M_CHAT_CONSTRAINTS" not in globals():
    N24M_CHAT_CONSTRAINTS = {}
if "N24M_REQUEST_SIDECARS" not in globals():
    N24M_REQUEST_SIDECARS = {}
if "N24M_PENDING_RELATIVE" not in globals():
    N24M_PENDING_RELATIVE = {}
if "N24M_FROZEN_RANK_CACHE" not in globals():
    N24M_FROZEN_RANK_CACHE = {}

N24M_CURRENT_CHAT_ID = _n24m_contextvars.ContextVar("n24m_current_chat_id", default=None)


def _n24m_sidecar(chat_id: int | None) -> dict:
    if chat_id is None:
        return _n24m_default_sidecar()
    current = N24M_CHAT_CONSTRAINTS.get(int(chat_id))
    if not isinstance(current, dict) or current.get("state_version") != N24M_STATE_VERSION:
        current = _n24m_default_sidecar()
        N24M_CHAT_CONSTRAINTS[int(chat_id)] = current
    return current


def _n24m_category_matches(evidence: dict, requested: str) -> bool:
    wanted = _n24m_normalize(requested)
    if not wanted:
        return False
    aliases = {
        "jackets": "jackets and coats", "jacket": "jackets and coats",
        "t shirts": "t shirts", "t shirt": "t shirts",
        "handbags": "handbags and wallets", "handbag": "handbags and wallets",
    }
    wanted = aliases.get(wanted, wanted)
    for actual in evidence["category_norms"]:
        if actual == wanted:
            return True
        if wanted == "watches" and actual == "wrist watches":
            return True
        if wanted == "accessories" and actual.endswith(" accessories"):
            return True
    return False


def _n24m_requested_audience(value: _N24MAny) -> N24CanonicalAudience:
    return _n24m_canonical_audience_text(value)


def _n24m_audience_compatible(actual: str, requested: N24CanonicalAudience) -> bool:
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


def _n24m_add_match(matches, evidence_values, name, match, evidence):
    matches[name] = match
    evidence_values[name] = evidence


def evaluate_n24_product_eligibility(product_id: str, request, sidecar: dict | None = None) -> N24ProductEligibilityEvidence:
    if not isinstance(request, N24ValidatedRecommendationRequest):
        request = N24ValidatedRecommendationRequest.model_validate(request)
    product_id = str(product_id)
    product = N24M_CATALOGUE_INDEX.get(product_id)
    if product is None:
        return N24ProductEligibilityEvidence(
            product_id=product_id, eligible=False,
            attribute_matches={"product_id": N24AttributeMatch.VIOLATION},
            attribute_evidence={"product_id": "not present in processed catalogue"},
            hard_constraint_count=1, exact_constraint_count=0, partial_constraint_count=0,
            unknown_constraint_count=0, violation_count=1, match_score=0.0,
        )
    sidecar = _n24m_deepcopy(sidecar or N24M_REQUEST_SIDECARS.get(request.request_fingerprint) or _n24m_default_sidecar())
    matches = {}
    evidence_values = {}

    if request.categories:
        ok = all(_n24m_category_matches(product, wanted) for wanted in request.categories)
        _n24m_add_match(matches, evidence_values, "category", N24AttributeMatch.EXACT if ok else N24AttributeMatch.VIOLATION, product["categories"])
    if request.brands:
        wanted = {_n24m_normalize(item) for item in request.brands}
        ok = product["brand_norm"] in wanted
        _n24m_add_match(matches, evidence_values, "brand", N24AttributeMatch.EXACT if ok else N24AttributeMatch.VIOLATION, product["brand"])
    if request.colours:
        wanted = [_N24M_COLOUR_ALIASES.get(_n24m_normalize(item), _n24m_normalize(item)) for item in request.colours]
        components = product["colour_components"]
        if not components:
            colour_match = N24AttributeMatch.UNKNOWN
            colour_mode = N24ColourMatchMode.UNKNOWN
        elif len(wanted) == 1:
            target = wanted[0]
            if components and all(component == target for component in components):
                colour_match = N24AttributeMatch.EXACT
                colour_mode = N24ColourMatchMode.STRICT_SINGLE_COLOUR
            elif target in components:
                colour_match = N24AttributeMatch.PARTIAL
                colour_mode = N24ColourMatchMode.MIXED_COLOUR
            else:
                colour_match = N24AttributeMatch.VIOLATION
                colour_mode = N24ColourMatchMode.NO_COLOUR_MATCH
        else:
            requested_set = set(wanted)
            component_set = set(components)
            if requested_set.issubset(component_set):
                colour_match = N24AttributeMatch.EXACT if component_set.issubset(requested_set) else N24AttributeMatch.PARTIAL
                colour_mode = N24ColourMatchMode.MIXED_COLOUR
            else:
                colour_match = N24AttributeMatch.VIOLATION
                colour_mode = N24ColourMatchMode.NO_COLOUR_MATCH
        _n24m_add_match(matches, evidence_values, "colour", colour_match, {
            "primary_colour": product["primary_colour"], "secondary_colours": product["secondary_colours"],
            "colour_components": components, "source": product["colour_source"], "mode": colour_mode.value,
        })
    requested_audience = _n24m_requested_audience(request.recipient)
    if request.recipient:
        if product["audience"] == "UNKNOWN":
            match = N24AttributeMatch.UNKNOWN
        else:
            match = N24AttributeMatch.EXACT if _n24m_audience_compatible(product["audience"], requested_audience) else N24AttributeMatch.VIOLATION
        _n24m_add_match(matches, evidence_values, "audience", match, {
            "canonical": product["audience"], "raw": product["audience_raw"], "source": product["audience_source"],
        })
        requested_age = "ADULT" if requested_audience in {N24CanonicalAudience.MEN, N24CanonicalAudience.WOMEN, N24CanonicalAudience.UNISEX_ADULT} else "TODDLER" if requested_audience == N24CanonicalAudience.TODDLER else "CHILD"
        age_match = N24AttributeMatch.UNKNOWN if product["age_group"] == "UNKNOWN" else N24AttributeMatch.EXACT if product["age_group"] == requested_age or (requested_age == "CHILD" and product["age_group"] == "TODDLER" and requested_audience == N24CanonicalAudience.KIDS) else N24AttributeMatch.VIOLATION
        _n24m_add_match(matches, evidence_values, "age_group", age_match, product["age_group"])
    if request.minimum_price is not None or request.maximum_price is not None:
        price = product["price"]
        ok = price is not None and (request.minimum_price is None or price >= request.minimum_price) and (request.maximum_price is None or price <= request.maximum_price)
        match = N24AttributeMatch.UNKNOWN if price is None else N24AttributeMatch.EXACT if ok else N24AttributeMatch.VIOLATION
        _n24m_add_match(matches, evidence_values, "historical_price", match, price)
    minimum_rating = sidecar.get("minimum_rating")
    if minimum_rating is not None:
        rating = product["rating"]
        threshold_ok = rating is not None and (rating > float(minimum_rating) if sidecar.get("rating_exclusive") else rating >= float(minimum_rating))
        match = N24AttributeMatch.UNKNOWN if rating is None else N24AttributeMatch.EXACT if threshold_ok else N24AttributeMatch.VIOLATION
        _n24m_add_match(matches, evidence_values, "rating", match, rating)

    if request.excluded_product_ids:
        ok = product_id.casefold() not in {str(item).casefold() for item in request.excluded_product_ids}
        _n24m_add_match(matches, evidence_values, "excluded_product", N24AttributeMatch.EXACT if ok else N24AttributeMatch.VIOLATION, product_id)
    if request.excluded_brands:
        forbidden = {_n24m_normalize(item) for item in request.excluded_brands}
        ok = product["brand_norm"] not in forbidden
        _n24m_add_match(matches, evidence_values, "excluded_brand", N24AttributeMatch.EXACT if ok else N24AttributeMatch.VIOLATION, product["brand"])
    if request.excluded_categories:
        violates = any(_n24m_category_matches(product, item) for item in request.excluded_categories)
        _n24m_add_match(matches, evidence_values, "excluded_category", N24AttributeMatch.VIOLATION if violates else N24AttributeMatch.EXACT, product["categories"])
    if request.excluded_colours:
        components = product["colour_components"]
        forbidden = {_N24M_COLOUR_ALIASES.get(_n24m_normalize(item), _n24m_normalize(item)) for item in request.excluded_colours}
        if not components:
            match = N24AttributeMatch.UNKNOWN
        else:
            match = N24AttributeMatch.VIOLATION if set(components) & forbidden else N24AttributeMatch.EXACT
        _n24m_add_match(matches, evidence_values, "excluded_colour", match, components)
    excluded_audiences = [_n24m_requested_audience(item) for item in sidecar.get("excluded_audiences", [])]
    if excluded_audiences:
        if product["audience"] == "UNKNOWN":
            match = N24AttributeMatch.UNKNOWN
        else:
            violates = any(_n24m_audience_compatible(product["audience"], item) for item in excluded_audiences)
            match = N24AttributeMatch.VIOLATION if violates else N24AttributeMatch.EXACT
        _n24m_add_match(matches, evidence_values, "excluded_audience", match, product["audience"])

    values = list(matches.values())
    exact = sum(item == N24AttributeMatch.EXACT for item in values)
    partial = sum(item == N24AttributeMatch.PARTIAL for item in values)
    unknown = sum(item == N24AttributeMatch.UNKNOWN for item in values)
    violation = sum(item == N24AttributeMatch.VIOLATION for item in values)
    mixed_allowed = bool(sidecar.get("allow_mixed_colours")) or len(request.colours) > 1
    partial_allowed = mixed_allowed and matches.get("colour") == N24AttributeMatch.PARTIAL
    disallowed_partial = partial and not partial_allowed
    eligible = violation == 0 and unknown == 0 and not disallowed_partial
    score = 0.0 if not values else round(100.0 * (exact + 0.75 * partial) / len(values), 2)
    return N24ProductEligibilityEvidence(
        product_id=product_id, eligible=eligible, attribute_matches=matches,
        attribute_evidence=evidence_values, hard_constraint_count=len(values),
        exact_constraint_count=exact, partial_constraint_count=partial,
        unknown_constraint_count=unknown, violation_count=violation, match_score=score,
    )


def _n24m_fast_eligible(product: dict, product_id: str, request, sidecar: dict) -> bool:
    if request.categories and not all(_n24m_category_matches(product, item) for item in request.categories):
        return False
    if request.brands and product["brand_norm"] not in {_n24m_normalize(item) for item in request.brands}:
        return False
    if request.colours:
        wanted = [_N24M_COLOUR_ALIASES.get(_n24m_normalize(item), _n24m_normalize(item)) for item in request.colours]
        components = product["colour_components"]
        if not components:
            return False
        if len(wanted) == 1:
            if all(component == wanted[0] for component in components):
                pass
            elif sidecar.get("allow_mixed_colours") and wanted[0] in components:
                pass
            else:
                return False
        elif not set(wanted).issubset(set(components)):
            return False
    if request.recipient:
        requested = _n24m_requested_audience(request.recipient)
        if product["audience"] == "UNKNOWN" or not _n24m_audience_compatible(product["audience"], requested):
            return False
        requested_age = "ADULT" if requested in {N24CanonicalAudience.MEN, N24CanonicalAudience.WOMEN, N24CanonicalAudience.UNISEX_ADULT} else "TODDLER" if requested == N24CanonicalAudience.TODDLER else "CHILD"
        if product["age_group"] == "UNKNOWN":
            return False
        if product["age_group"] != requested_age and not (requested_age == "CHILD" and requested == N24CanonicalAudience.KIDS and product["age_group"] == "TODDLER"):
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
    if request.excluded_product_ids and product_id.casefold() in {str(item).casefold() for item in request.excluded_product_ids}:
        return False
    if request.excluded_brands and product["brand_norm"] in {_n24m_normalize(item) for item in request.excluded_brands}:
        return False
    if request.excluded_categories and any(_n24m_category_matches(product, item) for item in request.excluded_categories):
        return False
    if request.excluded_colours:
        components = product["colour_components"]
        if not components:
            return False
        forbidden = {_N24M_COLOUR_ALIASES.get(_n24m_normalize(item), _n24m_normalize(item)) for item in request.excluded_colours}
        if set(components) & forbidden:
            return False
    excluded_audiences = [_n24m_requested_audience(item) for item in sidecar.get("excluded_audiences", [])]
    if excluded_audiences:
        if product["audience"] == "UNKNOWN":
            return False
        if any(_n24m_audience_compatible(product["audience"], item) for item in excluded_audiences):
            return False
    return True


def _n24m_eligible_ids(request, sidecar: dict) -> set[str]:
    return {
        product_id for product_id, product in N24M_CATALOGUE_INDEX.items()
        if _n24m_fast_eligible(product, product_id, request, sidecar)
    }


def _n24m_relaxation_options(request, sidecar):
    options = []
    if request.maximum_price is not None or request.minimum_price is not None:
        options.append("relax the historical price range")
    if request.colours:
        options.append("allow mixed colours" if not sidecar.get("allow_mixed_colours") else "relax the colour")
    if request.brands:
        options.append("relax the brand")
    if request.recipient:
        options.append("relax the audience")
    if request.categories:
        options.append("broaden the product type")
    if sidecar.get("minimum_rating") is not None:
        options.append("lower the rating threshold")
    return options


n24m_pre_recommender = N24_APPLICATION_BASES.get(
    "get_n24_recommendations_from_validated_state", globals().get("n24m_pre_recommender")
)
if not callable(n24m_pre_recommender):
    raise RuntimeError("The pre-N24M recommendation entry point is unavailable.")


def get_n24_recommendations_from_validated_state(request, top_n=10, candidate_pool_size=REQUEST_AWARE_DEFAULT_CANDIDATE_POOL_SIZE):
    request = N24ValidatedRecommendationRequest.model_validate(request.model_dump(mode="python"))
    if not isinstance(top_n, int) or top_n < 1:
        raise ValueError("top_n must be a positive integer")
    sidecar = _n24m_deepcopy(N24M_REQUEST_SIDECARS.get(request.request_fingerprint) or _n24m_sidecar(N24M_CURRENT_CHAT_ID.get()))
    ranking_request = request.model_copy(deep=True)
    ranking_request.excluded_categories = []
    ranking_request.excluded_brands = []
    ranking_request.excluded_colours = []
    ranking_request.excluded_materials = []
    ranking_request.excluded_sizes = []
    ranking_request.excluded_product_ids = []
    depth = 500 if request.brands and request.categories else 1500 if request.categories else 2000
    depth = max(depth, top_n * 30)
    cache_payload = {
        "profile_id": request.profile_id, "categories": request.categories,
        "brands": request.brands, "colours": request.colours,
        "materials": request.materials, "sizes": request.sizes,
        "minimum_price": request.minimum_price, "maximum_price": request.maximum_price,
        "occasions": request.occasions, "recipient": request.recipient,
        "depth": depth,
    }
    cache_key = _n24m_json.dumps(cache_payload, sort_keys=True, default=str)
    frozen = N24M_FROZEN_RANK_CACHE.get(cache_key)
    if frozen is None:
        frozen = _n24c_run_frozen_ranking(ranking_request, depth, max(candidate_pool_size, depth))
        N24M_FROZEN_RANK_CACHE[cache_key] = {
            **frozen, "recommendations": frozen["recommendations"].copy(deep=True),
        }
        while len(N24M_FROZEN_RANK_CACHE) > 32:
            N24M_FROZEN_RANK_CACHE.pop(next(iter(N24M_FROZEN_RANK_CACHE)))
    else:
        frozen = {**frozen, "recommendations": frozen["recommendations"].copy(deep=True)}
    eligibility = {}
    eligible_ids = _n24m_eligible_ids(request, sidecar)
    ranked = frozen["recommendations"].copy()
    if not ranked.empty:
        ranked = ranked.loc[ranked["product_id"].astype(str).isin(eligible_ids)].drop_duplicates("product_id").copy()
    selected = ranked.head(top_n).reset_index(drop=True)
    if not selected.empty:
        eligibility = {
            product_id: evaluate_n24_product_eligibility(product_id, request, sidecar)
            for product_id in selected["product_id"].astype(str)
        }
        selected["request_rank"] = _n24l_np.arange(1, len(selected) + 1, dtype=_n24l_np.int32)
        selected["n24m_match_score"] = selected["product_id"].astype(str).map(lambda item: eligibility[item].match_score)
        selected["n24m_match_evidence"] = selected["product_id"].astype(str).map(lambda item: eligibility[item].model_dump(mode="json"))
        selected["matched_request_categories"] = ", ".join(request.categories)
        selected["matched_request_brands"] = ", ".join(request.brands)
        selected["matched_request_colors"] = selected["product_id"].astype(str).map(
            lambda item: ", ".join(N24M_CATALOGUE_INDEX[item]["colour_components"])
        )
        selected["matched_request_materials"] = ", ".join(request.materials)
        selected["matched_request_sizes"] = ", ".join(request.sizes)
        selected["matched_request_occasions"] = ", ".join(request.occasions)
        selected["request_explanation"] = selected["product_id"].astype(str).map(
            lambda item: "N24M verified: " + "; ".join(
                f"{name}={status.value}" for name, status in eligibility[item].attribute_matches.items()
            )
        )
    parsed = _n24c_structured_parsed_request(request)
    parsed["n24m_capability_registry_version"] = N24M_CAPABILITY_REGISTRY_VERSION
    parsed["n24m_sidecar"] = sidecar
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
            "categories": request.categories, "brands": request.brands, "colours": request.colours,
            "recipient": request.recipient, "minimum_price": request.minimum_price,
            "maximum_price": request.maximum_price, "minimum_rating": sidecar.get("minimum_rating"),
        },
        "exclusions_applied": {
            "categories": request.excluded_categories, "brands": request.excluded_brands,
            "colours": request.excluded_colours, "product_ids": request.excluded_product_ids,
            "audiences": sidecar.get("excluded_audiences", []),
        },
        "relaxation_candidates": _n24m_relaxation_options(request, sidecar) if count < top_n else [],
        "clarification_needed": False, "clarification_question": None,
        "category_constraint_mode": "n24m_exact_hierarchy",
        "engine_version": N24M_ELIGIBILITY_ENGINE_VERSION,
        "eligibility_overhead_seconds": None,
    }


n24m_pre_match_score = N24_APPLICATION_BASES.get(
    "calculate_product_match_score", globals().get("n24m_pre_match_score")
)
if not callable(n24m_pre_match_score):
    raise RuntimeError("The pre-N24M match-score entry point is unavailable.")


def calculate_product_match_score(product_row, parsed_request):
    score = getattr(product_row, "n24m_match_score", None)
    evidence = getattr(product_row, "n24m_match_evidence", None)
    if score is not None and not (_n24m_math.isnan(score) if isinstance(score, float) else False):
        if isinstance(evidence, dict):
            phrase = "; ".join(f"{name}: {status}" for name, status in evidence.get("attribute_matches", {}).items())
        else:
            phrase = "all supported explicit constraints were verified by N24M"
        return round(float(score), 2), phrase
    return n24m_pre_match_score(product_row, parsed_request)


n24m_pre_card_builder = N24_APPLICATION_BASES.get(
    "build_final_recommendation_cards", globals().get("n24m_pre_card_builder")
)
if not callable(n24m_pre_card_builder):
    raise RuntimeError("The pre-N24M card-builder entry point is unavailable.")


def build_final_recommendation_cards(request_result: dict, top_n=FINAL_PRODUCT_CARD_DEFAULT_TOP_N):
    built = n24m_pre_card_builder(request_result, top_n=top_n)
    cards = built.get("cards")
    recommendations = request_result.get("recommendations")
    if cards is None or recommendations is None or cards.empty or recommendations.empty:
        return built
    evidence_lookup = {}
    for row in recommendations.to_dict("records"):
        product_id = str(row.get("product_id"))
        evidence = row.get("n24m_match_evidence")
        if isinstance(evidence, dict):
            evidence_lookup[product_id] = evidence
    cards = cards.copy()
    cards["eligibility_evidence"] = cards["product_id"].astype(str).map(evidence_lookup)
    cards["matched_attributes"] = cards["eligibility_evidence"].map(
        lambda item: [] if not isinstance(item, dict) else [
            f"{name}:{status}" for name, status in item.get("attribute_matches", {}).items()
        ]
    )
    cards["audience"] = cards["product_id"].astype(str).map(
        lambda item: N24M_CATALOGUE_INDEX.get(item, {}).get("audience")
    )
    cards["colour_components"] = cards["product_id"].astype(str).map(
        lambda item: N24M_CATALOGUE_INDEX.get(item, {}).get("colour_components", [])
    )
    built["cards"] = cards
    built["product_card_version"] = "n24m_eligibility_cards_v1"
    return built


def _n24m_enrich_superlative(selected, request, sidecar, operation):
    selected = selected.copy()
    if selected.empty:
        return selected
    evidence = evaluate_n24_product_eligibility(str(selected.iloc[0]["product_id"]), request, sidecar)
    selected["profile_id"] = request.profile_id
    selected["original_request"] = request.request_display_text
    selected["request_rank"] = _n24l_np.arange(1, len(selected) + 1, dtype=_n24l_np.int32)
    selected["currency"] = request.currency
    selected["request_score"] = 1.0
    selected["normalised_base_score"] = 1.0
    selected["quality_score"] = 1.0
    selected["request_match_boost"] = 0.0
    selected["matched_request_categories"] = ", ".join(request.categories)
    selected["matched_request_brands"] = ", ".join(request.brands)
    selected["matched_request_colors"] = ", ".join(N24M_CATALOGUE_INDEX[str(selected.iloc[0]["product_id"])]["colour_components"])
    selected["matched_request_materials"] = ", ".join(request.materials)
    selected["matched_request_sizes"] = ", ".join(request.sizes)
    selected["matched_request_occasions"] = ", ".join(request.occasions)
    selected["request_explanation"] = f"Deterministic N24M {operation.replace('_', ' ')} over eligible catalogue products."
    selected["base_strategy"] = "n24m_catalogue_superlative"
    selected["base_rank"] = selected["request_rank"]
    selected["n24m_match_score"] = evidence.match_score
    selected["n24m_match_evidence"] = [evidence.model_dump(mode="json")]
    return selected


def _n24m_drop_price_outliers(sorted_eligible, cheapest: bool):
    """Guard the price-superlative pick against single-row pricing errors in
    the historical dataset -- e.g. a $479.85 sandal whose own brand's other
    listings top out at $72 (a real case found in this catalogue). Only
    trims the extreme end of an already-sorted, already-eligible frame;
    never changes eligibility itself, and only engages with enough rows for
    a percentile to be meaningful.
    """
    if len(sorted_eligible) < 8:
        return sorted_eligible
    metric = sorted_eligible["_metric"]
    reference = metric.quantile(0.05 if cheapest else 0.95)
    if reference <= 0:
        return sorted_eligible
    fence = reference / 4.0 if cheapest else reference * 4.0
    kept = sorted_eligible.loc[metric >= fence] if cheapest else sorted_eligible.loc[metric <= fence]
    return kept if not kept.empty else sorted_eligible


def n24l_superlative_recommendation(request, operation: str):
    sidecar = _n24m_deepcopy(N24M_REQUEST_SIDECARS.get(request.request_fingerprint) or _n24m_sidecar(N24M_CURRENT_CHAT_ID.get()))
    eligible_ids = _n24m_eligible_ids(request, sidecar)
    eligible = application_request_metadata_df.loc[
        application_request_metadata_df["product_id"].astype(str).isin(eligible_ids)
    ].drop_duplicates("product_id").copy()
    if operation in {"costliest", "cheapest"}:
        eligible["_metric"] = _n24l_pd.to_numeric(eligible["price"], errors="coerce")
        eligible = eligible.loc[eligible["_metric"].notna()].sort_values(
            ["_metric", "product_id"], ascending=[operation == "cheapest", True], kind="mergesort"
        )
        eligible = _n24m_drop_price_outliers(eligible, cheapest=(operation == "cheapest"))
    elif operation == "highest_rated":
        eligible["_metric"] = _n24l_pd.to_numeric(eligible["average_rating"], errors="coerce")
        eligible["_tie"] = _n24l_pd.to_numeric(eligible["rating_number"], errors="coerce").fillna(0)
        eligible = eligible.loc[eligible["_metric"].notna()].sort_values(
            ["_metric", "_tie", "product_id"], ascending=[False, False, True], kind="mergesort"
        )
    elif operation == "most_reviewed":
        eligible["_metric"] = _n24l_pd.to_numeric(eligible["rating_number"], errors="coerce")
        eligible["_tie"] = _n24l_pd.to_numeric(eligible["average_rating"], errors="coerce").fillna(0)
        eligible = eligible.loc[eligible["_metric"].notna()].sort_values(
            ["_metric", "_tie", "product_id"], ascending=[False, False, True], kind="mergesort"
        )
    else:
        raise ValueError("Unsupported catalogue superlative.")
    selected = eligible.head(1).drop(columns=[item for item in ("_metric", "_tie", "request_search_text") if item in eligible.columns])
    selected = _n24m_enrich_superlative(selected, request, sidecar, operation)
    result = _n24l_recommendation_result(request, selected.to_dict("records"))
    result.update({
        "recommendations": selected.reset_index(drop=True), "eligible_catalogue_count": len(eligible),
        "superlative_operation": operation, "engine_version": N24M_ELIGIBILITY_ENGINE_VERSION,
    })
    return result


def _n24m_operation(operation, value=None):
    return N24FieldOperation(operation=operation, value=value, confidence=1.0)


def _n24m_extract_categories(text: str) -> list[str]:
    lower = _n24m_normalize(text)
    for alias in sorted(_N24M_CATEGORY_ALIASES, key=len, reverse=True):
        if _n24m_re.search(rf"\b{_n24m_re.escape(_n24m_normalize(alias))}\b", lower):
            return list(_N24M_CATEGORY_ALIASES[alias])
    return []


def _n24m_extract_brands(text: str) -> tuple[list[str], list[str], str | None]:
    lower = _n24m_normalize(text)
    positive, excluded = [], []
    for normalized, canonical in sorted(_N24M_BRAND_CANONICAL.items(), key=lambda item: len(item[0]), reverse=True):
        if len(normalized) < 3 or not _n24m_re.search(rf"\b{_n24m_re.escape(normalized)}\b", lower):
            continue
        if normalized in _N24M_AMBIGUOUS_BRAND_TOKENS and not _n24m_re.search(
            rf"\b(?:brand|from)\s+{_n24m_re.escape(normalized)}\b", lower
        ):
            continue
        match = _n24m_re.search(rf"\b{_n24m_re.escape(normalized)}\b", lower)
        prefix = lower[max(0, match.start() - 35):match.start()]
        if _n24m_re.search(r"(?:\bnot\b|\bno\b|\bexcept\b|\bexcluding\b|\bwithout\b)\s+(?:brand\s+)?$", prefix):
            if canonical not in excluded:
                excluded.append(canonical)
        elif canonical not in positive:
            positive.append(canonical)
    unknown = None
    from_match = _n24m_re.search(r"\bfrom\s+([a-z][a-z0-9' -]{1,30})", lower)
    if from_match and not positive and not excluded:
        candidate = from_match.group(1).strip().split(" for ")[0].split(" under ")[0].strip()
        if candidate and candidate not in {"which", "this", "that", "any brand"}:
            unknown = candidate
    return positive, excluded, unknown


def _n24m_extract_colours_from_request(text: str) -> tuple[list[str], list[str]]:
    lower = _n24m_normalize(text)
    positive, excluded = [], []
    request_aliases = {
        "white": "white", "black": "black", "gray": "grey", "grey": "grey",
        "blue": "blue", "navy": "blue", "red": "red", "pink": "pink",
        "green": "green", "purple": "purple", "yellow": "yellow", "orange": "orange",
        "brown": "brown", "tan": "tan", "beige": "beige", "silver": "silver", "gold": "gold",
    }
    for word, canonical in request_aliases.items():
        for match in _n24m_re.finditer(rf"\b{word}\b", lower):
            prefix = lower[max(0, match.start() - 40):match.start()]
            negative = bool(_n24m_re.search(r"(?:\bnot\b|\bno\b|\bexcept\b|\bexcluding\b|\bwithout\b|anything except)\s+$", prefix))
            target = excluded if negative else positive
            if canonical not in target:
                target.append(canonical)
    return positive, excluded


def _n24m_extract_audience_request(text: str) -> tuple[str | None, list[str]]:
    lower = _n24m_normalize(text)
    excluded = []
    mapping = [
        (("unisex adult", "unisex"), "unisex adult"),
        (("for women", "women's", "womens", "ladies", "woman", "women", "female"), "women"),
        (("for men", "men's", "mens", "man", "men", "male"), "men"),
        (("for boys", "boys'", "boys", "boy"), "boys"),
        (("for girls", "girls'", "girls", "girl"), "girls"),
        (("for kids", "kids'", "kids", "kid", "children", "children's"), "kids"),
        (("toddler", "baby"), "toddler"),
    ]
    for phrases, canonical in mapping:
        for phrase in phrases:
            norm = _n24m_normalize(phrase)
            match = _n24m_re.search(rf"\b{_n24m_re.escape(norm)}\b", lower)
            if not match:
                continue
            prefix = lower[max(0, match.start() - 25):match.start()]
            if _n24m_re.search(r"(?:\bnot\b|\bno\b|\bexcept\b|\bexcluding\b|\bwithout\b)\s*$", prefix):
                excluded.append(canonical)
                continue
            return canonical, excluded
    return None, excluded


def _n24m_price_operations(text: str):
    lower = _n24m_normalize(text.replace("$", " $"))
    between = _n24m_re.search(r"\bbetween\s+\$?\s*(\d+(?:\.\d+)?)\s+(?:and|to)\s+\$?\s*(\d+(?:\.\d+)?)", lower)
    if between:
        low, high = sorted((float(between.group(1)), float(between.group(2))))
        return {"minimum_price": _n24m_operation(N24FieldOperationType.SET, low), "maximum_price": _n24m_operation(N24FieldOperationType.SET, high), "price_mode": _n24m_operation(N24FieldOperationType.SET, N24PriceMode.RANGE.value)}
    around = _n24m_re.search(r"\b(?:around|about|roughly)\s+\$?\s*(\d+(?:\.\d+)?)", lower)
    if around:
        value = float(around.group(1))
        return {"minimum_price": _n24m_operation(N24FieldOperationType.SET, round(value * 0.8, 2)), "maximum_price": _n24m_operation(N24FieldOperationType.SET, round(value * 1.2, 2)), "price_mode": _n24m_operation(N24FieldOperationType.SET, N24PriceMode.APPROXIMATE.value)}
    maximum = _n24m_re.search(r"\b(?:under|below|less than|max(?:imum)?(?: price)?(?: of)?|budget(?: is| of)?|up to)\s+\$?\s*(\d+(?:\.\d+)?)", lower)
    if maximum:
        return {"maximum_price": _n24m_operation(N24FieldOperationType.SET, float(maximum.group(1))), "price_mode": _n24m_operation(N24FieldOperationType.SET, N24PriceMode.EXACT_MAX.value)}
    minimum = _n24m_re.search(r"\b(?:over|above|more than|at least)\s+\$?\s*(\d+(?:\.\d+)?)", lower)
    if minimum:
        return {"minimum_price": _n24m_operation(N24FieldOperationType.SET, float(minimum.group(1))), "price_mode": _n24m_operation(N24FieldOperationType.SET, N24PriceMode.RANGE.value)}
    replacement = _n24m_re.search(r"\b(?:raise|increase|change|set)(?: the)?(?: budget| limit| price)?(?: to)?\s+\$?\s*(\d+(?:\.\d+)?)", lower)
    if replacement:
        return {"maximum_price": _n24m_operation(N24FieldOperationType.REPLACE, float(replacement.group(1))), "price_mode": _n24m_operation(N24FieldOperationType.SET, N24PriceMode.EXACT_MAX.value)}
    return {}


def _n24m_rating_constraint(text: str):
    lower = _n24m_normalize(text)
    match = _n24m_re.search(r"\b(?:rating\s*(?:of|at least|above|over)?|(?:rated\s*)?(?:at least|above|over))\s*(\d(?:\.\d+)?)\s*(?:stars?)?", lower)
    if not match:
        match = _n24m_re.search(r"\b(\d(?:\.\d+)?)\s+stars?\s+(?:or higher|minimum|and above)", lower)
    if not match:
        return None, False
    value = float(match.group(1))
    if not 0 <= value <= 5:
        return None, False
    exclusive = bool(_n24m_re.search(r"\b(?:above|over)\s+" + _n24m_re.escape(match.group(1)), lower))
    return value, exclusive


def _n24m_is_new_goal(text: str, categories: list[str], state) -> bool:
    if not categories:
        return False
    prior = {_n24m_normalize(item) for item in state.hard_request.categories}
    current = {_n24m_normalize(item) for item in categories}
    if prior and prior != current:
        return True
    lower = _n24m_normalize(text)
    return bool(prior and _n24m_re.search(r"\b(?:now|instead|actually forget|new search|i need|show me|find me|looking for)\b", lower))


def _n24m_question_delta(text, active_result_set):
    refs = _n24l_refs(text, active_result_set)
    return N24TurnDelta(intent=N24Intent.PRODUCT_QUESTION, result_reference=refs[:1], confidence=1.0, raw_message=text)


def interpret_n24m_deterministic_turn(raw_message: str, context, state, active_result_set):
    text = " ".join(str(raw_message).strip().split())
    lower = _n24m_normalize(text)
    if not lower:
        return None
    chat_id = int(context.chat_id)

    if _n24m_re.search(r"\b(?:ignore|disregard|override)\b.{0,45}\b(?:instruction|prompt|rule)s?\b", lower):
        return N24TurnDelta(intent=N24Intent.GENERAL_SHOPPING_ADVICE, confidence=1.0, raw_message=text), {"semantic_guard": "n24m_prompt_injection", "superlative": None}, {}

    if (
        _n24m_re.search(r"\bwhat should i look for\b", lower)
        or _n24m_re.search(r"\bwhich (?:type|kind) of .+? (?:is|are) (?:good|best|better) for\b", lower)
        or _n24m_re.search(r"\bhow (?:should|do) i (?:choose|pick|buy)\b", lower)
    ):
        return N24TurnDelta(
            intent=N24Intent.GENERAL_SHOPPING_ADVICE,
            confidence=1.0,
            raw_message=text,
        ), {"semantic_guard": "n24m_general_shopping_advice_no_mutation", "superlative": None}, {}

    unsupported = []
    if _n24m_re.search(r"\b(?:current|live|today s?)\s+(?:amazon\s+)?price\b", lower): unsupported.append(N24UnsupportedCommerceTopic.LIVE_CURRENT_PRICE)
    if _n24m_re.search(r"\b(?:deliver|delivery|arrive|arrival|tomorrow)\b", lower): unsupported.append(N24UnsupportedCommerceTopic.DELIVERY)
    if _n24m_re.search(r"\b(?:in stock|stock availability)\b", lower): unsupported.append(N24UnsupportedCommerceTopic.STOCK)
    if _n24m_re.search(r"\b(?:coupon|promo code)\b", lower): unsupported.append(N24UnsupportedCommerceTopic.COUPON)
    if _n24m_re.search(r"\b(?:size availability|available in size|current size)\b", lower): unsupported.append(N24UnsupportedCommerceTopic.UNSUPPORTED_SIZE_AVAILABILITY)
    if unsupported:
        return N24TurnDelta(intent=N24Intent.UNSUPPORTED_DATA_QUESTION, unsupported_commerce=N24UnsupportedCommerceRequest(topics=list(dict.fromkeys(unsupported))), confidence=1.0, raw_message=text), {"semantic_guard": "n24m_unsupported_commerce", "superlative": None}, {}

    if _n24m_re.search(r"\b(?:complete\s+)?outfit\b|\bbuild\s+(?:me\s+)?(?:a\s+)?look\b", lower):
        audience, _ = _n24m_extract_audience_request(text)
        price_fields = _n24m_price_operations(text)
        outfit_colours, _ = _n24m_extract_colours_from_request(text)
        fields = N24FieldOperations(
            recipient=_n24m_operation(N24FieldOperationType.SET, audience) if audience else None,
            colours=(
                _n24m_operation(N24FieldOperationType.SET, outfit_colours)
                if outfit_colours else None
            ),
            maximum_price=price_fields.get("maximum_price"),
        )
        return N24TurnDelta(
            intent=N24Intent.OUTFIT_REQUEST, field_operations=fields,
            outfit_operation=N24OutfitOperation(operation=N24OutfitOperationType.CREATE),
            confidence=1.0, raw_message=text,
        ), {"semantic_guard": "n24m_outfit_route", "superlative": None}, {}

    if _n24m_re.search(r"\bgift\b", lower):
        return N24TurnDelta(
            intent=N24Intent.GIFT_REQUEST, confidence=1.0, raw_message=text,
        ), {"semantic_guard": "n24m_gift_route", "superlative": None}, {}

    if active_result_set is not None and "compare" in lower and len(_n24l_refs(text, active_result_set)) >= 2:
        return N24TurnDelta(intent=N24Intent.COMPARE, result_reference=_n24l_refs(text, active_result_set), confidence=1.0, raw_message=text), {"semantic_guard": "n24m_comparison", "superlative": None}, {}
    if active_result_set is not None and _n24l_refs(text, active_result_set) and _n24m_re.search(r"\b(?:tell|explain|show|open|link|about)\b", lower):
        return N24TurnDelta(intent=N24Intent.PRODUCT_REFERENCE, result_reference=_n24l_refs(text, active_result_set)[:1], confidence=1.0, raw_message=text), {"semantic_guard": "n24m_reference", "superlative": None}, {}

    relative = None
    if _n24m_re.search(r"\b(?:anything|show me|ones?)?\s*cheaper\b", lower): relative = N24RelativeOperationType.CHEAPER
    elif _n24m_re.search(r"\bmore expensive\b", lower): relative = N24RelativeOperationType.MORE_EXPENSIVE
    elif _n24m_re.search(r"\b(?:higher|better)[ -]?rated\b", lower): relative = N24RelativeOperationType.HIGHER_RATED
    elif _n24m_re.search(r"\bmost\s+(?:reviewed|reviews)\b|\bmore reviewed\b", lower): relative = N24RelativeOperationType.MOST_REVIEWED
    elif _n24m_re.search(r"\bcheapest\b", lower): relative = N24RelativeOperationType.CHEAPEST
    elif _n24m_re.search(r"\bbetter match\b|\bbetter options?\b", lower): relative = N24RelativeOperationType.BETTER_MATCH
    if active_result_set is not None and relative is not None and not _n24m_extract_categories(text):
        N24M_PENDING_RELATIVE[chat_id] = relative
        return N24TurnDelta(intent=N24Intent.SHOW_MORE, pagination=N24PaginationOperation(show_more=True), relative_operation=relative, confidence=1.0, raw_message=text), {"semantic_guard": "n24m_active_result_relative", "superlative": None}, {}

    if active_result_set is not None and (
        _n24m_re.match(r"^(?:why|are|is|which brand|what brand|why did)\b", lower)
        or "why this one" in lower
    ):
        return _n24m_question_delta(text, active_result_set), {"semantic_guard": "n24m_question_no_mutation", "superlative": None}, {}

    if lower in {"show me more", "show more", "more", "more products", "more options", "anything else"}:
        return N24TurnDelta(intent=N24Intent.SHOW_MORE, pagination=N24PaginationOperation(show_more=True), confidence=1.0, raw_message=text), {"semantic_guard": "n24m_show_more", "superlative": None}, {}

    positive_brands, excluded_brands, unknown_brand = _n24m_extract_brands(text)
    positive_colours, excluded_colours = _n24m_extract_colours_from_request(text)
    categories = _n24m_extract_categories(text)
    audience, excluded_audiences = _n24m_extract_audience_request(text)

    if _n24m_re.search(r"\b(?:i like|i prefer|my favorite|my favourite)\b", lower) and (positive_brands or positive_colours):
        preference_type = "brand" if positive_brands else "color"
        value = (positive_brands or positive_colours)[0]
        return N24TurnDelta(intent=N24Intent.PROFILE_UPDATE, profile_update=N24ProfileUpdate(operation=N24ProfilePreferenceOperation.ADD_PREFERENCE, preference_type=preference_type, value=value, weight=1.0), confidence=1.0, raw_message=text), {"semantic_guard": "n24m_soft_preference_add", "superlative": None}, {}
    if _n24m_re.search(r"\b(?:i don t like|remove my preference|don t prefer)\b", lower) and (positive_brands or positive_colours):
        preference_type = "brand" if positive_brands else "color"
        value = (positive_brands or positive_colours)[0]
        return N24TurnDelta(intent=N24Intent.PROFILE_UPDATE, profile_update=N24ProfileUpdate(operation=N24ProfilePreferenceOperation.REMOVE_PREFERENCE, preference_type=preference_type, value=value, weight=1.0), confidence=1.0, raw_message=text), {"semantic_guard": "n24m_soft_preference_remove", "superlative": None}, {}

    if _n24m_re.search(r"\bwhich brand\b.*\b(?:costly|expensive)\b", lower):
        fields = N24FieldOperations(categories=_n24m_operation(N24FieldOperationType.SET, categories) if categories else None)
        return N24TurnDelta(intent=N24Intent.NEW_GOAL, field_operations=fields, confidence=1.0, requires_clarification=True, clarification_question="Do you want the costliest individual product, or the brand with the highest-priced products?", raw_message=text), {"semantic_guard": "n24m_ambiguous_brand_superlative", "superlative": None}, {}

    clear_budget = bool(_n24m_re.search(r"\b(?:forget|remove|ignore)\s+(?:the\s+)?(?:budget|price|price limit)\b|\bprice doesn t matter\b|\bdon t worry about (?:the )?budget\b|\bregardless of price\b|\bno budget limit\b", lower))
    clear_brand = bool(_n24m_re.search(r"\bany brand (?:is )?(?:fine|okay|ok)\b|\bit doesn t have to be\b", lower))
    clear_colour = bool(_n24m_re.search(r"\bany colou?r (?:is )?(?:fine|okay|ok)\b", lower))
    allow_mixed = bool(_n24m_re.search(r"\bmixed colou?rs? (?:are )?(?:fine|okay|ok|allowed)\b", lower))
    if clear_budget or clear_brand or clear_colour or allow_mixed:
        fields = N24FieldOperations(
            brands=_n24m_operation(N24FieldOperationType.CLEAR) if clear_brand else None,
            colours=_n24m_operation(N24FieldOperationType.CLEAR) if clear_colour else None,
            minimum_price=_n24m_operation(N24FieldOperationType.CLEAR) if clear_budget else None,
            maximum_price=_n24m_operation(N24FieldOperationType.CLEAR) if clear_budget else None,
            price_mode=_n24m_operation(N24FieldOperationType.CLEAR) if clear_budget else None,
        )
        return N24TurnDelta(intent=N24Intent.REFINE, field_operations=fields, confidence=1.0, raw_message=text), {"semantic_guard": "n24m_clear_relax", "superlative": None}, {"allow_mixed_colours": True if allow_mixed else None}

    if unknown_brand:
        return N24TurnDelta(intent=N24Intent.PRODUCT_SEARCH, confidence=1.0, requires_clarification=True, clarification_question=f"I could not verify '{unknown_brand}' as a catalogue brand. Which known brand did you mean?", raw_message=text), {"semantic_guard": "n24m_unknown_brand", "superlative": None}, {}

    material_terms = [item for item in sorted(_N24M_MATERIAL_TERMS, key=len, reverse=True) if _n24m_re.search(rf"\b{_n24m_re.escape(item)}\b", lower)]
    style_terms = [item for item in sorted(_N24M_STYLE_TERMS, key=len, reverse=True) if _n24m_re.search(rf"\b{_n24m_re.escape(item)}\b", lower)]
    if material_terms and _n24m_re.search(r"\b(?:not|no|except|excluding|without)\b", lower):
        return N24TurnDelta(intent=N24Intent.GENERAL_SHOPPING_ADVICE, confidence=1.0, requires_clarification=True, clarification_question="Material coverage is too sparse to guarantee that exclusion from this historical catalogue. Would you like to continue without a hard material filter?", raw_message=text), {"semantic_guard": "n24m_material_exclusion_unsupported", "superlative": None}, {"limitations": ["material_hard_filter_unsupported"]}
    if _n24m_re.search(r"\bsize\s+[a-z0-9.-]+\b", lower):
        return N24TurnDelta(intent=N24Intent.UNSUPPORTED_DATA_QUESTION, unsupported_commerce=N24UnsupportedCommerceRequest(topics=[N24UnsupportedCommerceTopic.UNSUPPORTED_SIZE_AVAILABILITY]), confidence=1.0, raw_message=text), {"semantic_guard": "n24m_size_unsupported", "superlative": None}, {"limitations": ["size_availability_unsupported"]}

    fields_data = {}
    if categories:
        fields_data["categories"] = _n24m_operation(N24FieldOperationType.REPLACE if _n24m_is_new_goal(text, categories, state) else N24FieldOperationType.SET, categories)
    if positive_brands:
        replace = bool(_n24m_re.search(r"\b(?:actually|instead|make that)\b", lower))
        fields_data["brands"] = _n24m_operation(N24FieldOperationType.REPLACE if replace else N24FieldOperationType.SET, positive_brands)
    elif excluded_brands:
        fields_data["brands"] = _n24m_operation(N24FieldOperationType.EXCLUDE, excluded_brands)
    if positive_colours:
        replace = bool(_n24m_re.search(r"\b(?:actually|instead|make (?:them|it)|change)\b", lower))
        fields_data["colours"] = _n24m_operation(N24FieldOperationType.REPLACE if replace else N24FieldOperationType.SET, positive_colours)
    elif excluded_colours:
        fields_data["colours"] = _n24m_operation(N24FieldOperationType.EXCLUDE, excluded_colours)
    if audience:
        fields_data["recipient"] = _n24m_operation(N24FieldOperationType.SET, audience)
    fields_data.update(_n24m_price_operations(text))

    minimum_rating, rating_exclusive = _n24m_rating_constraint(text)
    updates = {
        "minimum_rating": minimum_rating,
        "rating_exclusive": rating_exclusive,
        "excluded_audiences": excluded_audiences or None,
        "allow_mixed_colours": True if len(positive_colours) > 1 else None,
        "soft_materials": material_terms or None,
        "style_context": style_terms or None,
    }

    superlative = None
    relative_operation = None
    if _n24m_re.search(r"\b(?:costliest|most expensive)\b", lower): superlative, relative_operation = "costliest", N24RelativeOperationType.MORE_EXPENSIVE
    elif _n24m_re.search(r"\bcheapest\b|\bcheap\b", lower): superlative, relative_operation = "cheapest", N24RelativeOperationType.CHEAPEST
    elif _n24m_re.search(r"\bhighest[ -]?rated\b|\bbest[ -]?rated\b", lower): superlative, relative_operation = "highest_rated", N24RelativeOperationType.HIGHER_RATED
    elif _n24m_re.search(r"\bmost[ -]?reviewed\b|\bmost reviews\b", lower): superlative, relative_operation = "most_reviewed", N24RelativeOperationType.MOST_REVIEWED

    if excluded_audiences and not fields_data:
        intent = N24Intent.REFINE if state.hard_request.categories else N24Intent.PRODUCT_SEARCH
    elif _n24m_is_new_goal(text, categories, state):
        intent = N24Intent.NEW_GOAL
    elif fields_data or minimum_rating is not None or material_terms or style_terms:
        intent = N24Intent.REFINE if (state.hard_request.categories and not categories) else N24Intent.PRODUCT_SEARCH
    else:
        return None
    return N24TurnDelta(intent=intent, field_operations=N24FieldOperations(**fields_data), relative_operation=relative_operation, confidence=1.0, raw_message=text), {"semantic_guard": "n24m_deterministic_semantics", "superlative": superlative}, updates


def _n24m_apply_updates(chat_id: int, delta, updates: dict):
    if delta.intent == N24Intent.NEW_GOAL:
        current = _n24m_default_sidecar()
    else:
        current = _n24m_deepcopy(_n24m_sidecar(chat_id))
    for key, value in updates.items():
        if value is not None:
            current[key] = value
    if getattr(delta, "field_operations", None):
        if delta.field_operations.colours and delta.field_operations.colours.operation == N24FieldOperationType.CLEAR:
            current["allow_mixed_colours"] = False
        if delta.field_operations.categories and delta.intent == N24Intent.NEW_GOAL:
            current["minimum_rating"] = updates.get("minimum_rating")
            current["rating_exclusive"] = updates.get("rating_exclusive", False)
    current["state_version"] = N24M_STATE_VERSION
    N24M_CHAT_CONSTRAINTS[int(chat_id)] = current
    return current


if "n24m_pre_interpret_turn" not in globals():
    n24m_pre_interpret_turn = n24l_interpret_turn


def n24l_interpret_turn(raw_message: str, context, state, active_result_set):
    chat_id = int(context.chat_id)
    N24M_CURRENT_CHAT_ID.set(chat_id)
    parsed = interpret_n24m_deterministic_turn(raw_message, context, state, active_result_set)
    if parsed is not None:
        delta, guard, updates = parsed
        _n24m_apply_updates(chat_id, delta, updates)
        return delta, guard, {
            "intent": 0, "response": 0, "repair": 0, "total": 0,
            "interpreter_status": "N24M_DETERMINISTIC", "interpreter_latency_seconds": 0.0,
            "semantic_guard": guard["semantic_guard"], "ollama_available": bool(n24l_detect_ollama().get("available")),
            "model_available": bool(n24l_detect_ollama().get("model_available")),
        }
    delta, guard, metrics = n24m_pre_interpret_turn(raw_message, context, state, active_result_set)
    if delta is not None:
        _n24m_apply_updates(chat_id, delta, {})
    guard = dict(guard or {})
    guard["n24m_validated"] = True
    return delta, guard, metrics


n24m_pre_build_request = N24_APPLICATION_BASES.get(
    "build_n24_validated_recommendation_request", globals().get("n24m_pre_build_request")
)
if not callable(n24m_pre_build_request):
    raise RuntimeError("The pre-N24M request compiler is unavailable.")


def build_n24_validated_recommendation_request(profile_id, hard_state, exclusion_state):
    request = n24m_pre_build_request(profile_id, hard_state, exclusion_state)
    chat_id = N24M_CURRENT_CHAT_ID.get()
    N24M_REQUEST_SIDECARS[request.request_fingerprint] = _n24m_deepcopy(_n24m_sidecar(chat_id))
    return request


n24m_pre_show_more = N24_APPLICATION_BASES.get(
    "show_more_n24_results", globals().get("n24m_pre_show_more")
)
if not callable(n24m_pre_show_more):
    raise RuntimeError("The pre-N24M show-more entry point is unavailable.")


def show_more_n24_results(active_result_set, *, chat_id, top_n=10, source_message_id=None):
    operation = N24M_PENDING_RELATIVE.pop(int(chat_id), None)
    if operation is None:
        return n24m_pre_show_more(active_result_set, chat_id=chat_id, top_n=top_n, source_message_id=source_message_id)
    relative = refine_n24_result_set_relative(active_result_set, operation, chat_id=chat_id)
    if relative.result_set is None:
        # An exhausted relative refinement is not a new result set.  Keeping
        # the immutable set the user actually saw preserves ordinal/reference
        # memory and avoids constructing a schema-less empty DataFrame.
        return N24PaginationResult(
            status="EXHAUSTED", result_set=active_result_set,
            exact_match_count=0, exhausted=True, constraints_relaxed=False,
        )
    return N24PaginationResult(
        status="CONTINUATION_READY" if relative.ordered_product_ids else "EXHAUSTED",
        result_set=relative.result_set, exact_match_count=len(relative.ordered_product_ids),
        exhausted=not bool(relative.ordered_product_ids), constraints_relaxed=False,
    )


if "n24m_pre_load_state" not in globals():
    n24m_pre_load_state = n24l_load_persistent_state
if "n24m_pre_save_state" not in globals():
    n24m_pre_save_state = n24l_save_persistent_state


def n24l_load_persistent_state(chat_id: int, user_id: int):
    root, payload, state, active = n24m_pre_load_state(chat_id, user_id)
    canonical_raw = payload.get("canonical_request_state")
    if isinstance(canonical_raw, dict):
        try:
            canonical = N24CanonicalRequestState.model_validate(canonical_raw)
            state = state.model_copy(update={
                "hard_request": canonical.hard_request.model_copy(deep=True),
                "exclusions": canonical.exclusions.model_copy(deep=True),
            })
            restored_sidecar = _n24m_sidecar_from_canonical(canonical)
            persisted_offer = payload.get("pending_offer")
            if isinstance(persisted_offer, dict) and persisted_offer.get("status") == "pending":
                restored_sidecar["pending_relaxation"] = _n24m_deepcopy(persisted_offer)
            N24M_CHAT_CONSTRAINTS[int(chat_id)] = restored_sidecar
        except Exception:
            canonical = None
    else:
        canonical = None
    if canonical is None:
        # One-way compatibility migration for chats written before the
        # canonical request-state contract existed.
        stored = payload.get("n24m_constraints")
        if isinstance(stored, dict) and stored.get("state_version") == N24M_STATE_VERSION:
            N24M_CHAT_CONSTRAINTS[int(chat_id)] = _n24m_deepcopy(stored)
        else:
            _n24m_sidecar(chat_id)
    N24M_CURRENT_CHAT_ID.set(int(chat_id))
    return root, payload, state, active


def n24l_save_persistent_state(chat_id, user_id, state, active_result_set=None, *, active_goal=None, pending_clarification=None):
    payload = n24m_pre_save_state(
        chat_id, user_id, state, active_result_set,
        active_goal=active_goal, pending_clarification=pending_clarification,
    )
    root = _n24l_root_state(chat_id, user_id)
    saved = root.get(N24L_STATE_KEY)
    if isinstance(saved, dict):
        canonical = _n24m_canonical_request_state(
            state, _n24m_sidecar(chat_id), saved.get("pending_offer")
        )
        saved["canonical_request_state"] = canonical.model_dump(mode="json")
        # Do not maintain two writable persisted representations.  Loading
        # still understands the legacy field for existing chats.
        saved.pop("n24m_constraints", None)
        root[N24L_STATE_KEY] = saved
        save_chat_active_request_state(chat_id=chat_id, user_id=user_id, state=root)
        payload = saved
    return payload


if "n24m_pre_result_question" not in globals():
    n24m_pre_result_question = _n24l_result_question_data


def _n24l_result_question_data(raw_message: str, active_result_set, chat_id: int):
    entry = _n24d_get_entry(active_result_set.result_set_id, chat_id)
    rows = []
    for row in entry["recommendation_result"]["recommendations"].head(10).to_dict("records"):
        product_id = str(row.get("product_id"))
        evidence = N24M_CATALOGUE_INDEX.get(product_id, {})
        rows.append({
            "product_id": product_id, "title": row.get("title"), "brand": row.get("brand"),
            "categories": evidence.get("categories"), "colour_components": evidence.get("colour_components"),
            "audience": evidence.get("audience"), "historical_price": row.get("price"),
            "rating": row.get("average_rating"), "review_count": row.get("rating_number"),
        })
    explanation = "The shopping state was not changed by this question. "
    if rows:
        explanation += "The displayed products retain their N24M eligibility evidence: " + "; ".join(
            f"{item['brand']} / {','.join(item.get('colour_components') or ['colour unknown'])} / {item.get('audience')}"
            for item in rows[:3]
        ) + "."
    return {"question": raw_message, "explanation": explanation, "products": rows}


if "n24m_pre_compose" not in globals():
    n24m_pre_compose = _n24l_compose


def _n24l_compose(raw_message: str, orchestration, call_metrics: dict):
    response = n24m_pre_compose(raw_message, orchestration, call_metrics)
    if orchestration.status != "no_exact_match":
        return response
    request = orchestration.validated_request
    sidecar = _n24m_deepcopy(N24M_REQUEST_SIDECARS.get(request.request_fingerprint) or _n24m_default_sidecar()) if request is not None else _n24m_default_sidecar()
    parts = []
    if request is not None:
        if request.colours: parts.append("/".join(request.colours))
        if request.brands: parts.append("/".join(request.brands))
        if request.recipient: parts.append(str(request.recipient))
        if request.categories: parts.append(" ".join(request.categories))
        if request.maximum_price is not None: parts.append(f"under ${request.maximum_price:g}")
        if request.minimum_price is not None: parts.append(f"above ${request.minimum_price:g}")
        if sidecar.get("minimum_rating") is not None: parts.append(f"rated at least {sidecar['minimum_rating']:g}")
    options = _n24m_relaxation_options(request, sidecar) if request is not None else []
    message = "I found no exact match for " + (" ".join(parts) if parts else "those verified constraints") + "."
    if options:
        message += " I can " + ", ".join(options[:-1]) + ((" or " + options[-1]) if len(options) > 1 else options[0]) + "."
    return N24GroundedResponse(
        status=response.status, message=message, response_type=response.response_type,
        cards=response.cards, comparison=response.comparison, referenced_products=response.referenced_products,
        clarification=response.clarification, limitations=response.limitations,
        preference_update_summary=response.preference_update_summary, result_set_id=response.result_set_id,
        generated_by="n24m_deterministic_no_match_v1", warnings=[*response.warnings, "n24m_no_silent_relaxation"],
    )


N24_SUPPORTED_CAPABILITY_MANIFEST = {
    **N24_SUPPORTED_CAPABILITY_MANIFEST,
    "catalogue_registry_version": N24M_CAPABILITY_REGISTRY_VERSION,
    "hard_filters": [name for name, entry in N24_CATALOGUE_CAPABILITY_REGISTRY.items() if entry.classification == N24CatalogueCapability.HARD_FILTER_SUPPORTED],
    "soft_matches": [name for name, entry in N24_CATALOGUE_CAPABILITY_REGISTRY.items() if entry.classification == N24CatalogueCapability.SOFT_MATCH_SUPPORTED],
    "context_only": [name for name, entry in N24_CATALOGUE_CAPABILITY_REGISTRY.items() if entry.classification == N24CatalogueCapability.CONTEXT_ONLY],
    "ranking_supported": [name for name, entry in N24_CATALOGUE_CAPABILITY_REGISTRY.items() if entry.classification == N24CatalogueCapability.RANKING_SUPPORTED],
    "unsupported": [name for name, entry in N24_CATALOGUE_CAPABILITY_REGISTRY.items() if entry.classification == N24CatalogueCapability.UNSUPPORTED],
}


def run_n24m_deterministic_property_tests(target_assertions: int = 272):
    """Exercise the unified evaluator with deterministic real-catalogue values.

    Product IDs are sampled only as test evidence; no ID is embedded in product
    logic.  The frozen scorer and every language model are intentionally absent
    from this suite.
    """
    if target_assertions < 150:
        raise ValueError("N24M property validation requires at least 150 assertions")
    started = _n24m_time.perf_counter()
    profile_id = N24A_GOLDEN_PROFILE_ID
    cases = []

    def add_case(name, hard=None, exclusions=None, sidecar=None):
        cases.append((
            name,
            hard or N24HardRequestState(),
            exclusions or N24ExclusionState(),
            {**_n24m_default_sidecar(), **(sidecar or {})},
        ))

    all_category_norms = set().union(*(item["category_norms"] for item in N24M_CATALOGUE_INDEX.values()))
    category_samples = []
    for path in _N24M_CATEGORY_ALIASES.values():
        if all(_n24m_normalize(value) in all_category_norms for value in path):
            key = tuple(path)
            if key not in {tuple(item) for item in category_samples}:
                category_samples.append(list(path))
        if len(category_samples) >= 12:
            break
    brand_counts = _N24MCounter(
        item["brand"] for item in N24M_CATALOGUE_INDEX.values()
        if item["brand_norm"] in _N24M_BRAND_CANONICAL
        and item["brand_norm"] not in _N24M_AMBIGUOUS_BRAND_TOKENS
    )
    brand_samples = [name for name, _ in brand_counts.most_common(12)]
    colour_counts = _N24MCounter(
        item["primary_colour"] for item in N24M_CATALOGUE_INDEX.values()
        if len(item["colour_components"]) == 1
    )
    colour_samples = [name for name, _ in colour_counts.most_common(8) if name]
    audience_samples = [
        value for value in ("MEN", "WOMEN", "UNISEX_ADULT", "BOYS", "GIRLS", "KIDS")
        if any(item["audience"] == value for item in N24M_CATALOGUE_INDEX.values())
    ]
    prices = sorted(item["price"] for item in N24M_CATALOGUE_INDEX.values() if item["price"] is not None)
    price_samples = [prices[int((len(prices) - 1) * fraction)] for fraction in (0.2, 0.4, 0.6, 0.8)]

    for index, path in enumerate(category_samples, 1):
        add_case(f"category_{index}", N24HardRequestState(categories=path))
    for index, brand in enumerate(brand_samples, 1):
        add_case(f"brand_{index}", N24HardRequestState(brands=[brand]))
    for index, colour in enumerate(colour_samples, 1):
        add_case(f"strict_colour_{index}", N24HardRequestState(colours=[colour]))
    for audience in audience_samples:
        add_case(f"audience_{audience.casefold()}", N24HardRequestState(recipient=audience))
    for index, value in enumerate(price_samples, 1):
        add_case(f"maximum_price_{index}", N24HardRequestState(maximum_price=value))
        add_case(f"minimum_price_{index}", N24HardRequestState(minimum_price=value))
    for threshold in (3.5, 4.0, 4.5):
        add_case(f"minimum_rating_{threshold:g}", sidecar={"minimum_rating": threshold})

    intersection_products = [
        item for item in N24M_CATALOGUE_INDEX.values()
        if item["categories"] and item["brand_norm"] in _N24M_BRAND_CANONICAL
        and item["brand_norm"] not in _N24M_AMBIGUOUS_BRAND_TOKENS
        and len(item["colour_components"]) == 1
        and item["audience"] != "UNKNOWN"
        and item["price"] is not None and item["rating"] is not None
    ]
    stride = max(1, len(intersection_products) // 30)
    for index, product in enumerate(intersection_products[::stride][:30], 1):
        category = next(
            (value for value in reversed(product["categories"]) if _n24m_normalize(value) in all_category_norms),
            product["categories"][-1],
        )
        maximum = round(float(product["price"]) + 0.01, 2)
        minimum_rating = max(0.0, round(float(product["rating"]) - 0.01, 2))
        add_case(
            f"intersection_{index}",
            N24HardRequestState(
                categories=[category], brands=[product["brand"]],
                colours=[product["primary_colour"]], recipient=product["audience"],
                maximum_price=maximum,
            ),
            sidecar={"minimum_rating": minimum_rating},
        )

    if brand_samples:
        add_case("excluded_brand", exclusions=N24ExclusionState(brands=[brand_samples[0]]))
    if colour_samples:
        add_case("excluded_colour", exclusions=N24ExclusionState(colours=[colour_samples[0]]))
    if category_samples:
        add_case("excluded_category", exclusions=N24ExclusionState(categories=[category_samples[0][-1]]))

    assertions = []
    case_summaries = []
    for name, hard, exclusions, sidecar in cases:
        if len(assertions) >= target_assertions:
            break
        request = build_n24_validated_recommendation_request(profile_id, hard, exclusions)
        N24M_REQUEST_SIDECARS[request.request_fingerprint] = _n24m_deepcopy(sidecar)
        eligible_ids = sorted(_n24m_eligible_ids(request, sidecar))
        sampled_ids = eligible_ids[: min(5, target_assertions - len(assertions))]
        case_summaries.append({
            "case": name, "eligible_count": len(eligible_ids),
            "sampled_count": len(sampled_ids),
            "request": request.model_dump(mode="json"), "sidecar": sidecar,
        })
        for product_id in sampled_ids:
            evidence = evaluate_n24_product_eligibility(product_id, request, sidecar)
            passed = bool(
                evidence.eligible and evidence.violation_count == 0
                and evidence.unknown_constraint_count == 0
                and product_id in eligible_ids
            )
            assertions.append({
                "case": name, "product_id": product_id, "passed": passed,
                "attribute_matches": {
                    key: value.value for key, value in evidence.attribute_matches.items()
                },
            })

    if len(assertions) < target_assertions:
        assertions.append({
            "case": "minimum_assertion_target", "product_id": None, "passed": False,
            "detail": f"only {len(assertions)} real-catalogue assertions were available",
        })
    passed = sum(bool(item["passed"]) for item in assertions)
    failed = len(assertions) - passed
    return {
        "suite": "N24M deterministic real-catalogue eligibility properties",
        "total": len(assertions), "passed": passed, "failed": failed,
        "target_assertions": target_assertions,
        "cases_evaluated": len(case_summaries),
        "sample_dimensions": {
            "categories": category_samples, "brands": brand_samples,
            "strict_colours": colour_samples, "audiences": audience_samples,
            "price_thresholds": price_samples, "rating_thresholds": [3.5, 4.0, 4.5],
        },
        "seconds": round(_n24m_time.perf_counter() - started, 3),
        "case_summaries": case_summaries, "assertions": assertions,
    }


def run_n24m_contract_tests():
    tests = {}
    profile = N24A_GOLDEN_PROFILE_ID
    request = build_n24_validated_recommendation_request(
        profile,
        N24HardRequestState(categories=["Shoes"], brands=["adidas"], colours=["white"], recipient="men"),
        N24ExclusionState(),
    )
    result = get_n24_recommendations_from_validated_state(request, top_n=10)
    evidences = [evaluate_n24_product_eligibility(item, request) for item in result["recommendations"]["product_id"].astype(str).tolist()]
    tests["manual_hard_contract"] = all(item.eligible and item.violation_count == 0 and item.unknown_constraint_count == 0 for item in evidences)
    tests["manual_no_padding"] = len(result["recommendations"]) <= result["eligible_catalogue_count"]
    tests["brand_exact"] = "which is" not in _N24M_BRAND_CANONICAL
    tests["registry_versioned"] = all(isinstance(item, N24CatalogueCapabilityEntry) for item in N24_CATALOGUE_CAPABILITY_REGISTRY.values())
    tests["n23_callable_preserved"] = callable(n24l_n23_workspace_controller)
    tests["engine_n24"] = get_shopmate_engine() == "n24"
    return {"tests": tests, "all_passed": all(tests.values()), "manual_count": len(result["recommendations"]), "eligible_count": result["eligible_catalogue_count"]}


N24M_CONTRACT_TEST_REPORT = run_n24m_contract_tests()
set_shopmate_engine("n24")
N24M_INTEGRATION_STATUS = {
    "section_version": N24M_SECTION_VERSION,
    "capability_registry_version": N24M_CAPABILITY_REGISTRY_VERSION,
    "eligibility_engine_version": N24M_ELIGIBILITY_ENGINE_VERSION,
    "catalogue_rows": len(N24M_CATALOGUE_INDEX),
    "contract_tests": N24M_CONTRACT_TEST_REPORT,
    "engine": get_shopmate_engine(),
    "n23_controller_preserved": callable(n24l_n23_workspace_controller),
    "additional_llm_calls_for_eligibility": 0,
}

print("SECTION 153E7N24M - COMPLETE PRODUCT SEMANTICS, ELIGIBILITY AND REAL-WORLD ACCEPTANCE HARDENING ready")
print(_n24m_json.dumps(N24M_INTEGRATION_STATUS, indent=2, default=str))
