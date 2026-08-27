"""ShopMate N24N grounded conversational search planner.

Executed inside the authoritative notebook namespace after N24M3.  This layer
owns contextual pending-action resolution and verifies a proposed mixed-colour
relaxation against the real trusted catalogue path before offering it.  It does
not select products, alter N23, or change the frozen recommender.
"""

from __future__ import annotations

from copy import deepcopy as _n24n_deepcopy
from enum import Enum as _N24NEnum
import re as _n24n_re
import time as _n24n_time


N24N_PLANNER_VERSION = "n24n_grounded_conversation_planner_v1"


class N24NConversationAction(str, _N24NEnum):
    NEW_SEARCH = "NEW_SEARCH"
    REFINE = "REFINE"
    REFORMULATE = "REFORMULATE"
    SHOW_MORE = "SHOW_MORE"
    COMPARE = "COMPARE"
    PRODUCT_QUESTION = "PRODUCT_QUESTION"
    ACCEPT_PENDING_ACTION = "ACCEPT_PENDING_ACTION"
    REJECT_PENDING_ACTION = "REJECT_PENDING_ACTION"
    PROFILE_PREFERENCE = "PROFILE/PREFERENCE"
    SAFE_FALLBACK = "SAFE_FALLBACK"


class N24NColourMode(str, _N24NEnum):
    STRICT = "STRICT"
    MIXED_ALLOWED = "MIXED_ALLOWED"
    MONOCHROME = "MONOCHROME"


# Consolidation Stage 4: this is a token classifier, not a closed
# whole-utterance phrase whitelist. The earlier design required the ENTIRE
# message to equal one fixed alternative via .fullmatch(), so a perfectly
# ordinary compound reply such as "yes, show me those" matched nothing (the
# comma alone broke it) and silently fell through to ordinary interpretation,
# discarding the pending offer. Adding more literal strings to that
# alternation cannot fix the underlying problem -- any new compound phrasing
# breaks it again. Instead: strip punctuation, tokenize, and decide from
# leading/contained affirmation or negation cue words plus message length,
# so a short trailing or leading clause around a clear yes/no does not
# defeat classification, while a longer message that goes on to state a
# distinct new shopping request is deliberately left unclassified (returns
# None) so it falls through to ordinary interpretation rather than being
# misread as a bare accept/reject.
_N24N_NEGATION_WORDS = {"no", "nope", "nah", "never", "don't", "dont", "cancel"}
_N24N_AFFIRMATION_WORDS = {
    "yes", "yeah", "yea", "yep", "yup", "ya", "sure", "ok", "okay", "fine",
    "alright", "allowed", "go", "allow", "please",
}
# Short, inherently deictic phrases ("those"/"them"/"it" only make sense as a
# reference to what was just offered) that are safe to recognise verbatim
# without a leading yes/no, precisely because classify_n24n_pending_response
# never even looks at these unless a pending offer already exists -- there is
# no freestanding sentence they could be mistaken for. Unlike the retired
# regex whitelist, this is one signal inside a real classifier, not the whole
# matching strategy, and it is checked as a substring so a short leading
# filler ("ok, do that") still resolves via the ordinary affirmation-word
# checks below rather than needing yet another literal variant added here.
_N24N_AFFIRMATION_ANAPHORA = {
    "do it", "do that", "show me those", "show me them", "show those", "show them",
}
_N24N_REJECTION_PHRASES = {
    "not mixed", "keep it black", "keep it white", "dont do that",
    "do not do that", "something else", "never mind",
}
_N24N_MAX_LEADING_AFFIRMATION_TOKENS = 6
_N24N_MAX_CONTAINED_AFFIRMATION_TOKENS = 5
_N24N_MAX_ANAPHORA_TOKENS = 6


def _n24n_clean(raw_message: str) -> str:
    return " ".join(str(raw_message or "").strip().split())


def _n24n_tokenize(text: str) -> list[str]:
    normalized = text.casefold().replace("â€™", "'")
    normalized = _n24n_re.sub(r"\bdon['’]?t\b", "dont", normalized)
    return _n24n_re.sub(r"[^\w\s]", " ", normalized).split()


