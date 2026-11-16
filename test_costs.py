"""Behaviour checks. AI assistance: ChatGPT, 2026-11-16."""
import unittest
from costs import calculate_monthly_cost, calculate_ranking_score, salary_to_hourly_value


class CostTests(unittest.TestCase):
    def test_worked_example(self):
        value = salary_to_hourly_value(78000, 40)
        self.assertAlmostEqual(value, 37.5)
        result = calculate_monthly_cost(1800, 150, 30, 20, value)
        self.assertAlmostEqual(result["commute_hours_monthly"], 20)
        self.assertAlmostEqual(result["cash_cost_monthly"], 1950)
        self.assertAlmostEqual(result["total_cost_monthly"], 2700)

    def test_home_working_preserves_pass_cost(self):
        result = calculate_monthly_cost(1800, 150, 30, 0, 40)
        self.assertEqual(result["time_cost_monthly"], 0)
        self.assertEqual(result["total_cost_monthly"], 1950)

    def test_zero_time_valuation(self):
        result = calculate_monthly_cost(1800, 150, 30, 20, 0)
        self.assertEqual(result["total_cost_monthly"], 1950)

    def test_annual_pass_conversion(self):
        result = calculate_monthly_cost(1800, 1200 / 12, 0, 20, 40)
        self.assertEqual(result["cash_cost_monthly"], 1900)

    def test_score_rewards_underpricing_and_penalises_overpricing(self):
        self.assertEqual(calculate_ranking_score(2700, 1800, 2000, 0.5), 2600)
        self.assertEqual(calculate_ranking_score(2700, 1800, 1600, 0.5), 2800)
        self.assertEqual(calculate_ranking_score(2700, 1800, 1800, 1), 2700)

    def test_missing_model_allowed_only_when_disabled(self):
        self.assertEqual(calculate_ranking_score(2700, 1800, None, 0), 2700)
        with self.assertRaises(ValueError):
            calculate_ranking_score(2700, 1800, None, 1)

    def test_invalid_cost_inputs(self):
        for index in range(5):
            for bad in (-1, float("nan"), float("inf"), None, "10", True):
                args = [1800, 150, 30, 20, 40]
                args[index] = bad
                with self.subTest(index=index, bad=bad), self.assertRaises(ValueError):
                    calculate_monthly_cost(*args)
        with self.assertRaises(ValueError):
            calculate_monthly_cost(1800, 150, 30, 32, 40)

    def test_invalid_salary_and_weight(self):
        with self.assertRaises(ValueError):
            salary_to_hourly_value(78000, 0)
        with self.assertRaises(ValueError):
            salary_to_hourly_value(78000, 40, 1.5)
        with self.assertRaises(ValueError):
            calculate_ranking_score(2700, 1800, 2000, -1)

    def test_more_commuting_increases_total_not_cash(self):
        shorter = calculate_monthly_cost(1800, 150, 15, 20, 40)
        longer = calculate_monthly_cost(1800, 150, 45, 20, 40)
        self.assertEqual(shorter["cash_cost_monthly"], longer["cash_cost_monthly"])
        self.assertAlmostEqual(longer["total_cost_monthly"] - shorter["total_cost_monthly"], 800)


if __name__ == "__main__":
    unittest.main()
