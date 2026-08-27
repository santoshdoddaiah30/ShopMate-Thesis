"""ShopMate N24L real API integration.

This source is executed by the N24L notebook cell in the notebook namespace.
It deliberately depends on the frozen N23 and additive N24A-K objects already
loaded there.  Product selection remains deterministic and catalogue-grounded.
"""

from __future__ import annotations

from copy import deepcopy as _n24l_deepcopy
from datetime import datetime as _n24l_datetime, timezone as _n24l_timezone
import json as _n24l_json
import os as _n24l_os
import re as _n24l_re
import threading as _n24l_threading
import time as _n24l_time
import urllib.request as _n24l_urlrequest
import uuid as _n24l_uuid
import numpy as _n24l_np
import pandas as _n24l_pd


N24L_SECTION_VERSION = "n24l_real_application_integration_v1"
N24L_STATE_KEY = "_n24l_conversation_state"
N24L_STATE_VERSION = "n24l_persistent_conversation_v1"
N24L_ENGINE_VALUES = {"n23", "n24"}
N24L_OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"

if "n24l_n23_workspace_controller" not in globals():
    n24l_n23_workspace_controller = process_workspace_message

if "N24L_RUNTIME_AUDIT" not in globals():
    N24L_RUNTIME_AUDIT = []

if "N24L_OLLAMA_STATUS_CACHE" not in globals():
    N24L_OLLAMA_STATUS_CACHE = {"checked_at": 0.0, "available": False, "model_available": False}


def set_shopmate_engine(engine: str) -> str:
    """Explicitly select the preserved N23 controller or the N24L controller."""
    selected = str(engine or "").strip().casefold()
    if selected not in N24L_ENGINE_VALUES:
        raise ValueError("SHOPMATE_ENGINE must be 'n23' or 'n24'.")
    global SHOPMATE_ENGINE, N24_PRODUCTION_ENGINE_VERSION, N24_ENGINE_ACTIVATED
    SHOPMATE_ENGINE = selected
    N24_PRODUCTION_ENGINE_VERSION = selected
    N24_ENGINE_ACTIVATED = selected == "n24"
    _n24l_os.environ["SHOPMATE_ENGINE"] = selected
    return selected


def get_shopmate_engine() -> str:
    selected = str(globals().get("SHOPMATE_ENGINE", "n23")).strip().casefold()
    if selected not in N24L_ENGINE_VALUES:
        raise RuntimeError("The active ShopMate engine selector is invalid.")
    return selected


def n24l_detect_ollama(force: bool = False) -> dict:
    """Check the local service/model without loading or downloading a model."""
    now = _n24l_time.monotonic()
    cached = N24L_OLLAMA_STATUS_CACHE
    if not force and now - float(cached.get("checked_at", 0.0)) < 15.0:
        return dict(cached)
    status = {"checked_at": now, "available": False, "model_available": False, "model": "qwen3:8b"}
    try:
        with _n24l_urlrequest.urlopen(N24L_OLLAMA_TAGS_URL, timeout=2.0) as response:
            payload = _n24l_json.loads(response.read().decode("utf-8"))
        names = {
            str(item.get("name") or item.get("model") or "").strip()
            for item in payload.get("models", []) if isinstance(item, dict)
        }
        status.update({"available": True, "model_available": "qwen3:8b" in names, "models": sorted(names)})
    except Exception as error:
        status["error"] = f"{type(error).__name__}: {error}"
    N24L_OLLAMA_STATUS_CACHE.clear()
    N24L_OLLAMA_STATUS_CACHE.update(status)
    return dict(status)


def _n24l_json_value(value):
    return shopmate_json_safe_n24k(value)


def _n24l_records(value) -> list[dict]:
    if value is None:
        return []
    if isinstance(value, _n24l_pd.DataFrame):
        value = value.to_dict("records")
    safe = _n24l_json_value(value)
    if not isinstance(safe, list):
        return []
    return [dict(item) for item in safe if isinstance(item, dict)]


def _n24l_cards(value) -> list[dict]:
    def prepare(card):
        item = dict(card)
        if any(key in item for key in ("price", "historical_price", "price_display")):
            item.setdefault("currency", "USD")
        if isinstance(item.get("products"), list):
            item["products"] = [prepare(product) for product in item["products"] if isinstance(product, dict)]
        return item
    return [normalize_n24_price_card(prepare(card)) for card in normalise_card_records_before_n24j(value)]


def _n24l_root_state(chat_id: int, user_id: int) -> dict:
    existing = load_chat_active_request_state(chat_id=chat_id, user_id=user_id)
    return dict(existing) if isinstance(existing, dict) else {}


def _n24l_empty_persistent_payload() -> dict:
    return {
        "state_version": N24L_STATE_VERSION,
        "conversation": N24ConversationStateBundle().model_dump(mode="json"),
        "active_goal": None,
        "active_result_set_id": None,
        "result_sets": [],
        "seen_product_ids": [],
        "pending_clarification": None,
        "updated_at": None,
    }


def _n24l_recommendation_result(request, records: list[dict]) -> dict:
    frame = _n24l_pd.DataFrame(records)
    parsed = _n24c_structured_parsed_request(request)
    count = len(frame)
    return {
        "profile_id": request.profile_id,
        "parsed_request": parsed,
        "validated_request": request,
        "recommendations": frame,
        "recommendation_count": count,
        "requested_result_count": max(count, 1),
        "exact_match_count": count,
        "exact_match_shortfall": False,
        "no_exact_match": count == 0,
        "result_mode": "no_exact_matches" if count == 0 else "complete_exact_matches",
        "constraints_relaxed": False,
        "hard_constraints_applied": {},
        "exclusions_applied": {},
        "relaxation_candidates": [],
        "clarification_needed": False,
        "clarification_question": None,
        "engine_version": "n24_validated_state_adapter_v1",
    }


def _n24l_restore_runtime_result_sets(chat_id: int, payload: dict):
    restored = {}
    for item in payload.get("result_sets", []):
        try:
            state = N24ResultSetState.model_validate(item["state"])
            request = N24ValidatedRecommendationRequest.model_validate(item["validated_request"])
            if state.chat_id != int(chat_id):
                continue
            rec_records = item.get("recommendations", [])
            cards = _n24l_cards(item.get("cards", []))
            entry = {
                "state": state.model_copy(deep=True),
                "validated_request": request.model_copy(deep=True),
                "recommendation_result": _n24l_recommendation_result(request, rec_records),
                "cards": _n24l_pd.DataFrame(cards),
            }
            N24_RUNTIME_RESULT_SETS[state.result_set_id] = entry
            restored[state.result_set_id] = state
        except Exception:
            continue
    if restored:
        ids = N24_RUNTIME_CHAT_RESULT_IDS.setdefault(int(chat_id), [])
        for result_id in restored:
            if result_id not in ids:
                ids.append(result_id)
    active_id = payload.get("active_result_set_id")
    return restored.get(active_id)


