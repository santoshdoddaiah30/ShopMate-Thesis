"""ShopMate N24M3 visual-colour and contextual-relaxation hardening.

This module is executed inside the existing notebook namespace.  It is an
additive N24-only boundary: N23 and the frozen hybrid ranker are left intact.
Metadata eligibility and frozen ranking run first; only the ranked metadata-
eligible shortlist is checked against the catalogue image.
"""

from __future__ import annotations

from collections import Counter as _N24M3Counter, deque as _N24M3Deque
from concurrent.futures import ThreadPoolExecutor as _N24M3ThreadPoolExecutor
from copy import deepcopy as _n24m3_deepcopy
from datetime import datetime as _N24M3DateTime, timezone as _N24M3TimeZone
from enum import Enum as _N24M3Enum
from hashlib import sha256 as _n24m3_sha256
from io import BytesIO as _N24M3BytesIO
from pathlib import Path as _N24M3Path
from threading import RLock as _N24M3RLock
from typing import Any as _N24M3Any
from urllib.parse import urlparse as _n24m3_urlparse
from urllib.request import Request as _N24M3URLRequest, urlopen as _n24m3_urlopen
import json as _n24m3_json
import math as _n24m3_math
import re as _n24m3_re
import time as _n24m3_time
import uuid as _n24m3_uuid

from PIL import Image as _N24M3Image


N24M3_SECTION_VERSION = "n24m3_visual_colour_contextual_relaxation_v1"
N24M3_VISUAL_CONTRACT_VERSION = "n24m3_local_foreground_colour_v2"
N24M3_PENDING_OFFER_VERSION = "n24m3_pending_relaxation_offer_v1"
N24M3_VISUAL_SHORTLIST_MINIMUM = 12
N24M3_VISUAL_SHORTLIST_MAXIMUM = 24
N24M3_VISUAL_DOWNLOAD_TIMEOUT_SECONDS = 15.0


def _n24m3_project_root() -> _N24M3Path:
    current = _N24M3Path.cwd().resolve()
    candidates = [current, current.parent, current.parent.parent]
    for candidate in candidates:
        if (candidate / "Notebooks" / "Thesis_clean.ipynb").is_file():
            return candidate
    return current.parent if current.name.casefold() == "notebooks" else current


N24M3_PROJECT_ROOT = _n24m3_project_root()
N24M3_AUDIT_ROOT = N24M3_PROJECT_ROOT / "Results" / "N24M3_Visual_Relaxation_Audit"
N24M3_IMAGE_CACHE_ROOT = N24M3_AUDIT_ROOT / "image_cache"
N24M3_ANALYSIS_CACHE_PATH = N24M3_AUDIT_ROOT / "visual_analysis_cache.json"
N24M3_IMAGE_CACHE_ROOT.mkdir(parents=True, exist_ok=True)


class N24VisualColourClassification(str, _N24M3Enum):
    VISUAL_EXACT = "VISUAL_EXACT"
    VISUAL_COMPATIBLE = "VISUAL_COMPATIBLE"
    VISUAL_MIXED = "VISUAL_MIXED"
    VISUAL_CONFLICT = "VISUAL_CONFLICT"
    VISUAL_UNKNOWN = "VISUAL_UNKNOWN"


class N24VisualRawEvidence(N24StrictModel):
    contract_version: str = N24M3_VISUAL_CONTRACT_VERSION
    product_id: str
    image_url: str | None = None
    image_cache_key: str
    local_image_path: str | None = None
    image_width: int | None = None
    image_height: int | None = None
    foreground_pixels: int = 0
    foreground_fraction: float = 0.0
    connected_white_background_fraction: float = 0.0
    colour_proportions: dict[str, float] = {}
    dominant_colours: list[str] = []
    analysis_status: str
    analysis_reason: str | None = None
    analysis_seconds: float = 0.0


class N24VisualColourAssessment(N24StrictModel):
    contract_version: str = N24M3_VISUAL_CONTRACT_VERSION
    product_id: str
    requested_colours: list[str]
    classification: N24VisualColourClassification
    confidence: float
    requested_share: float
    per_requested_share: dict[str, float]
    dominant_colours: list[str]
    colour_proportions: dict[str, float]
    foreground_pixels: int
    foreground_fraction: float
    connected_white_background_fraction: float
    image_url: str | None = None
    local_image_path: str | None = None
    cache_hit: bool = False
    analysis_seconds: float = 0.0
    mismatch_type: str | None = None
    accepted: bool = False


class N24PendingRelaxationAction(str, _N24M3Enum):
    ALLOW_MIXED_COLOURS = "ALLOW_MIXED_COLOURS"
    CLEAR_BRAND = "CLEAR_BRAND"
    CLEAR_COLOUR = "CLEAR_COLOUR"
    CLEAR_BUDGET = "CLEAR_BUDGET"
    BROADEN_CATEGORY = "BROADEN_CATEGORY"
    INCREASE_BUDGET = "INCREASE_BUDGET"


