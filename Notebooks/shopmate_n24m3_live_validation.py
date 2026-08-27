"""Focused live API validation for N24M3 relaxation and N24 compatibility."""

from __future__ import annotations

from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "Notebooks"
if str(NOTEBOOKS) not in sys.path:
    sys.path.insert(0, str(NOTEBOOKS))

from shopmate_n24m_validation import LiveShopMateAudit, PASSWORD, http_json, snapshot


OUTPUT_DIR = ROOT / "Results" / "N24M3_Visual_Relaxation_Audit"


def _normal(values):
    return {str(item).strip().casefold() for item in (values or [])}


def _turn(audit, message, *, chat=None, top_n=10):
    snap = snapshot(audit.message(message, chat_id=chat, top_n=top_n))
    return {
        "message": message, "http_status": snap["http_status"],
        "engine": snap["engine"], "status": snap["status"],
        "assistant": snap["message"], "state": snap["state"],
        "product_ids": snap["product_ids"], "cards": snap["cards"],
        "result_metadata": snap["result_metadata"],
        "latest_outfit_groups": snap["latest_outfit_groups"],
        "comparison": snap["comparison"], "response_seconds": snap["response_seconds"],
        "ollama_calls": snap["ollama_calls"],
    }


def _state(turn, key):
    return (turn.get("state") or {}).get(key)