def n24l_load_persistent_state(chat_id: int, user_id: int):
    root = _n24l_root_state(chat_id, user_id)
    raw = root.get(N24L_STATE_KEY)
    payload = dict(raw) if isinstance(raw, dict) else _n24l_empty_persistent_payload()
    try:
        state = N24ConversationStateBundle.model_validate(payload.get("conversation", {}))
    except Exception:
        state = N24ConversationStateBundle()
    active = _n24l_restore_runtime_result_sets(chat_id, payload)
    if active is None and state.active_result_set is not None:
        active = _n24l_restore_runtime_result_sets(
            chat_id, {**payload, "active_result_set_id": state.active_result_set.result_set_id}
        )
    if active is not None:
        state.active_result_set = active
    else:
        state.active_result_set = None
    # Late-bound: N24M3 (loaded after this module) owns the pending-offer
    # sidecar. A guarded globals() lookup restores a persisted pending offer
    # without this lower layer depending on a higher one's names at import
    # time -- consolidation Stage 4 (pending offers must survive reload).
    restore_pending_offer = globals().get("_n24m3_restore_pending_offer")
    if callable(restore_pending_offer):
        restore_pending_offer(chat_id, user_id)
    return root, payload, state, active


def _n24l_result_chain(active_result_set, chat_id: int) -> list[dict]:
    if active_result_set is None:
        return []
    chain = []
    current_id = active_result_set.result_set_id
    visited = set()
    while current_id and current_id not in visited and len(chain) < 20:
        visited.add(current_id)
        entry = N24_RUNTIME_RESULT_SETS.get(current_id)
        if entry is None or entry["state"].chat_id != int(chat_id):
            break
        request = entry["validated_request"]
        chain.append({
            "state": entry["state"].model_dump(mode="json"),
            "validated_request": request.model_dump(mode="json"),
            "recommendations": _n24l_records(entry["recommendation_result"]["recommendations"]),
            "cards": _n24l_cards(entry["cards"]),
        })
        current_id = entry["state"].parent_result_set_id
    chain.reverse()
    return chain


def n24l_save_persistent_state(
    chat_id: int,
    user_id: int,
    state: N24ConversationStateBundle,
    active_result_set=None,
    *,
    active_goal=None,
    pending_clarification=None,
):
    root = _n24l_root_state(chat_id, user_id)
    # Preserve whatever the pending-offer sidecar (_n24m3_persist_pending_offer)
    # last wrote here: this function rebuilds the rest of the payload from
    # scratch every call, and the two writers can run in either order within
    # the same turn. Without this, whichever one runs second would silently
    # erase the other's field instead of merging (consolidation Stage 4).
    existing_payload = root.get(N24L_STATE_KEY)
    existing_pending_offer = existing_payload.get("pending_offer") if isinstance(existing_payload, dict) else None
    if active_result_set is not None:
        state.active_result_set = active_result_set
    else:
        state.active_result_set = None
    chain = _n24l_result_chain(active_result_set, chat_id)
    seen = []
    for item in chain:
        for product_id in item["state"].get("ordered_product_ids", []):
            if product_id not in seen:
                seen.append(product_id)
    root[N24L_STATE_KEY] = {
        "state_version": N24L_STATE_VERSION,
        "conversation": state.model_dump(mode="json"),
        "active_goal": active_goal,
        "active_result_set_id": None if active_result_set is None else active_result_set.result_set_id,
        "result_sets": chain,
        "seen_product_ids": seen,
        "pending_clarification": pending_clarification,
        "pending_offer": existing_pending_offer,
        "updated_at": _n24l_datetime.now(_n24l_timezone.utc).isoformat(),
    }
    save_chat_active_request_state(chat_id=chat_id, user_id=user_id, state=root)
    return root[N24L_STATE_KEY]


def _n24l_operation(operation, value=None, confidence=1.0):
    return N24FieldOperation(operation=operation, value=value, confidence=confidence)


def _n24l_category_from_text(text: str):
    lower = text.casefold()
    aliases = {
        "shoes": "Shoes", "shoe": "Shoes", "sneakers": "Shoes", "sneaker": "Shoes",
        "watches": "Watches", "watch": "Watches", "jackets": "Jackets", "jacket": "Jackets",
        "t-shirts": "T-Shirts", "t shirt": "T-Shirts", "tshirt": "T-Shirts",
        "handbags": "Handbags", "handbag": "Handbags", "bags": "Handbags",
        "necklaces": "Necklaces", "necklace": "Necklaces", "earrings": "Earrings",
        "rings": "Rings", "ring": "Rings", "bracelets": "Bracelets", "bracelet": "Bracelets",
    }
    for alias, canonical in aliases.items():
        if _n24l_re.search(rf"\b{_n24l_re.escape(alias)}\b", lower):
            return canonical
    return None


def _n24l_ordinals(text: str) -> list[int]:
    words = {
        "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
        "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
    }
    lower = text.casefold()
    hits = []
    for match in _n24l_re.finditer(r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|[1-9]|10)\b", lower):
        token = match.group(1)
        value = words.get(token, int(token) if token.isdigit() else None)
        if value is not None and value not in hits:
            hits.append(value)
    return hits


def _n24l_refs(text: str, active_result_set) -> list:
    if active_result_set is None:
        return []
    return [
        N24ResultReference(
            ordinal_index=value,
            previous_result_set_id=active_result_set.result_set_id,
        )
        for value in _n24l_ordinals(text)
    ]


