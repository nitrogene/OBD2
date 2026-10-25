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

        # Jeu 0.35 mm de chaque cote -> inner_w = 81.28 + 0.70 = 81.98 mm
        self.assertAlmostEqual(self.gen.inner_w, 81.98, places=2)
        self.assertAlmostEqual(self.gen.inner_h, 36.26, places=2)

        # Paroi 2.0 mm de chaque cote -> outer_w = 81.98 + 4.0 = 85.98 mm
        self.assertAlmostEqual(self.gen.outer_w, 85.98, places=2)
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
        # Vérifie que les composants conservent leurs noms fonctionnels explicites dans les STEP
        out_dir = PROJECT_ROOT / "documents" / "enclosure"
        full_step = (out_dir / "enclosure_full_assembly.step").read_text(encoding="latin-1", errors="ignore")
        self.assertIn("Boitier_Inferieur", full_step)
        self.assertIn("Boitier_Superieur", full_step)
        self.assertIn("Bride_Serre_Cable", full_step)
        self.assertIn("Carte_PCB", full_step)


if __name__ == "__main__":
    unittest.main()
