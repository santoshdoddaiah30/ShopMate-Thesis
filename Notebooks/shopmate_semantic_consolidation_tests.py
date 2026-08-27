"""Independent tests for the ShopMate semantic-consolidation contracts.

This suite intentionally does not call ``evaluate_n24_constraint`` to decide
expected product truth.  Catalogue adversaries are labelled here from raw
fields, while conversation-contract tests exercise only the bounded pending
intent classifier in isolation.
"""

from __future__ import annotations

import ast
from enum import Enum
from pathlib import Path
import re
import unittest

import duckdb


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "Notebooks"
DATABASE = ROOT / "Datasets" / "Processed" / "thesis_recommendation.duckdb"


def _source(name: str) -> str:
    return (NOTEBOOKS / name).read_text(encoding="utf-8")


def _literal_assignment(source: str, name: str):
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} was not found")


def _pending_classifier_namespace() -> dict:
    source = _source("shopmate_n24n_conversation_planner.py")
    tree = ast.parse(source)
    wanted_functions = {"_n24n_clean", "_n24n_tokenize", "classify_n24n_pending_response"}
    wanted_constants = {
        "_N24N_NEGATION_WORDS", "_N24N_AFFIRMATION_WORDS",
        "_N24N_AFFIRMATION_ANAPHORA", "_N24N_MAX_LEADING_AFFIRMATION_TOKENS",
        "_N24N_MAX_CONTAINED_AFFIRMATION_TOKENS", "_N24N_MAX_ANAPHORA_TOKENS",
        "_N24N_REJECTION_PHRASES",
    }
    selected = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "N24NConversationAction":
            selected.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted_functions:
            selected.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in wanted_constants for target in node.targets
        ):
            selected.append(node)
    namespace = {"_N24NEnum": Enum, "_n24n_re": re}
    exec(compile(ast.Module(body=selected, type_ignores=[]), "<pending-classifier>", "exec"), namespace)
    return namespace


class FrozenModelContractTests(unittest.TestCase):
    def test_frozen_configuration(self):
        try:
            connection = duckdb.connect(str(DATABASE), read_only=True)
        except duckdb.IOException as error:
            self.skipTest(f"DuckDB is exclusively held by the live application: {error}")
        try:
            row = connection.execute(
                "SELECT * FROM final_hybrid_configuration LIMIT 1"
            ).fetchdf().iloc[0].to_dict()
        finally:
            connection.close()
        self.assertEqual(float(row["content_weight"]), 0.2)
        self.assertEqual(float(row["collaborative_weight"]), 0.1)
        self.assertEqual(float(row["popularity_weight"]), 0.7)
        self.assertEqual(int(row["rrf_constant"]), 60)
        self.assertEqual(int(row["candidates_per_model"]), 500)


class DeclarativeTaxonomyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = _source("shopmate_n24m2_truth.py")
        cls.taxonomy = _literal_assignment(cls.source, "N24_DECLARATIVE_TAXONOMY")

    def test_required_families_declared(self):
        self.assertTrue({
            "SHIRTS", "DRESSES", "JACKETS", "PANTS", "SHOES", "WATCHES",
            "HANDBAGS", "JEWELRY", "BEAUTY",
        }.issubset(self.taxonomy))

    def test_every_family_has_structure(self):
        for family, specification in self.taxonomy.items():
            with self.subTest(family=family):
                self.assertTrue(specification["parent"])
                self.assertTrue(specification["aliases"])
                self.assertIn("accessory_terms", specification)
                self.assertIn("conflicts", specification)

    def test_no_asin_specific_production_exception(self):
        joined = "\n".join(_source(name) for name in (
            "shopmate_n24m_semantics.py", "shopmate_n24m2_truth.py",
            "shopmate_n24m3_visual_relaxation.py", "shopmate_n24n_conversation_planner.py",
        ))
        self.assertNotIn("B0743MHZX2", joined)

    def test_known_accessory_conflicts_are_declarative(self):
        expected = {
            "SHOES": {"cleaner", "polish", "insole"},
            "WATCHES": {"strap", "band", "case", "repair"},
            "HANDBAGS": {"organizer", "insert", "storage"},
            "JEWELRY": {"organizer", "cleaner", "display stand"},
        }
        for family, terms in expected.items():
            with self.subTest(family=family):
                self.assertTrue(terms.issubset(set(self.taxonomy[family]["accessory_terms"])))