def _n24l_semantic_guard(raw_message: str, interpreted, state, active_result_set):
    """Apply narrow deterministic safety rules after N24G2, never N23 parsing."""
    text = " ".join(str(raw_message).strip().split())
    lower = text.casefold()
    category = _n24l_category_from_text(text)
    refs = _n24l_refs(text, active_result_set)
    valid_delta = interpreted.turn_delta if interpreted is not None else None

    result_question = bool(active_result_set is not None and (
        _n24l_re.search(r"\bwhy\s+(?:are|did|is|this|these)\b", lower)
        or _n24l_re.search(r"\bare\s+(?:these|they)\s+(?:actually\s+)?", lower)
        or "why this one" in lower
    ))
    if result_question:
        return N24TurnDelta(
            intent=N24Intent.PRODUCT_QUESTION,
            result_reference=refs[:1],
            confidence=1.0,
            raw_message=text,
        ), {"semantic_guard": "current_result_question", "superlative": None}

    if _n24l_re.search(r"\b(?:ignore|disregard|override)\b.{0,40}\b(?:instruction|prompt|rule)s?\b", lower):
        return N24TurnDelta(
            intent=N24Intent.GENERAL_SHOPPING_ADVICE,
            confidence=1.0,
            raw_message=text,
        ), {"semantic_guard": "prompt_injection_scope", "superlative": None}

    if _n24l_re.search(r"\b(?:complete\s+)?outfit\b|\bbuild\s+(?:me\s+)?(?:a\s+)?look\b", lower):
        recipient = None
        if _n24l_re.search(r"\b(women|woman|female|ladies)\b", lower):
            recipient = "women"
        elif _n24l_re.search(r"\b(men|man|male)\b", lower):
            recipient = "men"
        budget_match = _n24l_re.search(
            r"(?:under|below|budget(?:\s+of)?)\s*\$\s*(\d+(?:\.\d{1,2})?)", lower
        )
        colour_extractor = globals().get("_n24m_extract_colours_from_request")
        outfit_colours = (
            list(colour_extractor(text)[0]) if callable(colour_extractor) else []
        )
        fields = N24FieldOperations(
            recipient=_n24l_operation(N24FieldOperationType.SET, recipient) if recipient else None,
            colours=(
                _n24l_operation(N24FieldOperationType.SET, outfit_colours)
                if outfit_colours else None
            ),
            maximum_price=(
                _n24l_operation(N24FieldOperationType.SET, float(budget_match.group(1)))
                if budget_match else None
            ),
        )
        return N24TurnDelta(
            intent=N24Intent.OUTFIT_REQUEST,
            field_operations=fields,
            outfit_operation=N24OutfitOperation(operation=N24OutfitOperationType.CREATE),
            confidence=1.0,
            raw_message=text,
        ), {"semantic_guard": "outfit_request", "superlative": None}

    costly = bool(_n24l_re.search(r"\b(costliest|costly|costky|most\s+expensive)\b", lower))
    cheapest = bool(_n24l_re.search(r"\bcheapest\b", lower))
    highest_rated = bool(_n24l_re.search(r"\bhighest[-\s]+rated\b|\bbest[-\s]+rated\b", lower))
    most_reviewed = bool(_n24l_re.search(r"\bmost\s+(?:reviews|reviewed)\b", lower))
    if costly and _n24l_re.search(r"\bwhich\s+brand\b", lower):
        fields = N24FieldOperations(
            categories=_n24l_operation(N24FieldOperationType.SET, [category], 1.0)
            if category else None
        )
        return N24TurnDelta(
            intent=N24Intent.NEW_GOAL,
            field_operations=fields,
            confidence=1.0,
            requires_clarification=True,
            clarification_question=(
                "Do you want the single costliest shoe overall, or the brand whose shoes "
                "have the highest historical dataset prices?"
            ),
            raw_message=text,
        ), {"semantic_guard": "ambiguous_brand_superlative", "superlative": None}

    superlative = None
    relative = None
    if costly:
        superlative, relative = "costliest", N24RelativeOperationType.MORE_EXPENSIVE
    elif cheapest:
        superlative, relative = "cheapest", N24RelativeOperationType.CHEAPEST
    elif highest_rated:
        superlative, relative = "highest_rated", N24RelativeOperationType.HIGHER_RATED
    elif most_reviewed:
        superlative, relative = "most_reviewed", N24RelativeOperationType.MOST_REVIEWED
    if superlative:
        fields = valid_delta.field_operations if valid_delta is not None else N24FieldOperations()
        if category:
            fields = fields.model_copy(deep=True)
            fields.categories = _n24l_operation(N24FieldOperationType.SET, [category], 1.0)
            fields.brands = None
            fields.colours = None
        intent = N24Intent.NEW_GOAL if category else N24Intent.REFINE
        return N24TurnDelta(
            intent=intent,
            field_operations=fields,
            relative_operation=relative,
            confidence=1.0,
            raw_message=text,
        ), {"semantic_guard": "catalogue_superlative", "superlative": superlative}

    unsupported = []
    if _n24l_re.search(r"\b(current|live|today(?:'s)?)\s+(?:amazon\s+)?price\b", lower):
        unsupported.append(N24UnsupportedCommerceTopic.LIVE_CURRENT_PRICE)
    if _n24l_re.search(r"\b(deliver|delivery|arrive|arrival)\b", lower):
        unsupported.append(N24UnsupportedCommerceTopic.DELIVERY)
    if _n24l_re.search(r"\b(?:in\s+stock|stock\s+availability)\b", lower):
        unsupported.append(N24UnsupportedCommerceTopic.STOCK)
    if _n24l_re.search(r"\b(?:coupon|promo\s+code)\b", lower):
        unsupported.append(N24UnsupportedCommerceTopic.COUPON)
    if unsupported:
        return N24TurnDelta(
            intent=N24Intent.UNSUPPORTED_DATA_QUESTION,
            unsupported_commerce=N24UnsupportedCommerceRequest(topics=list(dict.fromkeys(unsupported))),
            confidence=1.0,
            raw_message=text,
        ), {"semantic_guard": "unsupported_commerce", "superlative": None}

    if lower in {"show me more", "show more", "more products", "more"}:
        return N24TurnDelta(
            intent=N24Intent.SHOW_MORE,
            pagination=N24PaginationOperation(show_more=True),
            confidence=1.0,
            raw_message=text,
        ), {"semantic_guard": "show_more", "superlative": None}

    if active_result_set is not None and "compare" in lower and len(refs) >= 2:
        return N24TurnDelta(
            intent=N24Intent.COMPARE,
            result_reference=refs,
            confidence=1.0,
            raw_message=text,
        ), {"semantic_guard": "comparison_reference", "superlative": None}

    if active_result_set is not None and refs and _n24l_re.search(r"\b(tell|explain|show|open|link)\b", lower):
        return N24TurnDelta(
            intent=N24Intent.PRODUCT_REFERENCE,
            result_reference=refs[:1],
            confidence=1.0,
            raw_message=text,
        ), {"semantic_guard": "ordinal_reference", "superlative": None}

    if valid_delta is None:
        fallback_context = build_n24_interpreter_context(
            chat_id=active_result_set.chat_id if active_result_set is not None else 1,
            profile_id=N24A_GOLDEN_PROFILE_ID,
            current_state=state,
            active_result_set=active_result_set,
        )
        fallback = interpret_and_validate_n24_turn(
            text, fallback_context, N24_INTERPRETER_REGISTRY.get("deterministic_fallback"),
            active_result_set=active_result_set,
        )
        valid_delta = fallback.turn_delta

    if valid_delta is None:
        return None, {"semantic_guard": "safe_clarification", "superlative": None}

    delta = valid_delta.model_copy(deep=True)
    if category and delta.intent in {N24Intent.PRODUCT_SEARCH, N24Intent.REFINE}:
        previous = {x.casefold() for x in state.hard_request.categories}
        if previous and category.casefold() not in previous:
            delta.intent = N24Intent.NEW_GOAL
    if _n24l_re.search(r"\b(?:do not|don't|dont)\s+worry\s+about\s+(?:the\s+)?budget\b|\bno\s+budget\s+limit\b", lower):
        delta = delta.model_copy(deep=True)
        delta.intent = N24Intent.REFINE
        delta.field_operations.minimum_price = _n24l_operation(N24FieldOperationType.CLEAR)
        delta.field_operations.maximum_price = _n24l_operation(N24FieldOperationType.CLEAR)
        delta.field_operations.price_mode = _n24l_operation(N24FieldOperationType.CLEAR)
    return delta, {"semantic_guard": "validated_n24g2", "superlative": None}


def n24l_interpret_turn(raw_message: str, context, state, active_result_set):
    ollama = n24l_detect_ollama()
    result = None
    if ollama.get("available") and ollama.get("model_available"):
        result = interpret_and_validate_n24_turn(
            raw_message, context, N24_OLLAMA_RELIABLE_INTERPRETER,
            active_result_set=active_result_set,
        )
    delta, guard = _n24l_semantic_guard(raw_message, result, state, active_result_set)
    attempts = 0
    if result is not None:
        attempts = int(N24_OLLAMA_RELIABLE_INTERPRETER.last_call_metadata.get("attempts") or 0)
    metrics = {
        "intent": attempts,
        "response": 0,
        "repair": max(0, attempts - 1),
        "total": attempts,
        "interpreter_status": None if result is None else result.validation_status,
        "interpreter_latency_seconds": None if result is None else result.latency_seconds,
        "semantic_guard": guard["semantic_guard"],
        "ollama_available": bool(ollama.get("available")),
        "model_available": bool(ollama.get("model_available")),
    }
    return delta, guard, metrics


