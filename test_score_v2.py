#!/usr/bin/env python3
"""Unit tests for the pure scoring helpers in recipe/score-v2.py.

Standard library only; uv-run compatible
(`uv run python test_score_v2.py`).
"""

import importlib.util
import sys
import unittest
from pathlib import Path


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_score = _load("score_v2", Path(__file__).resolve().parent / "recipe" / "score-v2.py")
cluster_label_map = _score.cluster_label_map
extract_answer = _score.extract_answer
norm_set = _score.norm_set
normalize = _score.normalize
score_answer = _score.score_answer


class TestNormalize(unittest.TestCase):
    def test_lowercase_and_whitespace(self):
        self.assertEqual(normalize("  Agent  Ready "), "agent ready")

    def test_json_suffix_stripped(self):
        self.assertEqual(normalize("post.json"), "post")

    def test_non_json_suffix_kept(self):
        self.assertEqual(normalize("post.md"), "post.md")


class TestNormSet(unittest.TestCase):
    def test_dedupes_and_ignores_non_strings(self):
        self.assertEqual(norm_set(["A.json", "a.json", 3, None]), {"a"})


class TestExtractAnswer(unittest.TestCase):
    def test_plain_json(self):
        ans, found = extract_answer('{"answer": ["a.json"]}', False)
        self.assertTrue(found)
        self.assertEqual(ans, ["a.json"])

    def test_fenced_json(self):
        text = "Reasoning here.\n```json\n{\"answer\": \"x\"}\n```\n"
        ans, found = extract_answer(text, False)
        self.assertTrue(found)
        self.assertEqual(ans, "x")

    def test_embedded_json_content_first(self):
        text = 'Prefix {"answer": "first"} suffix'
        ans, _ = extract_answer(text, reasoning_fallback=False)
        self.assertEqual(ans, "first")

    def test_embedded_json_reasoning_fallback_takes_last(self):
        text = '{"answer": "first"} then {"answer": "second"}'
        ans, _ = extract_answer(text, reasoning_fallback=True)
        self.assertEqual(ans, "second")

    def test_no_json_is_not_found(self):
        ans, found = extract_answer("no structured answer here", False)
        self.assertFalse(found)
        self.assertIsNone(ans)

    def test_empty_string(self):
        self.assertEqual(extract_answer("", False), (None, False))


class TestScoreAnswer(unittest.TestCase):
    def test_f1_set_equality_exact(self):
        exact, dice = score_answer("F1", ["a.json", "b.json"], ["B.json", "A.json", "A.json"])
        self.assertEqual(exact, 1)
        self.assertEqual(dice, 1.0)

    def test_f1_partial_overlap(self):
        exact, dice = score_answer("F1", ["a.json", "b.json"], ["a.json"])
        self.assertEqual(exact, 0)
        self.assertAlmostEqual(dice, 2 * 1 / 3)

    def test_f1_empty_answer(self):
        exact, dice = score_answer("F1", ["a.json"], [])
        self.assertEqual((exact, dice), (0, 0.0))

    def test_f2_counts(self):
        truth = {"inbound": 3, "outbound": 5}
        exact, dice = score_answer("F2", truth, {"inbound": 3, "outbound": 5})
        self.assertEqual((exact, dice), (1, 1.0))

    def test_f2_one_of_two_counts(self):
        truth = {"inbound": 3, "outbound": 5}
        exact, dice = score_answer("F2", truth, {"inbound": 3, "outbound": 9})
        self.assertEqual((exact, dice), (0, 0.5))

    def test_f2_non_dict_answer(self):
        exact, dice = score_answer("F2", {"inbound": 3, "outbound": 5}, "nope")
        self.assertEqual((exact, dice), (0, 0.0))

    def test_f4_label_mapping(self):
        labels = {"cluster-a": "cluster-a", "cluster a": "cluster-a"}
        exact, dice = score_answer("F4", ["cluster-a"], ["Cluster A"], labels=labels)
        self.assertEqual((exact, dice), (1, 1.0))

    def test_f4_requires_labels(self):
        exact, dice = score_answer("F4", ["cluster-a"], ["cluster-a"], labels=None)
        self.assertEqual((exact, dice), (0, 0.0))


class TestClusterLabelMap(unittest.TestCase):
    def test_bidirectional_mapping(self):
        snapshot = {"clusters": [{"id": "c1", "name": "Agent Infrastructure"}]}
        labels = cluster_label_map(snapshot)
        self.assertEqual(labels["c1"], "c1")
        self.assertEqual(labels["agent infrastructure"], "c1")


if __name__ == "__main__":
    unittest.main()