def classify_n24n_pending_response(raw_message: str, pending_offer) -> N24NConversationAction | None:
    """Classify only contextual acceptance/rejection of an existing pending
    offer; never invent search state, and never touch the message when there
    is no offer to respond to."""
    if pending_offer is None:
        return None
    tokens = _n24n_tokenize(_n24n_clean(raw_message))
    if not tokens:
        return None
    joined = " ".join(tokens)
    if (
        tokens[0] in _N24N_NEGATION_WORDS
        or any(word in _N24N_NEGATION_WORDS for word in tokens)
        or any(phrase in joined for phrase in _N24N_REJECTION_PHRASES)
    ):
        return N24NConversationAction.REJECT_PENDING_ACTION
    if tokens[0] in _N24N_AFFIRMATION_WORDS and len(tokens) <= _N24N_MAX_LEADING_AFFIRMATION_TOKENS:
        return N24NConversationAction.ACCEPT_PENDING_ACTION
    if len(tokens) <= _N24N_MAX_ANAPHORA_TOKENS and any(
        phrase in joined for phrase in _N24N_AFFIRMATION_ANAPHORA
    ):
        return N24NConversationAction.ACCEPT_PENDING_ACTION
    if (
        len(tokens) <= _N24N_MAX_CONTAINED_AFFIRMATION_TOKENS
        and any(word in _N24N_AFFIRMATION_WORDS for word in tokens)
    ):
        return N24NConversationAction.ACCEPT_PENDING_ACTION
    # A trailing affirmation ("...mixed colours is fine", "...that's ok")
    # commonly restates the offered constraint before agreeing to it, so it
    # is allowed a longer message than a bare contained-anywhere match.
    if tokens[-1] in _N24N_AFFIRMATION_WORDS and len(tokens) <= 8:
        return N24NConversationAction.ACCEPT_PENDING_ACTION
    return None


def _n24n_zero_call_metrics(status: str, guard: str, **extra) -> dict:
    return {
        "intent": 0, "response": 0, "repair": 0, "total": 0,
        "interpreter_status": status, "interpreter_latency_seconds": 0.0,
        "semantic_guard": guard, "ollama_available": False,
        "model_available": False, **extra,
    }


if "N24N_BASE_INTERPRET_TURN" not in globals():
    N24N_BASE_INTERPRET_TURN = n24l_interpret_turn


