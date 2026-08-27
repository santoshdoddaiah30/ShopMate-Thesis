"""Focused local visual validation for N24M3 (no broad acceptance replay)."""

from __future__ import annotations

from collections import Counter as _N24M3ValidationCounter
from concurrent.futures import ThreadPoolExecutor as _N24M3ValidationPool
from hashlib import sha256 as _n24m3_validation_sha256
from pathlib import Path as _N24M3ValidationPath
import json as _n24m3_validation_json
import time as _n24m3_validation_time


N24M3_VISUAL_CASES = [
    ("V1", "show me white t-shirts"),
    ("V2", "show me black t-shirts"),
    ("V3", "show me red shoes"),
    ("V4", "show me white shoes"),
    ("V5", "show me black shoes"),
    ("V6", "show me blue shoes"),
    ("V7", "show me white Adidas shoes"),
    ("V8", "show me white shoes for men"),
    ("V9", "show me white and black shoes"),
    ("V10", "show me white shoes, mixed colours are okay"),
]


def _n24m3_validation_output_root():
    root = globals().get("N24M3_AUDIT_ROOT")
    if root is not None:
        return _N24M3ValidationPath(root)
    current = _N24M3ValidationPath.cwd().resolve()
    project = current.parent if current.name.casefold() == "notebooks" else current
    return project / "Results" / "N24M3_Visual_Relaxation_Audit"


def _n24m3_visual_case(case_id: str, query: str, chat_id: int) -> dict:
    N24M_CHAT_CONSTRAINTS.pop(int(chat_id), None)
    state = N24ConversationStateBundle()
    context = build_n24_interpreter_context(
        chat_id=int(chat_id), profile_id=N24A_GOLDEN_PROFILE_ID,
        current_state=state, active_result_set=None,
    )
    delta, guard, metrics = n24l_interpret_turn(query, context, state, None)
    if delta is None or delta.requires_clarification:
        return {
            "case": case_id, "query": query, "passed": False,
            "failure": "query did not produce an executable N24 turn",
            "guard": guard, "metrics": metrics,
        }
    reduced = reduce_n24_conversation_state(state, delta)
    request = build_n24_validated_recommendation_request(
        N24A_GOLDEN_PROFILE_ID, reduced.new_state.hard_request,
        reduced.new_state.exclusions,
    )
    result = get_n24_recommendations_from_validated_state(request, top_n=10)
    audit = list(result.get("visual_colour_audit") or [])
    returned_ids = set(result["recommendations"]["product_id"].astype(str)) if not result["recommendations"].empty else set()
    returned_audit = [item for item in audit if item["product_id"] in returned_ids]
    counts = _N24M3ValidationCounter(item["classification"] for item in audit)
    conflicts_returned = [
        item["product_id"] for item in returned_audit
        if item["classification"] == N24VisualColourClassification.VISUAL_CONFLICT.value
    ]
    unknown_returned = [
        item["product_id"] for item in returned_audit
        if item["classification"] == N24VisualColourClassification.VISUAL_UNKNOWN.value
    ]
    internal = []
    for item in audit:
        product = N24M2_TRUSTED_CATALOGUE_INDEX.get(item["product_id"], {})
        colour = (product.get("trusted_attributes") or {}).get("colour") or {}
        internal.append({
            "product_id": item["product_id"], "title": product.get("title"),
            "brand": product.get("brand"), "metadata_colour_evidence": colour,
            "variant_evidence": colour.get("raw_value"),
            "image_url": item.get("image_url"), "local_image_path": item.get("local_image_path"),
            "visual_classification": item["classification"],
            "visual_confidence": item["confidence"], "returned": item["product_id"] in returned_ids,
        })
    # Zero trusted candidates is a grounded catalogue limitation, not a visual
    # gate failure.  Every returned result must nevertheless satisfy the gate.
    passed = not conflicts_returned and not unknown_returned and all(item.get("accepted") for item in returned_audit)
    if case_id == "V1":
        passed = passed and bool(returned_ids)
    return {
        "case": case_id, "query": query, "passed": bool(passed),
        "metadata_eligible": int(result.get("eligible_catalogue_count") or 0),
        "metadata_shortlist": int(result.get("metadata_eligible_shortlist_count") or 0),
        "visually_checked": int(result.get("visual_checked_count") or 0),
        "visual_exact": counts.get("VISUAL_EXACT", 0),
        "visual_compatible": counts.get("VISUAL_COMPATIBLE", 0),
        "visual_mixed": counts.get("VISUAL_MIXED", 0),
        "visual_conflict": counts.get("VISUAL_CONFLICT", 0),
        "visual_unknown": counts.get("VISUAL_UNKNOWN", 0),
        "returned": len(returned_ids), "returned_product_ids": list(returned_ids),
        "visual_conflicts_returned": conflicts_returned,
        "visual_unknown_returned": unknown_returned,
        "visual_overhead_seconds": result.get("visual_overhead_seconds"),
        "cache_hits": result.get("visual_cache_hits"), "cache_misses": result.get("visual_cache_misses"),
        "hard_state": reduced.new_state.hard_request.model_dump(mode="json"),
        "sidecar": _n24m3_deepcopy(_n24m_sidecar(chat_id)),
        "internal_product_audit": internal,
    }


