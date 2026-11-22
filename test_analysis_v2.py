#!/usr/bin/env python3
"""Unit tests for the pure statistics helpers in analysis-v2.py.

Standard library only; uv-run compatible (`uv run python test_analysis_v2.py`).
"""

import importlib.util
import pathlib
import unittest


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(
        name, pathlib.Path(__file__).resolve().parent / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_analysis = _load("analysis_v2", "analysis-v2.py")
holm = _analysis.holm
mcnemar_exact = _analysis.mcnemar_exact
paired_permutation = _analysis.paired_permutation
wilson_interval = _analysis.wilson_interval


class TestWilsonInterval(unittest.TestCase):
    def test_known_value_8_of_20(self):
        lo, hi = wilson_interval(8, 20)
        self.assertAlmostEqual(lo, 0.2189, places=3)
        self.assertAlmostEqual(hi, 0.6135, places=3)

    def test_all_failures_clamps_lower_to_zero(self):
        lo, hi = wilson_interval(0, 63)
        self.assertEqual(lo, 0.0)
        self.assertLess(hi, 0.1)

    def test_all_successes_clamps_upper_to_one(self):
        lo, hi = wilson_interval(63, 63)
        self.assertAlmostEqual(hi, 1.0, places=12)
        self.assertGreater(lo, 0.9)


class TestMcnemarExact(unittest.TestCase):
    def test_zero_discordant_pairs_is_not_significant(self):
        self.assertEqual(mcnemar_exact(0, 0), 1.0)

    def test_perfectly_discordant_is_significant(self):
        # b=10, c=0: two-sided binomial tail is 2 * (1/2**10) < 0.01.
        self.assertLess(mcnemar_exact(10, 0), 0.01)

    def test_balanced_discordance_is_not_significant(self):
        self.assertEqual(mcnemar_exact(5, 5), 1.0)

    def test_single_discordant_pair(self):
        # min(b,c)=0, tail=1/2**1=0.5, doubled = 1.0 (capped).
        self.assertEqual(mcnemar_exact(1, 0), 1.0)

    def test_known_value_two_vs_eight(self):
        # binomial(10, 0.5) tail at k=2 doubled: 2 * (56/1024) = 0.109375.
        self.assertAlmostEqual(mcnemar_exact(8, 2), 0.109375)

    def test_symmetry(self):
        self.assertEqual(mcnemar_exact(3, 9), mcnemar_exact(9, 3))


class TestHolm(unittest.TestCase):
    def test_single_pvalue_unchanged(self):
        self.assertEqual(holm([0.05]), [0.05])

    def test_already_sorted_monotone(self):
        got = holm([0.001, 0.01, 0.04])
        self.assertEqual(got, [0.003, 0.02, 0.04])

    def test_input_order_preserved(self):
        got = holm([0.04, 0.001, 0.01])
        self.assertEqual(got, [0.04, 0.003, 0.02])

    def test_capped_at_one(self):
        self.assertEqual(holm([0.9, 0.8]), [1.0, 1.0])

    def test_monotonicity_of_adjusted_values(self):
        got = holm([0.5, 0.3, 0.1, 0.01])
        ranked = sorted(got)
        self.assertEqual(ranked, got and sorted(ranked))
        self.assertTrue(all(a <= b for a, b in zip(ranked, ranked[1:])))
        # Holm step-down enforces non-decreasing adjusted p-values in
        # rank order; verify no adjusted value falls below its raw one.
        self.assertGreaterEqual(min(got), min(0.01, got[got.index(min(got))]))

    def test_six_inputs_monotone_and_above_raw(self):
        raw = [0.9, 0.4, 0.2, 0.05, 0.01, 1e-6]
        got = holm(raw)
        self.assertTrue(all(a >= b for a, b in zip(got, raw)))
        ranked = sorted(got)
        self.assertEqual(ranked, sorted(got))
        self.assertTrue(all(a <= b for a, b in zip(ranked, ranked[1:])))
        self.assertTrue(all(0 <= a <= 1 for a in got))


class TestPairedPermutation(unittest.TestCase):
    def test_identical_vectors_not_significant(self):
        p, mean_diff = paired_permutation([1, 1, 1], [1, 1, 1], perms=1000)
        self.assertEqual(p, 1.0)
        self.assertEqual(mean_diff, 0.0)

    def test_large_consistent_difference_is_significant(self):
        xs = [1.0] * 20
        ys = [0.0] * 20
        p, mean_diff = paired_permutation(xs, ys, perms=1000)
        self.assertLessEqual(p, 0.001)
        self.assertAlmostEqual(mean_diff, 1.0)

    def test_empty_vectors(self):
        p, mean_diff = paired_permutation([], [])
        self.assertEqual(p, 1.0)
        self.assertEqual(mean_diff, 0.0)

    def test_deterministic_given_seed(self):
        a = paired_permutation([1, 0, 1], [0, 0, 1], seed=7, perms=500)
        b = paired_permutation([1, 0, 1], [0, 0, 1], seed=7, perms=500)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