def n24l_interpret_turn(raw_message: str, context, state, active_result_set):
    """Resolve a stored offered action before ordinary parsing or an LLM call."""
    text = _n24n_clean(raw_message)
    chat_id = int(context.chat_id)
    N24M_CURRENT_CHAT_ID.set(chat_id)
    pending = _n24m3_pending_offer(chat_id)
    action = classify_n24n_pending_response(text, pending)
    if action == N24NConversationAction.ACCEPT_PENDING_ACTION:
        delta, updates = _n24m3_delta_for_offer(pending, text)
        if pending.action_type == N24PendingRelaxationAction.ALLOW_MIXED_COLOURS:
            updates["colour_mode"] = N24NColourMode.MIXED_ALLOWED.value
        _n24m_apply_updates(chat_id, delta, updates)
        has_replay = bool(pending.candidate_product_ids)
        _n24m3_clear_pending_offer(chat_id, status="consumed")
        guard = "n24n_pending_action_accepted"
        return delta, {"semantic_guard": guard, "superlative": None}, _n24n_zero_call_metrics(
            "N24N_PENDING_ACTION", guard, accepted_offer_id=pending.offer_id,
            accepted_action=pending.action_type.value,
            # n24l_execute_turn replays these exact candidates instead of
            # re-invoking the recommender when this offer already has a
            # verified candidate snapshot (consolidation Stage 4).
            replay_offer=pending.model_dump(mode="json") if has_replay else None,
        )
    if action == N24NConversationAction.REJECT_PENDING_ACTION:
        _n24m3_clear_pending_offer(chat_id, status="rejected")
        guard = "n24n_pending_action_rejected"
        return None, {"semantic_guard": guard, "superlative": None}, _n24n_zero_call_metrics(
            "N24N_PENDING_REJECTED", guard,
        )
    lower = text.casefold()
    if _n24n_re.search(r"\b(?:beauty products?|makeup|skin\s*care|hair\s*care|fragrances?|razors?|shaving)\b", lower):
        guard = "n24n_unsupported_catalogue_category"
        delta = N24TurnDelta(
            intent=N24Intent.PRODUCT_SEARCH,
            confidence=1.0,
            requires_clarification=True,
            clarification_question=(
                "Beauty products are not represented in this processed catalogue. "
                "I can search its supported fashion, footwear, watches, jewellery, or accessory categories instead."
            ),
            raw_message=text,
        )
        return delta, {"semantic_guard": guard, "superlative": None}, _n24n_zero_call_metrics(
            "N24N_DETERMINISTIC", guard,
        )
    if active_result_set is not None and "compare" in lower:
        count_words = {
            "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        }
        first_count = _n24n_re.search(
            r"\bcompare\s+(?:the\s+)?first\s+(two|three|four|five|six|seven|eight|nine|ten|[2-9]|10)\b",
            lower,
        )
        compare_both = bool(_n24n_re.search(r"\bcompare\s+(?:the\s+)?(?:two|both)\b", lower))
        if first_count or compare_both:
            requested = 2 if compare_both else count_words.get(first_count.group(1), int(first_count.group(1)) if first_count.group(1).isdigit() else 2)
            available = len(active_result_set.ordered_product_ids)
            count = min(requested, available)
            if count >= 2:
                refs = [
                    N24ResultReference(
                        ordinal_index=index,
                        previous_result_set_id=active_result_set.result_set_id,
                    )
                    for index in range(1, count + 1)
                ]
                delta = N24TurnDelta(
                    intent=N24Intent.COMPARE, result_reference=refs,
                    confidence=1.0, raw_message=text,
                )
                guard = "n24n_compare_first_n"
                return delta, {"semantic_guard": guard, "superlative": None}, _n24n_zero_call_metrics(
                    "N24N_DETERMINISTIC", guard,
                )
    result = N24N_BASE_INTERPRET_TURN(raw_message, context, state, active_result_set)
    delta, guard, metrics = result
    if delta is not None:
        colour_operation = getattr(delta.field_operations, "colours", None)
        if colour_operation is not None and colour_operation.operation in {
            N24FieldOperationType.SET, N24FieldOperationType.REPLACE,
        }:
            values = colour_operation.value if isinstance(colour_operation.value, list) else [colour_operation.value]
            normalized = [str(value).strip().casefold() for value in values if str(value).strip()]
            monochrome = bool(_n24n_re.search(r"\b(?:all|fully|entirely|triple)[-\s]+[a-z]+\b", text, _n24n_re.IGNORECASE))
            updates = {
                "allow_mixed_colours": False if monochrome or len(normalized) <= 1 else True,
                "colour_mode": (
                    N24NColourMode.MONOCHROME.value if monochrome
                    else N24NColourMode.MIXED_ALLOWED.value if len(normalized) > 1
                    else N24NColourMode.STRICT.value
                ),
            }
            _n24m_apply_updates(chat_id, delta, updates)
    return delta, guard, metrics


def _n24n_recommendation_count(result) -> int:
    if not isinstance(result, dict):
        return 0
    value = result.get("exact_match_count", result.get("recommendation_count", 0))
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _n24n_probe_relaxation(orchestration, *, sidecar_updates=None, request_transform=None) -> dict:
    """Probe the canonical recommender with a temporarily relaxed request
    and/or sidecar, restoring prior state afterward regardless of outcome.
    Returns the actual recommendation_result (not just a count), so a real
    offer can capture concrete, ordered candidate IDs and their evidence
    instead of a bare count that would have to be recomputed at acceptance
    time (consolidation Stage 4). Generalises the earlier colour-only probe
    to any relaxation dimension.
    """
    request = orchestration.validated_request
    chat_id = N24M_CURRENT_CHAT_ID.get()
    if request is None or chat_id is None:
        return {"available": False, "count": 0, "result": None, "probe_request": None, "reason": "not_applicable"}
    probe_request = request.model_copy(deep=True)
    if request_transform is not None:
        probe_request = request_transform(probe_request)
    fingerprint = probe_request.request_fingerprint
    prior_request_sidecar = _n24n_deepcopy(N24M_REQUEST_SIDECARS.get(fingerprint))
    prior_chat_sidecar = _n24n_deepcopy(_n24m_sidecar(chat_id))
    probe_sidecar = _n24n_deepcopy(prior_chat_sidecar)
    probe_sidecar.update(sidecar_updates or {})
    N24M_REQUEST_SIDECARS[fingerprint] = probe_sidecar
    N24M_CHAT_CONSTRAINTS[int(chat_id)] = _n24n_deepcopy(probe_sidecar)
    started = _n24n_time.perf_counter()
    try:
        result = N24N_BASE_RECOMMENDER(probe_request, top_n=10)
        count = _n24n_recommendation_count(result)
        return {
            "available": count > 0, "count": count, "result": result,
            "probe_request": probe_request,
            "elapsed_seconds": round(_n24n_time.perf_counter() - started, 6),
            "reason": "trusted_n24m2_n24m3_probe",
        }
    finally:
        N24M_CHAT_CONSTRAINTS[int(chat_id)] = prior_chat_sidecar
        if prior_request_sidecar is None:
            N24M_REQUEST_SIDECARS.pop(fingerprint, None)
        else:
            N24M_REQUEST_SIDECARS[fingerprint] = prior_request_sidecar


def _n24n_relaxation_candidates(orchestration):
    """Priority-ordered relaxations to try for the current no-exact-match
    request: colour, then budget, then brand, then category. Restores
    N24M3's full offer menu (_n24m3_offer_from_orchestration), which this
    module's own no_exact_match handling had shadowed for anything other
    than colour, since it intercepted status == "no_exact_match" before
    N24M3's composer was ever reached.
    """
    request = orchestration.validated_request
    candidates = []
    if request.colours:
        candidates.append((
            N24PendingRelaxationAction.ALLOW_MIXED_COLOURS, "colours",
            {"sidecar_updates": {"allow_mixed_colours": True}},
            {"allow_mixed_colours": True, "retain_colours": list(request.colours)},
        ))
    if request.maximum_price is not None or request.minimum_price is not None:
        candidates.append((
            N24PendingRelaxationAction.CLEAR_BUDGET, "historical_price",
            {"request_transform": lambda r: r.model_copy(update={"minimum_price": None, "maximum_price": None})},
            {"minimum_price": None, "maximum_price": None},
        ))
    if request.brands:
        candidates.append((
            N24PendingRelaxationAction.CLEAR_BRAND, "brands",
            {"request_transform": lambda r: r.model_copy(update={"brands": []})},
            {"brands": []},
        ))
    if request.categories:
        candidates.append((
            N24PendingRelaxationAction.BROADEN_CATEGORY, "categories",
            {"request_transform": lambda r: r.model_copy(update={"categories": []})},
            {"categories": []},
        ))
    return candidates


_N24N_RELAXATION_LABELS = {
    N24PendingRelaxationAction.ALLOW_MIXED_COLOURS: "the colour constraint (allow mixed colours)",
    N24PendingRelaxationAction.CLEAR_BUDGET: "the budget",
    N24PendingRelaxationAction.CLEAR_BRAND: "the brand",
    N24PendingRelaxationAction.BROADEN_CATEGORY: "the category",
    N24PendingRelaxationAction.INCREASE_BUDGET: "the budget limit",
}


def _n24n_build_relaxation_offer(orchestration):
    """Try each relaxation in priority order; on the first one that verifies
    at least one real candidate, persist a PendingRelaxationOffer carrying
    those exact, ordered product IDs and their evidence, and return it
    alongside the probe that produced it. Returns (None, None) if nothing
    relaxable is available or nothing verified."""
    request = orchestration.validated_request
    chat_id = N24M_CURRENT_CHAT_ID.get()
    if request is None or chat_id is None:
        return None, None
    for action, target_attribute, probe_kwargs, proposed_operation in _n24n_relaxation_candidates(orchestration):
        probe = _n24n_probe_relaxation(orchestration, **probe_kwargs)
        if not probe["available"]:
            continue
        frame = probe["result"]["recommendations"]
        records = frame.to_dict("records")
        candidate_ids = [str(row["product_id"]) for row in records]
        candidate_evidence = {
            str(row["product_id"]): row.get("n24m_match_evidence") for row in records
        }
        offer = _n24m3_set_pending_offer(
            chat_id, action, target_attribute, proposed_operation,
            getattr(orchestration.result_set, "source_message_id", None),
            source_request_fingerprint=request.request_fingerprint,
            source_result_set_id=getattr(orchestration.result_set, "result_set_id", None),
            candidate_product_ids=candidate_ids,
            candidate_evidence=candidate_evidence,
        )
        return offer, probe
    return None, None


def _n24n_replay_recommendation_result(offer, request, top_n: int = 10) -> dict:
    """Rebuild a recommendation_result identical in shape to
    get_n24_recommendations_from_validated_state's output, but populated
    directly from a pending offer's stored candidate_product_ids and
    candidate_evidence. No eligibility gate or ranking is re-run here: the
    exact products verified when the offer was made are exactly what
    acceptance returns, even after a chat reload or kernel restart
    (consolidation Stage 4's core safety property).
    """
    candidate_ids = [str(item) for item in offer.candidate_product_ids][:top_n]
    base = application_request_metadata_df[
        application_request_metadata_df["product_id"].astype(str).isin(candidate_ids)
    ].drop_duplicates("product_id").copy()
    base["product_id"] = base["product_id"].astype(str)
    base = base.set_index("product_id").reindex(candidate_ids).dropna(how="all").reset_index()
    count = int(len(base))
    if count:
        base["request_rank"] = _n24l_np.arange(1, count + 1, dtype=_n24l_np.int32)
        base["n24m_match_score"] = base["product_id"].map(
            lambda pid: (offer.candidate_evidence.get(pid) or {}).get("match_score", 0.0)
        )
        base["n24m_match_evidence"] = base["product_id"].map(
            lambda pid: offer.candidate_evidence.get(pid) or {}
        )
        base["matched_request_categories"] = ", ".join(request.categories)
        base["matched_request_brands"] = ", ".join(request.brands)
        base["matched_request_colors"] = base["product_id"].map(
            lambda pid: ", ".join(
                getattr(N24_CANONICAL_SEMANTICS_INDEX.get(pid), "colour_components", []) or []
            )
        )
        base["matched_request_materials"] = ", ".join(request.materials)
        base["matched_request_sizes"] = ", ".join(request.sizes)
        base["matched_request_occasions"] = ", ".join(request.occasions)
        base["request_explanation"] = (
            "Verified when offered as a " + offer.action_type.value.replace("_", " ").lower() + " alternative."
        )
        base["currency"] = request.currency
        # build_final_recommendation_cards's base implementation merges in
        # request_search_text from application_request_metadata_df itself by
        # product_id; this frame is sourced from that same table and already
        # carries the column, so it must be dropped here or the merge would
        # rename both copies (request_search_text_x/_y) and the base card
        # builder's direct .request_search_text attribute access would fail.
        base = base.drop(columns=["request_search_text"], errors="ignore")
    parsed = _n24c_structured_parsed_request(request)
    parsed["n24n_pending_offer_replay_of"] = offer.offer_id
    return {
        "profile_id": request.profile_id, "parsed_request": parsed,
        "validated_request": request, "recommendations": base,
        "recommendation_count": count, "requested_result_count": top_n,
        "exact_match_count": count, "eligible_catalogue_count": count,
        "exact_match_shortfall": count < top_n, "no_exact_match": count == 0,
        "result_mode": "n24n_pending_offer_replay",
        "constraints_relaxed": True,
        "hard_constraints_applied": offer.proposed_operation,
        "exclusions_applied": {},
        "relaxation_candidates": [],
        "clarification_needed": False, "clarification_question": None,
        "category_constraint_mode": "n24n_pending_offer_replay_v1",
        "engine_version": N24_CANONICAL_CONTRACT_VERSION,
        "eligibility_overhead_seconds": 0.0,
        "ranking_started_after_trusted_gate": True,
    }


if "N24N_BASE_COMPOSE" not in globals():
    N24N_BASE_COMPOSE = _n24l_compose
if "N24N_BASE_RECOMMENDER" not in globals():
    N24N_BASE_RECOMMENDER = get_n24_recommendations_from_validated_state


def _n24n_no_match_subject(request) -> str:
    parts = []
    if request is not None:
        if request.colours:
            parts.append("/".join(request.colours))
        if request.brands:
            parts.append("/".join(request.brands))
        if request.recipient:
            parts.append(str(request.recipient))
        if request.categories:
            parts.append(" ".join(request.categories))
        if request.maximum_price is not None:
            parts.append(f"under ${request.maximum_price:g}")
        if request.minimum_price is not None:
            parts.append(f"above ${request.minimum_price:g}")
    return " ".join(parts) if parts else "those verified constraints"


def _n24n_response(orchestration, *, message: str, response_type: str, warnings=None):
    grounded = orchestration.grounded_data if isinstance(orchestration.grounded_data, dict) else {}
    raw_cards = orchestration.cards
    cards = raw_cards.to_dict("records") if hasattr(raw_cards, "to_dict") else list(raw_cards or [])
    return N24GroundedResponse(
        status=orchestration.status,
        message=message,
        response_type=response_type,
        cards=cards,
        comparison=grounded.get("comparison"),
        referenced_products=list(grounded.get("referenced_products") or []),
        clarification=orchestration.clarification_reason,
        limitations=list(grounded.get("limitations") or []),
        preference_update_summary=grounded.get("preference_update"),
        result_set_id=(
            orchestration.result_set.result_set_id
            if orchestration.result_set is not None else None
        ),
        generated_by=N24N_PLANNER_VERSION,
        warnings=list(warnings or []),
    )


def _n24n_deterministic_recommendation(orchestration):
    raw_cards = orchestration.cards
    cards = raw_cards.to_dict("records") if hasattr(raw_cards, "to_dict") else list(raw_cards or [])
    titles = [str(card.get("title") or "this verified product") for card in cards]
    if len(titles) == 1:
        listing = titles[0]
    elif len(titles) == 2:
        listing = " and ".join(titles)
    else:
        listing = ", ".join(titles[:-1]) + ", and " + titles[-1]
    message = (
        f"I found {len(cards)} verified match{'es' if len(cards) != 1 else ''}: {listing}. "
        "Prices shown are historical dataset prices, not live current prices."
    )
    return _n24n_response(
        orchestration, message=message, response_type="recommendations",
        warnings=["n24n_deterministic_grounded_composer"],
    )


def _n24l_compose(raw_message: str, orchestration, call_metrics: dict):
    if call_metrics.get("semantic_guard") == "n24n_unsupported_catalogue_category":
        return _n24n_response(
            orchestration,
            message=(
                "Beauty products are not represented in this processed catalogue. "
                "I can search its supported fashion, footwear, watches, jewellery, or accessory categories instead."
            ),
            response_type="unsupported_catalogue_category",
            warnings=["n24n_unsupported_catalogue_category"],
        )
    if call_metrics.get("semantic_guard") == "n24n_pending_action_rejected":
        return _n24n_response(
            orchestration,
            message="Okay, I’ll keep your current shopping constraints unchanged.",
            response_type="acknowledgement",
            warnings=["n24n_pending_action_rejected"],
        )
    if orchestration.status == "recommendations" and orchestration.response_intent in {
        N24Intent.PRODUCT_SEARCH, N24Intent.REFINE, N24Intent.NEW_GOAL,
    }:
        return _n24n_deterministic_recommendation(orchestration)
    if orchestration.status != "no_exact_match":
        return N24N_BASE_COMPOSE(raw_message, orchestration, call_metrics)
    request = orchestration.validated_request
    chat_id = N24M_CURRENT_CHAT_ID.get()
    if chat_id is not None:
        _n24m3_clear_pending_offer(chat_id, status="expired")
    grounded = orchestration.grounded_data if isinstance(orchestration.grounded_data, dict) else {}
    offer, probe = _n24n_build_relaxation_offer(orchestration)
    if offer is not None:
        grounded["pending_action"] = offer.model_dump(mode="json")
        label = _N24N_RELAXATION_LABELS.get(offer.action_type, "that constraint")
        message = (
            f"I found no exact match for {_n24n_no_match_subject(request)}. "
            f"I verified {offer.verified_count} eligible candidate"
            f"{'s' if offer.verified_count != 1 else ''} if I relax {label}. "
            "Say yes to see those exact candidates, or tell me what else to change."
        )
    else:
        message = (
            f"I found no exact match for {_n24n_no_match_subject(request)}. "
            "I also could not verify an eligible relaxed alternative, so I won't offer one."
        )
    return _n24n_response(
        orchestration, message=message, response_type="no_exact_match",
        warnings=["n24n_grounded_relaxation_probe"],
    )


def run_n24n_deterministic_tests() -> dict:
    fake = object()
    cases = {
        "yes_accepts": classify_n24n_pending_response("yes", fake) == N24NConversationAction.ACCEPT_PENDING_ACTION,
        "failing_phrase_accepts": classify_n24n_pending_response("ok show me mixed", fake) == N24NConversationAction.ACCEPT_PENDING_ACTION,
        "mixed_colours_accepts": classify_n24n_pending_response("ok show me mixed colours", fake) == N24NConversationAction.ACCEPT_PENDING_ACTION,
        "contextual_colour_accepts": classify_n24n_pending_response("red with other colours is fine", fake) == N24NConversationAction.ACCEPT_PENDING_ACTION,
        "no_rejects": classify_n24n_pending_response("no", fake) == N24NConversationAction.REJECT_PENDING_ACTION,
        "no_pending_no_action": classify_n24n_pending_response("yes", None) is None,
        "question_not_acceptance": classify_n24n_pending_response("why are you showing white shoes?", fake) is None,
        # Regression: this exact compound phrase (leading "yes" + comma +
        # trailing clause) was reported as a manual defect against the
        # earlier closed-phrase-whitelist classifier -- it fell through to
        # ordinary interpretation and silently discarded the pending offer.
        "compound_yes_comma_accepts": classify_n24n_pending_response("yes, show me those", fake) == N24NConversationAction.ACCEPT_PENDING_ACTION,
        "compound_sure_that_works_accepts": classify_n24n_pending_response("sure, that works", fake) == N24NConversationAction.ACCEPT_PENDING_ACTION,
        "no_thanks_rejects": classify_n24n_pending_response("no thanks", fake) == N24NConversationAction.REJECT_PENDING_ACTION,
        # Bare anaphoric acceptance, no leading yes/no -- supported by the
        # retired regex whitelist too; must not regress.
        "bare_do_that_accepts": classify_n24n_pending_response("do that", fake) == N24NConversationAction.ACCEPT_PENDING_ACTION,
        "bare_show_me_those_accepts": classify_n24n_pending_response("show me those", fake) == N24NConversationAction.ACCEPT_PENDING_ACTION,
        "showing_question_not_hijacked": classify_n24n_pending_response("why are you showing white shoes?", fake) is None,
        "long_new_request_not_hijacked": classify_n24n_pending_response(
            "actually show me red adidas jackets under 50 dollars instead please", fake
        ) is None,
    }
    return {"version": N24N_PLANNER_VERSION, "passed": all(cases.values()), "cases": cases}


N24N_COMPATIBILITY_STATUS = {
    "planner_version": N24N_PLANNER_VERSION,
    "n23_modified": False,
    "frozen_ranker_changed": False,
    "pending_action_consumed_once": True,
    "mixed_offer_requires_trusted_probe": True,
    "relaxation_menu": [action.value for action in N24PendingRelaxationAction],
    "pending_offer_stores_concrete_candidates": True,
    "pending_offer_grammar": "tokenized affirmation/negation classifier (not a closed phrase whitelist)",
}

print("N24N grounded conversation planner loaded.")
print(run_n24n_deterministic_tests())
