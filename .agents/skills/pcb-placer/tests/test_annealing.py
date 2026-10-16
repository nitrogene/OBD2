import sys
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from simulated_annealing import FastAnnealingEngine
from export_geometry import BoardGeometrySnapshot, ComponentGeometry, PadGeometry


class TestAnnealingPhysics(unittest.TestCase):
    def test_annealing_run_synthetic(self):
        manifest = {
            "packages": {
                "0603": {"width_mm": 1.6, "length_mm": 0.8, "courtyard_margin_mm": 0.2}
            },
            "components": {
                "C1": {"package": "0603", "emc_class": "aggressor"},
                "U1": {"package": "0603", "emc_class": "victim"},
                "D1": {"package": "0603"}
            },
            "placement_constraints": [
                {
                    "id": "LOOP_1",
                    "type": "loop",
                    "members": [{"ref": "C1", "pin": "1"}, {"ref": "U1", "pin": "1"}],
                    "return_members": [{"ref": "D1", "pin": "1"}],
                    "target_max_area_mm2": 25.0,
                    "target_max_inductance_nH": 8.0,
                    "weight": 8.0
                },
                {
                    "id": "RET_1",
                    "type": "return_path_proximity",
                    "signal_net": "SIG_SW",
                    "reference_net": "GND",
                    "max_distance_to_reference_mm": 4.0,
                    "weight": 7.0
                }
            ]
        }
        board_constraints = {
            "board": {"width_mm": 40.0, "height_mm": 30.0, "edge_clearance_mm": 1.0},
            "anchors": {},
            "keepout_zones": [
                {
                    "id": "KO_RF",
                    "name": "KO_RF",
                    "rect_mm": {"x_min": 32.0, "x_max": 40.0, "y_min": 10.0, "y_max": 20.0}
                }
            ],
            "separation_rules": [
                {
                    "id": "SEP_1",
                    "group_a": {"emc_class": "aggressor"},
                    "group_b": {"zone": "KO_RF"},
                    "min_distance_mm": 10.0,
                    "coupling": "H_field",
                    "weight": 6.0
                }
            ],
            "net_classes": {
                "SW": {"nets": ["SIG_SW"], "emc_class": "aggressor"}
            }
        }
        comps = {
            "C1": ComponentGeometry("C1", "p1", "0603", 5.0, 5.0, 0.0, 1, False, [PadGeometry("1", "SIG_SW", 5.0, 5.0, 0.0, 0.0)]),
            "U1": ComponentGeometry("U1", "p2", "0603", 10.0, 5.0, 0.0, 1, False, [PadGeometry("1", "GND", 10.0, 5.0, 0.0, 0.0)]),
            "D1": ComponentGeometry("D1", "p3", "0603", 7.5, 9.0, 0.0, 1, False, [PadGeometry("1", "GND", 7.5, 9.0, 0.0, 0.0)])
        }
        nets = {
            "SIG_SW": [("C1", "1")],
            "GND": [("U1", "1"), ("D1", "1")]
        }
        geom = BoardGeometrySnapshot("now", 3, 3, 2, {}, comps, nets)

        engine = FastAnnealingEngine(manifest, board_constraints, geom, spacing_margin_mm=0.2)
        initial_prox = engine.compute_proximity_and_loop_penalties()
        self.assertGreaterEqual(initial_prox, 0.0)

        # Exécution d'un cycle court
        res_positions = engine.run(steps=300, t_start=20.0, t_end=0.1, seed=42)
        self.assertEqual(len(res_positions), 3)

        for des, pos in res_positions.items():
            self.assertGreaterEqual(pos["x_mm"], 1.0)
            self.assertLessEqual(pos["x_mm"], 39.0)
            self.assertGreaterEqual(pos["y_mm"], 1.0)
            self.assertLessEqual(pos["y_mm"], 29.0)


if __name__ == "__main__":
    unittest.main()
