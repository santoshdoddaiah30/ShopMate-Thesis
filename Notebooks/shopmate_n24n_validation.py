"""Focused reproducible validation for the N24N notebook runtime.

Execute this file inside the fully loaded ``Thesis_clean.ipynb`` namespace.
It uses dedicated chats and the real local HTTP API.  It does not retrain or
modify the frozen recommender.
"""

from __future__ import annotations

import json as _n24nv_json
import urllib.request as _n24nv_urlrequest


def run_n24n_live_acceptance(user_id: int = 24, top_n: int = 5) -> dict:
    token = create_shopmate_api_session(
        user_id=user_id,
        workspace=load_authenticated_workspace(user_id),
    )

    def turn(chat_id: int, message: str) -> dict:
        request = _n24nv_urlrequest.Request(
            "http://127.0.0.1:8000/api/messages",
            data=_n24nv_json.dumps({
                "chat_id": chat_id, "message_text": message, "top_n": top_n,
            }).encode("utf-8"),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        with _n24nv_urlrequest.urlopen(request, timeout=300) as response:
            return _n24nv_json.load(response)["workspace"]

    def new_chat(title: str) -> int:
        return int(create_chat_session(user_id, title=title)["chat_id"])

    results = {"planner": run_n24n_deterministic_tests(), "cases": {}}

    chat_a = new_chat("N24N validation A")
    a1 = turn(chat_a, "i need red shirt")
    pending = _n24m3_pending_offer(chat_a)
    a2 = turn(chat_a, "ok show me mixed") if pending is not None else None
    results["cases"]["A"] = {
        "passed": pending is None or (
            a2["response_status"] in {"recommendations", "no_exact_match"}
            and _n24m3_pending_offer(chat_a) is None
        ),
        "strict_status": a1["response_status"],
        "mixed_was_groundedly_offered": pending is not None,
        "followup_status": None if a2 is None else a2["response_status"],
    }

    chat_b = new_chat("N24N validation B")
    turn(chat_b, "i need black nike shoes")
    b2 = turn(chat_b, "ok suggest me men all black shoes")
    _, _, b_state, _ = n24l_load_persistent_state(chat_b, user_id)
    b_cards = b2.get("product_cards") or []
    results["cases"]["B"] = {
        "passed": (
            b_state.hard_request.categories == ["Shoes"]
            and b_state.hard_request.brands == []
            and b_state.hard_request.colours == ["black"]
            and b_state.hard_request.recipient == "men"
            and _n24m_sidecar(chat_b).get("colour_mode") == "MONOCHROME"
            and all(set(card.get("colour_components") or []) <= {"black"} for card in b_cards)
        ),
        "product_ids": [card.get("product_id") for card in b_cards],
    }

    chat_c = new_chat("N24N validation C")
    c = turn(chat_c, "show me white shoes")
    c_cards = c.get("product_cards") or []
    unsafe = [card for card in c_cards if "white mountain" in str(card.get("title", "")).casefold()
              or "white ledge" in str(card.get("title", "")).casefold()]
    results["cases"]["C"] = {"passed": not unsafe, "unsafe_ids": [x.get("product_id") for x in unsafe]}

    chat_d = new_chat("N24N validation D")
    d = turn(chat_d, "show me men's shoes")
    d_cards = d.get("product_cards") or []
    results["cases"]["D"] = {
        "passed": bool(d_cards) and all(card.get("audience") == "MEN" for card in d_cards),
        "audiences": [card.get("audience") for card in d_cards],
    }

    chat_e = new_chat("N24N validation E")
    e = turn(chat_e, "all black shoes")
    e_cards = e.get("product_cards") or []
    results["cases"]["E"] = {
        "passed": (
            _n24m_sidecar(chat_e).get("colour_mode") == "MONOCHROME"
            and not _n24m_sidecar(chat_e).get("allow_mixed_colours")
            and all(set(card.get("colour_components") or []) <= {"black"} for card in e_cards)
        ),
        "product_ids": [card.get("product_id") for card in e_cards],
    }

    results["passed"] = results["planner"]["passed"] and all(
        case["passed"] for case in results["cases"].values()
    )
    return results


print("N24N validation helpers loaded; call run_n24n_live_acceptance().")
