#!/usr/bin/env python3
"""
test_manifest_builder.py - Unit Tests for Dynamic Manifest Builder
================================================================================
Compatible with pytest and python -m unittest.
"""

import json
import sys
import unittest
from pathlib import Path

# Ensure skill directory is in sys.path
TEST_DIR = Path(__file__).resolve().parent
SKILL_DIR = TEST_DIR.parent
PROJECT_ROOT = SKILL_DIR.parent.parent

# Dynamically locate project root if needed
cur = SKILL_DIR
while cur.parent != cur:
    if (cur / "AGENTS.md").exists() or (cur / "readme.md").exists():
        PROJECT_ROOT = cur
        break
    cur = cur.parent

if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from manifest_builder import DynamicManifestBuilder


class TestManifestBuilder(unittest.TestCase):
    """Unit tests for DynamicManifestBuilder."""

    def setUp(self):
        self.semantics_path = PROJECT_ROOT / "documents" / "schema" / "semantics.json"
        self.constraints_path = PROJECT_ROOT / "documents" / "pcb" / "constraints.json"
        self.bom_path = PROJECT_ROOT / "documents" / "schema" / "bom.json"
        self.geometry_path = SKILL_DIR / ".cache" / "netlist_geometry.json"

        self.builder = DynamicManifestBuilder(
            semantics_path=self.semantics_path,
            constraints_path=self.constraints_path,
            bom_path=self.bom_path,
            geometry_path=self.geometry_path,
            use_offline_geometry=True
        )

    def test_load_upstream_contracts(self):
        """Tests that upstream configuration contracts load properly."""
        self.builder.load_upstream_contracts()
        self.assertIn("power_rails", self.builder.semantics)
        self.assertIn("functional_blocks", self.builder.semantics)
        self.assertIn("components", self.builder.semantics)
        self.assertIn("board", self.builder.constraints)
        self.assertIn("components", self.builder.bom)
        self.assertEqual(len(self.builder.bom["components"]), 85)

    def test_synthesize_manifest_offline(self):
        """Tests manifest synthesis from offline geometry snapshot."""
        target_manifest = PROJECT_ROOT / "documents" / "pcb" / "manifest.json"
        manifest = self.builder.synthesize_manifest(base_manifest_path=target_manifest)

        # Basic metadata
        self.assertIn("project", manifest)
        self.assertIn("packages", manifest)
        self.assertIn("components", manifest)
        self.assertIn("rigid_groups", manifest)
        self.assertIn("placement_constraints", manifest)

        # 85 components present
        comps = manifest["components"]
        self.assertEqual(len(comps), 85)

        # Check all components have a valid package string
        for des, c_info in comps.items():
            self.assertIn("package", c_info)
            self.assertIsInstance(c_info["package"], str)
            self.assertNotEqual(c_info["package"], "")
            self.assertNotEqual(c_info["package"], "UNKNOWN")

        # Check rigid groups
        groups = manifest["rigid_groups"]
        self.assertGreaterEqual(len(groups), 5)
        group_ids = [g["id"] for g in groups]
        self.assertIn("G_BUCK_CORE", group_ids)
        self.assertIn("G_ESP32_CORE", group_ids)
        self.assertIn("G_CAN_CORE", group_ids)

        # Check placement constraints
        constraints = manifest["placement_constraints"]
        self.assertGreaterEqual(len(constraints), 15)
        c_types = [c["type"] for c in constraints]
        self.assertIn("proximity", c_types)
        self.assertIn("loop", c_types)
        self.assertIn("net_compact", c_types)
        self.assertIn("edge_access", c_types)

        # Check loop constraint for switching converter
        buck_loop = next((c for c in constraints if c.get("id") == "PC_BUCK_HOT_LOOP"), None)
        self.assertIsNotNone(buck_loop)
        self.assertEqual(buck_loop["type"], "loop")
        self.assertEqual(buck_loop["metric"], "polygon_area_shoelace")
        self.assertLessEqual(buck_loop["target_max_area_mm2"], 30.0)

    def test_manifest_validation(self):
        """Tests that synthesized manifest passes JSON schema and cross-validation."""
        target_manifest = PROJECT_ROOT / "documents" / "pcb" / "manifest.json"
        manifest = self.builder.synthesize_manifest(base_manifest_path=target_manifest)
        is_valid, errors = self.builder.validate_manifest(manifest)
        self.assertTrue(is_valid, f"Validation failed with errors: {errors}")
        self.assertEqual(len(errors), 0)


if __name__ == "__main__":
    unittest.main()