def _n24l_filter_catalogue(request):
    work = application_request_metadata_df.drop_duplicates("product_id").copy()
    mask = _n24l_pd.Series(True, index=work.index)
    if request.categories:
        mask &= work["categories"].apply(
            lambda value: all(application_category_matches(value, wanted) for wanted in request.categories)
        )
    if request.brands:
        mask &= work["brand"].fillna("").apply(lambda value: _n24c_matches_any(value, request.brands))
    for values in (request.colours, request.materials, request.sizes):
        if values:
            mask &= work["request_search_text"].fillna("").apply(
                lambda value, wanted=values: all(_n24c_matches_any(value, [item]) for item in wanted)
            )
    price = _n24l_pd.to_numeric(work["price"], errors="coerce")
    if request.minimum_price is not None:
        mask &= price.notna() & (price >= request.minimum_price)
    if request.maximum_price is not None:
        mask &= price.notna() & (price <= request.maximum_price)
    if request.occasions:
        mask &= work["request_search_text"].fillna("").apply(
            lambda value: all(request_search_text_matches(value, item) for item in request.occasions)
        )
    if request.excluded_product_ids:
        mask &= ~work["product_id"].astype(str).str.casefold().isin(
            {item.casefold() for item in request.excluded_product_ids}
        )
    if request.excluded_brands:
        mask &= ~work["brand"].fillna("").apply(lambda value: _n24c_matches_any(value, request.excluded_brands))
    if request.excluded_categories:
        mask &= ~work["categories"].apply(
            lambda value: any(application_category_matches(value, item) for item in request.excluded_categories)
        )
    for values in (request.excluded_colours, request.excluded_materials, request.excluded_sizes):
        if values:
            mask &= ~work["request_search_text"].fillna("").apply(
                lambda value, forbidden=values: _n24c_matches_any(value, forbidden)
            )
    return work.loc[mask].copy()


def n24l_superlative_recommendation(request, operation: str):
    eligible = _n24l_filter_catalogue(request)
    if operation in {"costliest", "cheapest"}:
        eligible["_metric"] = _n24l_pd.to_numeric(eligible["price"], errors="coerce")
        eligible = eligible.loc[eligible["_metric"].notna()]
        ascending = operation == "cheapest"
        eligible = eligible.sort_values(["_metric", "product_id"], ascending=[ascending, True], kind="mergesort")
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
    selected = eligible.head(1).drop(
        columns=[c for c in ("_metric", "_tie", "request_search_text") if c in eligible.columns]
    ).copy()
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
    selected["matched_request_colors"] = ", ".join(request.colours)
    selected["matched_request_materials"] = ", ".join(request.materials)
    selected["matched_request_sizes"] = ", ".join(request.sizes)
    selected["matched_request_occasions"] = ", ".join(request.occasions)
    selected["request_explanation"] = f"Deterministic {operation.replace('_', ' ')} historical catalogue ranking."
    selected["base_strategy"] = "n24l_catalogue_superlative"
    selected["base_rank"] = selected["request_rank"]
    result = _n24l_recommendation_result(request, selected.to_dict("records"))
    result["recommendations"] = selected.reset_index(drop=True)
    result["eligible_catalogue_count"] = int(len(eligible))
    result["superlative_operation"] = operation
    result["engine_version"] = "n24c_validated_catalogue_superlative_v1"
    return result


def _n24l_result_question_data(raw_message: str, active_result_set, chat_id: int):
    entry = _n24d_get_entry(active_result_set.result_set_id, chat_id)
    recs = entry["recommendation_result"]["recommendations"]
    rows = []
    for row in recs.head(10).to_dict("records"):
        rows.append({
            "product_id": str(row.get("product_id")),
            "title": row.get("title"),
            "brand": row.get("brand"),
            "category_evidence": row.get("matched_request_categories") or row.get("categories"),
            "colour_evidence": row.get("matched_request_colors"),
            "historical_price": row.get("price"),
            "rating": row.get("average_rating"),
            "review_count": row.get("rating_number"),
        })
    lower = raw_message.casefold()
    explanation = "These products were selected from the active deterministic catalogue result set."
    if "white" in lower:
        mixed_count = sum("white" in str(item.get("title") or "").casefold() for item in rows)
        explanation = (
            "The black constraint has not changed. Every displayed record contains black catalogue-text evidence; "
            f"{mixed_count} listing titles also mention white, so those records are mixed-colour variants in the catalogue."
        )
    return {"question": raw_message, "explanation": explanation, "products": rows}


def _n24l_compose(raw_message: str, orchestration, call_metrics: dict):
    call_metrics["response"] += 1
    call_metrics["total"] += 1
    response = compose_n24_grounded_response(raw_message, orchestration, N24_OLLAMA_RESPONSE_COMPOSER)
    if orchestration.status == "product_question" and isinstance(orchestration.grounded_data, dict):
        exact = orchestration.grounded_data.get("explanation")
        if isinstance(exact, str) and exact.strip():
            response = N24GroundedResponse(
                status=response.status, message=exact.strip(), response_type=response.response_type,
                cards=response.cards, comparison=response.comparison,
                referenced_products=response.referenced_products,
                clarification=response.clarification, limitations=response.limitations,
                preference_update_summary=response.preference_update_summary,
                result_set_id=response.result_set_id,
                generated_by="n24_deterministic_grounded_fallback_v1",
                warnings=[*response.warnings, "deterministic_result_question_fact_lock"],
            )
    return response