class N24PendingRelaxationOffer(N24StrictModel):
    # Consolidation Stage 4: an offer that quantifies verified alternatives
    # ("I verified N eligible candidates") must carry those N concrete product
    # IDs and their evidence, not just an action to re-run later. Acceptance
    # replays candidate_product_ids exactly instead of re-invoking the
    # recommender, so the promised products cannot silently change or vanish,
    # and a chat reload before the user answers no longer loses the offer
    # (see source_request_fingerprint / status / n24l_save_persistent_state).
    contract_version: str = N24M3_PENDING_OFFER_VERSION
    offer_id: str
    chat_id: int
    action_type: N24PendingRelaxationAction
    target_attribute: str
    proposed_operation: dict[str, _N24M3Any]
    source_turn_id: int | None = None
    expires_after_next_relevant_turn: bool = True
    active: bool = True
    created_at: str
    source_request_fingerprint: str | None = None
    source_result_set_id: str | None = None
    original_hard_constraints: dict[str, _N24M3Any] = Field(default_factory=dict)
    relaxed_constraint: str | None = None
    relaxed_mode: str | None = None
    candidate_product_ids: list[str] = Field(default_factory=list)
    candidate_evidence: dict[str, _N24M3Any] = Field(default_factory=dict)
    verified_count: int = 0
    status: str = "pending"  # pending | consumed | rejected | expired


if "N24M3_VISUAL_CACHE_LOCK" not in globals():
    N24M3_VISUAL_CACHE_LOCK = _N24M3RLock()
if "N24M3_LAST_VISUAL_AUDIT" not in globals():
    N24M3_LAST_VISUAL_AUDIT = []
if "N24M3_VISUAL_RUNTIME_METRICS" not in globals():
    N24M3_VISUAL_RUNTIME_METRICS = []


def _n24m3_load_analysis_cache() -> dict[str, dict]:
    try:
        payload = _n24m3_json.loads(N24M3_ANALYSIS_CACHE_PATH.read_text(encoding="utf-8"))
        if payload.get("contract_version") != N24M3_VISUAL_CONTRACT_VERSION:
            return {}
        items = payload.get("items")
        return dict(items) if isinstance(items, dict) else {}
    except Exception:
        return {}


if "N24M3_VISUAL_ANALYSIS_CACHE" not in globals():
    N24M3_VISUAL_ANALYSIS_CACHE = _n24m3_load_analysis_cache()


