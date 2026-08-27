"""Independent raw-source oracle for ShopMate N24M2 validation.

This file is executed inside the live notebook namespace after N24M2 loads.
Its expected values are derived directly from raw dataframe columns/details
with separate parsing code.  It never consumes the production trusted index to
decide what the expected attribute should be.
"""

from __future__ import annotations

import json as _m2o_json
import re as _m2o_re
import time as _m2o_time
from collections import Counter as _M2OCounter
from pathlib import Path as _M2OPath


_M2O_COLOUR_FIELDS = ("Color", "Colour", "Color Name", "Band Color", "Stone Color", "Lens Color")
_M2O_AUDIENCE_FIELDS = ("Department", "Suggested Users", "Target Audience", "Target gender")
_M2O_MATERIAL_FIELDS = (
    "Material", "Fabric Type", "Inner Material", "Outer Material", "Material Type",
    "material_composition", "Material Composition",
)
_M2O_COLOUR_ALIASES = {
    "footwear white": "white", "ftwr white": "white", "core white": "white",
    "cloud white": "white", "off white": "white", "white": "white",
    "core black": "black", "jet black": "black", "black": "black",
    "grey two": "grey", "gray": "grey", "grey": "grey", "silver": "silver",
    "navy blue": "blue", "navy": "blue", "royal blue": "blue", "blue": "blue",
    "wine red": "red", "burgundy": "red", "red": "red",
    "pink tint": "pink", "rose pink": "pink", "pink": "pink",
    "forest green": "green", "olive green": "green", "green": "green",
    "purple": "purple", "violet": "purple", "yellow": "yellow", "orange": "orange",
    "dark brown": "brown", "brown": "brown", "tan": "tan", "beige": "beige",
    "khaki": "khaki", "gold": "gold", "rose gold": "gold",
    "multicolor": "multicolour", "multi color": "multicolour", "multi": "multicolour",
}
_M2O_ADVERSARIAL_TOKENS = (
    "white", "black", "red", "blue", "green", "orange", "brown", "gold",
    "silver", "pink", "men", "women", "kids", "leather", "cotton",
)


def _m2o_norm(value):
    text = "" if value is None else str(value)
    text = text.replace("&", " and ").replace("’", "'").casefold()
    return _m2o_re.sub(r"\s+", " ", _m2o_re.sub(r"[^a-z0-9]+", " ", text)).strip()


def _m2o_obj(value):
    if isinstance(value, dict):
        return dict(value)
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = _m2o_json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _m2o_categories(value):
    if isinstance(value, list):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = _m2o_json.loads(value)
        except Exception:
            parsed = []
    else:
        parsed = []
    return [str(item).strip() for item in parsed if str(item).strip()]


def _m2o_mask_brand(title, brand):
    title, brand = str(title or ""), str(brand or "").strip()
    if not title or not brand:
        return title
    parts = [part for part in _m2o_re.split(r"\s+", brand) if part]
    pattern = r"(?<![A-Za-z0-9])" + r"\s+".join(_m2o_re.escape(part) for part in parts) + r"(?![A-Za-z0-9])"
    return _m2o_re.sub(pattern, " ", title, count=1, flags=_m2o_re.I).strip()


def _m2o_colour_tokens(value):
    text = str(value or "")
    if not text.strip():
        return []
    text = _m2o_re.sub(r"(?i)\bwhite\s+gold\b", "", text)
    aliases = sorted(_M2O_COLOUR_ALIASES, key=len, reverse=True)
    pattern = r"(?<![a-z0-9])(" + "|".join(_m2o_re.escape(item) for item in aliases) + r")(?![a-z0-9])"
    return [_M2O_COLOUR_ALIASES[match.group(1).casefold()] for match in _m2o_re.finditer(pattern, text, flags=_m2o_re.I)]


def _m2o_raw_colour(details):
    for field in _M2O_COLOUR_FIELDS:
        raw = details.get(field)
        components = _m2o_colour_tokens(raw)
        if components:
            return components, f"details.{field}", str(raw)
    return [], None, None


