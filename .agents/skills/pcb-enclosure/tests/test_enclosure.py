#!/usr/bin/env python3
"""
test_enclosure.py - Tests Unitaires pour le Skill pcb-enclosure (unittest standard)
==================================================================================
Valide la conformité géométrique, le respect des tolérances de fabrication,
l'alignement des bossages M2 avec les perçages du PCB et l'intégrité des exports STEP/STL.
"""

import json
import unittest
from pathlib import Path
import sys

import build123d as bd

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from enclosure_generator import EnclosureGenerator

PROJECT_ROOT = SKILL_DIR.parent.parent.parent


class TestPCBEnclosure(unittest.TestCase):

    def setUp(self):
        with open(PROJECT_ROOT / "documents" / "pcb" / "constraints.json", "r", encoding="utf-8") as f:
            self.constraints = json.load(f)
        with open(PROJECT_ROOT / "documents" / "pcb" / "enclosure.json", "r", encoding="utf-8") as f:
            self.enclosure_cfg = json.load(f)
        self.gen = EnclosureGenerator(self.constraints, self.enclosure_cfg)

    def test_dimensions_calculation(self):
        # PCB 81.28 x 35.56
        self.assertEqual(self.gen.board_w, 81.28)
        self.assertEqual(self.gen.board_h, 35.56)

        # Chambre technique câble 25 mm + jeu 0.35 mm -> inner_w = 81.28 + 0.70 + 25.0 = 106.98 mm
        self.assertAlmostEqual(self.gen.inner_w, 106.98, places=2)
        self.assertAlmostEqual(self.gen.inner_h, 36.26, places=2)

        # Paroi 2.0 mm de chaque cote -> outer_w = 106.98 + 4.0 = 110.98 mm
        self.assertAlmostEqual(self.gen.outer_w, 110.98, places=2)
        self.assertAlmostEqual(self.gen.outer_h, 40.26, places=2)

    def test_mounting_holes_alignment(self):
        # 4 trous M2 doivent etre extraits de constraints.json
        self.assertEqual(len(self.gen.mounting_holes), 4)
        hole_ids = {h["id"] for h in self.gen.mounting_holes}
        self.assertEqual(hole_ids, {"MH1", "MH2", "MH3", "MH4"})

        # Entraxe X = 77.78 - 3.5 = 74.28 mm
        mh1 = next(h for h in self.gen.mounting_holes if h["id"] == "MH1")
        mh3 = next(h for h in self.gen.mounting_holes if h["id"] == "MH3")
        self.assertAlmostEqual(mh3["x_mm"] - mh1["x_mm"], 74.28, places=2)

    def test_boss_and_screw_dimensions(self):
        self.assertEqual(self.gen.boss_d, 5.0)
        self.assertEqual(self.gen.insert_d, 3.2)
        self.assertEqual(self.gen.screw_clr_d, 2.4)
        # Le bossage doit etre plus grand que le trou d'insert laiton
        self.assertGreater(self.gen.boss_d, self.gen.insert_d)
        # Le perçage traversant vis M2 doit laisser du jeu (> 2.0 mm)
        self.assertGreater(self.gen.screw_clr_d, 2.0)

    def test_solids_construction(self):
        bot = self.gen.build_bottom_shell()
        top = self.gen.build_top_shell()
        clamp = self.gen.build_cable_clamp()

        self.assertIsNotNone(bot)
        self.assertIsNotNone(top)
        self.assertIsNotNone(clamp)

        # Verification des volumes positifs
        self.assertGreater(bot.volume, 5000.0)  # mm3
        self.assertGreater(top.volume, 5000.0)
        self.assertGreater(clamp.volume, 100.0)

    def test_files_export_existence(self):
        out_dir = PROJECT_ROOT / "documents" / "enclosure"
        expected_files = [
            "enclosure_bottom.step",
            "enclosure_top.step",
            "enclosure_clamp.step",
            "enclosure_full_assembly.step",
            "enclosure_exploded.step",
            "enclosure_assembly.stl",
            "enclosure_exploded.stl",
        ]
        for fname in expected_files:
            fpath = out_dir / fname
            self.assertTrue(fpath.exists(), f"Le fichier {fname} doit exister dans documents/enclosure")
            self.assertGreater(fpath.stat().st_size, 1000, f"Le fichier {fname} ne doit pas etre vide")

    def test_step_labels_integrity(self):
        # Vérifie que les composants conservent leurs noms fonctionnels explicites en anglais dans les STEP
        out_dir = PROJECT_ROOT / "documents" / "enclosure"
        full_step = (out_dir / "enclosure_full_assembly.step").read_text(encoding="latin-1", errors="ignore")
        self.assertIn("Enclosure_Bottom_Shell", full_step)
        self.assertIn("Enclosure_Top_Shell", full_step)
        self.assertIn("Cable_Clamp", full_step)

    def test_cable_clamp_orientation_and_clearances(self):
        """Vérifie que la gorge du serre-câble traverse selon X et n'entaille ni les vis M2 ni les extrémités Y."""
        clamp = self.gen.build_cable_clamp()
        clamp_len = self.gen.clamp_screw_spacing + self.gen.boss_d + 2.0
        compression_r = (self.gen.cable_d * 0.95) / 2.0

        def _intersect_volume(a: bd.Solid, b: bd.Solid) -> float:
            inter = a.intersect(b)
            if inter is None:
                return 0.0
            if hasattr(inter, "volume"):
                return float(inter.volume)
            return float(sum(s.volume for s in inter))

        # 1. La gorge doit être ouverte sur toute la largeur X au centre (Y=0, Z=0.5)
        probe_groove = bd.Solid.make_box(self.gen.clamp_w - 0.2, 0.4, 0.4).locate(
            bd.Location((-(self.gen.clamp_w - 0.2) / 2.0, -0.2, 0.3))
        )
        self.assertAlmostEqual(
            _intersect_volume(clamp, probe_groove), 0.0, places=3,
            msg="La gorge du serre-câble doit traverser librement selon l'axe X"
        )

        # 2. Les extrémités Y doivent rester pleines (pas d'entaille par un mauvais plan XZ)
        for sign in (-1.0, 1.0):
            y_end = sign * (clamp_len / 2.0 - 0.5)
            probe_end = bd.Solid.make_box(0.4, 0.4, 0.4).locate(
                bd.Location((-0.2, y_end - 0.2, 0.3))
            )
            self.assertGreater(
                _intersect_volume(clamp, probe_end), 0.05,
                msg=f"L'extrémité Y={y_end:.2f} mm du serre-câble doit être pleine"
            )

        # 3. Distance entre la gorge et le lamage M2 >= 0.8 mm (JLC3DP)
        groove_to_cbore = (self.gen.clamp_screw_spacing / 2.0) - (self.gen.cbore_d / 2.0) - compression_r
        self.assertGreaterEqual(groove_to_cbore, 0.8)

        # 4. Épaisseur de paroi aux extrémités Y et bords X >= 0.8 mm (JLC3DP)
        end_wall_y = (clamp_len / 2.0) - (self.gen.clamp_screw_spacing / 2.0) - (self.gen.cbore_d / 2.0)
        side_wall_x = (self.gen.clamp_w / 2.0) - (self.gen.cbore_d / 2.0)
        self.assertGreaterEqual(end_wall_y, 0.8)
        self.assertGreaterEqual(side_wall_x, 0.8)

    def test_dfm_3d_wall_thickness_jlc3dp(self):
        """Vérifie le respect du seuil DFM 3D JLC3DP (>= 0.8 mm) sur les parois, lèvres et bossages."""
        min_jlc3dp_wall = 0.8

        # Paroi nominale du boîtier
        self.assertGreaterEqual(self.gen.wall_t, min_jlc3dp_wall)

        # Lèvre d'emboîtement (demi-paroi moins le jeu)
        lip_thickness = (self.gen.wall_t - 2.0 * self.gen.lip_clr) / 2.0
        self.assertGreaterEqual(lip_thickness, min_jlc3dp_wall)

        # Paroi radiale des colonnettes d'inserts M2 (coquille basse) et passage vis (coquille haute)
        insert_boss_wall = (self.gen.boss_d - self.gen.insert_d) / 2.0
        screw_boss_wall = (self.gen.boss_d - self.gen.screw_clr_d) / 2.0
        self.assertGreaterEqual(insert_boss_wall, min_jlc3dp_wall)
        self.assertGreaterEqual(screw_boss_wall, min_jlc3dp_wall)


if __name__ == "__main__":
    unittest.main()
