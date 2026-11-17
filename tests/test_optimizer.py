"""Tests unitarios para el optimizador de asignación de CEDEARs."""

import unittest
from cedear_allocator.optimizer import optimize_allocation


class TestOptimizer(unittest.TestCase):
    def test_basic_allocation(self):
        budget = 100_000.0
        prices = {"SPY": 20_000.0, "VEA": 10_000.0, "IEMG": 10_000.0}
        weights = {"SPY": 70, "VEA": 20, "IEMG": 10}

        res = optimize_allocation(budget, prices, weights)

        self.assertLessEqual(res.invested_ars, budget)
        self.assertGreaterEqual(res.cash_leftover_ars, 0.0)
        self.assertEqual(res.invested_ars + res.cash_leftover_ars, budget)

        # SPY objetivo 70k -> ~3 nominales (60k) o 4 (80k)
        # VEA objetivo 20k -> 2 nominales (20k)
        # IEMG objetivo 10k -> 1 nominal (10k)
        nom_map = {p.ticker: p.nominales for p in res.positions}
        self.assertGreater(nom_map["SPY"], 0)
        self.assertGreater(nom_map["VEA"], 0)
        self.assertGreater(nom_map["IEMG"], 0)

    def test_small_budget_no_overspending(self):
        # Presupuesto menor que el precio de un SPY
        budget = 15_000.0
        prices = {"SPY": 20_000.0, "VEA": 10_000.0, "IEMG": 5_000.0}
        weights = {"SPY": 0.7, "VEA": 0.2, "IEMG": 0.1}

        res = optimize_allocation(budget, prices, weights)
        self.assertLessEqual(res.invested_ars, budget)
        nom_map = {p.ticker: p.nominales for p in res.positions}
        self.assertEqual(nom_map["SPY"], 0)
        self.assertGreater(nom_map["VEA"] + nom_map["IEMG"], 0)

    def test_zero_prices_ignored(self):
        budget = 50_000.0
        prices = {"SPY": 20_000.0, "VEA": 0.0}
        weights = {"SPY": 0.8, "VEA": 0.2}

        res = optimize_allocation(budget, prices, weights)
        self.assertLessEqual(res.invested_ars, budget)
        self.assertEqual(len(res.positions), 1)
        self.assertEqual(res.positions[0].ticker, "SPY")


if __name__ == "__main__":
    unittest.main()