def _m2o_audience(value):
    text = _m2o_norm(value)
    if not text:
        return "UNKNOWN"
    if _m2o_re.search(r"\b(?:toddler|baby|infant)s?\b", text): return "TODDLER"
    if _m2o_re.search(r"\bunisex\s+(?:child|kids?|youth)\b", text): return "UNISEX_CHILD"
    if _m2o_re.search(r"\bunisex\s+adult\b", text) or text == "unisex": return "UNISEX_ADULT"
    if _m2o_re.search(r"\b(?:boys?|male child)\b", text): return "BOYS"
    if _m2o_re.search(r"\b(?:girls?|female child)\b", text): return "GIRLS"
    if _m2o_re.search(r"\b(?:kids?|children|child|youth)\b", text): return "KIDS"
    if _m2o_re.search(r"\b(?:mens?|man|male)\b", text): return "MEN"
    if _m2o_re.search(r"\b(?:womens?|woman|female|ladies)\b", text): return "WOMEN"
    if text == "adult": return "UNISEX_ADULT"
    return "UNKNOWN"


def _m2o_raw_audience(details, categories, masked_title):
    for field in _M2O_AUDIENCE_FIELDS:
        raw = details.get(field)
        canonical = _m2o_audience(raw)
        if canonical != "UNKNOWN":
            return canonical, f"details.{field}", str(raw)
    for raw in categories:
        canonical = _m2o_audience(raw)
        if canonical != "UNKNOWN":
            return canonical, "categories", raw
    title_patterns = (
        (r"\bunisex[- ]child\b", "UNISEX_CHILD"), (r"\bunisex[- ]adult\b", "UNISEX_ADULT"),
        (r"\bmen(?:'|’)s\b", "MEN"), (r"\bwomen(?:'|’)s\b", "WOMEN"),
        (r"\bboys(?:'|’)?\b", "BOYS"), (r"\bgirls(?:'|’)?\b", "GIRLS"),
        (r"\b(?:toddler|baby|infant)s?\b", "TODDLER"), (r"\bkids(?:'|’)?\b", "KIDS"),
    )
    for pattern, canonical in title_patterns:
        if _m2o_re.search(pattern, masked_title, flags=_m2o_re.I):
            return canonical, "title_after_brand_mask", masked_title
    return "UNKNOWN", None, None


def _m2o_age_from_audience(audience):
    if audience in {"MEN", "WOMEN", "UNISEX_ADULT"}: return "ADULT"
    if audience == "TODDLER": return "TODDLER"
    if audience in {"BOYS", "GIRLS", "KIDS", "UNISEX_CHILD"}: return "CHILD"
    return "UNKNOWN"


def _m2o_simple_material(details):
    for field in _M2O_MATERIAL_FIELDS:
        raw = details.get(field)
        if raw is not None and str(raw).strip():
            return _m2o_norm(raw), f"details.{field}", str(raw)
    return "", None, None


def _m2o_raw_record(record):
    details = _m2o_obj(record.get("details"))
    categories = _m2o_categories(record.get("categories"))
    brand = str(record.get("brand") or "").strip()
    title = str(record.get("title") or "")
    masked = _m2o_mask_brand(title, brand)
    colours, colour_source, colour_raw = _m2o_raw_colour(details)
    audience, audience_source, audience_raw = _m2o_raw_audience(details, categories, masked)
    material, material_source, material_raw = _m2o_simple_material(details)
    return {
        "product_id": str(record.get("product_id")), "title": title, "brand": brand,
        "masked_title": masked, "details": details, "categories": categories,
        "colour_components": colours, "colour_source": colour_source, "colour_raw": colour_raw,
        "audience": audience, "audience_source": audience_source, "audience_raw": audience_raw,
        "age_group": _m2o_age_from_audience(audience),
        "material_norm": material, "material_source": material_source, "material_raw": material_raw,
        "price": safely_convert_to_float(record.get("price")),
        "rating": safely_convert_to_float(record.get("average_rating")),
        "review_count": safely_convert_to_float(record.get("rating_number")),
    }


def _m2o_request(*, categories=None, brands=None, colours=None, recipient=None,
                 minimum_price=None, maximum_price=None, excluded_categories=None,
                 excluded_brands=None, excluded_colours=None, minimum_rating=None,
                 rating_exclusive=False, allow_mixed=False):
    request = build_n24_validated_recommendation_request(
        N24A_GOLDEN_PROFILE_ID,
        N24HardRequestState(
            categories=categories or [], brands=brands or [], colours=colours or [],
            recipient=recipient, minimum_price=minimum_price, maximum_price=maximum_price,
        ),
        N24ExclusionState(
            categories=excluded_categories or [], brands=excluded_brands or [],
            colours=excluded_colours or [],
        ),
    )
    sidecar = {**_n24m_default_sidecar(), "minimum_rating": minimum_rating,
               "rating_exclusive": bool(rating_exclusive), "allow_mixed_colours": bool(allow_mixed)}
    N24M_REQUEST_SIDECARS[request.request_fingerprint] = sidecar
    return request, sidecar


