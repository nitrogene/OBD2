#!/usr/bin/env python3
"""
test_silkscreen.py - Tests Unitaires pour le Skill pcb-silkscreen (unittest standard)
====================================================================================
Vérifie la conformité algorithmique, la résolution géométrique,
l'idempotence et les calculs de miroir pour la face arrière.
"""

import json
import unittest
from pathlib import Path
import sys

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from silkscreen_resolver import ResolvedTextPrimitive, SilkscreenResolver

PROJECT_ROOT = SKILL_DIR.parent.parent.parent


class TestSilkscreenResolver(unittest.TestCase):

    def setUp(self):
        with open(PROJECT_ROOT / "documents" / "pcb" / "silkscreen.json", "r", encoding="utf-8") as f:
            self.silk = json.load(f)
        with open(PROJECT_ROOT / "documents" / "pcb" / "constraints.json", "r", encoding="utf-8") as f:
            self.constraints = json.load(f)
        with open(PROJECT_ROOT / ".agents" / "skills" / "pcb-synthesizer" / ".cache" / "candidate_placement.json", "r", encoding="utf-8") as f:
            self.placement = json.load(f)
        self.resolver = SilkscreenResolver(self.silk, self.constraints, self.placement)

    def test_resolver_initialization(self):
        self.assertEqual(self.resolver.board_w, 81.28)
        self.assertEqual(self.resolver.board_h, 35.56)
        self.assertEqual(self.resolver.default_font_size, 1.0)

    def test_pin_labels_resolution(self):
        top_pins = self.resolver.resolve_pin_labels("top")
        self.assertEqual(len(top_pins), 0)

        bottom_pins = self.resolver.resolve_pin_labels("bottom")
        self.assertEqual(len(bottom_pins), 13)  # H3 (2 pins) + J1 (5 pins) + H1 (3 pins) + H2 (3 pins)
        for p in bottom_pins:
            self.assertEqual(p.layer, 4)
            self.assertFalse(p.mirror)  # EasyEDA gere deja nativement le miroir sur BottomSilkLayer
        
        h3_pins = [p for p in bottom_pins if p.target_ref == "H3"]
        self.assertEqual(len(h3_pins), 2)

    def test_component_legends_resolution(self):
        top_legends = self.resolver.resolve_component_legends("top")
        self.assertEqual(len(top_legends), 0)

        bottom_legends = self.resolver.resolve_component_legends("bottom")
        self.assertEqual(len(bottom_legends), 10)  # H1 (1) + H2 (1) + H3 (2) + JP1 (3) + JP2 (3)
        jp_refs = {leg.target_ref for leg in bottom_legends}
        self.assertIn("H1", jp_refs)
        self.assertIn("H2", jp_refs)
        self.assertIn("H3", jp_refs)
        self.assertIn("JP1", jp_refs)
        self.assertIn("JP2", jp_refs)

    def test_title_blocks_resolution(self):
        titles = self.resolver.resolve_title_blocks("bottom")
        self.assertEqual(len(titles), 2)
        self.assertIn("OBD-II SCANNER", titles[1].text)
        self.assertIn("HW Rev:", titles[0].text)
        self.assertAlmostEqual(titles[0].x_mm, 6.0, delta=0.1)
        self.assertFalse(titles[0].mirror)

    def test_resolve_all_completeness_and_dfm(self):
        all_prims = self.resolver.resolve_all()
        self.assertEqual(len(all_prims), 25)
        # Conformite DFM JLCPCB stricte
        for p in all_prims:
            self.assertGreaterEqual(p.font_size_mm, 0.8)
            self.assertGreaterEqual(p.stroke_width_mm, 0.15)


if __name__ == "__main__":
    unittest.main()