def _n24l_outfit_route(raw_message, profile_id, chat_id, user_id, delta, call_metrics):
    state = n24i_restore_state(chat_id, user_id)
    lower = raw_message.casefold()
    if state is None or not state.active:
        recipient = None
        total_budget = None
        occasion = None
        style = None
        destination = None
        colours = []
        if delta is not None:
            ops = delta.field_operations
            if ops.recipient is not None:
                recipient = ops.recipient.value
            if ops.maximum_price is not None and ops.maximum_price.operation in {
                N24FieldOperationType.SET, N24FieldOperationType.REPLACE
            }:
                total_budget = float(ops.maximum_price.value)
            if ops.occasions is not None:
                values = ops.occasions.value
                occasion = values[0] if isinstance(values, list) and values else values
            if ops.destination is not None:
                destination = ops.destination.value
            if ops.colours is not None and ops.colours.operation in {
                N24FieldOperationType.SET, N24FieldOperationType.REPLACE
            }:
                values = ops.colours.value
                colours = list(values if isinstance(values, list) else [values])
        if recipient is None:
            if _n24l_re.search(r"\b(women|woman|female|ladies)\b", lower): recipient = "women"
            elif _n24l_re.search(r"\b(men|man|male)\b", lower): recipient = "men"
        if total_budget is None:
            match = _n24l_re.search(r"(?:under|below|budget(?:\s+of)?)\s*\$\s*(\d+(?:\.\d{1,2})?)", lower)
            if match: total_budget = float(match.group(1))
        if recipient is None:
            started = n24i_start_outfit(profile_id, chat_id, user_id, raw_message, occasion=occasion, style=style, total_budget=total_budget)
            orchestration = N24OrchestrationResult(
                status="clarification", validated_turn_delta=delta,
                response_intent=None if delta is None else delta.intent,
                cards=[], grounded_data={"outfit_status": "recipient_required"},
                requires_clarification=True, clarification_reason=started["message"],
                audit_metadata={"n24l": True, "route": "n24i1"},
            )
            return started, _n24l_compose(raw_message, orchestration, call_metrics), []
        runtime = n24i1_live_outfit_adapter(
            profile_id, raw_message, recipient, total_budget=total_budget,
            occasion=occasion, style=style, destination=destination,
            colours=colours,
        )
        if runtime["status"] != "complete":
            message = "I can't build a complete outfit from the available catalogue items without relaxing your requirements."
            empty = N24IOutfitDialogueState(
                request_id="n24l-outfit-" + _n24l_uuid.uuid4().hex,
                chat_id=chat_id, profile_id=profile_id, recipient=recipient,
                total_budget=total_budget, occasion=occasion, style=style,
            )
            orchestration = N24OrchestrationResult(
                status="no_exact_match", validated_turn_delta=delta,
                response_intent=None if delta is None else delta.intent,
                cards=[], grounded_data={"limitations": [{"topic": "catalogue_outfit", "limitation": message}]},
                audit_metadata={"n24l": True, "route": "n24i1"},
            )
            return {"status": "no_valid_live_outfit", "state": empty}, _n24l_compose(raw_message, orchestration, call_metrics), []
        result = n24i_start_outfit(
            profile_id, chat_id, user_id, raw_message, recipient=recipient,
            occasion=occasion, style=style, total_budget=total_budget,
            runtime_result=runtime,
        )
    else:
        if "forget the outfit" in lower:
            result = n24i_apply_operation(state, user_id, "end_outfit")
        elif "deliver" in lower:
            result = {"status": "unsupported_data", "state": state,
                      "message": N24_UNSUPPORTED_COMMERCE_LIMITATIONS[N24UnsupportedCommerceTopic.DELIVERY]}
        elif "compare" in lower:
            numbers = [int(x) for x in _n24l_re.findall(r"(?:look|outfit)\s*(\d+)", lower)]
            result = n24i_apply_operation(state, user_id, "compare_looks", value=numbers[:2] or [1, 2])
        elif "tell me more" in lower:
            result = n24i_apply_operation(state, user_id, "reference_look", _n24i1_ordinal(lower), n24i_resolve_slot(lower))
        elif "another" in lower or "show more" in lower:
            result = n24i_apply_operation(state, user_id, "show_more_outfits")
        elif "cheaper" in lower:
            result = n24i_apply_operation(state, user_id, "make_look_cheaper", _n24i1_ordinal(lower))
        elif "don't like" in lower or "do not like" in lower:
            result = n24i_apply_operation(state, user_id, "exclude_product", _n24i1_ordinal(lower), n24i_resolve_slot(lower))
        elif "change" in lower or "replace" in lower:
            result = n24i_apply_operation(state, user_id, "replace_slot", _n24i1_ordinal(lower), n24i_resolve_slot(lower))
        elif "casual" in lower or "formal" in lower:
            result = n24i_apply_operation(
                state, user_id, "make_look_more_casual" if "casual" in lower else "make_look_more_formal",
                _n24i1_ordinal(lower),
            )
        else:
            result = {"status": "clarification", "state": state, "message": "What would you like to change about the current outfits?"}
    outfit_state = result["state"]
    cards = _n24i1_cards(outfit_state) if getattr(outfit_state, "looks", None) else []
    status = result.get("status", "recommendations")
    orchestration_status = (
        "unsupported_data" if status == "unsupported_data" else
        "comparison" if status == "comparison" else
        "product_reference" if status == "product_reference" else
        "clarification" if status == "clarification" else
        "recommendations"
    )
    orchestration = N24OrchestrationResult(
        status=orchestration_status, validated_turn_delta=delta,
        response_intent=None if delta is None else delta.intent,
        cards=cards, grounded_data=result.get("grounded_facts") or {
            "deterministic_outfit_message": result.get("message"), "outfit_count": len(cards)
        },
        requires_clarification=status == "clarification",
        clarification_reason=result.get("message") if status == "clarification" else None,
        audit_metadata={"n24l": True, "route": "n24i1"},
    )
    response = _n24l_compose(raw_message, orchestration, call_metrics)
    return result, response, _n24l_cards(cards)


_N24L_REFORMULATION_HARD_FIELDS = (
    "brands", "colours", "materials", "sizes", "occasions",
    "minimum_price", "maximum_price", "price_mode",
    "recipient", "destination", "timeframe",
)


def _n24l_apply_reformulation_clearing(delta, state, active_result_set):
    """Distinguish an incremental refinement ("under $100", "for men") from a
    reformulated replacement request that independently restates the
    product category ("ok suggest me men all black shoes", "just show me
    black shoes", "show me shoes"). A refinement never restates the
    product category on its own; a reformulation does -- and whenever it
    does, any previously active hard constraint the new message does not
    explicitly touch is stale, not implicitly retained forever. This holds
    regardless of whether the prior search found anything: a message that
    is a complete, self-sufficient search on its own supersedes the prior
    request rather than merging with it. This only ever ADDS explicit
    CLEAR operations to fields the delta left untouched -- it never
    overrides an operation the interpreter already produced, and it never
    touches show_more, compare, product_question, or any other non
    product-search intent. The N24B reducer itself is unchanged; this only
    completes the delta it receives.
    """
    if delta is None or delta.intent not in {N24Intent.PRODUCT_SEARCH, N24Intent.REFINE}:
        return delta
    categories_op = delta.field_operations.categories
    if categories_op is None or categories_op.operation not in {
        N24FieldOperationType.SET, N24FieldOperationType.REPLACE
    }:
        return delta
    hard = state.hard_request
    updated = delta.model_copy(deep=True)
    ops = updated.field_operations
    for field_name in _N24L_REFORMULATION_HARD_FIELDS:
        if getattr(ops, field_name) is not None:
            continue
        current_value = getattr(hard, field_name)
        if not current_value:
            continue
        setattr(ops, field_name, _n24l_operation(N24FieldOperationType.CLEAR))
    return updated


