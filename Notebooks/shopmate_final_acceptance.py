"""Final real-API acceptance and independent catalogue validation for ShopMate.

Execute inside the fully loaded authoritative notebook namespace. The runner
creates dedicated chats for an existing test user and writes reproducible
CSV/JSON/Markdown artifacts. It never retrains or changes the frozen ranker.
"""

from __future__ import annotations

from datetime import datetime as _sfa_datetime, timezone as _sfa_timezone
import json as _sfa_json
from pathlib import Path as _SFAPath
import statistics as _sfa_statistics
import re as _sfa_re
import urllib.request as _sfa_urlrequest

import pandas as _sfa_pd


SFA_VERSION = "shopmate_final_application_acceptance_v2_raw_category_oracle"
SFA_ROOT = _SFAPath(r"C:\Users\santo\Desktop\Thesis\Results\Final_Application_Acceptance")


def run_shopmate_final_acceptance(user_id: int = 24, top_n: int = 5) -> dict:
    SFA_ROOT.mkdir(parents=True, exist_ok=True)
    token = create_shopmate_api_session(user_id=user_id, workspace=load_authenticated_workspace(user_id))
    catalogue_ids = set(application_request_metadata_df["product_id"].astype(str))
    rows, scenarios = [], []

    raw_family_patterns = {
        "SHIRTS": r"\b(?:shirt|t[ -]?shirt|tee|polo|blouse)\b",
        "SHOES": r"\b(?:shoe|sneaker|boot|sandal|slipper|loafer|footwear)\b",
        "WATCHES": r"\b(?:watch|wristwatch|timepiece)\b",
        "HANDBAGS": r"\b(?:handbag|purse|tote|clutch|wallet)\b",
        "DRESSES": r"\b(?:dress|gown)\b",
        "JEWELRY": r"\b(?:jewelry|jewellery|ring|necklace|bracelet|earring)\b",
        "BEAUTY": r"\b(?:razor|shav(?:e|er|ing)|cosmetic|makeup|lipstick|mascara|perfume|fragrance)\b",
    }
    requested_families = {
        "shirts":"SHIRTS", "t-shirts":"SHIRTS", "shoes":"SHOES",
        "watches":"WATCHES", "handbags & wallets":"HANDBAGS",
        "dresses":"DRESSES", "rings":"JEWELRY", "earrings":"JEWELRY",
        "necklaces":"JEWELRY", "bracelets":"JEWELRY",
    }

    def independent_raw_category_ok(product, request):
        if request is None or not request.categories:
            return True, None
        row = product.get("row", {})
        title = str(row.get("title") or "")
        main = str(row.get("main_category") or "")
        observed = {name for name, pattern in raw_family_patterns.items()
                    if _sfa_re.search(pattern, title, flags=_sfa_re.I)}
        if _sfa_re.search(r"beauty|personal care", main, flags=_sfa_re.I):
            observed.add("BEAUTY")
        for category in request.categories:
            wanted = requested_families.get(str(category).casefold())
            conflicts = observed - ({wanted} if wanted else set())
            if wanted and conflicts and wanted not in observed:
                return False, f"raw_product_family_conflict:{','.join(sorted(conflicts))}"
        return True, None

    def api(chat_id, message):
        req = _sfa_urlrequest.Request(
            "http://127.0.0.1:8000/api/messages",
            data=_sfa_json.dumps({"chat_id": chat_id, "message_text": message, "top_n": top_n}).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        started = __import__("time").perf_counter()
        with _sfa_urlrequest.urlopen(req, timeout=300) as response:
            workspace = _sfa_json.load(response)["workspace"]
        return workspace, __import__("time").perf_counter() - started

    def new_chat(label):
        return int(create_chat_session(user_id, title=f"Final acceptance {label}")["chat_id"])

    def evidence(chat_id, workspace):
        _, payload, state, active = n24l_load_persistent_state(chat_id, user_id)
        cards = workspace.get("product_cards") or []
        product_ids = [str(card.get("product_id")) for card in cards]
        real = all(pid in catalogue_ids for pid in product_ids)
        raw_ok, eligibility_ok, violations = True, True, []
        request = None
        if active is not None:
            entry = _n24d_get_entry(active.result_set_id, chat_id)
            request = entry["validated_request"]
        sidecar = _n24m_sidecar(chat_id)
        for card in cards:
            pid = str(card.get("product_id"))
            product = N24M2_TRUSTED_CATALOGUE_INDEX.get(pid)
            if product is None:
                raw_ok = False
                violations.append(f"{pid}:missing_trusted_product")
                continue
            card_price = card.get("price")
            raw_price = product.get("price")
            if card_price is not None and raw_price is not None and abs(float(card_price) - float(raw_price)) > 0.001:
                raw_ok = False; violations.append(f"{pid}:price_mismatch")
            card_rating = card.get("rating", card.get("average_rating"))
            raw_rating = product.get("rating")
            if card_rating is not None and raw_rating is not None and abs(float(card_rating) - float(raw_rating)) > 0.001:
                raw_ok = False; violations.append(f"{pid}:rating_mismatch")
            if request is not None:
                assessment = evaluate_n24_product_eligibility(pid, request, sidecar)
                if not assessment.eligible:
                    eligibility_ok = False
                    violations.append(f"{pid}:trusted_ineligible")
                raw_category_ok, raw_reason = independent_raw_category_ok(product, request)
                if not raw_category_ok:
                    raw_ok = False
                    violations.append(f"{pid}:{raw_reason}")
            title = str(card.get("title") or "").casefold()
            if request is not None and request.colours and "white" in [x.casefold() for x in request.colours]:
                if "white mountain" in title or "white ledge" in title:
                    eligibility_ok = False; violations.append(f"{pid}:unsafe_white_name")
        return state, active, cards, {
            "real_product_ids": real, "raw_price_rating_match": raw_ok,
            "trusted_eligibility": eligibility_ok, "violations": violations,
        }

    def turn(sid, family, chat_id, number, message, expected, check):
        workspace, wall = api(chat_id, message)
        state, active, cards, ev = evidence(chat_id, workspace)
        try:
            behavior_ok, notes = check(workspace, state, active, cards, ev)
        except Exception as error:
            behavior_ok, notes = False, f"validator_error:{type(error).__name__}:{error}"
        grounding_ok = ev["real_product_ids"] and ev["raw_price_rating_match"] and ev["trusted_eligibility"]
        status = "PASS" if behavior_ok and grounding_ok else "FAIL"
        row = {
            "scenario_id": sid, "family": family, "chat_id": chat_id, "turn": number,
            "message": message, "expected": expected,
            "response_status": workspace.get("response_status"),
            "assistant_message": workspace.get("assistant_message"),
            "hard_state_json": _sfa_json.dumps(state.hard_request.model_dump(mode="json"), sort_keys=True),
            "product_ids_json": _sfa_json.dumps([c.get("product_id") for c in cards]),
            "product_count": len(cards), "outfit_group_count": len(workspace.get("latest_outfit_groups") or []),
            "constraint_verification": grounding_ok, "violations_json": _sfa_json.dumps(ev["violations"]),
            "behavior_ok": behavior_ok, "latency_seconds": round(float(workspace.get("response_seconds") or wall), 6),
            "ollama_calls": int((workspace.get("n24_metadata", {}).get("ollama_calls") or {}).get("total", 0)),
            "status": status, "notes": notes,
        }
        rows.append(row); print(_sfa_json.dumps({k: row[k] for k in ("scenario_id","turn","status","response_status","product_count","latency_seconds","notes")}), flush=True)
        return workspace, state, active, cards, ev

    def simple_check(category=None, brand=None, colour=None, recipient=None, max_price=None, min_rating=None, monochrome=False):
        def check(workspace, state, active, cards, ev):
            hard = state.hard_request
            ok = True; notes = []
            if category is not None: ok &= category in hard.categories
            if brand is not None: ok &= any(str(x).casefold().startswith(brand.casefold()) for x in hard.brands)
            if colour is not None: ok &= colour.casefold() in [str(x).casefold() for x in hard.colours]
            if recipient is not None: ok &= hard.recipient == recipient
            if max_price is not None: ok &= hard.maximum_price == max_price
            if min_rating is not None: ok &= _n24m_sidecar(active.chat_id if active else 0).get("minimum_rating") == min_rating
            if monochrome:
                ok &= all(set(card.get("colour_components") or []) <= {colour} for card in cards)
            return bool(ok), "hard state and product evidence verified" if ok else "hard-state mismatch"
        return check

    basics = [
        ("F001","Shoes","show me shoes"),("F002","Shirts","show me shirts"),
        ("F003","Dresses","show me dresses"),
        ("F005","Handbags & Wallets","show me handbags"),
    ]
    for sid, category, message in basics:
        chat = new_chat(sid); turn(sid,"basic_search",chat,1,message,f"category {category}",simple_check(category=category))

    chat = new_chat("F004")
    def beauty_check(w,s,a,c,e):
        text=(w.get("assistant_message") or "").casefold()
        return w.get("response_status")=="clarification" and "not represented" in text and not c,"honest unsupported catalogue category"
    turn("F004","basic_search",chat,1,"show me beauty products","honestly state catalogue limitation",beauty_check)

    hard_cases = [
        ("F006","show me black Nike shoes",dict(category="Shoes",brand="Nike",colour="black")),
        ("F007","show me white shoes",dict(category="Shoes",colour="white")),
        ("F008","show me men's black shoes",dict(category="Shoes",colour="black",recipient="men")),
        ("F009","show me women's black shoes",dict(category="Shoes",colour="black",recipient="women")),
        ("F010","show me red shoes for men under $100",dict(category="Shoes",colour="red",recipient="men",max_price=100.0)),
        ("F011","all black shoes",dict(category="Shoes",colour="black",monochrome=True)),
    ]
    for sid, message, kwargs in hard_cases:
        chat = new_chat(sid); turn(sid,"hard_constraints",chat,1,message,"all explicit hard constraints",simple_check(**kwargs))

    chat = new_chat("F012")
    turn("F012","refinement",chat,1,"show me black Nike shoes","initial Nike/black/shoes",simple_check(category="Shoes",brand="Nike",colour="black"))
    turn("F012","refinement",chat,2,"under 100 dollars","retain prior constraints plus budget",simple_check(category="Shoes",brand="Nike",colour="black",max_price=100.0))

    chat = new_chat("F013")
    turn("F013","reformulation",chat,1,"show me black Nike shoes","initial search",simple_check(category="Shoes",brand="Nike",colour="black"))
    def reform_check(w,s,a,c,e):
        h=s.hard_request; ok=h.categories==["Shoes"] and h.brands==[] and h.colours==["black"] and h.recipient=="men" and _n24m_sidecar(a.chat_id if a else 0).get("colour_mode")=="MONOCHROME"; return ok,"stale brand cleared"
    turn("F013","reformulation",chat,2,"show me men's all-black shoes","clear Nike; retain black Shoes; add men",reform_check)

    chat = new_chat("F014")
    first=turn("F014","show_more",chat,1,"show me shoes","base result set",simple_check(category="Shoes"))
    first_ids={c.get("product_id") for c in first[3]}
    def more_check(w,s,a,c,e): return not (first_ids & {x.get("product_id") for x in c}) and s.hard_request.categories==["Shoes"],"no duplicates and state unchanged"
    turn("F014","show_more",chat,2,"show me more","distinct continuation",more_check)

    chat = new_chat("F015")
    turn("F015","comparison_questions",chat,1,"show me watches","base watches",simple_check(category="Watches"))
    def comparison_check(w,s,a,c,e): return w.get("response_status")=="comparison" and bool(w.get("comparison")),"grounded comparison object present"
    turn("F015","comparison_questions",chat,2,"compare the first two","compare grounded facts",comparison_check)
    def question_check(w,s,a,c,e): return s.hard_request.categories==["Watches"] and bool(c),"state unchanged and grounded referenced cards"
    turn("F015","comparison_questions",chat,3,"which one is cheaper?","grounded relative question",question_check)

    chat = new_chat("F016")
    turn("F016","pending_relaxation",chat,1,"i need red shirt","offer mixed only if verified",lambda w,s,a,c,e:(not (_n24m3_pending_offer(chat) and not (w.get("assistant_message") or "").casefold().find("mixed")>=0),"offer state consistent"))
    if _n24m3_pending_offer(chat):
        turn("F016","pending_relaxation",chat,2,"ok show me mixed","consume pending exactly once",lambda w,s,a,c,e:(_n24m3_pending_offer(chat) is None,"pending consumed"))

    chat = new_chat("F017")
    for number, message in enumerate(["is the first one in stock?","what is today's Amazon price?","can it arrive tomorrow?","is there a coupon?"],1):
        def unsupported_check(w,s,a,c,e):
            text=(w.get("assistant_message") or "").casefold(); return w.get("response_status")=="unsupported_data" and any(x in text for x in ("not contain","does not contain","unavailable","cannot verify","not live")),"unsupported data stated honestly"
        turn("F017","unsupported",chat,number,message,"no live commerce fabrication",unsupported_check)

    chat = new_chat("F018")
    def outfit_check(w,s,a,c,e):
        groups=w.get("latest_outfit_groups") or []; ids=[p.get("product_id") for g in groups for p in (g.get("products") or [])]; return len(groups)>=3 and all(x in catalogue_ids for x in ids),"three real catalogue outfit groups"
    turn("F018","outfits",chat,1,"put together a casual outfit for men","three coherent real-product looks",outfit_check)
    turn("F018","outfits",chat,2,"show me another outfit","distinct outfit follow-up",lambda w,s,a,c,e:(len(w.get("latest_outfit_groups") or [])>=4,"additional group returned"))

    chat = new_chat("F019")
    turn("F019","personalization",chat,1,"I like Nike","save soft preference",lambda w,s,a,c,e:(w.get("response_status")=="profile_updated" and not s.hard_request.brands,"soft preference only"))
    turn("F019","personalization",chat,2,"show me Adidas shoes","hard request overrides Nike preference",simple_check(category="Shoes",brand="adidas"))

    chat = new_chat("F020")
    turn("F020","persistence",chat,1,"show me black shoes","persist request/results",simple_check(category="Shoes",colour="black"))
    _, payload_before, state_before, active_before = n24l_load_persistent_state(chat,user_id)
    N24_RUNTIME_CHAT_RESULT_IDS.pop(chat,None)
    _, payload_after, state_after, active_after = n24l_load_persistent_state(chat,user_id)
    persistence_ok = state_before.hard_request == state_after.hard_request and active_after is not None
    rows.append({"scenario_id":"F020","family":"persistence","chat_id":chat,"turn":2,"message":"reload persisted conversation","expected":"same hard state and restored result set","response_status":"restored","assistant_message":"","hard_state_json":_sfa_json.dumps(state_after.hard_request.model_dump(mode="json"),sort_keys=True),"product_ids_json":_sfa_json.dumps([] if active_after is None else active_after.ordered_product_ids),"product_count":0 if active_after is None else len(active_after.ordered_product_ids),"outfit_group_count":0,"constraint_verification":persistence_ok,"violations_json":"[]","behavior_ok":persistence_ok,"latency_seconds":0.0,"ollama_calls":0,"status":"PASS" if persistence_ok else "FAIL","notes":"persistent state/result restoration"})

    # Regression for the exact browser conversation and a fresh-chat control.
    chat = new_chat("F021")
    turn("F021","cross_category_live",chat,1,"i need black nike shoes","valid footwear",simple_check(category="Shoes",brand="Nike",colour="black"))
    turn("F021","cross_category_live",chat,2,"i need red shirt","zero or independently proven shirts",simple_check(category="Shirts",colour="red"))
    turn("F021","cross_category_live",chat,3,"i need black shirt","never return another product family",simple_check(category="Shirts",colour="black"))
    chat = new_chat("F022")
    turn("F022","cross_category_live",chat,1,"i need black shirt","fresh chat never returns another product family",simple_check(category="Shirts",colour="black"))

    # Actual catalogue IDs selected from independent raw titles/main_category.
    adversaries = {
        "razor":"B0743MHZX2", "shirt":"B008L1J7YU", "shoe":"B071RZFKJR",
        "watch":"B01GNVW8MC", "handbag":"B09F348NC5", "jewelry":"B075LLJQZY",
        "perfume":"B07X1TK3VS",
    }
    adversarial_matrix = {
        "Shirts":["razor","perfume","shoe","watch","handbag","jewelry"],
        "Shoes":["shirt","razor","perfume","jewelry"],
        "Watches":["shirt","razor","shoe"],
    }
    audit_number = 0
    for requested, names in adversarial_matrix.items():
        for name in names:
            audit_number += 1
            pid = adversaries[name]
            request = N24ValidatedRecommendationRequest(
                profile_id="category_audit", categories=[requested],
                request_display_text=f"raw adversarial {requested}",
                request_fingerprint="sha256:" + f"{audit_number:064x}",
            )
            assessment = evaluate_n24_trusted_eligibility(pid, request, _n24m_default_sidecar())
            ok = not assessment.eligible
            rows.append({"scenario_id":f"A{audit_number:03d}","family":"raw_category_adversarial","chat_id":0,"turn":1,"message":f"{requested} vs raw {name}","expected":"category rejection","response_status":"offline_raw_oracle","assistant_message":"","hard_state_json":"{}","product_ids_json":_sfa_json.dumps([pid]),"product_count":0,"outfit_group_count":0,"constraint_verification":ok,"violations_json":"[]" if ok else _sfa_json.dumps([f"{pid}:cross_category_survived"]),"behavior_ok":ok,"latency_seconds":0.0,"ollama_calls":0,"status":"PASS" if ok else "FAIL","notes":"independent raw title/main_category adversary"})

    frame = _sfa_pd.DataFrame(rows)
    scenario_frame = frame.groupby(["scenario_id","family"],as_index=False).agg(
        turns=("turn","count"), status=("status",lambda s:"PASS" if (s=="PASS").all() else "FAIL"),
        mean_latency_seconds=("latency_seconds","mean"), product_count=("product_count","sum"),
    )
    frame.to_csv(SFA_ROOT/"acceptance_turn_results.csv",index=False)
    scenario_frame.to_csv(SFA_ROOT/"acceptance_scenario_summary.csv",index=False)
    latencies=[float(x) for x in frame.loc[frame["latency_seconds"]>0,"latency_seconds"]]
    summary={
        "version":SFA_VERSION,"generated_at":_sfa_datetime.now(_sfa_timezone.utc).isoformat(),
        "scenario_count":int(len(scenario_frame)),"turn_count":int(len(frame)),
        "pass":int((scenario_frame.status=="PASS").sum()),"fail":int((scenario_frame.status=="FAIL").sum()),
        "hard_constraint_violations":int(frame["violations_json"].apply(lambda x:len(_sfa_json.loads(x))).sum()),
        "average_latency_seconds":round(_sfa_statistics.mean(latencies),3),
        "median_latency_seconds":round(_sfa_statistics.median(latencies),3),
        "zero_result_turns":int((frame.product_count==0).sum()),
        "files":{"turns":"acceptance_turn_results.csv","scenarios":"acceptance_scenario_summary.csv"},
    }
    (SFA_ROOT/"acceptance_summary.json").write_text(_sfa_json.dumps(summary,indent=2),encoding="utf-8")
    (SFA_ROOT/"acceptance_report.md").write_text(
        "# Final ShopMate application acceptance\n\n"+
        "Generated: "+summary["generated_at"]+"\n\n"+
        f"Scenarios: {summary['scenario_count']} | PASS: {summary['pass']} | FAIL: {summary['fail']}\n\n"+
        f"Turns: {summary['turn_count']} | Hard-constraint/evidence violations: {summary['hard_constraint_violations']}\n\n"+
        f"Mean latency: {summary['average_latency_seconds']} s | Median: {summary['median_latency_seconds']} s\n",
        encoding="utf-8",
    )
    print(_sfa_json.dumps(summary,indent=2),flush=True)
    return {"summary":summary,"turns":frame,"scenarios":scenario_frame}


print("Final ShopMate acceptance runner loaded; call run_shopmate_final_acceptance().")
