"""Deterministic ShopMate N24 application-layer bootstrap.

Run this once the N24C validated-state adapter
(get_n24_recommendations_from_validated_state) is present in the target
namespace.  It installs the authoritative L -> M -> M2 -> M3 -> N chain
exactly once from reviewed source files, explicitly wiring each layer to its
immediate predecessor.  Embedded report/test invocations are deliberately
excluded; validation is a separate operation.

This chain has no dependency on the notebook's N24I/N24I1/N24J/N24K cells in
either direction, so it may run before or after them; N24I1's own live
outfit-adapter self-test does depend on this bootstrap having already run
(it calls n24_filter_outfit_candidates_with_canonical_truth, installed here
by M2), so in practice this should run before N24I1.

The bootstrap does not train, tune, or mutate the frozen N23 recommender.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, MutableMapping


N24_RUNTIME_BOOTSTRAP_VERSION = "n24_option_b_runtime_bootstrap_v1"

_LAYER_FILES = (
    "shopmate_n24l_backend.py",
    "shopmate_n24m_semantics.py",
    "shopmate_n24m2_truth.py",
    "shopmate_n24m3_visual_relaxation.py",
    "shopmate_n24n_conversation_planner.py",
)


def _is_embedded_report_node(node: ast.stmt) -> bool:
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        function = node.value.func
        return isinstance(function, ast.Name) and function.id in {"print", "display"}
    if not isinstance(node, (ast.Assign, ast.AnnAssign)):
        return False
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    names = {target.id for target in targets if isinstance(target, ast.Name)}
    return any("TEST_REPORT" in name or "INTEGRATION_STATUS" in name for name in names)


def _execute_layer(path: Path, namespace: MutableMapping[str, Any]) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    tree.body = [node for node in tree.body if not _is_embedded_report_node(node)]
    ast.fix_missing_locations(tree)
    exec(compile(tree, str(path), "exec"), namespace, namespace)


def initialize_shopmate_n24_application(
    namespace: MutableMapping[str, Any],
    *,
    source_directory: str | Path | None = None,
) -> dict[str, Any]:
    """Install and verify the single authoritative N24 application chain."""
    source_root = Path(source_directory or Path(__file__).resolve().parent)
    missing = [name for name in _LAYER_FILES if not (source_root / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing N24 layer sources: {missing}")
    # Only "get_n24_recommendations_from_validated_state" genuinely predates L:
    # it is defined by the N24C validated-state adapter. "n24l_interpret_turn"
    # and "_n24l_compose" are NOT pre-L definitions -- they are first defined
    # inside shopmate_n24l_backend.py itself (L is the very file this function
    # is about to load), so requiring them beforehand made this precondition
    # unsatisfiable on any namespace where L has never been loaded before.
    required_base = {
        "get_n24_recommendations_from_validated_state",
    }
    absent = sorted(required_base - set(namespace))
    if absent:
        raise RuntimeError(
            "Historical notebook definitions through N24K must be loaded first; "
            f"missing {absent}."
        )

    _execute_layer(source_root / _LAYER_FILES[0], namespace)
    _execute_layer(source_root / _LAYER_FILES[1], namespace)

    # M2 wraps the deterministic parser and price parser.  Rebind explicitly
    # on every initialization so a warm notebook reload cannot retain an old
    # function object from a previous source version.
    namespace["N24M2_BASE_DETERMINISTIC_INTERPRETER"] = namespace[
        "interpret_n24m_deterministic_turn"
    ]
    namespace["N24M2_BASE_PRICE_OPERATIONS"] = namespace["_n24m_price_operations"]
    _execute_layer(source_root / _LAYER_FILES[2], namespace)

    namespace["N24M3_BASE_INTERPRET_TURN"] = namespace["n24l_interpret_turn"]
    namespace["N24M3_BASE_COMPOSE"] = namespace["_n24l_compose"]
    namespace["N24M3_BASE_RECOMMENDER"] = namespace[
        "get_n24_recommendations_from_validated_state"
    ]
    _execute_layer(source_root / _LAYER_FILES[3], namespace)

    namespace["N24N_BASE_INTERPRET_TURN"] = namespace["n24l_interpret_turn"]
    namespace["N24N_BASE_COMPOSE"] = namespace["_n24l_compose"]
    _execute_layer(source_root / _LAYER_FILES[4], namespace)

    # Post-bootstrap validation: the L->M->M2->M3->N chain must have actually
    # installed the live semantic symbols downstream N24 integrations (e.g.
    # the N24I1 outfit adapter) depend on -- not just the conversation-layer
    # bindings. Checked after loading, never before: these names do not
    # exist until M2 has run.
    required_post = ("n24_filter_outfit_candidates_with_canonical_truth",)
    absent_post = sorted(name for name in required_post if name not in namespace)
    if absent_post:
        raise RuntimeError(
            f"N24 bootstrap completed without installing expected symbols: {absent_post}."
        )

    bindings = {
        "interpret": namespace["n24l_interpret_turn"].__code__.co_filename,
        "compose": namespace["_n24l_compose"].__code__.co_filename,
        "recommender": namespace[
            "get_n24_recommendations_from_validated_state"
        ].__code__.co_filename,
        "pre_build_request": namespace["n24m_pre_build_request"].__code__.co_filename,
        "outfit_canonical_filter": namespace[
            "n24_filter_outfit_candidates_with_canonical_truth"
        ].__code__.co_filename,
    }
    if not bindings["interpret"].endswith("shopmate_n24n_conversation_planner.py"):
        raise RuntimeError(f"Unexpected N24 interpreter binding: {bindings['interpret']}")
    if not bindings["compose"].endswith("shopmate_n24n_conversation_planner.py"):
        raise RuntimeError(f"Unexpected N24 composer binding: {bindings['compose']}")
    if not bindings["outfit_canonical_filter"].endswith("shopmate_n24m2_truth.py"):
        raise RuntimeError(
            f"Unexpected outfit canonical-filter binding: {bindings['outfit_canonical_filter']}"
        )
    return {
        "bootstrap_version": N24_RUNTIME_BOOTSTRAP_VERSION,
        "layer_order": list(_LAYER_FILES),
        "bindings": bindings,
        "engine": namespace.get("SHOPMATE_ENGINE"),
        "n23_modified": False,
    }


def finalize_n24_server_routes(
    namespace: MutableMapping[str, Any],
) -> dict[str, Any]:
    """Bind and verify N24 routes after the final FastAPI app is created.

    Server-startup notebook cells replace ``shopmate_api`` after the semantic
    bootstrap has run.  This finalizer deliberately installs routes only; it
    never reloads semantic layers or rebuilds recommender/catalogue state.
    """
    required = {
        "shopmate_api", "install_n24l_message_route",
        "shopmate_process_message_endpoint_n24l",
        "dispatch_shopmate_workspace_message", "process_workspace_message_n24",
        "n24l_execute_turn", "get_shopmate_engine",
    }
    absent = sorted(required - set(namespace))
    if absent:
        raise RuntimeError(f"Cannot finalize N24 server routes; missing {absent}.")
    if namespace["get_shopmate_engine"]() != "n24":
        raise RuntimeError("N24 route finalization requires the N24 engine.")

    namespace["install_n24l_message_route"]()
    message_routes = [
        route for route in namespace["shopmate_api"].router.routes
        if getattr(route, "path", None) == "/api/messages"
        and "POST" in (getattr(route, "methods", set()) or set())
    ]
    if len(message_routes) != 1:
        raise RuntimeError(
            f"Expected exactly one POST /api/messages route; found {len(message_routes)}."
        )
    endpoint = message_routes[0].endpoint
    expected_endpoint = namespace["shopmate_process_message_endpoint_n24l"]
    if endpoint is not expected_endpoint:
        raise RuntimeError(f"Unexpected POST /api/messages endpoint: {endpoint!r}.")

    dispatch = namespace["dispatch_shopmate_workspace_message"]
    process_n24 = namespace["process_workspace_message_n24"]
    execute_turn = namespace["n24l_execute_turn"]
    dispatch_verified = (
        dispatch.__globals__.get("process_workspace_message_n24") is process_n24
        and process_n24.__globals__.get("n24l_execute_turn") is execute_turn
    )
    if not dispatch_verified:
        raise RuntimeError("The N24 HTTP dispatch chain does not reach n24l_execute_turn.")

    return {
        "route_count": 1,
        "path": "/api/messages",
        "methods": sorted(message_routes[0].methods),
        "endpoint": endpoint.__name__,
        "endpoint_source": endpoint.__code__.co_filename,
        "dispatch_reaches_n24l_execute_turn": True,
        "semantic_bootstrap_rerun": False,
        "n23_modified": False,
    }
