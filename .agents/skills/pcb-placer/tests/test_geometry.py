#!/usr/bin/env python3
"""
Tests unitaires pour la géométrie 2D (RectBox, courtyards IPC, rotations).
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

from score import RectBox, rotate_offset, get_component_courtyard_box


class TestRectBox(unittest.TestCase):
    """Tests des primitives de boîte englobante 2D (RectBox)."""

    def test_properties(self):
        b = RectBox(x_min=1.0, x_max=5.0, y_min=2.0, y_max=8.0)
        self.assertAlmostEqual(b.width, 4.0)
        self.assertAlmostEqual(b.height, 6.0)
        self.assertAlmostEqual(b.area, 24.0)
        self.assertAlmostEqual(b.center[0], 3.0)
        self.assertAlmostEqual(b.center[1], 5.0)

    def test_disjoint_boxes(self):
        b1 = RectBox(0.0, 2.0, 0.0, 2.0)
        b2 = RectBox(3.0, 5.0, 3.0, 5.0)
        self.assertFalse(b1.intersects(b2))
        self.assertFalse(b2.intersects(b1))
        self.assertAlmostEqual(b1.intersection_area(b2), 0.0)

    def test_touching_edge_boxes(self):
        # Deux boîtes adjacentes partageant une frontière ne doivent pas être considérées en collision
        b1 = RectBox(0.0, 2.0, 0.0, 2.0)
        b2 = RectBox(2.0, 4.0, 0.0, 2.0)
        self.assertFalse(b1.intersects(b2))
        self.assertAlmostEqual(b1.intersection_area(b2), 0.0)

    def test_partial_overlap(self):
        b1 = RectBox(0.0, 3.0, 0.0, 3.0)
        b2 = RectBox(1.0, 4.0, 1.0, 4.0)
        self.assertTrue(b1.intersects(b2))
        # Recouvrement dx = 2.0, dy = 2.0 -> aire = 4.0 mm²
        self.assertAlmostEqual(b1.intersection_area(b2), 4.0)
        self.assertAlmostEqual(b2.intersection_area(b1), 4.0)

    def test_nested_box(self):
        outer = RectBox(0.0, 10.0, 0.0, 10.0)
        inner = RectBox(2.0, 5.0, 3.0, 7.0)
        self.assertTrue(outer.intersects(inner))
        self.assertAlmostEqual(outer.intersection_area(inner), 12.0)

    def test_negative_coordinates(self):
        b1 = RectBox(-5.0, -1.0, -4.0, 0.0)
        b2 = RectBox(-2.0, 2.0, -2.0, 2.0)
        self.assertTrue(b1.intersects(b2))
        # dx = min(-1, 2) - max(-5, -2) = -1 - (-2) = 1.0
        # dy = min(0, 2) - max(-4, -2) = 0 - (-2) = 2.0
        self.assertAlmostEqual(b1.intersection_area(b2), 2.0)


class TestRotationsAndCourtyards(unittest.TestCase):
    """Tests des rotations vectorielles et du calcul de courtyards IPC."""

    def test_rotate_offset_cardinal_angles(self):
        # Vecteur unitaire (1, 0)
        rx, ry = rotate_offset(1.0, 0.0, 0.0)
        self.assertAlmostEqual(rx, 1.0)
        self.assertAlmostEqual(ry, 0.0)

        rx, ry = rotate_offset(1.0, 0.0, 90.0)
        self.assertAlmostEqual(rx, 0.0)
        self.assertAlmostEqual(ry, 1.0)

        rx, ry = rotate_offset(1.0, 0.0, 180.0)
        self.assertAlmostEqual(rx, -1.0)
        self.assertAlmostEqual(ry, 0.0)

        rx, ry = rotate_offset(1.0, 0.0, 270.0)
        self.assertAlmostEqual(rx, 0.0)
        self.assertAlmostEqual(ry, -1.0)

    def test_courtyard_box_unrotated(self):
        pkg = {"width_mm": 2.0, "length_mm": 1.0, "courtyard_margin_mm": 0.25}
        box = get_component_courtyard_box(10.0, 20.0, 0.0, pkg)
        # Largeur avec marge = 2.0 + 2 * 0.25 = 2.5
        # Longueur avec marge = 1.0 + 2 * 0.25 = 1.5
        self.assertAlmostEqual(box.width, 2.5)
        self.assertAlmostEqual(box.height, 1.5)
        self.assertAlmostEqual(box.center[0], 10.0)
        self.assertAlmostEqual(box.center[1], 20.0)

    def test_courtyard_box_rotated_90_and_270(self):
        pkg = {"width_mm": 2.0, "length_mm": 1.0, "courtyard_margin_mm": 0.25}
        box_90 = get_component_courtyard_box(10.0, 20.0, 90.0, pkg)
        # À 90°, largeur et hauteur sont interverties
        self.assertAlmostEqual(box_90.width, 1.5)
        self.assertAlmostEqual(box_90.height, 2.5)

        box_270 = get_component_courtyard_box(10.0, 20.0, 270.0, pkg)
        self.assertAlmostEqual(box_270.width, 1.5)
        self.assertAlmostEqual(box_270.height, 2.5)


if __name__ == "__main__":
    unittest.main()
