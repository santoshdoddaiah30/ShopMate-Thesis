"""Focused live/API validation for the N24M2 trusted catalogue truth layer.

This intentionally runs only the twenty cases requested for N24M2.  It does
not replay the historical acceptance manifest and it does not drive a browser.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "Notebooks"
if str(NOTEBOOKS) not in sys.path:
    sys.path.insert(0, str(NOTEBOOKS))

from shopmate_n24m_validation import LiveShopMateAudit, card_contract, snapshot


OUTPUT_DIR = ROOT / "Results" / "N24M2_Trusted_Truth_Audit"
RAW_TAG_MARKERS = (":EXACT", ":PARTIAL", ":UNKNOWN", ":VIOLATION")


def _write(name, payload):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / name).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )


def _card_failures(cards):
    failures = list(card_contract(cards))
    for card in cards or []:
        if not isinstance(card, dict) or not card.get("product_id"):
            continue
        evidence = card.get("eligibility_evidence") or {}
        if evidence.get("engine_version") != "n24m2_trusted_exact_eligibility_v1":
            failures.append(f"{card.get('product_id')}: missing N24M2 eligibility version")
        if int(evidence.get("partial_constraint_count") or 0):
            failures.append(f"{card.get('product_id')}: partial hard evidence returned")
        tags = card.get("matched_attributes") or []
        visible = " ".join(str(item) for item in tags)
        explanation = str(card.get("recommendation_explanation") or "")
        if any(marker in visible.upper() for marker in RAW_TAG_MARKERS):
            failures.append(f"{card.get('product_id')}: raw match tag visible")
        if any(marker in explanation.upper() for marker in RAW_TAG_MARKERS):
            failures.append(f"{card.get('product_id')}: raw match tag leaked into explanation")
    return failures


def _state_failures(state, expected):
    failures = []
    for key, wanted in (expected or {}).items():
        actual = state.get(key)
        if isinstance(wanted, list):
            if {str(x).casefold() for x in (actual or [])} != {str(x).casefold() for x in wanted}:
                failures.append(f"state {key}={actual!r}; expected {wanted!r}")
        elif wanted is None:
            if actual is not None:
                failures.append(f"state {key}={actual!r}; expected cleared")
        elif isinstance(wanted, (int, float)):
            if actual is None or abs(float(actual) - float(wanted)) > 1e-9:
                failures.append(f"state {key}={actual!r}; expected {wanted!r}")
        elif str(actual).casefold() != str(wanted).casefold():
            failures.append(f"state {key}={actual!r}; expected {wanted!r}")
    return failures


def _turn(audit, chat_id, text, *, spec=None, state=None, statuses=None, expect_cards=None):
    snap = snapshot(audit.message(text, chat_id=chat_id, top_n=10))
    failures = []
    if snap["http_status"] != 200:
        failures.append(f"HTTP {snap['http_status']}")
    if snap["engine"] != "n24":
        failures.append(f"engine={snap['engine']!r}")
    failures.extend(_state_failures(snap["state"], state))
    if statuses and snap["status"] not in statuses:
        failures.append(f"status={snap['status']!r}; expected {statuses!r}")
    if expect_cards is True and not snap["cards"]:
        failures.append("expected at least one exact card")
    if expect_cards is False and snap["cards"]:
        failures.append("expected zero cards")
    if snap["cards"]:
        failures.extend(_card_failures(snap["cards"]))
    return {
        "message": text, "classification": "PASS" if not failures else "FAIL",
        "failures": failures, "oracle_spec": spec, **snap,
    }


def _case(case_id, label, turns, extra_failures=None):
    failures = [failure for turn in turns for failure in turn["failures"]]
    failures.extend(extra_failures or [])
    return {
        "case": case_id, "label": label,
        "classification": "PASS" if not failures else "FAIL",
        "failures": failures, "turns": turns,
    }


def run_focused(base_url="http://127.0.0.1:8000"):
    audit = LiveShopMateAudit(base_url)
    results = []

    def fresh():
        return audit.create_chat()

    simple = [
        (1, "white shoes", "I need white shoes.", {"categories": ["Shoes"], "colours": ["white"]}, {"categories": ["Shoes"], "colours": ["white"]}),
        (2, "black shoes", "I need black shoes.", {"categories": ["Shoes"], "colours": ["black"]}, {"categories": ["Shoes"], "colours": ["black"]}),
        (3, "white Adidas shoes", "Show me white Adidas shoes.", {"categories": ["Shoes"], "brands": ["adidas"], "colours": ["white"]}, {"categories": ["Shoes"], "brands": ["adidas"], "colours": ["white"]}),
        (4, "white Adidas shoes for men", "Show me white Adidas shoes for men.", {"categories": ["Shoes"], "brands": ["adidas"], "colours": ["white"], "recipient": "men"}, {"categories": ["Shoes"], "brands": ["adidas"], "colours": ["white"], "recipient": "men"}),
        (5, "black Nike shoes for women", "Show me black Nike shoes for women.", {"categories": ["Shoes"], "brands": ["Nike"], "colours": ["black"], "recipient": "women"}, {"categories": ["Shoes"], "brands": ["Nike"], "colours": ["black"], "recipient": "women"}),
        (6, "red shoes for men under $100", "Show me red shoes for men under $100.", {"categories": ["Shoes"], "colours": ["red"], "recipient": "men", "maximum_price": 100}, {"categories": ["Shoes"], "colours": ["red"], "recipient": "men", "maximum_price": 100}),
        (7, "shoes for kids", "Show me shoes for kids.", {"categories": ["Shoes"], "recipient": "kids"}, {"categories": ["Shoes"], "recipient": "kids"}),
        (8, "Nike shoes above 4 stars", "Show me Nike shoes above 4 stars.", {"categories": ["Shoes"], "brands": ["Nike"], "minimum_rating": 4.0, "rating_exclusive": True}, {"categories": ["Shoes"], "brands": ["Nike"], "minimum_price": None}),
        (9, "white and black shoes", "Show me white and black shoes.", {"categories": ["Shoes"], "colours": ["white", "black"]}, {"categories": ["Shoes"], "colours": ["white", "black"]}),
        (10, "white shoes, mixed colours okay", "Show me white shoes; mixed colours are okay.", {"categories": ["Shoes"], "colours": ["white"], "allow_mixed": True}, {"categories": ["Shoes"], "colours": ["white"]}),
        (11, "shoes except red", "Show me shoes except red.", {"categories": ["Shoes"], "excluded_colours": ["red"]}, {"categories": ["Shoes"]}),
    ]
    for case_id, label, text, spec, state in simple:
        print(f"FOCUSED {case_id}/20 {label}", flush=True)
        turn = _turn(audit, fresh(), text, spec=spec, state=state, statuses={"recommendations", "no_exact_match"})
        results.append(_case(case_id, label, [turn]))
        print(f"FOCUSED RESULT {case_id}: {results[-1]['classification']} cards={len(turn['cards'])}", flush=True)

    print("FOCUSED 12/20 any colour is fine", flush=True)
    chat = fresh()
    setup = _turn(audit, chat, "Show me blue shoes.", spec={"categories": ["Shoes"], "colours": ["blue"]}, state={"categories": ["Shoes"], "colours": ["blue"]}, statuses={"recommendations", "no_exact_match"})
    target = _turn(audit, chat, "Any colour is fine.", spec={"categories": ["Shoes"]}, state={"categories": ["Shoes"], "colours": []}, statuses={"recommendations", "no_exact_match"}, expect_cards=True)
    results.append(_case(12, "any colour is fine", [setup, target]))

    print("FOCUSED 13/20 why are these white?", flush=True)
    chat = fresh()
    setup = _turn(audit, chat, "Show me black Adidas shoes.", spec={"categories": ["Shoes"], "brands": ["adidas"], "colours": ["black"]}, state={"categories": ["Shoes"], "brands": ["adidas"], "colours": ["black"]}, statuses={"recommendations", "no_exact_match"})
    before = dict(setup["state"])
    target = _turn(audit, chat, "Why are these white?", spec=None, statuses={"product_question"})
    extra = [] if target["state"] == before else ["product question mutated active shopping state"]
    results.append(_case(13, "why are these white?", [setup, target], extra))

    for case_id, label, text, spec, state, sort_key, reverse in [
        (14, "cheapest shoe", "Show me the cheapest shoe.", {"categories": ["Shoes"]}, {"categories": ["Shoes"]}, "price", False),
        (15, "costliest shoe", "Show me the costliest shoe.", {"categories": ["Shoes"]}, {"categories": ["Shoes"]}, "price", True),
        (16, "highest-rated men's shoe", "Show me the highest-rated men's shoe.", {"categories": ["Shoes"], "recipient": "men"}, {"categories": ["Shoes"], "recipient": "men"}, "average_rating", True),
    ]:
        print(f"FOCUSED {case_id}/20 {label}", flush=True)
        turn = _turn(audit, fresh(), text, spec=spec, state=state, statuses={"recommendations", "no_exact_match"}, expect_cards=True)
        extra = []
        values = [card.get(sort_key) for card in turn["cards"] if isinstance(card, dict) and card.get(sort_key) is not None]
        if len(values) > 1 and values != sorted(values, reverse=reverse):
            extra.append(f"cards are not ordered by {sort_key} {'descending' if reverse else 'ascending'}")
        results.append(_case(case_id, label, [turn], extra))

    print("FOCUSED 17/20 show more", flush=True)
    chat = fresh()
    spec = {"categories": ["Shoes"], "brands": ["Nike"]}
    setup = _turn(audit, chat, "Show me Nike shoes.", spec=spec, state={"categories": ["Shoes"], "brands": ["Nike"]}, statuses={"recommendations", "no_exact_match"}, expect_cards=True)
    target = _turn(audit, chat, "Show more.", spec=spec, state={"categories": ["Shoes"], "brands": ["Nike"]}, statuses={"recommendations", "no_exact_match"})
    overlap = set(setup["product_ids"]) & set(target["product_ids"])
    results.append(_case(17, "show more", [setup, target], [f"show-more repeated IDs: {sorted(overlap)}"] if overlap else []))

    print("FOCUSED 18/20 compare first and third", flush=True)
    chat = fresh()
    setup = _turn(audit, chat, "Show me watches.", spec={"categories": ["Watches"]}, state={"categories": ["Watches"]}, statuses={"recommendations", "no_exact_match"}, expect_cards=True)
    target = _turn(audit, chat, "Compare first and third.", spec={"categories": ["Watches"]}, statuses={"comparison"})
    expected_ids = [setup["product_ids"][i] for i in (0, 2) if len(setup["product_ids"]) > i]
    comparison_text = json.dumps(target.get("comparison"), default=str)
    extra = [] if len(expected_ids) == 2 and all(item in comparison_text for item in expected_ids) else ["comparison did not resolve persisted first/third IDs"]
    results.append(_case(18, "compare first and third", [setup, target], extra))

    print("FOCUSED 19/20 new goal watches", flush=True)
    chat = fresh()
    setup = _turn(audit, chat, "Show me black Nike shoes under $80.", spec={"categories": ["Shoes"], "brands": ["Nike"], "colours": ["black"], "maximum_price": 80}, statuses={"recommendations", "no_exact_match"})
    target = _turn(audit, chat, "New goal: show me watches.", spec={"categories": ["Watches"]}, state={"categories": ["Watches"], "brands": [], "colours": [], "minimum_price": None, "maximum_price": None}, statuses={"recommendations", "no_exact_match"}, expect_cards=True)
    results.append(_case(19, "new goal watches", [setup, target]))

    print("FOCUSED 20/20 no-match case", flush=True)
    turn = _turn(audit, fresh(), "Show me white Adidas shoes for men under $1.", spec={"categories": ["Shoes"], "brands": ["adidas"], "colours": ["white"], "recipient": "men", "maximum_price": 1}, statuses={"no_exact_match"}, expect_cards=False)
    relaxation = str(turn.get("message") or "").casefold()
    extra = [] if any(word in relaxation for word in ("relax", "broaden", "remove", "increase", "try")) else ["no-match response lacks grounded relaxation guidance"]
    results.append(_case(20, "no-match case", [turn], extra))

    summary = {
        "suite": "N24M2 focused live language tests", "total": 20,
        "passed": sum(item["classification"] == "PASS" for item in results),
        "failed": sum(item["classification"] == "FAIL" for item in results),
        "user_id": audit.user_id, "profile_id": audit.profile_id,
    }
    _write("focused_live_results.json", results)
    _write("focused_live_summary.json", summary)
    print("FOCUSED_SUMMARY=" + json.dumps(summary), flush=True)
    return summary


if __name__ == "__main__":
    run_focused(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000")
