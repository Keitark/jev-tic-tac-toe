import unittest

from tic_lab.benchmark import (
    exact_binomial_two_sided,
    exact_binomial_upper,
    run_benchmark,
    summarize,
)


class BenchmarkTests(unittest.TestCase):
    def test_exact_binomial(self):
        self.assertAlmostEqual(exact_binomial_upper(10, 0), 1 / 1024)
        self.assertAlmostEqual(exact_binomial_two_sided(10, 0), 2 / 1024)
        self.assertEqual(exact_binomial_two_sided(5, 5), 1.0)

    def test_alternates_subject_color(self):
        results, summary = run_benchmark(
            games=10,
            subject="legal-random",
            opponent="legal-random",
            seed=123,
            prompt_mode="minimal",
            illegal_policy="retry",
            max_illegal_streak=20,
            progress_every=0,
        )
        self.assertEqual(sum(r.subject_mark == "X" for r in results), 5)
        self.assertEqual(sum(r.subject_mark == "O" for r in results), 5)
        self.assertEqual(summary["by_subject_mark"]["X"]["games"], 5)
        self.assertEqual(summary["by_subject_mark"]["O"]["games"], 5)

    def test_legal_random_never_makes_illegal_move(self):
        _, summary = run_benchmark(
            games=20,
            subject="legal-random",
            opponent="legal-random",
            seed=7,
            prompt_mode="minimal",
            illegal_policy="forfeit",
            max_illegal_streak=20,
            progress_every=0,
        )
        self.assertEqual(summary["subject_illegal"], 0)
        self.assertEqual(summary["subject_illegal_rate"], 0.0)

    def test_summary_score_rate(self):
        results, _ = run_benchmark(
            games=4,
            subject="legal-random",
            opponent="legal-random",
            seed=99,
            prompt_mode="minimal",
            illegal_policy="retry",
            max_illegal_streak=20,
            progress_every=0,
        )
        summary = summarize(results, "legal-random", "legal-random", "retry")
        expected = (summary["wins"] + 0.5 * summary["draws"]) / summary["games"]
        self.assertAlmostEqual(summary["score_rate"], expected)


if __name__ == "__main__":
    unittest.main()