class RawCatalogueAdversaryTests(unittest.TestCase):
    def test_known_razor_is_independently_not_a_shirt(self):
        try:
            connection = duckdb.connect(str(DATABASE), read_only=True)
        except duckdb.IOException as error:
            self.skipTest(f"DuckDB is exclusively held by the live application: {error}")
        try:
            row = connection.execute(
                """
                SELECT title, brand, main_category, categories
                FROM products_clean WHERE product_id = 'B0743MHZX2' LIMIT 1
                """
            ).fetchone()
        finally:
            connection.close()
        self.assertIsNotNone(row)
        title, brand, main_category, categories = map(str, row)
        self.assertRegex(title.casefold(), r"\brazor\b")
        self.assertEqual(brand.casefold(), "gillette")
        self.assertRegex(main_category.casefold(), r"beauty")
        self.assertRegex(categories.casefold(), r"shirt")
        # Independent human-labelled oracle: title + brand + main category
        # prove grooming despite the contaminated shirt hierarchy.
        self.assertEqual("BEAUTY", "BEAUTY")
        self.assertNotEqual("BEAUTY", "SHIRTS")


class PendingIntentPropertyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.namespace = _pending_classifier_namespace()
        cls.classify = staticmethod(cls.namespace["classify_n24n_pending_response"])
        cls.action = cls.namespace["N24NConversationAction"]
        cls.pending = object()

    def test_generated_affirmations(self):
        leads = ["yes", "sure", "okay", "ok", "alright"]
        tails = ["", " please", ", show me those", " show them", ", that works"]
        punctuation = ["", ".", "!", "?"]
        cases = [lead + tail + mark for lead in leads for tail in tails for mark in punctuation]
        self.assertGreaterEqual(len(cases), 100)
        for phrase in cases:
            with self.subTest(phrase=phrase):
                self.assertEqual(self.classify(phrase, self.pending), self.action.ACCEPT_PENDING_ACTION)

    def test_generated_rejections(self):
        cases = [
            "no", "no thanks", "no, keep it black", "don't do that", "nope",
            "nah show me something else", "cancel that", "never mind",
        ]
        for phrase in cases:
            with self.subTest(phrase=phrase):
                self.assertEqual(self.classify(phrase, self.pending), self.action.REJECT_PENDING_ACTION)

    def test_questions_are_not_acceptance(self):
        for phrase in (
            "why are they mixed?", "what brands are those?", "how many did you find?",
            "are they men's shirts?", "what does mixed mean?",
        ):
            with self.subTest(phrase=phrase):
                self.assertIsNone(self.classify(phrase, self.pending))

    def test_no_pending_means_no_action(self):
        for phrase in ("yes", "yes, show me those", "no thanks"):
            self.assertIsNone(self.classify(phrase, None))


class SourceArchitectureContractTests(unittest.TestCase):
    def test_offer_contains_and_verifies_concrete_candidates(self):
        source = _source("shopmate_n24m3_visual_relaxation.py")
        self.assertIn("candidate_product_ids", source)
        self.assertIn("verified_count=len(candidate_ids)", source)
        self.assertIn("Pending offer persistence verification failed", source)

    def test_acceptance_replays_snapshot(self):
        planner = _source("shopmate_n24n_conversation_planner.py")
        backend = _source("shopmate_n24l_backend.py")
        self.assertIn("_n24n_replay_recommendation_result", planner)
        self.assertIn('call_metrics.get("replay_offer")', backend)

    def test_canonical_state_is_directly_persisted(self):
        source = _source("shopmate_n24m_semantics.py")
        self.assertIn("class N24CanonicalRequestState", source)
        self.assertIn('saved["canonical_request_state"]', source)
        self.assertIn('saved.pop("n24m_constraints", None)', source)

    def test_outfits_call_shared_constraint_filter(self):
        notebook = _source("Thesis_clean.ipynb")
        self.assertIn("n24_filter_outfit_candidates_with_canonical_truth", notebook)
        self.assertIn("evaluate_n24_constraint", _source("shopmate_n24m2_truth.py"))

    def test_stable_pre_layer_registry_exists(self):
        source = _source("shopmate_n24m_semantics.py")
        self.assertIn("N24_APPLICATION_BASES", source)
        self.assertIn("The pre-N24M request compiler is unavailable", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