def _n24m3_save_analysis_cache() -> None:
    payload = {
        "contract_version": N24M3_VISUAL_CONTRACT_VERSION,
        "updated_at": _N24M3DateTime.now(_N24M3TimeZone.utc).isoformat(),
        "items": N24M3_VISUAL_ANALYSIS_CACHE,
    }
    temporary = N24M3_ANALYSIS_CACHE_PATH.with_suffix(".tmp")
    temporary.write_text(_n24m3_json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(N24M3_ANALYSIS_CACHE_PATH)


def _n24m3_clean_image_url(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and _n24m3_math.isnan(value):
        return None
    text = str(value).strip()
    return None if not text or text.casefold() in {"nan", "none", "null"} else text


def _n24m3_cache_key(product_id: str, image_url: str | None) -> str:
    identity = f"{product_id}\n{image_url or 'NO_IMAGE'}\n{N24M3_VISUAL_CONTRACT_VERSION}"
    return _n24m3_sha256(identity.encode("utf-8")).hexdigest()


def _n24m3_image_path(product_id: str, image_url: str, cache_key: str) -> _N24M3Path:
    suffix = _N24M3Path(_n24m3_urlparse(image_url).path).suffix.casefold()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".img"
    safe_id = _n24m3_re.sub(r"[^A-Za-z0-9_.-]+", "_", str(product_id))
    return N24M3_IMAGE_CACHE_ROOT / f"{safe_id}_{cache_key[:14]}{suffix}"


def _n24m3_download_image(product_id: str, image_url: str, cache_key: str) -> _N24M3Path:
    path = _n24m3_image_path(product_id, image_url, cache_key)
    if path.is_file() and path.stat().st_size > 0:
        return path
    # Accept the two original trace filenames as ordinary cache entries.  This
    # is product-agnostic: any <product_id>.<supported-extension> is reusable.
    for suffix in (".jpg", ".jpeg", ".png", ".webp"):
        legacy = N24M3_IMAGE_CACHE_ROOT / f"{product_id}{suffix}"
        if legacy.is_file() and legacy.stat().st_size > 0:
            return legacy
    request = _N24M3URLRequest(
        image_url,
        headers={"User-Agent": "ShopMate-N24M3/1.0 local-colour-verifier"},
    )
    with _n24m3_urlopen(request, timeout=N24M3_VISUAL_DOWNLOAD_TIMEOUT_SECONDS) as response:
        content = response.read(8 * 1024 * 1024 + 1)
    if not content or len(content) > 8 * 1024 * 1024:
        raise ValueError("image payload was empty or exceeded 8 MiB")
    # Validate before making the cache entry visible.
    with _N24M3Image.open(_N24M3BytesIO(content)) as image:
        image.verify()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)
    return path


def _n24m3_connected_white_background(rgb, alpha):
    height, width, _ = rgb.shape
    maximum = rgb.max(axis=2)
    minimum = rgb.min(axis=2)
    candidate = ((minimum >= 248) & ((maximum - minimum) <= 8)) | (alpha < 32)
    connected = _n24l_np.zeros((height, width), dtype=bool)
    queue = _N24M3Deque()
    for x in range(width):
        if candidate[0, x]: queue.append((0, x))
        if candidate[height - 1, x]: queue.append((height - 1, x))
    for y in range(height):
        if candidate[y, 0]: queue.append((y, 0))
        if candidate[y, width - 1]: queue.append((y, width - 1))
    while queue:
        y, x = queue.popleft()
        if connected[y, x] or not candidate[y, x]:
            continue
        connected[y, x] = True
        if y: queue.append((y - 1, x))
        if y + 1 < height: queue.append((y + 1, x))
        if x: queue.append((y, x - 1))
        if x + 1 < width: queue.append((y, x + 1))
    return connected


def _n24m3_colour_labels(pixels):
    values = pixels.astype(_n24l_np.float32) / 255.0
    maximum = values.max(axis=1)
    minimum = values.min(axis=1)
    delta = maximum - minimum
    saturation = _n24l_np.divide(delta, maximum, out=_n24l_np.zeros_like(delta), where=maximum > 0)
    hue = _n24l_np.zeros_like(maximum)
    nonzero = delta > 1e-6
    red_max = nonzero & (values[:, 0] == maximum)
    green_max = nonzero & (values[:, 1] == maximum)
    blue_max = nonzero & (values[:, 2] == maximum)
    hue[red_max] = (60.0 * ((values[red_max, 1] - values[red_max, 2]) / delta[red_max])) % 360.0
    hue[green_max] = 60.0 * ((values[green_max, 2] - values[green_max, 0]) / delta[green_max] + 2.0)
    hue[blue_max] = 60.0 * ((values[blue_max, 0] - values[blue_max, 1]) / delta[blue_max] + 4.0)

    labels = _n24l_np.full(len(pixels), "unknown", dtype="<U12")
    labels[maximum <= 0.26] = "black"
    labels[(saturation <= 0.16) & (maximum > 0.26) & (maximum < 0.50)] = "dark_grey"
    labels[(saturation <= 0.16) & (maximum >= 0.50) & (maximum < 0.70)] = "grey"
    labels[(saturation <= 0.16) & (maximum >= 0.70) & (maximum < 0.82)] = "light_grey"
    labels[(saturation <= 0.16) & (maximum >= 0.82)] = "white"

    chromatic = (saturation > 0.16) & (maximum > 0.26)
    labels[chromatic & ((hue < 15) | (hue >= 345))] = "red"
    labels[chromatic & (hue >= 15) & (hue < 45) & (maximum < 0.72)] = "brown"
    labels[chromatic & (hue >= 15) & (hue < 45) & (maximum >= 0.72)] = "orange"
    labels[chromatic & (hue >= 45) & (hue < 70)] = "yellow"
    labels[chromatic & (hue >= 70) & (hue < 170)] = "green"
    labels[chromatic & (hue >= 170) & (hue < 195)] = "cyan"
    labels[chromatic & (hue >= 195) & (hue < 260)] = "blue"
    labels[chromatic & (hue >= 260) & (hue < 315)] = "purple"
    labels[chromatic & (hue >= 315) & (hue < 345)] = "pink"
    return labels


def _n24m3_analyse_image_uncached(product_id: str, image_url: str | None, cache_key: str) -> N24VisualRawEvidence:
    started = _n24m3_time.perf_counter()
    if image_url is None:
        return N24VisualRawEvidence(
            product_id=product_id, image_url=None, image_cache_key=cache_key,
            analysis_status="UNKNOWN", analysis_reason="catalogue image URL absent",
            analysis_seconds=round(_n24m3_time.perf_counter() - started, 6),
        )
    try:
        path = _n24m3_download_image(product_id, image_url, cache_key)
        with _N24M3Image.open(path) as source:
            image = source.convert("RGBA")
            original_width, original_height = image.size
            image.thumbnail((320, 320), _N24M3Image.Resampling.LANCZOS)
            rgba = _n24l_np.asarray(image, dtype=_n24l_np.uint8)
        rgb = rgba[:, :, :3]
        alpha = rgba[:, :, 3]
        background = _n24m3_connected_white_background(rgb, alpha)
        foreground = (alpha >= 32) & ~background
        foreground_pixels = int(foreground.sum())
        total_pixels = int(foreground.size)
        if foreground_pixels < max(200, int(total_pixels * 0.015)):
            raise ValueError("too few foreground pixels after border-background removal")
        labels = _n24m3_colour_labels(rgb[foreground])
        counts = _N24M3Counter(str(item) for item in labels if item != "unknown")
        labelled = sum(counts.values())
        if labelled < max(150, int(foreground_pixels * 0.6)):
            raise ValueError("foreground colour evidence was insufficient")
        proportions = {
            key: round(value / labelled, 6)
            for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        }
        return N24VisualRawEvidence(
            product_id=product_id, image_url=image_url, image_cache_key=cache_key,
            local_image_path=str(path.resolve()), image_width=original_width,
            image_height=original_height, foreground_pixels=foreground_pixels,
            foreground_fraction=round(foreground_pixels / total_pixels, 6),
            connected_white_background_fraction=round(float(background.sum()) / total_pixels, 6),
            colour_proportions=proportions, dominant_colours=list(proportions)[:4],
            analysis_status="ANALYSED",
            analysis_seconds=round(_n24m3_time.perf_counter() - started, 6),
        )
    except Exception as error:
        return N24VisualRawEvidence(
            product_id=product_id, image_url=image_url, image_cache_key=cache_key,
            analysis_status="UNKNOWN", analysis_reason=f"{type(error).__name__}: {error}",
            analysis_seconds=round(_n24m3_time.perf_counter() - started, 6),
        )


def n24m3_get_raw_visual_evidence(product_id: str, image_url) -> tuple[N24VisualRawEvidence, bool]:
    product_id = str(product_id)
    clean_url = _n24m3_clean_image_url(image_url)
    cache_key = _n24m3_cache_key(product_id, clean_url)
    with N24M3_VISUAL_CACHE_LOCK:
        cached = N24M3_VISUAL_ANALYSIS_CACHE.get(cache_key)
    if isinstance(cached, dict):
        try:
            return N24VisualRawEvidence.model_validate(cached), True
        except Exception:
            pass
    evidence = _n24m3_analyse_image_uncached(product_id, clean_url, cache_key)
    with N24M3_VISUAL_CACHE_LOCK:
        N24M3_VISUAL_ANALYSIS_CACHE[cache_key] = evidence.model_dump(mode="json")
        _n24m3_save_analysis_cache()
    return evidence, False


_N24M3_COMPATIBLE_BUCKETS = {
    "white": {"white", "light_grey"},
    "black": {"black", "dark_grey"},
    "grey": {"light_grey", "grey", "dark_grey"},
    "gray": {"light_grey", "grey", "dark_grey"},
    "blue": {"blue", "cyan"},
    "red": {"red"}, "green": {"green"}, "yellow": {"yellow"},
    "orange": {"orange"}, "brown": {"brown"}, "purple": {"purple"},
    "pink": {"pink"},
}


def _n24m3_canonical_colour(value: str) -> str:
    normal = _n24m2_normalize(value)
    return _N24M_COLOUR_ALIASES.get(normal, normal).replace("gray", "grey")


def n24m3_assess_visual_colour(raw: N24VisualRawEvidence, requested_colours) -> N24VisualColourAssessment:
    requested = list(dict.fromkeys(_n24m3_canonical_colour(item) for item in requested_colours if str(item).strip()))
    if raw.analysis_status != "ANALYSED" or not requested:
        return N24VisualColourAssessment(
            product_id=raw.product_id, requested_colours=requested,
            classification=N24VisualColourClassification.VISUAL_UNKNOWN,
            confidence=0.0, requested_share=0.0, per_requested_share={},
            dominant_colours=raw.dominant_colours, colour_proportions=raw.colour_proportions,
            foreground_pixels=raw.foreground_pixels, foreground_fraction=raw.foreground_fraction,
            connected_white_background_fraction=raw.connected_white_background_fraction,
            image_url=raw.image_url, local_image_path=raw.local_image_path,
            analysis_seconds=raw.analysis_seconds,
        )
    proportions = raw.colour_proportions
    shares = {
        colour: round(sum(proportions.get(bucket, 0.0) for bucket in _N24M3_COMPATIBLE_BUCKETS.get(colour, {colour})), 6)
        for colour in requested
    }
    requested_share = min(1.0, sum(shares.values()))
    incompatible_share = max(
        (share for colour, share in proportions.items()
         if not any(colour in _N24M3_COMPATIBLE_BUCKETS.get(item, {item}) for item in requested)),
        default=0.0,
    )
    if len(requested) > 1:
        if all(shares[item] >= 0.10 for item in requested) and requested_share >= 0.35:
            classification = N24VisualColourClassification.VISUAL_MIXED
            confidence = min(0.99, 0.60 + requested_share * 0.35)
        elif requested_share < 0.12 and incompatible_share >= 0.35:
            classification = N24VisualColourClassification.VISUAL_CONFLICT
            confidence = min(0.99, 0.55 + incompatible_share * 0.4)
        else:
            classification = N24VisualColourClassification.VISUAL_UNKNOWN
            confidence = 0.35
    else:
        share = shares[requested[0]]
        exact_bucket_share = proportions.get(requested[0], 0.0)
        if share >= 0.56 and incompatible_share < 0.34:
            classification = N24VisualColourClassification.VISUAL_EXACT
            confidence = min(0.99, 0.62 + share * 0.35)
        elif share >= 0.34 and incompatible_share < 0.48:
            classification = N24VisualColourClassification.VISUAL_COMPATIBLE
            confidence = min(0.94, 0.50 + share * 0.40)
        elif share >= 0.12 and incompatible_share >= 0.18:
            classification = N24VisualColourClassification.VISUAL_MIXED
            confidence = min(0.94, 0.48 + max(share, incompatible_share) * 0.42)
        elif share < 0.12 and incompatible_share >= 0.35:
            classification = N24VisualColourClassification.VISUAL_CONFLICT
            confidence = min(0.99, 0.58 + incompatible_share * 0.38)
        elif exact_bucket_share >= 0.22:
            classification = N24VisualColourClassification.VISUAL_COMPATIBLE
            confidence = 0.65
        else:
            classification = N24VisualColourClassification.VISUAL_UNKNOWN
            confidence = 0.30
    mismatch = (
        "DATASET_IMAGE_METADATA_MISMATCH"
        if classification == N24VisualColourClassification.VISUAL_CONFLICT else None
    )
    return N24VisualColourAssessment(
        product_id=raw.product_id, requested_colours=requested,
        classification=classification, confidence=round(float(confidence), 4),
        requested_share=round(float(requested_share), 6), per_requested_share=shares,
        dominant_colours=raw.dominant_colours, colour_proportions=proportions,
        foreground_pixels=raw.foreground_pixels, foreground_fraction=raw.foreground_fraction,
        connected_white_background_fraction=raw.connected_white_background_fraction,
        image_url=raw.image_url, local_image_path=raw.local_image_path,
        analysis_seconds=raw.analysis_seconds, mismatch_type=mismatch,
    )


def _n24m3_visual_accepts(assessment: N24VisualColourAssessment, requested, allow_mixed: bool) -> bool:
    classification = assessment.classification
    if len(requested) > 1:
        return classification in {
            N24VisualColourClassification.VISUAL_EXACT,
            N24VisualColourClassification.VISUAL_COMPATIBLE,
            N24VisualColourClassification.VISUAL_MIXED,
        } and all(assessment.per_requested_share.get(_n24m3_canonical_colour(item), 0.0) >= 0.10 for item in requested)
    if allow_mixed:
        return classification in {
            N24VisualColourClassification.VISUAL_EXACT,
            N24VisualColourClassification.VISUAL_COMPATIBLE,
            N24VisualColourClassification.VISUAL_MIXED,
        } and assessment.requested_share >= 0.12
    # Conservative policy: UNKNOWN is not promoted to an exact result.  It can
    # be audited, cached and reported, but never padded into strict results.
    return classification in {
        N24VisualColourClassification.VISUAL_EXACT,
        N24VisualColourClassification.VISUAL_COMPATIBLE,
    }


if "N24M3_BASE_RECOMMENDER" not in globals():
    N24M3_BASE_RECOMMENDER = get_n24_recommendations_from_validated_state


def get_n24_recommendations_from_validated_state(
    request, top_n=10,
    candidate_pool_size=REQUEST_AWARE_DEFAULT_CANDIDATE_POOL_SIZE,
):
    request = N24ValidatedRecommendationRequest.model_validate(request.model_dump(mode="python"))
    if not request.colours:
        return N24M3_BASE_RECOMMENDER(request, top_n=top_n, candidate_pool_size=candidate_pool_size)
    sidecar = _n24m3_deepcopy(
        N24M_REQUEST_SIDECARS.get(request.request_fingerprint)
        or _n24m_sidecar(N24M_CURRENT_CHAT_ID.get())
    )
    shortlist_n = min(
        N24M3_VISUAL_SHORTLIST_MAXIMUM,
        max(N24M3_VISUAL_SHORTLIST_MINIMUM, int(top_n) * 2),
    )
    total_started = _n24m3_time.perf_counter()
    metadata_result = N24M3_BASE_RECOMMENDER(
        request, top_n=shortlist_n, candidate_pool_size=candidate_pool_size
    )
    metadata_frame = metadata_result["recommendations"].copy()
    rows = metadata_frame.to_dict("records")
    visual_started = _n24m3_time.perf_counter()

    def check(row):
        raw, cache_hit = n24m3_get_raw_visual_evidence(
            str(row.get("product_id")), row.get("image_url")
        )
        assessment = n24m3_assess_visual_colour(raw, request.colours)
        accepted = _n24m3_visual_accepts(
            assessment, request.colours, bool(sidecar.get("allow_mixed_colours"))
        )
        return assessment.model_copy(update={"cache_hit": cache_hit, "accepted": accepted})

    if rows:
        workers = min(6, len(rows))
        with _N24M3ThreadPoolExecutor(max_workers=workers) as pool:
            assessments = list(pool.map(check, rows))
    else:
        assessments = []
    accepted_ids = [item.product_id for item in assessments if item.accepted]
    selected = metadata_frame.loc[
        metadata_frame["product_id"].astype(str).isin(accepted_ids)
    ].head(top_n).reset_index(drop=True) if not metadata_frame.empty else metadata_frame
    if not selected.empty:
        selected["request_rank"] = _n24l_np.arange(1, len(selected) + 1, dtype=_n24l_np.int32)
    returned_ids = set(selected["product_id"].astype(str)) if not selected.empty else set()
    audit = []
    for item in assessments:
        record = item.model_dump(mode="json")
        record["returned"] = item.product_id in returned_ids
        audit.append(record)
    visual_elapsed = _n24m3_time.perf_counter() - visual_started
    total_elapsed = _n24m3_time.perf_counter() - total_started
    counts = _N24M3Counter(item.classification.value for item in assessments)
    result = dict(metadata_result)
    result.update({
        "recommendations": selected,
        "recommendation_count": int(len(selected)),
        "requested_result_count": int(top_n),
        "exact_match_count": int(len(selected)),
        "exact_match_shortfall": len(selected) < top_n,
        "no_exact_match": len(selected) == 0,
        "result_mode": "no_exact_matches" if len(selected) == 0 else "partial_exact_matches" if len(selected) < top_n else "complete_exact_matches",
        "engine_version": "n24m3_visual_verified_exact_eligibility_v1",
        "metadata_eligible_shortlist_count": int(len(metadata_frame)),
        "visual_checked_count": len(assessments),
        "visual_classification_counts": dict(counts),
        "visual_conflicts_returned_as_exact": sum(
            item.classification == N24VisualColourClassification.VISUAL_CONFLICT
            and item.product_id in returned_ids for item in assessments
        ),
        "visual_colour_audit": audit,
        "visual_overhead_seconds": round(visual_elapsed, 6),
        "metadata_ranking_plus_visual_seconds": round(total_elapsed, 6),
        "visual_cache_hits": sum(item.cache_hit for item in assessments),
        "visual_cache_misses": sum(not item.cache_hit for item in assessments),
        "visual_unknown_policy": "EXCLUDE_FROM_STRICT_EXACT",
    })
    N24M3_LAST_VISUAL_AUDIT[:] = audit
    N24M3_VISUAL_RUNTIME_METRICS.append({
        "request_fingerprint": request.request_fingerprint,
        "requested_colours": list(request.colours), "images_checked": len(assessments),
        "cache_hits": result["visual_cache_hits"], "cache_misses": result["visual_cache_misses"],
        "visual_elapsed_seconds": round(visual_elapsed, 6),
        "total_elapsed_seconds": round(total_elapsed, 6),
    })
    return result


def _n24m3_pending_offer(chat_id: int) -> N24PendingRelaxationOffer | None:
    raw = _n24m_sidecar(chat_id).get("pending_relaxation")
    if not isinstance(raw, dict):
        return None
    try:
        offer = N24PendingRelaxationOffer.model_validate(raw)
        return offer if offer.active and offer.chat_id == int(chat_id) else None
    except Exception:
        return None


def _n24m3_set_pending_offer(
    chat_id: int, action, target_attribute: str, operation: dict, source_turn_id=None,
    *, source_request_fingerprint: str | None = None, source_result_set_id: str | None = None,
    candidate_product_ids=None, candidate_evidence=None,
    original_hard_constraints=None,
):
    candidate_ids = list(candidate_product_ids or [])
    offer = N24PendingRelaxationOffer(
        offer_id=f"n24m3-offer-{_n24m3_uuid.uuid4().hex}", chat_id=int(chat_id),
        action_type=action, target_attribute=target_attribute,
        proposed_operation=operation, source_turn_id=source_turn_id,
        created_at=_N24M3DateTime.now(_N24M3TimeZone.utc).isoformat(),
        source_request_fingerprint=source_request_fingerprint,
        source_result_set_id=source_result_set_id,
        original_hard_constraints=dict(original_hard_constraints or {}),
        relaxed_constraint=target_attribute,
        relaxed_mode=action.value if hasattr(action, "value") else str(action),
        candidate_product_ids=candidate_ids,
        candidate_evidence=dict(candidate_evidence or {}),
        verified_count=len(candidate_ids),
        status="pending",
    )
    # Persistence is part of the offer contract, not best-effort telemetry:
    # never emit "I verified N" unless the same N candidate IDs are already
    # durably stored for replay after reload.
    _n24m3_persist_pending_offer(chat_id, offer)
    _n24m_sidecar(chat_id)["pending_relaxation"] = offer.model_dump(mode="json")
    return offer


def _n24m3_clear_pending_offer(chat_id: int, status: str = "rejected") -> None:
    """Resolve the current pending offer. The live sidecar pointer is cleared
    (no offer is 'pending' any more this turn onward), but the persisted
    record keeps its final status (consumed/rejected/expired) rather than
    being deleted, so an offer's outcome is auditable and a restore never
    mistakes a resolved offer for a still-open one (see
    _n24m3_restore_pending_offer, which only restores status == "pending")."""
    current = _n24m3_pending_offer(chat_id)
    if current is not None:
        resolved = current.model_copy(update={"active": False, "status": status})
        _n24m3_persist_pending_offer(chat_id, resolved)
    else:
        _n24m3_persist_pending_offer(chat_id, None)
    _n24m_sidecar(chat_id)["pending_relaxation"] = None


def _n24m3_lookup_chat_user_id(chat_id: int):
    row = duckdb_connection.execute(
        "select user_id from app_chat_sessions where chat_id = ?", [int(chat_id)]
    ).fetchone()
    return None if row is None else int(row[0])


def _n24m3_persist_pending_offer(chat_id: int, offer) -> None:
    """Thread the pending offer into the same DB-backed payload as result_sets
    (n24l_save_persistent_state), so it survives chat reload and kernel
    restart instead of living only in the in-memory sidecar. Best-effort: the
    in-memory sidecar (checked first on every turn) remains authoritative
    within a live process; this call keeps the persisted copy in sync so a
    fresh load restores it. Never touches N23 or the frozen recommender.
    """
    user_id = _n24m3_lookup_chat_user_id(chat_id)
    if user_id is None:
        raise RuntimeError("Cannot persist a pending offer for an unknown chat.")
    root = _n24l_root_state(chat_id, user_id)
    raw = root.get(N24L_STATE_KEY)
    payload = dict(raw) if isinstance(raw, dict) else _n24l_empty_persistent_payload()
    expected = None if offer is None else offer.model_dump(mode="json")
    payload["pending_offer"] = expected
    root[N24L_STATE_KEY] = payload
    save_chat_active_request_state(chat_id=chat_id, user_id=user_id, state=root)
    verified_root = _n24l_root_state(chat_id, user_id)
    verified_payload = verified_root.get(N24L_STATE_KEY)
    actual = verified_payload.get("pending_offer") if isinstance(verified_payload, dict) else None
    if actual != expected:
        raise RuntimeError("Pending offer persistence verification failed.")


def _n24m3_restore_pending_offer(chat_id: int, user_id: int) -> None:
    """Load a persisted pending offer (if any) back into the in-memory
    sidecar on chat load, so an offer made before a reload/restart is not
    silently lost before the user even answers yes/no."""
    try:
        root = _n24l_root_state(chat_id, user_id)
        payload = root.get(N24L_STATE_KEY)
        if not isinstance(payload, dict):
            return
        stored = payload.get("pending_offer")
        if isinstance(stored, dict) and stored.get("status") == "pending":
            _n24m_sidecar(chat_id)["pending_relaxation"] = stored
    except Exception:
        pass


def _n24m3_delta_for_offer(offer: N24PendingRelaxationOffer, raw_message: str):
    action = offer.action_type
    fields = N24FieldOperations()
    updates = {}
    if action == N24PendingRelaxationAction.ALLOW_MIXED_COLOURS:
        updates["allow_mixed_colours"] = True
    elif action == N24PendingRelaxationAction.CLEAR_BRAND:
        fields.brands = _n24m_operation(N24FieldOperationType.CLEAR)
    elif action == N24PendingRelaxationAction.CLEAR_COLOUR:
        fields.colours = _n24m_operation(N24FieldOperationType.CLEAR)
        updates["allow_mixed_colours"] = False
    elif action == N24PendingRelaxationAction.CLEAR_BUDGET:
        fields.minimum_price = _n24m_operation(N24FieldOperationType.CLEAR)
        fields.maximum_price = _n24m_operation(N24FieldOperationType.CLEAR)
        fields.price_mode = _n24m_operation(N24FieldOperationType.CLEAR)
    elif action == N24PendingRelaxationAction.BROADEN_CATEGORY:
        fields.categories = _n24m_operation(N24FieldOperationType.CLEAR)
    elif action == N24PendingRelaxationAction.INCREASE_BUDGET:
        proposed = offer.proposed_operation.get("maximum_price")
        if proposed is None:
            fields.maximum_price = _n24m_operation(N24FieldOperationType.CLEAR)
        else:
            fields.maximum_price = _n24m_operation(N24FieldOperationType.REPLACE, float(proposed))
    return N24TurnDelta(
        intent=N24Intent.REFINE, field_operations=fields,
        confidence=1.0, raw_message=raw_message,
    ), updates


_N24M3_AFFIRMATIVE = _n24m3_re.compile(
    r"^(?:yes|yes show me|yes show me mixed|okay|ok|sure|do that|show me those|mixed colou?rs? (?:are )?(?:okay|ok|fine|allowed))[.!]*$",
    _n24m3_re.IGNORECASE,
)
_N24M3_NEGATIVE = _n24m3_re.compile(r"^(?:no|no thanks|no thank you)[.!]*$", _n24m3_re.IGNORECASE)


if "N24M3_BASE_INTERPRET_TURN" not in globals():
    N24M3_BASE_INTERPRET_TURN = n24l_interpret_turn


def n24l_interpret_turn(raw_message: str, context, state, active_result_set):
    text = " ".join(str(raw_message or "").strip().split())
    lower = _n24m_normalize(text)
    chat_id = int(context.chat_id)
    N24M_CURRENT_CHAT_ID.set(chat_id)
    pending = _n24m3_pending_offer(chat_id)

    # Explicit alternatives have priority over the pending action.
    relax_brand = bool(_n24m3_re.search(r"\brelax (?:the )?brand\b|\bforget (?:the )?brand\b", lower))
    forget_colour = bool(_n24m3_re.search(r"\b(?:actually )?(?:forget|remove|ignore) (?:the )?colou?r\b", lower))
    another_category = bool(_n24m3_re.search(r"\b(?:show me )?another category\b", lower))
    if relax_brand or forget_colour or another_category:
        _n24m3_clear_pending_offer(chat_id)
        if another_category:
            delta = N24TurnDelta(
                intent=N24Intent.REFINE, confidence=1.0, raw_message=text,
                requires_clarification=True,
                clarification_question="Which product category would you like instead?",
            )
            return delta, {"semantic_guard": "n24m3_explicit_alternative_category", "superlative": None}, {
                "intent": 0, "response": 0, "repair": 0, "total": 0,
                "interpreter_status": "N24M3_DETERMINISTIC", "interpreter_latency_seconds": 0.0,
                "semantic_guard": "n24m3_explicit_alternative_category", "ollama_available": False,
                "model_available": False,
            }
        fields = N24FieldOperations(
            brands=_n24m_operation(N24FieldOperationType.CLEAR) if relax_brand else None,
            colours=_n24m_operation(N24FieldOperationType.CLEAR) if forget_colour else None,
        )
        delta = N24TurnDelta(intent=N24Intent.REFINE, field_operations=fields, confidence=1.0, raw_message=text)
        _n24m_apply_updates(chat_id, delta, {"allow_mixed_colours": False if forget_colour else None})
        return delta, {"semantic_guard": "n24m3_explicit_relaxation_override", "superlative": None}, {
            "intent": 0, "response": 0, "repair": 0, "total": 0,
            "interpreter_status": "N24M3_DETERMINISTIC", "interpreter_latency_seconds": 0.0,
            "semantic_guard": "n24m3_explicit_relaxation_override", "ollama_available": False,
            "model_available": False,
        }

    if pending is not None and _N24M3_AFFIRMATIVE.fullmatch(text):
        _n24m3_clear_pending_offer(chat_id)
        delta, updates = _n24m3_delta_for_offer(pending, text)
        _n24m_apply_updates(chat_id, delta, updates)
        return delta, {"semantic_guard": "n24m3_pending_relaxation_accepted", "superlative": None}, {
            "intent": 0, "response": 0, "repair": 0, "total": 0,
            "interpreter_status": "N24M3_PENDING_OFFER", "interpreter_latency_seconds": 0.0,
            "semantic_guard": "n24m3_pending_relaxation_accepted", "ollama_available": False,
            "model_available": False, "accepted_offer_id": pending.offer_id,
            "accepted_action": pending.action_type.value,
        }
    if pending is not None:
        if _N24M3_NEGATIVE.fullmatch(text):
            _n24m3_clear_pending_offer(chat_id, status="rejected")
            return None, {"semantic_guard": "n24m3_pending_relaxation_rejected", "superlative": None}, {
                "intent": 0, "response": 0, "repair": 0, "total": 0,
                "interpreter_status": "N24M3_PENDING_REJECTED", "interpreter_latency_seconds": 0.0,
                "semantic_guard": "n24m3_pending_relaxation_rejected", "ollama_available": False,
                "model_available": False,
            }

    if pending is None and _N24M3_AFFIRMATIVE.fullmatch(text):
        # A bare confirmation has no shopping semantics of its own.  Never send
        # it to a language model that could invent a category or constraint.
        return None, {"semantic_guard": "n24m3_affirmative_without_pending_offer", "superlative": None}, {
            "intent": 0, "response": 0, "repair": 0, "total": 0,
            "interpreter_status": "N24M3_SAFE_CLARIFICATION", "interpreter_latency_seconds": 0.0,
            "semantic_guard": "n24m3_affirmative_without_pending_offer", "ollama_available": False,
            "model_available": False,
        }

    # "only mostly red ones" intentionally returns to strict colour policy.
    mostly = _n24m3_re.fullmatch(r"(?:only )?mostly ([a-z]+)(?: ones?)?[.!]*", lower)
    if mostly:
        colour = _n24m3_canonical_colour(mostly.group(1))
        if colour in _N24M3_COMPATIBLE_BUCKETS:
            delta = N24TurnDelta(
                intent=N24Intent.REFINE,
                field_operations=N24FieldOperations(
                    colours=_n24m_operation(N24FieldOperationType.REPLACE, [colour])
                ), confidence=1.0, raw_message=text,
            )
            _n24m_apply_updates(chat_id, delta, {"allow_mixed_colours": False})
            return delta, {"semantic_guard": "n24m3_mostly_colour_strict", "superlative": None}, {
                "intent": 0, "response": 0, "repair": 0, "total": 0,
                "interpreter_status": "N24M3_DETERMINISTIC", "interpreter_latency_seconds": 0.0,
                "semantic_guard": "n24m3_mostly_colour_strict", "ollama_available": False,
                "model_available": False,
            }
    result = N24M3_BASE_INTERPRET_TURN(raw_message, context, state, active_result_set)
    if pending is not None and result is not None:
        delta = result[0]
        category_operation = (
            None if delta is None else getattr(delta.field_operations, "categories", None)
        )
        starts_new_goal = bool(
            delta is not None and (
                delta.intent == N24Intent.NEW_GOAL
                or (
                    delta.intent == N24Intent.PRODUCT_SEARCH
                    and category_operation is not None
                    and category_operation.operation in {
                        N24FieldOperationType.SET, N24FieldOperationType.REPLACE,
                    }
                )
            )
        )
        if starts_new_goal:
            _n24m3_clear_pending_offer(chat_id, status="expired")
    # Questions, comparisons and other read-only turns deliberately retain a
    # pending offer; only accept/reject or a genuinely new shopping goal
    # resolves it.
    return result


def _n24m3_offer_from_orchestration(orchestration):
    request = orchestration.validated_request
    if request is None:
        return None
    chat_id = N24M_CURRENT_CHAT_ID.get()
    if chat_id is None:
        return None
    sidecar = _n24m_sidecar(chat_id)
    source_turn_id = None
    if orchestration.result_set is not None:
        source_turn_id = orchestration.result_set.source_message_id
    if request.colours and not sidecar.get("allow_mixed_colours"):
        return _n24m3_set_pending_offer(
            chat_id, N24PendingRelaxationAction.ALLOW_MIXED_COLOURS, "colours",
            {"allow_mixed_colours": True, "retain_colours": list(request.colours)}, source_turn_id,
        )
    if request.maximum_price is not None or request.minimum_price is not None:
        return _n24m3_set_pending_offer(
            chat_id, N24PendingRelaxationAction.CLEAR_BUDGET, "historical_price",
            {"minimum_price": None, "maximum_price": None}, source_turn_id,
        )
    if request.brands:
        return _n24m3_set_pending_offer(
            chat_id, N24PendingRelaxationAction.CLEAR_BRAND, "brands",
            {"brands": []}, source_turn_id,
        )
    if request.categories:
        return _n24m3_set_pending_offer(
            chat_id, N24PendingRelaxationAction.BROADEN_CATEGORY, "categories",
            {"categories": []}, source_turn_id,
        )
    return None


if "N24M3_BASE_COMPOSE" not in globals():
    N24M3_BASE_COMPOSE = _n24l_compose


def _n24l_compose(raw_message: str, orchestration, call_metrics: dict):
    response = N24M3_BASE_COMPOSE(raw_message, orchestration, call_metrics)
    if orchestration.status == "no_exact_match":
        _n24m3_offer_from_orchestration(orchestration)
    return response


N24M3_COMPATIBILITY_STATUS = {
    "section_version": N24M3_SECTION_VERSION,
    "development_engine": get_shopmate_engine(),
    "n23_modified": False,
    "frozen_ranker_changed": False,
    "visual_provider": "PIL_NUMPY_LOCAL_DETERMINISTIC",
    "additional_llm_calls_for_visual": 0,
    "visual_unknown_policy": "EXCLUDE_FROM_STRICT_EXACT",
    "cache_root": str(N24M3_IMAGE_CACHE_ROOT),
    "pending_offer_chat_scoped": True,
}

print("N24M3 visual-colour and contextual-relaxation layer loaded.")
print(_n24m3_json.dumps(N24M3_COMPATIBILITY_STATUS, indent=2))