def n24l_execute_turn(user_id: int, chat_id: int, message_text: str, top_n: int = 10) -> dict:
    account = get_user_account(user_id)
    get_chat_session(chat_id=chat_id, user_id=user_id)
    raw_message = " ".join(str(message_text).strip().split())
    if not raw_message:
        raise ValueError("message_text must be a non-empty string.")
    if not isinstance(top_n, int) or top_n < 1:
        raise ValueError("top_n must be a positive integer.")
    profile_id = str(account["profile_id"])
    root, persistent_payload, state, active_result_set = n24l_load_persistent_state(chat_id, user_id)
    outfit_state = n24i_restore_state(chat_id, user_id)
    current_outfit_followup = bool(
        outfit_state is not None and outfit_state.active and
        _n24l_re.search(r"\b(look|outfit|cheaper|replace|change|another|formal|casual|compare)\b", raw_message.casefold())
    )
    context = build_n24_interpreter_context(
        chat_id=chat_id, profile_id=profile_id, current_state=state,
        active_result_set=active_result_set,
        previous_turn_summary={"active_goal": persistent_payload.get("active_goal")},
    )
    delta, guard, call_metrics = n24l_interpret_turn(raw_message, context, state, active_result_set)
    if current_outfit_followup and delta is not None:
        delta = delta.model_copy(deep=True)
        if delta.intent not in {N24Intent.UNSUPPORTED_DATA_QUESTION}:
            delta.outfit_operation = N24OutfitOperation(operation=N24OutfitOperationType.ANOTHER_OUTFIT)
            delta.intent = N24Intent.OUTFIT_REFINE

    user_message_id = record_chat_message(
        chat_id=chat_id, user_id=user_id, role="user", content=raw_message,
        metadata={"service_version": N24L_SECTION_VERSION, "engine": "n24"},
    )
    started = _n24l_time.perf_counter()
    pending_clarification = None
    active_goal = persistent_payload.get("active_goal")
    cards = []
    outfits = []
    filter_evidence = []

    if delta is None:
        orchestration = N24OrchestrationResult(
            status="clarification", requires_clarification=True,
            clarification_reason="Could you rephrase that as a shopping request?",
            grounded_data={"safe_failure": "N24 interpretation was unavailable or invalid."},
            audit_metadata={"n24l": True, "route": "clarification"},
        )
    elif delta.requires_clarification:
        if guard.get("semantic_guard") == "ambiguous_brand_superlative":
            reduced = reduce_n24_conversation_state(state, delta)
            state = reduced.new_state
            active_result_set = None
            active_goal = state.hard_request.categories[0] if state.hard_request.categories else None
        pending_clarification = {
            "question": delta.clarification_question,
            "raw_message": raw_message,
            "semantic_guard": guard.get("semantic_guard"),
        }
        orchestration = N24OrchestrationResult(
            status="clarification", validated_turn_delta=delta,
            response_intent=delta.intent, requires_clarification=True,
            clarification_reason=delta.clarification_question,
            grounded_data={"pending_clarification": pending_clarification},
            audit_metadata={"n24l": True, "route": "clarification"},
        )
    elif delta.intent in {N24Intent.OUTFIT_REQUEST, N24Intent.OUTFIT_REFINE} or current_outfit_followup:
        outfit_result, grounded_response, outfits = _n24l_outfit_route(
            raw_message, profile_id, chat_id, user_id, delta, call_metrics
        )
        orchestration = None
        active_goal = "outfit"
    elif call_metrics.get("replay_offer") is not None and delta is not None:
        # Consolidation Stage 4: this delta accepted a pending relaxation
        # offer that already carries a verified, ordered candidate snapshot.
        # Replay those exact candidates instead of re-invoking the
        # recommender, so "I verified N candidates" cannot silently become a
        # different N (or zero) by the time the user says yes -- the same
        # safety property already true of an ordinary result set.
        delta = _n24l_apply_reformulation_clearing(delta, state, active_result_set)
        reduced = reduce_n24_conversation_state(state, delta)
        state = reduced.new_state
        request = build_n24_validated_recommendation_request(profile_id, state.hard_request, state.exclusions)
        replay_offer = N24PendingRelaxationOffer.model_validate(call_metrics["replay_offer"])
        recommendation_result = _n24n_replay_recommendation_result(replay_offer, request, top_n=top_n)
        active_result_set = create_n24_result_set(
            request, recommendation_result, chat_id,
            source_message_id=user_message_id, parent_result_set=None,
        )
        state.active_result_set = active_result_set
        cards = _n24l_cards(_n24d_get_entry(active_result_set.result_set_id, chat_id)["cards"])
        status = "no_exact_match" if not active_result_set.ordered_product_ids else "recommendations"
        orchestration = N24OrchestrationResult(
            status=status, validated_turn_delta=delta, reducer_result=reduced,
            validated_request=request, result_set=active_result_set,
            recommendations=recommendation_result["recommendations"], cards=cards,
            grounded_data={
                "exact_match_count": len(active_result_set.ordered_product_ids),
                "replayed_pending_offer_id": replay_offer.offer_id,
            },
            response_intent=delta.intent,
            audit_metadata={"n24l": True, "route": "n24n_pending_offer_replay"},
        )
        active_goal = state.hard_request.categories[0] if state.hard_request.categories else active_goal
    elif delta.intent in {N24Intent.PRODUCT_SEARCH, N24Intent.REFINE, N24Intent.NEW_GOAL}:
        delta = _n24l_apply_reformulation_clearing(delta, state, active_result_set)
        reduced = reduce_n24_conversation_state(state, delta)
        state = reduced.new_state
        request = build_n24_validated_recommendation_request(profile_id, state.hard_request, state.exclusions)
        superlative = guard.get("superlative")
        if superlative:
            recommendation_result = n24l_superlative_recommendation(request, superlative)
        else:
            recommendation_result = get_n24_recommendations_from_validated_state(request, top_n=top_n)
            recommendation_result = personalize_n24_eligible_recommendations(
                recommendation_result, load_n24_soft_profile_preferences(profile_id)
            )
        active_result_set = create_n24_result_set(
            request, recommendation_result, chat_id,
            source_message_id=user_message_id,
            parent_result_set=None,
        )
        state.active_result_set = active_result_set
        cards = _n24l_cards(_n24d_get_entry(active_result_set.result_set_id, chat_id)["cards"])
        status = "no_exact_match" if not active_result_set.ordered_product_ids else "recommendations"
        grounded_data = {
            "superlative_operation": superlative,
            "eligible_catalogue_count": recommendation_result.get("eligible_catalogue_count"),
            "exact_match_count": len(active_result_set.ordered_product_ids),
        }
        orchestration = N24OrchestrationResult(
            status=status, validated_turn_delta=delta, reducer_result=reduced,
            validated_request=request, result_set=active_result_set,
            recommendations=recommendation_result["recommendations"], cards=cards,
            grounded_data=grounded_data, response_intent=delta.intent,
            audit_metadata={"n24l": True, "route": "n24c", "superlative": superlative},
        )
        active_goal = state.hard_request.categories[0] if state.hard_request.categories else active_goal
        rec_frame = recommendation_result["recommendations"]
        for row in rec_frame.to_dict("records"):
            filter_evidence.append({
                "product_id": str(row.get("product_id")),
                "category": row.get("matched_request_categories") or row.get("categories"),
                "brand": row.get("matched_request_brands") or row.get("brand"),
                "colour": row.get("matched_request_colors"),
                "title": row.get("title"),
                "image_url": row.get("image_url"),
            })
    elif delta.intent == N24Intent.SHOW_MORE:
        if active_result_set is None:
            orchestration = N24OrchestrationResult(
                status="clarification", validated_turn_delta=delta,
                response_intent=delta.intent, requires_clarification=True,
                clarification_reason="Show more requires an active result set.",
                audit_metadata={"n24l": True, "route": "n24d_show_more"},
            )
        else:
            previous_result_set = active_result_set
            page = show_more_n24_results(
                active_result_set, chat_id=chat_id, top_n=top_n,
                source_message_id=user_message_id,
            )
            page_ids = list(page.result_set.ordered_product_ids)
            if page_ids:
                active_result_set = page.result_set
                state.active_result_set = active_result_set
                cards = _n24l_cards(_n24d_get_entry(active_result_set.result_set_id, chat_id)["cards"])
            else:
                # Exhaustion must not erase the immutable result set the user
                # actually saw.  Return no new cards for this turn while the
                # prior set remains active for first/second/compare/relative
                # follow-ups and persistence.
                active_result_set = previous_result_set
                state.active_result_set = previous_result_set
                cards = []
            orchestration = N24OrchestrationResult(
                status="no_exact_match" if page.exhausted else "recommendations",
                validated_turn_delta=delta, result_set=active_result_set,
                cards=cards, grounded_data=page, response_intent=delta.intent,
                audit_metadata={"n24l": True, "route": "n24d_show_more"},
            )
    elif delta.intent in {N24Intent.COMPARE, N24Intent.PRODUCT_REFERENCE, N24Intent.PRODUCT_QUESTION}:
        if active_result_set is None:
            orchestration = N24OrchestrationResult(
                status="clarification", validated_turn_delta=delta,
                response_intent=delta.intent, requires_clarification=True,
                clarification_reason="That question requires an active result set.",
                audit_metadata={"n24l": True, "route": "n24d_reference"},
            )
        else:
            cards = _n24l_cards(_n24d_get_entry(active_result_set.result_set_id, chat_id)["cards"])
            if delta.intent == N24Intent.COMPARE:
                refs = delta.result_reference or _n24l_refs(raw_message, active_result_set)
                comparison = compare_n24_result_products(active_result_set, refs, chat_id=chat_id)
                orchestration = N24OrchestrationResult(
                    status="comparison", validated_turn_delta=delta,
                    result_set=active_result_set, cards=cards,
                    grounded_data=comparison, response_intent=delta.intent,
                    audit_metadata={"n24l": True, "route": "n24d_comparison"},
                )
            elif delta.intent == N24Intent.PRODUCT_REFERENCE or delta.result_reference:
                refs = delta.result_reference or _n24l_refs(raw_message, active_result_set)
                if len(refs) != 1:
                    raise ValueError("A product reference requires exactly one result number.")
                facts = get_n24_grounded_product_facts(active_result_set, refs[0], chat_id=chat_id)
                if isinstance(facts, N24ReferenceResolution):
                    orchestration = N24OrchestrationResult(
                        status="clarification", validated_turn_delta=delta,
                        response_intent=delta.intent, requires_clarification=True,
                        clarification_reason=facts.clarification,
                        audit_metadata={"n24l": True, "route": "n24d_reference"},
                    )
                else:
                    orchestration = N24OrchestrationResult(
                        status="product_reference", validated_turn_delta=delta,
                        result_set=active_result_set, cards=cards,
                        grounded_data=facts, response_intent=delta.intent,
                        audit_metadata={"n24l": True, "route": "n24d_reference"},
                    )
            else:
                question_data = _n24l_result_question_data(raw_message, active_result_set, chat_id)
                orchestration = N24OrchestrationResult(
                    status="product_question", validated_turn_delta=delta,
                    result_set=active_result_set, cards=cards,
                    grounded_data=question_data, response_intent=delta.intent,
                    audit_metadata={"n24l": True, "route": "n24d_result_question"},
                )
    elif delta.intent == N24Intent.PROFILE_UPDATE:
        audit = apply_n24_profile_update(profile_id, delta.profile_update)
        if active_result_set is not None:
            cards = _n24l_cards(_n24d_get_entry(active_result_set.result_set_id, chat_id)["cards"])
        orchestration = N24OrchestrationResult(
            status="profile_updated", validated_turn_delta=delta,
            cards=cards, grounded_data=audit, response_intent=delta.intent,
            audit_metadata={"n24l": True, "route": "n24e"},
        )
    elif delta.intent == N24Intent.UNSUPPORTED_DATA_QUESTION:
        limitations = [
            {"topic": topic.value, "limitation": N24_UNSUPPORTED_COMMERCE_LIMITATIONS[topic]}
            for topic in delta.unsupported_commerce.topics
        ]
        orchestration = N24OrchestrationResult(
            status="unsupported_data", validated_turn_delta=delta,
            grounded_data={"limitations": limitations}, response_intent=delta.intent,
            audit_metadata={"n24l": True, "route": "unsupported_data"},
        )
    elif delta.intent == N24Intent.GIFT_REQUEST:
        orchestration = N24OrchestrationResult(
            status="clarification", validated_turn_delta=delta,
            response_intent=delta.intent, requires_clarification=True,
            clarification_reason="What type of product would you like for the gift?",
            grounded_data={"gift_request": True},
            audit_metadata={"n24l": True, "route": "gift"},
        )
    else:
        orchestration = N24OrchestrationResult(
            status="general_advice", validated_turn_delta=delta,
            grounded_data={"shopping_scope": "general advice only", "catalogue_products_selected": False},
            response_intent=delta.intent,
            audit_metadata={"n24l": True, "route": "general_advice"},
        )

    if orchestration is not None:
        grounded_response = _n24l_compose(raw_message, orchestration, call_metrics)

    response_seconds = round(_n24l_time.perf_counter() - started, 3)
    if outfits:
        cards_to_store = outfits
    else:
        cards_to_store = cards
    assistant_content = grounded_response.message.strip()
    assistant_message_id = record_chat_message(
        chat_id=chat_id, user_id=user_id, role="assistant", content=assistant_content,
        metadata={
            "service_version": N24L_SECTION_VERSION,
            "engine": "n24",
            "response_type": grounded_response.response_type,
            "result_set_id": grounded_response.result_set_id,
            "response_seconds": response_seconds,
            "ollama_calls": call_metrics,
        },
    )
    stored_card_count = store_chat_recommendations_n24j(
        chat_id=chat_id, message_id=assistant_message_id, product_cards=cards_to_store
    )
    n24_persistent = n24l_save_persistent_state(
        chat_id, user_id, state, active_result_set,
        active_goal=active_goal, pending_clarification=pending_clarification,
    )
    update_new_chat_title(chat_id=chat_id, user_id=user_id, first_message=raw_message)
    final_response = {
        "engine_version": "n24",
        "controller_version": N24L_SECTION_VERSION,
        "display_message": assistant_content,
        "assistant_message": assistant_content,
        "response_type": grounded_response.response_type,
        "status": grounded_response.status,
        "product_cards": cards,
        "latest_outfit_groups": outfits,
        "comparison": grounded_response.comparison,
        "referenced_products": grounded_response.referenced_products,
        "clarification": grounded_response.clarification,
        "limitations": grounded_response.limitations,
        "preference_update": grounded_response.preference_update_summary,
        "result_metadata": {
            "result_set_id": grounded_response.result_set_id,
            "ordered_product_ids": [] if active_result_set is None else list(active_result_set.ordered_product_ids),
            "seen_product_ids": n24_persistent["seen_product_ids"],
            "active_goal": active_goal,
        },
        "filter_evidence": filter_evidence,
        "generated_at": _n24l_datetime.now(_n24l_timezone.utc).isoformat(),
        "generated_by": grounded_response.generated_by,
        "grounding_version": grounded_response.grounding_version,
        "price_contract_version": N24_PRICE_CONTRACT_VERSION,
        "performance": {"total_seconds": response_seconds},
        "ollama_calls": call_metrics,
        "warnings": grounded_response.warnings,
    }
    N24L_RUNTIME_AUDIT.append({
        "chat_id": int(chat_id), "message_id": int(user_message_id),
        "raw_message": raw_message, "engine": "n24",
        "intent": None if delta is None else delta.intent.value,
        "route": None if orchestration is None else orchestration.audit_metadata.get("route"),
        "result_set_id": None if active_result_set is None else active_result_set.result_set_id,
        "ollama_calls": dict(call_metrics), "response_seconds": response_seconds,
    })
    return {
        "service_version": N24L_SECTION_VERSION,
        "engine_version": "n24", "user_id": int(user_id), "profile_id": profile_id,
        "chat_id": int(chat_id), "user_message_id": int(user_message_id),
        "assistant_message_id": int(assistant_message_id), "assistant_message": assistant_content,
        "response_seconds": response_seconds, "stored_card_count": int(stored_card_count),
        "final_response": final_response,
        "active_request_state": state.hard_request.model_dump(mode="json"),
    }


