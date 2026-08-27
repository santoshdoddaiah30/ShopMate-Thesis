"""Small, targeted N24M2 regression suite. No historical manifest replay."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "Notebooks"
if str(NOTEBOOKS) not in sys.path:
    sys.path.insert(0, str(NOTEBOOKS))

from shopmate_n24m_validation import (
    LiveShopMateAudit, PASSWORD, http_json, snapshot,
)


OUTPUT_DIR = ROOT / "Results" / "N24M2_Trusted_Truth_Audit"


def _restored_hard_request(active_request_state):
    active_request_state = active_request_state or {}
    persisted_n24 = active_request_state.get("_n24l_conversation_state") or {}
    conversation = persisted_n24.get("conversation") or {}
    return conversation.get("hard_request") or active_request_state


def _saved_focused_checks():
    focused = json.loads((OUTPUT_DIR / "focused_live_results.json").read_text(encoding="utf-8"))
    oracle = json.loads((OUTPUT_DIR / "focused_live_raw_oracle.json").read_text(encoding="utf-8"))
    by_case = {int(item["case"]): item for item in focused}
    first_card = by_case[1]["turns"][0]["cards"][0]
    return {
        "recommendation": by_case[1]["classification"] == "PASS" and oracle["failed_assertions"] == 0,
        "show_more": by_case[17]["classification"] == "PASS",
        "comparison": by_case[18]["classification"] == "PASS",
        "price": (
            isinstance(first_card.get("price"), (int, float))
            and first_card.get("price_is_historical") is True
            and first_card.get("price_contract_version") == "n24_historical_price_contract_v1"
            and "historical" in str(first_card.get("price_display") or "").casefold()
        ),
    }


def run_regression(base_url="http://127.0.0.1:8000"):
    checks = _saved_focused_checks()
    details = {}
    audit = LiveShopMateAudit(base_url)

    # Auth: registration occurs in LiveShopMateAudit; verify the migrated login
    # contract and use the refreshed token for the persistence boundary below.
    login_status, login_payload, login_seconds = http_json(
        base_url, "/api/auth/login", method="POST",
        body={"email": audit.email, "password": PASSWORD},
    )
    checks["auth"] = bool(login_status == 200 and login_payload.get("success") and login_payload.get("token"))
    details["auth"] = {"status": login_status, "seconds": login_seconds, "display_name": login_payload.get("display_name")}

    # Deterministic ordinal reference.
    chat = audit.create_chat()
    initial = snapshot(audit.message("Show me watches.", chat_id=chat))
    reference = snapshot(audit.message("Tell me about the first one.", chat_id=chat))
    target = initial["product_ids"][0] if initial["product_ids"] else None
    reference_payload = json.dumps({
        "referenced": reference.get("referenced_products"),
        "cards": reference.get("cards"), "comparison": reference.get("comparison"),
    }, default=str)
    checks["references"] = bool(target and reference["status"] == "product_reference" and target in reference_payload)
    details["references"] = {"target": target, "status": reference["status"]}

    # Soft preference must not become a chat-local hard brand constraint.
    chat = audit.create_chat()
    preference = snapshot(audit.message("I like Nike.", chat_id=chat))
    checks["preference"] = preference["status"] == "profile_updated" and not preference["state"].get("brands")
    details["preference"] = {"status": preference["status"], "hard_brands": preference["state"].get("brands")}

    # One real-catalogue outfit generation regression.
    chat = audit.create_chat()
    outfit = snapshot(audit.message("Build me a complete casual outfit for women under $500.", chat_id=chat))
    groups = outfit.get("latest_outfit_groups") or []
    outfit_ids = [
        str(product.get("product_id"))
        for group in groups for product in (group.get("products") or [])
        if product.get("product_id")
    ]
    totals = [group.get("total_price") for group in groups if group.get("total_price") is not None]
    checks["outfit"] = bool(
        outfit["http_status"] == 200 and outfit["engine"] == "n24" and groups and outfit_ids
        and all(float(total) <= 500.0 for total in totals)
    )
    details["outfit"] = {"status": outfit["status"], "looks": len(groups), "product_ids": outfit_ids, "totals": totals}

    # Chat A is persisted, Chat B is isolated, and a fresh login/token restores A.
    chat_a = audit.create_chat()
    state_a = snapshot(audit.message("Show me black Nike shoes under $80.", chat_id=chat_a))["state"]
    chat_b = audit.create_chat()
    state_b = snapshot(audit.message("Show me watches.", chat_id=chat_b))["state"]
    isolated_b = (
        {str(x).casefold() for x in state_b.get("categories", [])} == {"watches"}
        and not state_b.get("brands") and not state_b.get("colours")
        and state_b.get("minimum_price") is None and state_b.get("maximum_price") is None
    )
    if checks["auth"]:
        audit.token = login_payload["token"]
    restored_workspace = audit.select_chat(chat_a)
    restored_payload = (
        (restored_workspace.get("loaded_chat") or {}).get("active_request_state")
        or {}
    )
    restored = _restored_hard_request(restored_payload)
    expected_fields = ("categories", "brands", "colours", "minimum_price", "maximum_price")
    persistence_ok = all(restored.get(key) == state_a.get(key) for key in expected_fields)
    checks["persistence"] = persistence_ok
    checks["cross_chat_isolation"] = isolated_b and persistence_ok
    details["persistence_cross_chat"] = {
        "chat_a": chat_a, "chat_b": chat_b, "state_a": state_a,
        "state_b": state_b, "restored_state_a": restored_payload,
        "restored_hard_request": restored,
    }

    report = {
        "suite": "N24M2 focused regression only", "checks": checks,
        "passed": sum(checks.values()), "failed": sum(not value for value in checks.values()),
        "all_passed": all(checks.values()), "details": details,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "focused_regression.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    print("REGRESSION_SUMMARY=" + json.dumps({key: report[key] for key in ("checks", "passed", "failed", "all_passed")}), flush=True)
    return report


def recheck_saved_persistence_contract():
    """Re-evaluate the last live run using the documented nested state envelope."""
    path = OUTPUT_DIR / "focused_regression.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    detail = report["details"]["persistence_cross_chat"]
    state_a = detail["state_a"]
    state_b = detail["state_b"]
    restored = _restored_hard_request(detail["restored_state_a"])
    fields = ("categories", "brands", "colours", "minimum_price", "maximum_price")
    persisted = all(restored.get(key) == state_a.get(key) for key in fields)
    isolated = (
        {str(x).casefold() for x in state_b.get("categories", [])} == {"watches"}
        and not state_b.get("brands") and not state_b.get("colours")
        and state_b.get("minimum_price") is None and state_b.get("maximum_price") is None
    )
    detail["restored_hard_request"] = restored
    report["checks"]["persistence"] = persisted
    report["checks"]["cross_chat_isolation"] = persisted and isolated
    report["passed"] = sum(report["checks"].values())
    report["failed"] = sum(not value for value in report["checks"].values())
    report["all_passed"] = all(report["checks"].values())
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    run_regression(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000")
