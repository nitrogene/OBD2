import sys
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from score import RectBox, ScoreMetrics, PCBScorer
from export_geometry import BoardGeometrySnapshot, ComponentGeometry, PadGeometry


class TestScorePhysics(unittest.TestCase):
    def test_rectbox_distance_to_box(self):
        b1 = RectBox(0.0, 10.0, 0.0, 10.0)
        # b2 disjoint à droite (x: 15 à 20, y: 0 à 10) -> distance dx = 5.0, dy = 0.0 -> dist = 5.0
        b2 = RectBox(15.0, 20.0, 0.0, 10.0)
        self.assertAlmostEqual(b1.distance_to_box(b2), 5.0, places=3)

        # b3 disjoint en diagonale (x: 13 à 20, y: 14 à 20) -> dx = 3.0, dy = 4.0 -> dist = 5.0
        b3 = RectBox(13.0, 20.0, 14.0, 20.0)
        self.assertAlmostEqual(b1.distance_to_box(b3), 5.0, places=3)

        # b4 chevauchant -> dist = 0.0
        b4 = RectBox(5.0, 15.0, 5.0, 15.0)
        self.assertEqual(b1.distance_to_box(b4), 0.0)

    def test_rectbox_distance_to_point(self):
        b = RectBox(10.0, 20.0, 10.0, 20.0)
        # Point à gauche (x=7, y=10) -> dx = 3.0, dy = 0 -> dist = 3.0
        self.assertAlmostEqual(b.distance_to_point(7.0, 10.0), 3.0, places=3)
        # Point à l'intérieur -> dist = 0.0
        self.assertEqual(b.distance_to_point(15.0, 15.0), 0.0)
        # Point en diagonale (x=23, y=24) -> dx = 3.0, dy = 4.0 -> dist = 5.0
        self.assertAlmostEqual(b.distance_to_point(23.0, 24.0), 5.0, places=3)

    def test_score_loop_metrics_evaluated(self):
        # Configuration synthétique minimale
        manifest = {
            "packages": {
                "0603": {"width_mm": 1.6, "length_mm": 0.8, "courtyard_margin_mm": 0.2}
            },
            "components": {
                "C1": {"package": "0603"},
                "U1": {"package": "0603"},
                "D1": {"package": "0603"}
            },
            "placement_constraints": [
                {
                    "id": "LOOP_TEST",
                    "type": "loop",
                    "members": [{"ref": "C1", "pin": "1"}, {"ref": "U1", "pin": "1"}],
                    "return_members": [{"ref": "D1", "pin": "1"}],
                    "target_max_area_mm2": 20.0,
                    "target_max_inductance_nH": 6.0
                }
            ]
        }
        board_constraints = {
            "board": {"width_mm": 50.0, "height_mm": 30.0, "edge_clearance_mm": 1.0},
            "anchors": {},
            "keepout_zones": [],
            "separation_rules": []
        }
        comps = {
            "C1": ComponentGeometry("C1", "p1", "0603", 10.0, 10.0, 0.0, 1, False, [PadGeometry("1", "NET1", 10.0, 10.0, 0.0, 0.0)]),
            "U1": ComponentGeometry("U1", "p2", "0603", 15.0, 10.0, 0.0, 1, False, [PadGeometry("1", "NET1", 15.0, 10.0, 0.0, 0.0)]),
            "D1": ComponentGeometry("D1", "p3", "0603", 12.5, 14.0, 0.0, 1, False, [PadGeometry("1", "NET2", 12.5, 14.0, 0.0, 0.0)])
        }
        geom = BoardGeometrySnapshot("now", 3, 3, 1, {}, comps, {})
        scorer = PCBScorer(manifest, board_constraints, geom)
        res = scorer.evaluate()

        self.assertGreater(res.score.loop_area_mm2, 0.0)
        self.assertGreater(res.score.loop_inductance_nh, 0.0)
        self.assertGreater(res.score.f_loops_compactness, 0.0)


if __name__ == "__main__":
    unittest.main()
