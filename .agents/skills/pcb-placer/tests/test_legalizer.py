#!/usr/bin/env python3
"""
Tests unitaires pour le moteur de légalisation déterministe (FastAnnealingEngine.legalize).
Vérifie la répulsion géométrique, la non-régression des ancres fixes et le respect des bords.
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

from export_geometry import BoardGeometrySnapshot, ComponentGeometry
from simulated_annealing import FastAnnealingEngine, MovableItem
from score import RectBox


class TestLegalizer(unittest.TestCase):
    """Tests du légalisateur physique déterministe."""

    def _build_test_engine(self, manifest_comps, anchors, comp_geoms, mounting_holes=None):
        board_constraints = {
            "board": {
                "width_mm": 50.0,
                "height_mm": 30.0,
                "edge_clearance_mm": 1.0,
                "mounting_holes": mounting_holes or []
            },
            "anchors": anchors,
            "keepout_zones": []
        }
        manifest = {
            "packages": {
                "0603": {"width_mm": 1.6, "length_mm": 0.8, "courtyard_margin_mm": 0.25},
                "SOIC-8": {"width_mm": 5.0, "length_mm": 4.0, "courtyard_margin_mm": 0.5}
            },
            "components": manifest_comps,
            "placement_constraints": []
        }
        geom = BoardGeometrySnapshot(
            extracted_at="2026-01-01T00:00:00",
            components_count=len(comp_geoms),
            pads_count=0,
            nets_count=0,
            board_outline={},
            components=comp_geoms,
            nets={}
        )
        return FastAnnealingEngine(manifest, board_constraints, geom, spacing_margin_mm=0.0)

    def test_two_movable_overlapping_components(self):
        """Deux composants mobiles superposés doivent être repoussés jusqu'à chevauchement nul."""
        manifest_comps = {
            "R1": {"package": "0603"},
            "R2": {"package": "0603"}
        }
        comp_geoms = {
            "R1": ComponentGeometry("R1", "p1", "0603", 20.0, 15.0, 0.0, 1, False),
            "R2": ComponentGeometry("R2", "p2", "0603", 20.2, 15.1, 0.0, 1, False)
        }
        engine = self._build_test_engine(manifest_comps, {}, comp_geoms)

        it_r1 = [it for it in engine.items if it.designator == "R1"][0]
        it_r2 = [it for it in engine.items if it.designator == "R2"][0]

        # Initialement en forte collision
        self.assertTrue(it_r1.box.intersects(it_r2.box))
        self.assertGreater(it_r1.box.intersection_area(it_r2.box), 0.5)

        engine.legalize(max_passes=50)

        # Après légalisation : plus aucune collision
        inter_area = it_r1.box.intersection_area(it_r2.box)
        self.assertLessEqual(inter_area, 0.001)

        # Les composants doivent être restés dans la carte
        self.assertGreaterEqual(it_r1.box.x_min, 1.0)
        self.assertLessEqual(it_r1.box.x_max, 49.0)
        self.assertGreaterEqual(it_r2.box.x_min, 1.0)
        self.assertLessEqual(it_r2.box.x_max, 49.0)

    def test_fixed_anchor_immunity(self):
        """Une ancre mécanique fixe (J1) ne doit JAMAIS bouger ; seul le composant mobile doit être déplacé."""
        manifest_comps = {
            "J1": {"package": "SOIC-8"},
            "C1": {"package": "0603"}
        }
        anchors = {
            "J1": {"x_mm": 25.0, "y_mm": 15.0, "rot_deg": 0.0, "fixed": True}
        }
        comp_geoms = {
            "J1": ComponentGeometry("J1", "p1", "SOIC-8", 25.0, 15.0, 0.0, 1, True),
            "C1": ComponentGeometry("C1", "p2", "0603", 25.2, 15.1, 0.0, 1, False)
        }
        engine = self._build_test_engine(manifest_comps, anchors, comp_geoms)

        it_j1 = [it for it in engine.items if it.designator == "J1"][0]
        it_c1 = [it for it in engine.items if it.designator == "C1"][0]

        self.assertTrue(it_j1.is_fixed)
        self.assertFalse(it_c1.is_fixed)

        orig_x, orig_y = it_j1.x, it_j1.y

        engine.legalize(max_passes=50)

        # L'ancre n'a pas bougé d'un nanomètre
        self.assertEqual(it_j1.x, orig_x)
        self.assertEqual(it_j1.y, orig_y)

        # C1 a été éjecté hors de J1
        inter_area = it_j1.box.intersection_area(it_c1.box)
        self.assertLessEqual(inter_area, 0.001)

    def test_mounting_hole_clearance(self):
        """Un composant placé sur un trou de vis de fixation mécanique doit être repoussé hors du dégagement."""
        manifest_comps = {
            "C1": {"package": "0603"}
        }
        mholes = [
            {"id": "MH1", "x_mm": 5.0, "y_mm": 5.0, "head_clearance_mm": 4.5}
        ]
        # C1 placé en plein sur la tête de vis
        comp_geoms = {
            "C1": ComponentGeometry("C1", "p1", "0603", 5.2, 5.1, 0.0, 1, False)
        }
        engine = self._build_test_engine(manifest_comps, {}, comp_geoms, mounting_holes=mholes)

        it_c1 = [it for it in engine.items if it.designator == "C1"][0]
        hole_radius = 4.5 / 2.0
        hole_box = RectBox(5.0 - hole_radius, 5.0 + hole_radius, 5.0 - hole_radius, 5.0 + hole_radius)

        self.assertTrue(it_c1.box.intersects(hole_box))

        engine.legalize(max_passes=50)

        # Après légalisation : C1 doit être repoussé hors du centre de vis
        dist_to_center = math.hypot(it_c1.x - 5.0, it_c1.y - 5.0)
        self.assertGreater(dist_to_center, hole_radius)

    def test_legalizer_determinism(self):
        """Deux exécutions successives de legalize sur le même état doivent donner exactement les mêmes coordonnées."""
        manifest_comps = {
            "R1": {"package": "0603"},
            "R2": {"package": "0603"},
            "R3": {"package": "0603"}
        }
        comp_geoms = {
            "R1": ComponentGeometry("R1", "p1", "0603", 10.0, 10.0, 0.0, 1, False),
            "R2": ComponentGeometry("R2", "p2", "0603", 10.2, 10.1, 0.0, 1, False),
            "R3": ComponentGeometry("R3", "p3", "0603", 10.4, 10.2, 0.0, 1, False)
        }
        engine = self._build_test_engine(manifest_comps, {}, comp_geoms)
        engine.legalize(max_passes=50)

        coords_1 = [(it.x, it.y) for it in engine.items]

        # Re-passe sur l'état légalisé : aucune dérive
        engine.legalize(max_passes=50)
        coords_2 = [(it.x, it.y) for it in engine.items]

        for (x1, y1), (x2, y2) in zip(coords_1, coords_2):
            self.assertAlmostEqual(x1, x2, places=6)
            self.assertAlmostEqual(y1, y2, places=6)


if __name__ == "__main__":
    unittest.main()
