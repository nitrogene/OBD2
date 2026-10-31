#!/usr/bin/env python3
"""
Tests unitaires pour dsn_updater.py (Mise à jour agnostique des pastilles DSN).
Compatible pytest et python -m unittest.
"""

import math
import sys
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from dsn_updater import DsnPlacementUpdater, rotate_vector


class TestDsnUpdater(unittest.TestCase):
    """Tests unitaires pour DsnPlacementUpdater."""

    def setUp(self):
        # DSN factice minimal avec 1 composant C1 ayant 2 pastilles
        # C1 initialement à (10 mm, 20 mm), rotation 0°
        # pad 1 à (9 mm, 20 mm) -> offset dx_0 = -1 mm, dy_0 = 0 mm
        # pad 2 à (11 mm, 20 mm) -> offset dx_0 = +1 mm, dy_0 = 0 mm
        # 10 mm = 393.70 mil, 9 mm = 354.33 mil, 11 mm = 433.07 mil, 20 mm = 787.40 mil
        self.mock_dsn = """(pcb test
  (parser (string_quote "))
  (resolution mil 1000)
  (library
    (image u1
      (pin rect_pad pad_c1_1 354.33 787.40)
      (pin rect_pad pad_c1_2 433.07 787.40)
    )
  )
  (network
    (net Net_1 (pins u1-pad_c1_1))
    (net Net_2 (pins u1-pad_c1_2))
  )
)"""
        self.mock_geom = {
            "components": {
                "C1": {
                    "designator": "C1",
                    "x_mm": 10.0,
                    "y_mm": 20.0,
                    "rotation": 0.0,
                    "pads": [
                        {
                            "number": "1",
                            "x_mm": 9.0,
                            "y_mm": 20.0,
                            "dx_0_mm": -1.0,
                            "dy_0_mm": 0.0
                        },
                        {
                            "number": "2",
                            "x_mm": 11.0,
                            "y_mm": 20.0,
                            "dx_0_mm": 1.0,
                            "dy_0_mm": 0.0
                        }
                    ]
                }
            }
        }

    def test_correlation_and_translation(self):
        """Vérifie la mise à jour des coordonnées après une simple translation (sans rotation)."""
        updater = DsnPlacementUpdater(self.mock_dsn, self.mock_geom)
        self.assertEqual(updater.total_correlated_pads, 2)

        # Nouveau placement : C1 translaté à (30 mm, 40 mm), rotation 0°
        # pad 1 attendu à 29 mm (1141.73 mil), 40 mm (1574.80 mil)
        # pad 2 attendu à 31 mm (1220.47 mil), 40 mm (1574.80 mil)
        new_placement = {
            "components": {
                "C1": {"x_mm": 30.0, "y_mm": 40.0, "rotation": 0.0}
            }
        }
        updated = updater.update_placement(new_placement)

        self.assertIn("(pin rect_pad pad_c1_1 1141.73 1574.8)", updated)
        self.assertIn("(pin rect_pad pad_c1_2 1220.47 1574.8)", updated)
        self.assertNotIn("354.33", updated)
        self.assertNotIn("433.07", updated)

    def test_rotation_90_degrees(self):
        """Vérifie la rotation à 90° : (dx, dy) = (-1, 0) devient (0, -1)."""
        updater = DsnPlacementUpdater(self.mock_dsn, self.mock_geom)

        # Nouveau placement : C1 à (30 mm, 40 mm), rotation 90°
        # pad 1 attendu à (30 + 0, 40 + (-1)) = (30 mm, 39 mm) -> (1181.10 mil, 1535.43 mil)
        # pad 2 attendu à (30 + 0, 40 + (+1)) = (30 mm, 41 mm) -> (1181.10 mil, 1614.17 mil)
        # et (rotate 90) injecté sur les deux pastilles
        new_placement = {
            "components": {
                "C1": {"x_mm": 30.0, "y_mm": 40.0, "rotation": 90.0}
            }
        }
        updated = updater.update_placement(new_placement)

        self.assertIn("(pin rect_pad pad_c1_1 1181.1 1535.43 (rotate 90.0))", updated)
        self.assertIn("(pin rect_pad pad_c1_2 1181.1 1614.17 (rotate 90.0))", updated)


if __name__ == "__main__":
    unittest.main()
