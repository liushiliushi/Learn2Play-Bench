import unittest

from games.modelkeeper.modelkeeper import (
    ECHO,
    GATE,
    HOLD,
    MIX,
    EXPERT_CONFIG,
    ExpertReferenceSolver,
    ModelkeeperGame,
    _expert_dependencies_are_load_bearing,
    simulate,
)


class ExpertStructureTests(unittest.TestCase):
    def test_public_shape_and_controlled_topology(self):
        saw_four = saw_five = False
        for seed in range(40):
            game = ModelkeeperGame(seed=seed, mode="expert", lang="en")
            machine = game._machine
            self.assertEqual(machine.n_inputs, 3)
            self.assertEqual(len(machine.readout_ids), 2)
            self.assertIn(len(machine.nodes), (4, 5))
            saw_four |= len(machine.nodes) == 4
            saw_five |= len(machine.nodes) == 5

            driver, shared = machine.nodes[:2]
            self.assertIn(driver.kind, (GATE, MIX))
            self.assertEqual(len(driver.sources), 2)
            self.assertTrue(all(src[0] == "in" for src in driver.sources))
            self.assertEqual(len(set(driver.sources)), 2)
            if driver.kind == GATE:
                self.assertEqual(driver.signs, [1, 1])

            self.assertIn(shared.kind, (HOLD, ECHO))
            self.assertEqual(shared.sources, [("node", 0)])
            if shared.kind == HOLD:
                self.assertEqual(shared.cap, 2)

            visible = [machine.nodes[rid] for rid in machine.readout_ids]
            self.assertTrue(all(("node", 1) in node.sources for node in visible))
            anchors = [node for node in visible
                       if node.kind == MIX
                       and len(node.sources) == 2
                       and ("node", 1) in node.sources
                       and any(src[0] == "in" for src in node.sources)]
            self.assertTrue(anchors)
            self.assertTrue(_expert_dependencies_are_load_bearing(
                machine, game._exam_inputs))
        self.assertTrue(saw_four)
        self.assertTrue(saw_five)

    def test_generation_is_deterministic(self):
        a = ModelkeeperGame(seed=42, mode="expert")
        b = ModelkeeperGame(seed=42, mode="expert")
        self.assertEqual(a._machine, b._machine)
        self.assertEqual(a._exam_inputs, b._exam_inputs)
        self.assertEqual(a._exam_true, b._exam_true)


class ExpertSolverTests(unittest.TestCase):
    def test_battery_is_exactly_forty_probes(self):
        ops = ExpertReferenceSolver(EXPERT_CONFIG)._battery(3, 3)
        self.assertEqual(sum(op[0] == "tick" for op in ops), 40)

    def test_certified_solver_is_exact(self):
        solver = ExpertReferenceSolver(EXPERT_CONFIG)
        for seed in range(30):
            game = ModelkeeperGame(seed=seed, mode="expert")
            ok, probes, fitted = solver.solve(game._machine, game._exam_inputs)
            self.assertTrue(ok, seed)
            self.assertLessEqual(probes, EXPERT_CONFIG.probe_budget)
            self.assertEqual(simulate(fitted, game._exam_inputs), game._exam_true)

    def test_all_exam_columns_vary(self):
        for seed in range(30):
            game = ModelkeeperGame(seed=seed, mode="expert")
            for col in range(2):
                self.assertGreater(len({row[col] for row in game._exam_true}), 1)


class ExpertSurfaceTests(unittest.TestCase):
    def test_mode_and_surface(self):
        game = ModelkeeperGame(seed=7, mode="expert", lang="en")
        intro, info = game.reset()
        self.assertEqual(game.mode, "expert")
        self.assertEqual(game.cfg.family, "expert")
        self.assertIn("40 probes", intro)
        self.assertNotIn("GATE", intro)
        self.assertNotIn("HOLD", intro)
        self.assertIn("exam", info["valid"])
        self.assertEqual(
            [a for a in game.get_valid_actions() if a.startswith("probe ")],
            [f"probe {a} {b} {c}"
             for a in range(3) for b in range(3) for c in range(3)],
        )

    def test_existing_modes_keep_their_configs(self):
        self.assertEqual(ModelkeeperGame(seed=1).cfg.family, "standard")
        self.assertEqual(ModelkeeperGame(seed=1, mode="hard").cfg.family, "hard")


if __name__ == "__main__":
    unittest.main()