def run_n24m3_relaxation_tests(base_url="http://127.0.0.1:8000"):
    audit = LiveShopMateAudit(base_url)
    results = []

    chat = audit.create_chat()
    r1a = _turn(audit, "i need red dress", chat=chat)
    r1b = _turn(audit, "yes show me mixed", chat=chat)
    r1 = (
        r1a["status"] == "no_exact_match"
        and "mixed" in r1a["assistant"].casefold()
        and r1b["status"] != "clarification"
        and _normal(_state(r1b, "categories")) == {"dresses"}
        and _normal(_state(r1b, "colours")) == {"red"}
    )
    results.append({"case": "R1", "passed": r1, "turns": [r1a, r1b]})

    chat = audit.create_chat()
    r2a = _turn(audit, "white Adidas shoes", chat=chat)
    r2b = _turn(audit, "mixed colours are okay", chat=chat)
    r2 = (
        r2b["status"] != "clarification"
        and _normal(_state(r2b, "categories")) == {"shoes"}
        and _normal(_state(r2b, "brands")) == {"adidas"}
        and _normal(_state(r2b, "colours")) == {"white"}
    )
    results.append({"case": "R2", "passed": r2, "turns": [r2a, r2b]})

    chat = audit.create_chat()
    r3a = _turn(audit, "black Nike women's shoes", chat=chat)
    r3b = _turn(audit, "relax the brand", chat=chat)
    r3 = (
        r3b["status"] != "clarification" and not _state(r3b, "brands")
        and _normal(_state(r3b, "categories")) == {"shoes"}
        and _normal(_state(r3b, "colours")) == {"black"}
        and str(_state(r3b, "recipient") or "").casefold() == "women"
    )
    results.append({"case": "R3", "passed": r3, "turns": [r3a, r3b]})

    chat = audit.create_chat()
    r4a = _turn(audit, "shoes under $20", chat=chat)
    r4b = _turn(audit, "forget the budget", chat=chat)
    r4 = (
        r4b["status"] != "clarification"
        and _state(r4b, "minimum_price") is None and _state(r4b, "maximum_price") is None
        and _normal(_state(r4b, "categories")) == {"shoes"}
    )
    results.append({"case": "R4", "passed": r4, "turns": [r4a, r4b]})

    chat = audit.create_chat()
    r5 = _turn(audit, "yes", chat=chat)
    r5_pass = (
        r5["status"] == "clarification" and not _state(r5, "categories")
        and not _state(r5, "brands") and not _state(r5, "colours")
    )
    results.append({"case": "R5", "passed": r5_pass, "turns": [r5]})

    chat = audit.create_chat()
    r6a = _turn(audit, "red dress", chat=chat)
    r6b = _turn(audit, "no", chat=chat)
    r6 = (
        r6b["status"] == "clarification"
        and _normal(_state(r6b, "categories")) == {"dresses"}
        and _normal(_state(r6b, "colours")) == {"red"}
    )
    results.append({"case": "R6", "passed": r6, "turns": [r6a, r6b]})

    chat = audit.create_chat()
    r7a = _turn(audit, "black Nike women's shoes", chat=chat)
    r7b = _turn(audit, "no, relax brand instead", chat=chat)
    r7 = (
        r7b["status"] != "clarification" and not _state(r7b, "brands")
        and _normal(_state(r7b, "categories")) == {"shoes"}
        and _normal(_state(r7b, "colours")) == {"black"}
        and str(_state(r7b, "recipient") or "").casefold() == "women"
    )
    results.append({"case": "R7", "passed": r7, "turns": [r7a, r7b]})

    chat_a = audit.create_chat()
    r8a = _turn(audit, "red dress", chat=chat_a)
    chat_b = audit.create_chat()
    r8b = _turn(audit, "yes", chat=chat_b)
    r8 = (
        r8a["status"] == "no_exact_match" and r8b["status"] == "clarification"
        and not _state(r8b, "categories") and not _state(r8b, "colours")
    )
    results.append({
        "case": "R8", "passed": r8, "chat_a": chat_a, "chat_b": chat_b,
        "turns": [r8a, r8b],
    })

    report = {
        "suite": "N24M3 contextual relaxation R1-R8",
        "audit_user_id": audit.user_id, "audit_profile_id": audit.profile_id,
        "results": results, "passed": sum(item["passed"] for item in results),
        "failed": sum(not item["passed"] for item in results),
        "all_passed": all(item["passed"] for item in results),
        "cross_chat_pending_action_leakage": 0 if r8 else 1,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "contextual_relaxation_tests.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    return report


def run_n24m3_realistic_flow(base_url="http://127.0.0.1:8000"):
    audit = LiveShopMateAudit(base_url)
    chat = audit.create_chat()
    messages = [
        "i need red dress",
        "yes show me mixed",
        "only mostly red ones",
        "forget dresses, show me white t-shirts",
    ]
    turns = [_turn(audit, message, chat=chat) for message in messages]
    final_ids = turns[-1]["product_ids"]
    passed = bool(
        turns[0]["status"] == "no_exact_match"
        and "mixed" in turns[0]["assistant"].casefold()
        and turns[1]["status"] != "clarification"
        and _normal(_state(turns[1], "categories")) == {"dresses"}
        and _normal(_state(turns[1], "colours")) == {"red"}
        and _normal(_state(turns[2], "colours")) == {"red"}
        and _normal(_state(turns[3], "categories")) == {"t-shirts"}
        and _normal(_state(turns[3], "colours")) == {"white"}
        and final_ids
    )
    report = {
        "suite": "N24M3 realistic relaxation-to-new-goal flow",
        "audit_user_id": audit.user_id, "audit_profile_id": audit.profile_id,
        "chat_id": chat, "passed": passed, "turns": turns,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "realistic_flow.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    return report


def run_n24m3_focused_regression(base_url="http://127.0.0.1:8000"):
    audit = LiveShopMateAudit(base_url)
    checks = {}
    details = {}

    login_status, login_payload, _ = http_json(
        base_url, "/api/auth/login", method="POST",
        body={"email": audit.email, "password": PASSWORD},
    )
    checks["auth"] = bool(login_status == 200 and login_payload.get("success"))

    chat = audit.create_chat()
    normal = _turn(audit, "Show me watches.", chat=chat)
    checks["normal_category"] = bool(normal["http_status"] == 200 and _normal(_state(normal, "categories")) == {"watches"})
    checks["price_contract"] = all(
        isinstance(card.get("price"), (int, float))
        and card.get("price_is_historical") is True
        and "historical" in str(card.get("price_display") or "").casefold()
        for card in normal["cards"]
    ) and bool(normal["cards"])

    chat = audit.create_chat()
    brand = _turn(audit, "Show me Nike shoes.", chat=chat)
    checks["brand"] = _normal(_state(brand, "brands")) == {"nike"}

    chat = audit.create_chat()
    audience = _turn(audit, "Show me shoes for men.", chat=chat)
    checks["audience"] = str(_state(audience, "recipient") or "").casefold() == "men"

    chat = audit.create_chat()
    price = _turn(audit, "Show me shoes under $100.", chat=chat)
    checks["price"] = _state(price, "maximum_price") == 100

    chat = audit.create_chat()
    rating = _turn(audit, "Show me Nike shoes rated at least 4 stars.", chat=chat)
    checks["rating"] = rating["status"] in {"recommendations", "no_exact_match"} and _normal(_state(rating, "brands")) == {"nike"}

    chat = audit.create_chat()
    first = _turn(audit, "Show me watches.", chat=chat, top_n=3)
    more = _turn(audit, "show me more", chat=chat, top_n=3)
    checks["show_more"] = bool(first["product_ids"] and not set(first["product_ids"]) & set(more["product_ids"]))

    chat = audit.create_chat()
    compare_source = _turn(audit, "Show me watches.", chat=chat, top_n=3)
    compare = _turn(audit, "Compare the first and second ones.", chat=chat, top_n=3)
    checks["comparison"] = bool(
        len(compare_source["product_ids"]) >= 2 and compare["status"] == "comparison" and compare["comparison"]
    )

    chat = audit.create_chat()
    _turn(audit, "Show me Nike shoes under $100.", chat=chat)
    new_goal = _turn(audit, "Now show me watches.", chat=chat)
    checks["new_goal"] = bool(
        _normal(_state(new_goal, "categories")) == {"watches"}
        and not _state(new_goal, "brands") and _state(new_goal, "maximum_price") is None
    )

    chat = audit.create_chat()
    preference = _turn(audit, "I like Nike.", chat=chat)
    checks["preferences"] = preference["status"] == "profile_updated" and not _state(preference, "brands")

    chat = audit.create_chat()
    outfit = _turn(audit, "Build me a complete casual outfit for women under $500.", chat=chat)
    checks["outfit"] = bool(outfit["latest_outfit_groups"])

    chat_a = audit.create_chat()
    state_a = _turn(audit, "Show me Nike shoes under $100.", chat=chat_a)
    chat_b = audit.create_chat()
    state_b = _turn(audit, "Show me watches.", chat=chat_b)
    if checks["auth"]:
        audit.token = login_payload["token"]
    restored = audit.select_chat(chat_a)
    active = ((restored.get("loaded_chat") or {}).get("active_request_state") or {})
    conversation = (active.get("_n24l_conversation_state") or {}).get("conversation") or {}
    nested = conversation.get("hard_request") or conversation or active
    checks["persistence"] = bool(
        _normal(nested.get("categories")) == _normal(_state(state_a, "categories"))
        and _normal(nested.get("brands")) == _normal(_state(state_a, "brands"))
        and nested.get("maximum_price") == _state(state_a, "maximum_price")
    )
    checks["cross_chat"] = bool(
        _normal(_state(state_b, "categories")) == {"watches"}
        and not _state(state_b, "brands") and _state(state_b, "maximum_price") is None
    )
    details.update({
        "normal": normal, "brand": brand, "audience": audience,
        "price": price, "rating": rating, "show_more": [first, more],
        "comparison": [compare_source, compare], "new_goal": new_goal,
        "preference": preference, "outfit": outfit,
        "persistence": {"chat_a": state_a, "chat_b": state_b, "restored": active},
    })
    report = {
        "suite": "N24M3 focused regression (no broad replay)",
        "audit_user_id": audit.user_id, "audit_profile_id": audit.profile_id,
        "checks": checks, "passed": sum(checks.values()),
        "failed": sum(not value for value in checks.values()),
        "all_passed": all(checks.values()), "details": details,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "focused_n24_regression.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    return report


def recheck_saved_n24m3_regression():
    """Re-evaluate persistence from the saved nested N24L evidence only."""
    path = OUTPUT_DIR / "focused_n24_regression.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    detail = report["details"]["persistence"]
    state_a = detail["chat_a"]["state"]
    active = detail["restored"]
    conversation = (active.get("_n24l_conversation_state") or {}).get("conversation") or {}
    nested = conversation.get("hard_request") or conversation or active
    report["checks"]["persistence"] = bool(
        _normal(nested.get("categories")) == _normal(state_a.get("categories"))
        and _normal(nested.get("brands")) == _normal(state_a.get("brands"))
        and nested.get("maximum_price") == state_a.get("maximum_price")
    )
    report["passed"] = sum(report["checks"].values())
    report["failed"] = sum(not value for value in report["checks"].values())
    report["all_passed"] = all(report["checks"].values())
    report["persistence_recheck"] = "SAVED_NESTED_HARD_REQUEST_EVIDENCE"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    base = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000"
    output = {}
    if mode in {"all", "relaxation"}:
        output["relaxation"] = run_n24m3_relaxation_tests(base)
    if mode in {"all", "flow"}:
        output["flow"] = run_n24m3_realistic_flow(base)
    if mode in {"all", "regression"}:
        output["regression"] = run_n24m3_focused_regression(base)
    print("N24M3_LIVE_SUMMARY=" + json.dumps({
        key: ({"passed": value.get("passed"), "failed": value.get("failed"), "all_passed": value.get("all_passed")} if key != "flow" else {"passed": value["passed"]})
        for key, value in output.items()
    }, default=str), flush=True)