def _m2o_record_assertion(assertions, name, passed, product_id=None, detail=None):
    assertions.append({
        "name": name, "passed": bool(passed), "product_id": product_id,
        "detail": detail,
    })


def _m2o_oracle_satisfies(raw, spec):
    normalized_categories = {_m2o_norm(item) for item in raw["categories"]}
    for wanted in spec.get("categories", []):
        aliases = {"jackets": "jackets and coats", "jacket": "jackets and coats", "t shirt": "t shirts"}
        normalized = aliases.get(_m2o_norm(wanted), _m2o_norm(wanted))
        if normalized not in normalized_categories and not (normalized == "watches" and "wrist watches" in normalized_categories):
            return False, f"raw category does not prove {wanted}"
    if spec.get("brands") and _m2o_norm(raw["brand"]) not in {_m2o_norm(item) for item in spec["brands"]}:
        return False, "raw structured brand mismatch"
    wanted_colours = [_M2O_COLOUR_ALIASES.get(_m2o_norm(item), _m2o_norm(item)) for item in spec.get("colours", [])]
    if wanted_colours:
        components = raw["colour_components"]
        if not components:
            return False, "no raw structured colour"
        if len(wanted_colours) == 1:
            if all(item == wanted_colours[0] for item in components):
                pass
            elif spec.get("allow_mixed") and wanted_colours[0] in components:
                pass
            else:
                return False, "raw colour is not strict/allowed mixed"
        elif set(components) != set(wanted_colours):
            return False, "raw mixed components differ"
    recipient = spec.get("recipient")
    if recipient:
        requested = _m2o_audience(recipient)
        compatible = {
            "MEN": {"MEN", "UNISEX_ADULT"}, "WOMEN": {"WOMEN", "UNISEX_ADULT"},
            "UNISEX_ADULT": {"UNISEX_ADULT"}, "BOYS": {"BOYS", "UNISEX_CHILD"},
            "GIRLS": {"GIRLS", "UNISEX_CHILD"},
            "KIDS": {"BOYS", "GIRLS", "KIDS", "UNISEX_CHILD", "TODDLER"},
            "UNISEX_CHILD": {"UNISEX_CHILD"}, "TODDLER": {"TODDLER"},
        }
        if raw["audience"] not in compatible.get(requested, set()):
            return False, "raw audience incompatible"
    if spec.get("minimum_price") is not None and (raw["price"] is None or raw["price"] < spec["minimum_price"]):
        return False, "raw price below minimum"
    if spec.get("maximum_price") is not None and (raw["price"] is None or raw["price"] > spec["maximum_price"]):
        return False, "raw price above maximum"
    if spec.get("minimum_rating") is not None:
        rating_ok = raw["rating"] is not None and (
            raw["rating"] > spec["minimum_rating"]
            if spec.get("rating_exclusive") else raw["rating"] >= spec["minimum_rating"]
        )
        if not rating_ok:
            return False, "raw rating below threshold"
    if spec.get("excluded_brands") and _m2o_norm(raw["brand"]) in {_m2o_norm(item) for item in spec["excluded_brands"]}:
        return False, "raw brand is excluded"
    if spec.get("excluded_colours"):
        forbidden = {_M2O_COLOUR_ALIASES.get(_m2o_norm(item), _m2o_norm(item)) for item in spec["excluded_colours"]}
        if not raw["colour_components"] or set(raw["colour_components"]) & forbidden:
            return False, "raw colour unknown or excluded"
    return True, "all raw oracle constraints proven"


