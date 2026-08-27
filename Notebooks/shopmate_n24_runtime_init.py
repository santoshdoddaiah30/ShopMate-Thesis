"""Deterministic ShopMate N24 application-layer bootstrap.

Run this only after the historical notebook definitions through N24K are
present in the target namespace.  It installs the authoritative L -> M -> M2
-> M3 -> N chain exactly once from reviewed source files, explicitly wiring
each layer to its immediate predecessor.  Embedded report/test invocations
are deliberately excluded; validation is a separate operation.

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
    required_base = {
        "n24l_interpret_turn", "_n24l_compose",
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

    bindings = {
        "interpret": namespace["n24l_interpret_turn"].__code__.co_filename,
        "compose": namespace["_n24l_compose"].__code__.co_filename,
        "recommender": namespace[
            "get_n24_recommendations_from_validated_state"
        ].__code__.co_filename,
        "pre_build_request": namespace["n24m_pre_build_request"].__code__.co_filename,
    }
    if not bindings["interpret"].endswith("shopmate_n24n_conversation_planner.py"):
        raise RuntimeError(f"Unexpected N24 interpreter binding: {bindings['interpret']}")
    if not bindings["compose"].endswith("shopmate_n24n_conversation_planner.py"):
        raise RuntimeError(f"Unexpected N24 composer binding: {bindings['compose']}")
    return {
        "bootstrap_version": N24_RUNTIME_BOOTSTRAP_VERSION,
        "layer_order": list(_LAYER_FILES),
        "bindings": bindings,
        "engine": namespace.get("SHOPMATE_ENGINE"),
        "n23_modified": False,
    }