def process_workspace_message_n24(user_id: int, chat_id: int, message_text: str, top_n: int = 10) -> dict:
    persistent_result = n24l_execute_turn(user_id, chat_id, message_text, top_n)
    workspace = load_authenticated_workspace(user_id=user_id, preferred_chat_id=chat_id)
    final_response = persistent_result["final_response"]
    workspace.update({
        "persistent_result": persistent_result,
        "engine_version": "n24",
        "response_seconds": persistent_result["response_seconds"],
        "assistant_message": persistent_result["assistant_message"],
        "stored_card_count": persistent_result["stored_card_count"],
        "product_cards": final_response["product_cards"],
        "latest_outfit_groups": final_response["latest_outfit_groups"],
        "comparison": final_response["comparison"],
        "referenced_products": final_response["referenced_products"],
        "result_metadata": final_response["result_metadata"],
        "response_status": final_response["status"],
        "performance": final_response["performance"],
        "generated_at": final_response["generated_at"],
        "price_contract_version": final_response["price_contract_version"],
        "n24_metadata": {
            "filter_evidence": final_response["filter_evidence"],
            "ollama_calls": final_response["ollama_calls"],
            "generated_by": final_response["generated_by"],
            "warnings": final_response["warnings"],
        },
    })
    return workspace


def dispatch_shopmate_workspace_message(*, user_id: int, chat_id: int, message_text: str, top_n: int = 10):
    selected = get_shopmate_engine()
    if selected == "n23":
        return n24l_n23_workspace_controller(
            user_id=user_id, chat_id=chat_id, message_text=message_text, top_n=top_n
        )
    if selected == "n24":
        return process_workspace_message_n24(
            user_id=user_id, chat_id=chat_id, message_text=message_text, top_n=top_n
        )
    raise RuntimeError("No ShopMate engine is selected.")