def run_n24m3_required_visual_tests() -> dict:
    output_root = _n24m3_validation_output_root()
    output_root.mkdir(parents=True, exist_ok=True)
    results = []
    for offset, (case_id, query) in enumerate(N24M3_VISUAL_CASES):
        results.append(_n24m3_visual_case(case_id, query, 930000 + offset))
    white = results[0]
    dark_observed = next(
        (
            item for item in white.get("internal_product_audit", [])
            if item["visual_classification"] == N24VisualColourClassification.VISUAL_CONFLICT.value
            and not item["returned"]
        ),
        None,
    )
    report = {
        "suite": "N24M3 required visual tests V1-V10",
        "results": results, "passed": sum(item.get("passed", False) for item in results),
        "failed": sum(not item.get("passed", False) for item in results),
        "all_passed": all(item.get("passed", False) for item in results),
        "strict_visual_conflicts_returned": sum(len(item.get("visual_conflicts_returned", [])) for item in results),
        "strict_visual_unknown_returned": sum(len(item.get("visual_unknown_returned", [])) for item in results),
        "white_tshirt_observed_dark_product": dark_observed,
    }
    (output_root / "required_visual_tests.json").write_text(
        _n24m3_validation_json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    (output_root / "white_tshirt_trace.json").write_text(
        _n24m3_validation_json.dumps({
            "query": white.get("query"), "summary": white,
            "browser_observed_dark_product": dark_observed,
        }, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8",
    )
    return report


def _n24m3_adversarial_samples(target: int = 50):
    colours = ["white", "black", "red", "blue", "green", "brown"]
    buckets = {colour: [] for colour in colours}
    image_by_id = {
        str(row["product_id"]): row.get("image_url")
        for row in application_request_metadata_df.drop_duplicates("product_id").to_dict("records")
    }
    for product_id, product in N24M2_TRUSTED_CATALOGUE_INDEX.items():
        image_url = image_by_id.get(str(product_id))
        if not image_url:
            continue
        product = {**product, "image_url": image_url}
        components = set(product.get("colour_components") or [])
        for colour in colours:
            if colour in components:
                digest = _n24m3_validation_sha256(f"{colour}:{product_id}".encode("utf-8")).hexdigest()
                buckets[colour].append((digest, product_id, product))
    for colour in colours:
        buckets[colour].sort(key=lambda item: item[0])
    selected = []
    cursor = {colour: 0 for colour in colours}
    while len(selected) < target:
        progressed = False
        for colour in colours:
            index = cursor[colour]
            if index >= len(buckets[colour]):
                continue
            _, product_id, product = buckets[colour][index]
            cursor[colour] += 1
            selected.append((colour, product_id, product))
            progressed = True
            if len(selected) == target:
                break
        if not progressed:
            break
    return selected


def run_n24m3_adversarial_visual_audit(target: int = 50) -> dict:
    if target < 50:
        raise ValueError("N24M3 adversarial visual audit requires at least 50 images")
    output_root = _n24m3_validation_output_root()
    output_root.mkdir(parents=True, exist_ok=True)
    samples = _n24m3_adversarial_samples(target)
    if len(samples) < target:
        raise RuntimeError(f"Only {len(samples)} stratified trusted image samples were available")

    def analyse(sample):
        requested, product_id, product = sample
        raw, cache_hit = n24m3_get_raw_visual_evidence(product_id, product.get("image_url"))
        assessment = n24m3_assess_visual_colour(raw, [requested])
        accepted = _n24m3_visual_accepts(assessment, [requested], False)
        return {
            "requested_colour": requested, "product_id": product_id,
            "title": product.get("title"), "brand": product.get("brand"),
            "metadata_colour_components": product.get("colour_components"),
            "metadata_colour_evidence": product["trusted_attributes"]["colour"],
            "image_url": product.get("image_url"), "local_image_path": raw.local_image_path,
            "classification": assessment.classification.value,
            "confidence": assessment.confidence, "requested_share": assessment.requested_share,
            "dominant_colours": assessment.dominant_colours,
            "metadata_image_disagreement": assessment.classification == N24VisualColourClassification.VISUAL_CONFLICT,
            "strict_gate_accepted": accepted, "cache_hit": cache_hit,
            "analysis_seconds": raw.analysis_seconds,
        }

    started = _n24m3_validation_time.perf_counter()
    with _N24M3ValidationPool(max_workers=8) as pool:
        rows = list(pool.map(analyse, samples))
    cold_wall = _n24m3_validation_time.perf_counter() - started
    classifications = _N24M3ValidationCounter(item["classification"] for item in rows)
    disagreements = sum(item["metadata_image_disagreement"] for item in rows)
    conflicts_accepted = sum(
        item["classification"] == "VISUAL_CONFLICT" and item["strict_gate_accepted"] for item in rows
    )

    # Repeat raw retrieval only.  This verifies that no image is re-downloaded
    # or re-analysed and gives the warm-cache layer overhead.
    cached_started = _n24m3_validation_time.perf_counter()
    cached_hits = 0
    for requested, product_id, product in samples:
        _, hit = n24m3_get_raw_visual_evidence(product_id, product.get("image_url"))
        cached_hits += int(hit)
    cached_wall = _n24m3_validation_time.perf_counter() - cached_started
    report = {
        "suite": "N24M3 deterministic stratified 50-image development audit",
        "selection": "round-robin SHA-256 order across white, black, red, blue, green, brown trusted metadata buckets",
        "total": len(rows), "classifications": dict(classifications),
        "metadata_image_disagreements": disagreements,
        "mismatch_rate": round(disagreements / len(rows), 6),
        "strict_conflicts_incorrectly_accepted": conflicts_accepted,
        "cold_parallel_wall_seconds": round(cold_wall, 6),
        "cached_serial_wall_seconds": round(cached_wall, 6),
        "cached_hits": cached_hits, "rows": rows,
    }
    (output_root / "adversarial_50_image_audit.json").write_text(
        _n24m3_validation_json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    return report