def run_n24m2_independent_oracle_tests(output_dir):
    started = _m2o_time.perf_counter()
    raw_records = [
        _m2o_raw_record(record)
        for record in application_request_metadata_df.drop_duplicates("product_id").to_dict("records")
    ]
    raw_by_id = {item["product_id"]: item for item in raw_records}
    assertions = []

    # Raw category hierarchy assertions.
    category_count = 0
    for raw in raw_records:
        if not raw["categories"]:
            continue
        category = raw["categories"][-1]
        request, sidecar = _m2o_request(categories=[category])
        result = evaluate_n24_trusted_eligibility(raw["product_id"], request, sidecar)
        _m2o_record_assertion(assertions, "raw_category_exact", result.eligible, raw["product_id"], category)
        category_count += 1
        if category_count >= 40: break

    # Structured brand assertions.
    brand_count = 0
    for raw in raw_records:
        if not raw["brand"] or len(raw["brand"]) > 45 or "author" in _m2o_norm(raw["brand"]):
            continue
        request, sidecar = _m2o_request(brands=[raw["brand"]])
        result = evaluate_n24_trusted_eligibility(raw["product_id"], request, sidecar)
        _m2o_record_assertion(assertions, "raw_brand_exact", result.eligible, raw["product_id"], raw["brand"])
        brand_count += 1
        if brand_count >= 40: break

    # Structured/variant colour assertions from the independent parser.
    colour_count = 0
    for raw in raw_records:
        if not raw["colour_components"]:
            continue
        requested = list(dict.fromkeys(raw["colour_components"]))
        request, sidecar = _m2o_request(colours=requested)
        result = evaluate_n24_trusted_eligibility(raw["product_id"], request, sidecar)
        _m2o_record_assertion(
            assertions, "raw_variant_colour_exact", result.eligible,
            raw["product_id"], {"requested": requested, "source": raw["colour_source"], "raw": raw["colour_raw"]},
        )
        colour_count += 1
        if colour_count >= 60: break

    # Structured audience and age assertions.
    audience_count = 0
    for raw in raw_records:
        if raw["audience"] == "UNKNOWN" or not str(raw["audience_source"] or "").startswith("details."):
            continue
        request, sidecar = _m2o_request(recipient=raw["audience"])
        result = evaluate_n24_trusted_eligibility(raw["product_id"], request, sidecar)
        audience_ok = result.eligible and result.attribute_evidence["audience"].match_level == N24AttributeMatch.EXACT
        age_ok = result.attribute_evidence["age_group"].match_level == N24AttributeMatch.EXACT
        _m2o_record_assertion(assertions, "raw_audience_exact", audience_ok, raw["product_id"], raw["audience_source"])
        _m2o_record_assertion(assertions, "raw_age_compatible", age_ok, raw["product_id"], raw["age_group"])
        audience_count += 1
        if audience_count >= 25: break

    # Numeric price/rating assertions.
    numeric_count = 0
    for raw in raw_records:
        if raw["price"] is None or raw["rating"] is None:
            continue
        request, sidecar = _m2o_request(maximum_price=raw["price"])
        price_result = evaluate_n24_trusted_eligibility(raw["product_id"], request, sidecar)
        _m2o_record_assertion(assertions, "raw_numeric_price_exact", price_result.eligible, raw["product_id"], raw["price"])
        request, sidecar = _m2o_request(minimum_rating=raw["rating"])
        rating_result = evaluate_n24_trusted_eligibility(raw["product_id"], request, sidecar)
        _m2o_record_assertion(assertions, "raw_numeric_rating_exact", rating_result.eligible, raw["product_id"], raw["rating"])
        numeric_count += 1
        if numeric_count >= 20: break

    # Negative constraints independently target the product's own raw values.
    negative_count = 0
    for raw in raw_records:
        if not raw["categories"] or not raw["brand"] or not raw["colour_components"]:
            continue
        request, sidecar = _m2o_request(excluded_brands=[raw["brand"]])
        brand_result = evaluate_n24_trusted_eligibility(raw["product_id"], request, sidecar)
        _m2o_record_assertion(assertions, "raw_negative_brand", not brand_result.eligible, raw["product_id"], raw["brand"])
        request, sidecar = _m2o_request(excluded_colours=[raw["colour_components"][0]])
        colour_result = evaluate_n24_trusted_eligibility(raw["product_id"], request, sidecar)
        _m2o_record_assertion(assertions, "raw_negative_colour", not colour_result.eligible, raw["product_id"], raw["colour_components"][0])
        request, sidecar = _m2o_request(excluded_categories=[raw["categories"][-1]])
        category_result = evaluate_n24_trusted_eligibility(raw["product_id"], request, sidecar)
        _m2o_record_assertion(assertions, "raw_negative_category", not category_result.eligible, raw["product_id"], raw["categories"][-1])
        negative_count += 1
        if negative_count >= 10: break

    # Multi-constraint intersections where independent raw fields prove every value.
    intersection_count = 0
    for raw in raw_records:
        if not (raw["categories"] and raw["brand"] and raw["colour_components"] and raw["audience"] != "UNKNOWN" and raw["price"] is not None and raw["rating"] is not None):
            continue
        colours = list(dict.fromkeys(raw["colour_components"]))
        request, sidecar = _m2o_request(
            categories=[raw["categories"][-1]], brands=[raw["brand"]], colours=colours,
            recipient=raw["audience"], maximum_price=raw["price"], minimum_rating=raw["rating"],
        )
        result = evaluate_n24_trusted_eligibility(raw["product_id"], request, sidecar)
        _m2o_record_assertion(
            assertions, "raw_multi_constraint_intersection", result.eligible,
            raw["product_id"], {"category": raw["categories"][-1], "brand": raw["brand"], "colours": colours, "audience": raw["audience"], "price": raw["price"], "rating": raw["rating"]},
        )
        intersection_count += 1
        if intersection_count >= 20: break

    # Unknown/model-title ambiguity: raw title token with no structured colour.
    ambiguity_count = 0
    for raw in raw_records:
        if raw["colour_components"]:
            continue
        title_norm = _m2o_norm(raw["masked_title"])
        token = next((item for item in _M2O_COLOUR_ALIASES.values() if _m2o_re.search(rf"\b{_m2o_re.escape(item)}\b", title_norm)), None)
        if not token:
            continue
        request, sidecar = _m2o_request(colours=[token])
        result = evaluate_n24_trusted_eligibility(raw["product_id"], request, sidecar)
        ok = not result.eligible and result.attribute_evidence["colour"].match_level == N24AttributeMatch.UNKNOWN
        _m2o_record_assertion(assertions, "title_model_colour_not_exact", ok, raw["product_id"], {"token": token, "title": raw["title"]})
        ambiguity_count += 1
        if ambiguity_count >= 30: break

    summary = {
        "suite": "N24M2 independent raw-source provenance oracle",
        "total": len(assertions), "passed": sum(item["passed"] for item in assertions),
        "failed": sum(not item["passed"] for item in assertions),
        "assertion_groups": dict(_M2OCounter(item["name"] for item in assertions)),
        "seconds": round(_m2o_time.perf_counter() - started, 3),
        "independent_from_production_index": True, "llm_calls": 0,
        "assertions": assertions,
    }
    output = _M2OPath(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "independent_provenance_tests.json").write_text(
        _m2o_json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    return summary, raw_by_id


def run_n24m2_adversarial_tests(raw_by_id, output_dir):
    raw_records = list(raw_by_id.values())
    assertions = []
    for token in _M2O_ADVERSARIAL_TOKENS:
        for raw in raw_records:
            if not _m2o_re.search(rf"\b{_m2o_re.escape(token)}\b", _m2o_norm(raw["brand"])):
                continue
            if token in _M2O_COLOUR_ALIASES.values():
                if token in raw["colour_components"]:
                    continue
                request, sidecar = _m2o_request(colours=[token])
                result = evaluate_n24_trusted_eligibility(raw["product_id"], request, sidecar)
                passed = not result.eligible and result.attribute_evidence["colour"].match_level != N24AttributeMatch.EXACT
                _m2o_record_assertion(assertions, "brand_token_not_colour", passed, raw["product_id"], {"token": token, "brand": raw["brand"], "title": raw["title"]})
            elif token in {"men", "women", "kids"}:
                requested = _m2o_audience(token)
                compatible = {
                    "MEN": {"MEN", "UNISEX_ADULT"}, "WOMEN": {"WOMEN", "UNISEX_ADULT"},
                    "KIDS": {"BOYS", "GIRLS", "KIDS", "UNISEX_CHILD", "TODDLER"},
                }
                if raw["audience"] in compatible.get(requested, set()):
                    continue
                request, sidecar = _m2o_request(recipient=token)
                result = evaluate_n24_trusted_eligibility(raw["product_id"], request, sidecar)
                passed = not result.eligible and result.attribute_evidence["audience"].match_level != N24AttributeMatch.EXACT
                _m2o_record_assertion(assertions, "brand_token_not_audience", passed, raw["product_id"], {"token": token, "brand": raw["brand"]})
            else:
                if token in raw["material_norm"]:
                    continue
                production = N24M2_TRUSTED_CATALOGUE_INDEX[raw["product_id"]]["trusted_attributes"]["material"]
                source_type = getattr(production["source_type"], "value", str(production["source_type"]))
                match_level = getattr(production["match_level"], "value", str(production["match_level"]))
                raw_value = _m2o_norm(production.get("canonical_value"))
                passed = source_type != "BRAND" and not (
                    match_level == "EXACT" and token in raw_value
                )
                _m2o_record_assertion(
                    assertions, "brand_token_not_material", passed, raw["product_id"],
                    {
                        "token": token, "brand": raw["brand"], "title": raw["title"],
                        "masked_title": raw["masked_title"], "source_type": source_type,
                        "match_level": match_level, "observed_untrusted_value": raw_value,
                    },
                )

    # Ensure a substantial deterministic sample even when attribute-like brands are rare.
    model_count = 0
    for raw in raw_records:
        if raw["colour_components"]:
            continue
        title_norm = _m2o_norm(raw["masked_title"])
        token = next((item for item in ("white", "black", "red", "blue", "green", "orange", "brown", "gold", "silver", "pink") if _m2o_re.search(rf"\b{item}\b", title_norm)), None)
        if not token:
            continue
        request, sidecar = _m2o_request(colours=[token])
        result = evaluate_n24_trusted_eligibility(raw["product_id"], request, sidecar)
        passed = not result.eligible and result.attribute_evidence["colour"].match_level == N24AttributeMatch.UNKNOWN
        _m2o_record_assertion(assertions, "model_title_token_not_colour", passed, raw["product_id"], {"token": token, "title": raw["title"]})
        model_count += 1
        if model_count >= 80: break

    summary = {
        "suite": "N24M2 adversarial brand/model token generator",
        "total": len(assertions), "passed": sum(item["passed"] for item in assertions),
        "failed": sum(not item["passed"] for item in assertions),
        "groups": dict(_M2OCounter(item["name"] for item in assertions)),
        "llm_calls": 0, "assertions": assertions,
    }
    output = _M2OPath(output_dir)
    (output / "adversarial_brand_model_tests.json").write_text(
        _m2o_json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    return summary


def run_n24m2_named_multi_constraint_tests(raw_by_id, output_dir):
    specs = {
        "white shoes": {"categories": ["Shoes"], "colours": ["white"]},
        "black shoes": {"categories": ["Shoes"], "colours": ["black"]},
        "red shoes": {"categories": ["Shoes"], "colours": ["red"]},
        "white Adidas": {"categories": ["Shoes"], "brands": ["adidas"], "colours": ["white"]},
        "black Nike": {"categories": ["Shoes"], "brands": ["Nike"], "colours": ["black"]},
        "white men": {"categories": ["Shoes"], "colours": ["white"], "recipient": "men"},
        "white women": {"categories": ["Shoes"], "colours": ["white"], "recipient": "women"},
        "kids white": {"categories": ["Shoes"], "colours": ["white"], "recipient": "kids"},
        "white Adidas men": {"categories": ["Shoes"], "brands": ["adidas"], "colours": ["white"], "recipient": "men"},
        "black Nike women": {"categories": ["Shoes"], "brands": ["Nike"], "colours": ["black"], "recipient": "women"},
        "red men under100": {"categories": ["Shoes"], "colours": ["red"], "recipient": "men", "maximum_price": 100},
        "Nike rating>=4": {"categories": ["Shoes"], "brands": ["Nike"], "minimum_rating": 4.0},
    }
    reports = {}
    for name, spec in specs.items():
        request, sidecar = _m2o_request(**spec)
        eligible_ids = sorted(_n24m_eligible_ids(request, sidecar))
        violations = []
        for product_id in eligible_ids:
            passed, detail = _m2o_oracle_satisfies(raw_by_id[product_id], spec)
            if not passed:
                violations.append({"product_id": product_id, "detail": detail})
        reports[name] = {
            "eligible_count": len(eligible_ids), "checked": len(eligible_ids),
            "violations": violations, "passed": not violations,
        }
    summary = {
        "suite": "N24M2 named multi-constraint raw-oracle validation",
        "total": len(reports), "passed": sum(item["passed"] for item in reports.values()),
        "failed": sum(not item["passed"] for item in reports.values()),
        "tests": reports, "llm_calls": 0,
    }
    output = _M2OPath(output_dir)
    (output / "multi_constraint_tests.json").write_text(
        _m2o_json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    return summary


def run_n24m2_manual_white_and_diagnostics(raw_by_id, output_dir):
    request, sidecar = _m2o_request(categories=["Shoes"], colours=["white"])
    result = get_n24_recommendations_from_validated_state(request, top_n=10)
    rows = []
    for product_id in result["recommendations"]["product_id"].astype(str).tolist():
        raw = raw_by_id[product_id]
        strict = bool(raw["colour_components"] and all(item == "white" for item in raw["colour_components"]))
        rows.append({
            "product_id": product_id, "brand": raw["brand"], "title": raw["title"],
            "raw_colour_field": raw["colour_source"], "raw_variant_evidence": raw["colour_raw"],
            "trusted_colour": raw["colour_components"], "trusted_source": raw["colour_source"],
            "mode": "STRICT_SINGLE_COLOUR" if strict else "MIXED_COLOUR" if raw["colour_components"] else "UNKNOWN",
            "eligible": strict,
        })
    manual = {
        "request": "i need white shoes", "eligible_catalogue_count": result["eligible_catalogue_count"],
        "returned": len(rows),
        "brand_only_false_white": sum(item["raw_colour_field"] is None and "white" in _m2o_norm(item["brand"]) for item in rows),
        "model_name_only_false_white": sum(item["raw_colour_field"] is None and "white" in _m2o_norm(item["title"]) for item in rows),
        "mixed_exact_violations": sum(item["mode"] == "MIXED_COLOUR" for item in rows),
        "unknown_exact_violations": sum(item["mode"] == "UNKNOWN" for item in rows),
        "products": rows,
    }
    diagnostic_needles = {
        "WHITE MOUNTAIN Carly": "WHITE MOUNTAIN Women's Carly Footbed Sandal",
        "WHITE MOUNTAIN Helga": "WHITE MOUNTAIN Women's Helga Footbed Sandal",
        "WHITE MOUNTAIN Hayleigh": "WHITE MOUNTAIN Women's Hayleigh Footbed Sandal",
        "Timberland White Ledge": "Timberland Men's White Ledge Mid Waterproof Hiking Boot",
    }
    diagnostics = {}
    for label, needle in diagnostic_needles.items():
        raw = next((item for item in raw_by_id.values() if needle.casefold() in item["title"].casefold()), None)
        if raw is None:
            diagnostics[label] = {"found": False, "eligible": False}
            continue
        eligibility = evaluate_n24_trusted_eligibility(raw["product_id"], request, sidecar)
        diagnostics[label] = {
            "found": True, "product_id": raw["product_id"], "brand": raw["brand"],
            "title": raw["title"], "raw_colour_source": raw["colour_source"],
            "raw_colour_value": raw["colour_raw"], "trusted_components": raw["colour_components"],
            "title_after_brand_mask": raw["masked_title"],
            "production_source_type": eligibility.attribute_evidence["colour"].source_type.value,
            "production_match_level": eligibility.attribute_evidence["colour"].match_level.value,
            "eligible": eligibility.eligible,
        }
    output = _M2OPath(output_dir)
    (output / "manual_white_shoes_deterministic.json").write_text(
        _m2o_json.dumps(manual, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    (output / "diagnostic_products.json").write_text(
        _m2o_json.dumps(diagnostics, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    return manual, diagnostics


def run_n24m2_all_deterministic_validation(output_dir):
    provenance, raw_by_id = run_n24m2_independent_oracle_tests(output_dir)
    adversarial = run_n24m2_adversarial_tests(raw_by_id, output_dir)
    multi = run_n24m2_named_multi_constraint_tests(raw_by_id, output_dir)
    manual, diagnostics = run_n24m2_manual_white_and_diagnostics(raw_by_id, output_dir)
    summary = {
        "provenance": {key: provenance[key] for key in ("total", "passed", "failed", "seconds")},
        "adversarial": {key: adversarial[key] for key in ("total", "passed", "failed")},
        "multi_constraint": {key: multi[key] for key in ("total", "passed", "failed")},
        "manual_white": {key: manual[key] for key in (
            "eligible_catalogue_count", "returned", "brand_only_false_white",
            "model_name_only_false_white", "mixed_exact_violations", "unknown_exact_violations",
        )},
        "diagnostics": diagnostics, "critical_failures": provenance["failed"] + adversarial["failed"] + multi["failed"],
        "llm_calls": 0,
    }
    output = _M2OPath(output_dir)
    (output / "deterministic_validation_summary.json").write_text(
        _m2o_json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    return summary


def run_n24m2_focused_raw_oracle(results_path, output_dir):
    """Validate live returned IDs against separately parsed raw dataframe fields."""
    raw_records = [
        _m2o_raw_record(record)
        for record in application_request_metadata_df.drop_duplicates("product_id").to_dict("records")
    ]
    raw_by_id = {item["product_id"]: item for item in raw_records}
    cases = _m2o_json.loads(_M2OPath(results_path).read_text(encoding="utf-8"))
    assertions = []
    case_reports = {}
    for case in cases:
        failures = []
        checked_cards = 0
        for turn_index, turn in enumerate(case.get("turns", []), 1):
            spec = turn.get("oracle_spec")
            cards = [item for item in turn.get("cards", []) if isinstance(item, dict) and item.get("product_id")]
            if cards and not spec:
                failures.append(f"turn {turn_index}: recommendation cards lack an oracle specification")
                continue
            for card in cards:
                product_id = str(card["product_id"])
                raw = raw_by_id.get(product_id)
                if raw is None:
                    failures.append(f"turn {turn_index}: {product_id} absent from raw catalogue")
                    continue
                passed, reason = _m2o_oracle_satisfies(raw, spec)
                checked_cards += 1
                assertions.append({
                    "case": case["case"], "turn": turn_index, "product_id": product_id,
                    "passed": bool(passed), "reason": reason, "spec": spec,
                    "raw_sources": {
                        "categories": raw["categories"], "brand": raw["brand"],
                        "colour_source": raw["colour_source"], "colour_raw": raw["colour_raw"],
                        "colour_components": raw["colour_components"],
                        "audience_source": raw["audience_source"], "audience": raw["audience"],
                        "price": raw["price"], "rating": raw["rating"],
                    },
                })
                if not passed:
                    failures.append(f"turn {turn_index}: {product_id}: {reason}")
            if spec and not cards and turn.get("status") == "no_exact_match":
                independently_eligible = [
                    raw["product_id"] for raw in raw_records
                    if _m2o_oracle_satisfies(raw, spec)[0]
                ]
                assertions.append({
                    "case": case["case"], "turn": turn_index,
                    "product_id": None, "passed": not independently_eligible,
                    "reason": "independent raw oracle confirms empty intersection" if not independently_eligible else f"raw oracle found {len(independently_eligible)} eligible products",
                    "spec": spec, "eligible_sample": independently_eligible[:20],
                })
                if independently_eligible:
                    failures.append(
                        f"turn {turn_index}: no-match despite {len(independently_eligible)} independently eligible raw products"
                    )

        # Independently confirm the requested global superlative where present.
        if int(case["case"]) in {14, 15, 16} and case.get("turns"):
            turn = case["turns"][-1]
            spec = turn.get("oracle_spec") or {}
            candidates = [raw for raw in raw_records if _m2o_oracle_satisfies(raw, spec)[0]]
            cards = [item for item in turn.get("cards", []) if isinstance(item, dict) and item.get("product_id")]
            metric = "rating" if int(case["case"]) == 16 else "price"
            reverse = int(case["case"]) in {15, 16}
            candidates = [item for item in candidates if item.get(metric) is not None]
            if not candidates or not cards:
                failures.append("superlative has no independently comparable product")
            else:
                expected = sorted(candidates, key=lambda item: item[metric], reverse=reverse)[0][metric]
                actual_raw = raw_by_id.get(str(cards[0]["product_id"]))
                actual = None if actual_raw is None else actual_raw.get(metric)
                if actual is None or abs(float(actual) - float(expected)) > 1e-9:
                    failures.append(f"global {metric} superlative mismatch: {actual!r} vs {expected!r}")

        case_reports[str(case["case"])] = {
            "label": case.get("label"), "checked_cards": checked_cards,
            "passed": not failures, "failures": failures,
        }

    report = {
        "suite": "N24M2 focused live independent raw oracle",
        "total_card_assertions": sum(item.get("product_id") is not None for item in assertions),
        "total_no_match_assertions": sum(item.get("product_id") is None for item in assertions),
        "passed_assertions": sum(item["passed"] for item in assertions),
        "failed_assertions": sum(not item["passed"] for item in assertions),
        "case_passed": sum(item["passed"] for item in case_reports.values()),
        "case_failed": sum(not item["passed"] for item in case_reports.values()),
        "cases": case_reports, "assertions": assertions, "llm_calls": 0,
    }
    output = _M2OPath(output_dir)
    (output / "focused_live_raw_oracle.json").write_text(
        _m2o_json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    return report