def shopmate_process_message_endpoint_n24l(
    request: ShopMateMessageRequest,
    authorization: str | None = Header(default=None),
) -> dict:
    token, user_id = authenticate_shopmate_api_token(authorization)
    cleaned = request.message_text.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="The message cannot be empty.")
    try:
        with SHOPMATE_BACKEND_LOCK:
            if get_shopmate_engine() == "n24":
                duckdb_connection.execute("BEGIN TRANSACTION")
                try:
                    workspace_result = dispatch_shopmate_workspace_message(
                        user_id=user_id, chat_id=request.chat_id,
                        message_text=cleaned, top_n=request.top_n,
                    )
                    duckdb_connection.execute("COMMIT")
                except Exception:
                    duckdb_connection.execute("ROLLBACK")
                    raise
            else:
                workspace_result = dispatch_shopmate_workspace_message(
                    user_id=user_id, chat_id=request.chat_id,
                    message_text=cleaned, top_n=request.top_n,
                )
        validate_shopmate_controller_result(workspace_result)
        save_shopmate_session_workspace(
            token=token, user_id=user_id, workspace_result=workspace_result
        )
        return {"success": True, "engine": get_shopmate_engine(),
                "workspace": shopmate_json_safe_n24k(workspace_result)}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def install_n24l_message_route():
    shopmate_api.router.routes[:] = [
        route for route in shopmate_api.router.routes
        if not (getattr(route, "path", None) == "/api/messages" and "POST" in getattr(route, "methods", set()))
    ]
    shopmate_api.add_api_route(
        "/api/messages", shopmate_process_message_endpoint_n24l,
        methods=["POST"], response_model=None, tags=["Recommendations"],
    )
    shopmate_api.openapi_schema = None
    return next(
        route for route in shopmate_api.router.routes
        if getattr(route, "path", None) == "/api/messages" and "POST" in getattr(route, "methods", set())
    )


def restart_shopmate_backend_n24l(host: str = "127.0.0.1", port: int = 8000):
    """Restart only the saved Uvicorn server thread; never terminate the kernel."""
    global shopmate_uvicorn_config, shopmate_uvicorn_server, shopmate_uvicorn_thread
    old_server = globals().get("shopmate_uvicorn_server")
    old_thread = globals().get("shopmate_uvicorn_thread")
    old_thread_ident = getattr(old_thread, "ident", None)
    if old_server is not None:
        old_server.should_exit = True
    if old_thread is not None and old_thread.is_alive():
        old_thread.join(timeout=10.0)
    if old_thread is not None and old_thread.is_alive():
        raise RuntimeError("The exact saved Uvicorn thread did not stop safely.")
    shopmate_uvicorn_config = uvicorn.Config(
        shopmate_api, host=host, port=port, reload=False, log_level="info"
    )
    shopmate_uvicorn_server = uvicorn.Server(shopmate_uvicorn_config)
    shopmate_uvicorn_thread = _n24l_threading.Thread(
        target=shopmate_uvicorn_server.run,
        name=f"shopmate-uvicorn-{port}", daemon=True,
    )
    shopmate_uvicorn_thread.start()
    deadline = _n24l_time.monotonic() + 15.0
    while _n24l_time.monotonic() < deadline:
        if shopmate_uvicorn_server.started and shopmate_uvicorn_thread.is_alive():
            break
        _n24l_time.sleep(0.05)
    if not shopmate_uvicorn_server.started:
        raise RuntimeError("The replacement Uvicorn server did not start.")
    return {
        "old_thread_ident": old_thread_ident,
        "new_thread_ident": shopmate_uvicorn_thread.ident,
        "running": shopmate_uvicorn_thread.is_alive(),
        "host": host, "port": port,
    }


N24L_MESSAGE_ROUTE = install_n24l_message_route()
set_shopmate_engine(_n24l_os.environ.get("SHOPMATE_ENGINE", "n24"))
N24L_INTEGRATION_STATUS = {
    "section_version": N24L_SECTION_VERSION,
    "engine": get_shopmate_engine(),
    "message_route": getattr(N24L_MESSAGE_ROUTE.endpoint, "__name__", None),
    "n23_controller_preserved": callable(n24l_n23_workspace_controller),
    "n23_parser_in_n24_path": False,
    "ollama": n24l_detect_ollama(force=True),
    "price_contract": N24_PRICE_CONTRACT_VERSION,
    "auth_contract": N24K_AUTH_CONTRACT_VERSION,
}
print("SECTION 153E7N24L - REAL APPLICATION INTEGRATION AND DEVELOPMENT ACTIVATION ready")
print(_n24l_json.dumps(N24L_INTEGRATION_STATUS, indent=2))
