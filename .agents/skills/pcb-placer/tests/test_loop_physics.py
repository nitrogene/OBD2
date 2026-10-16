#!/usr/bin/env python3
"""
Tests unitaires pour les calculs physiques CEM (Shoelace, inductance de boucle, décroissance 1/r³ et 1/r²).
Compatible avec pytest et python -m unittest.
"""

import math
import sys
import unittest
from pathlib import Path

# S'assurer que le répertoire du skill est accessible
SKILL_DIR = Path(__file__).resolve().parent.parent
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from emc_physics import (
    polygon_area_shoelace,
    loop_perimeter,
    estimate_loop_inductance_nh,
    magnetic_field_coupling,
    electric_field_coupling,
    decoupling_effective_inductance_nh
)


class TestLoopPhysics(unittest.TestCase):
    """Tests des fonctions de calcul physique de boucle et de champ."""

    def test_shoelace_triangle(self):
        # Triangle rectangle de base 4 mm et hauteur 3 mm -> aire = 6.0 mm²
        pts = [(0.0, 0.0), (4.0, 0.0), (0.0, 3.0)]
        self.assertAlmostEqual(polygon_area_shoelace(pts), 6.0)

    def test_shoelace_rectangle(self):
        # Rectangle 10 mm x 5 mm -> aire = 50.0 mm², périmètre = 30.0 mm
        pts = [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)]
        self.assertAlmostEqual(polygon_area_shoelace(pts), 50.0)
        self.assertAlmostEqual(loop_perimeter(pts), 30.0)

    def test_shoelace_collinear_degenerate(self):
        # Points colinéaires (aire = 0)
        pts = [(0.0, 0.0), (5.0, 5.0), (10.0, 10.0)]
        self.assertAlmostEqual(polygon_area_shoelace(pts), 0.0)

    def test_shoelace_clockwise_counterclockwise_invariance(self):
        pts_ccw = [(0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0)]
        pts_cw = [(0.0, 0.0), (0.0, 3.0), (4.0, 3.0), (4.0, 0.0)]
        self.assertAlmostEqual(polygon_area_shoelace(pts_ccw), polygon_area_shoelace(pts_cw))

    def test_loop_inductance_scaling(self):
        # Boucle compacte 10 mm x 5 mm (typiquement ~8-15 nH)
        compact_loop = [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)]
        l_compact = estimate_loop_inductance_nh(compact_loop)
        self.assertGreater(l_compact, 2.0)
        self.assertLess(l_compact, 25.0)

        # Une grande boucle de 30 mm x 20 mm doit avoir une inductance nettement plus grande
        large_loop = [(0.0, 0.0), (30.0, 0.0), (30.0, 20.0), (0.0, 20.0)]
        l_large = estimate_loop_inductance_nh(large_loop)
        self.assertGreater(l_large, l_compact)

    def test_magnetic_field_decay_and_orthogonality(self):
        # Couplage à 2 mm vs couplage à 10 mm (décroissance dipolaire rapide)
        c_near = magnetic_field_coupling(dist_mm=2.0, orientation_deg_1=0.0, orientation_deg_2=0.0)
        c_far = magnetic_field_coupling(dist_mm=10.0, orientation_deg_1=0.0, orientation_deg_2=0.0)
        # Ratio théorique (1/5)³ = 1/125
        self.assertGreater(c_near / c_far, 50.0)

        # Orthogonalité : composants à 90° ont un couplage atténué par rapport à des composants parallèles
        c_parallel = magnetic_field_coupling(dist_mm=5.0, orientation_deg_1=0.0, orientation_deg_2=0.0)
        c_orthogonal = magnetic_field_coupling(dist_mm=5.0, orientation_deg_1=0.0, orientation_deg_2=90.0)
        self.assertLess(c_orthogonal, c_parallel * 0.3)

    def test_electric_field_decay(self):
        # Décroissance capacitive en 1/r²
        e_1mm = electric_field_coupling(dist_mm=1.0)
        e_2mm = electric_field_coupling(dist_mm=2.0)
        self.assertAlmostEqual(e_1mm, 1.0)
        self.assertAlmostEqual(e_2mm, 0.25)

    def test_decoupling_effective_inductance(self):
        # Distance 1 mm vs distance 5 mm
        l_1mm = decoupling_effective_inductance_nh(dist_mm=1.0, via_count=2)
        l_5mm = decoupling_effective_inductance_nh(dist_mm=5.0, via_count=2)
        # Chaque mm ajoute environ 0.8 nH
        self.assertAlmostEqual(l_5mm - l_1mm, 4.0 * 0.8, places=2)


if __name__ == "__main__":
    unittest.main()
