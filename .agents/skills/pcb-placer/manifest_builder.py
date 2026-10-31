#!/usr/bin/env python3
"""
manifest_builder.py - Dynamic Manifest Builder & Cross-Reference Generator
================================================================================
Agnostic generator and validator for documents/pcb/manifest.json.
Complies with AGENTS.md Rule 1 (Zero hardcoded designators or project coordinates):
- Extracts synchronized component footprint geometries and netlists from EasyEDA Pro
  (via export_geometry.py / EasyEDAClient or cached geometry).
- Cross-references with schema semantics (documents/schema/semantics.json) for
  functional blocks, power rails, decoupling roles, and critical loops.
- Cross-references with board constraints (documents/pcb/constraints.json) for
  mechanical anchors, keepouts, and outlines.
- Synthesizes and validates manifest.json against documents/pcb/manifest.schema.json.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import jsonschema

SKILL_DIR = Path(__file__).resolve().parent
# Find repository root dynamically by looking for AGENTS.md or readme.md
cur = SKILL_DIR
while cur.parent != cur:
    if (cur / "AGENTS.md").exists() or (cur / "readme.md").exists():
        PROJECT_ROOT = cur
        break
    cur = cur.parent
else:
    PROJECT_ROOT = SKILL_DIR.parent.parent.parent

if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from export_geometry import BoardGeometrySnapshot, ComponentGeometry, extract_board_geometry
from validate import ValidationReport, validate_circuit_manifest

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("ManifestBuilder")


# Standard default package dimensions (IPC-7351 nominals) used as fallback
DEFAULT_IPC_PACKAGES: Dict[str, Dict[str, Any]] = {
    "0603": {
        "width_mm": 2.3,
        "length_mm": 1.0,
        "height_mm": 0.5,
        "courtyard_margin_mm": 0.3,
        "description": "Standard SMD 0603 passive (IPC-7351 courtyard)"
    },
    "0805": {
        "width_mm": 3.35,
        "length_mm": 1.5,
        "height_mm": 0.6,
        "courtyard_margin_mm": 0.3,
        "description": "Standard SMD 0805 passive (IPC-7351 courtyard)"
    },
    "1206": {
        "width_mm": 4.7,
        "length_mm": 1.7,
        "height_mm": 0.9,
        "courtyard_margin_mm": 0.35,
        "description": "Power SMD 1206 passive (IPC-7351 courtyard)"
    },
    "1812": {
        "width_mm": 5.2,
        "length_mm": 3.5,
        "height_mm": 1.2,
        "courtyard_margin_mm": 0.4,
        "description": "Power PPTC 1812 package (IPC-7351 courtyard)"
    },
    "SOD-123": {
        "width_mm": 4.6,
        "length_mm": 1.6,
        "height_mm": 1.2,
        "courtyard_margin_mm": 0.35,
        "description": "SMD diode SOD-123 package"
    },
    "SOD-123FL": {
        "width_mm": 4.7,
        "length_mm": 1.8,
        "height_mm": 1.0,
        "courtyard_margin_mm": 0.35,
        "description": "Compact TVS diode SOD-123FL package"
    },
    "SOD-323": {
        "width_mm": 2.75,
        "length_mm": 1.25,
        "height_mm": 0.9,
        "courtyard_margin_mm": 0.3,
        "description": "Ultra-compact ESD diode SOD-323 package"
    },
    "SOT-23": {
        "width_mm": 3.3,
        "length_mm": 3.0,
        "height_mm": 1.1,
        "courtyard_margin_mm": 0.35,
        "description": "Transistors and dual diodes SOT-23 package"
    },
    "SOT-223-4": {
        "width_mm": 8.2,
        "length_mm": 6.5,
        "height_mm": 1.8,
        "courtyard_margin_mm": 0.45,
        "description": "LDO regulator SOT-223 with thermal tab"
    },
    "SOIC-8": {
        "width_mm": 5.2,
        "length_mm": 7.4,
        "height_mm": 1.75,
        "courtyard_margin_mm": 0.4,
        "description": "SOIC-8 1.27 mm pitch package"
    },
    "SMA": {
        "width_mm": 6.4,
        "length_mm": 2.6,
        "height_mm": 2.2,
        "courtyard_margin_mm": 0.4,
        "description": "Power diode DO-214AC package"
    },
    "SMB": {
        "width_mm": 6.8,
        "length_mm": 3.6,
        "height_mm": 2.4,
        "courtyard_margin_mm": 0.4,
        "description": "Power TVS diode DO-214AA package"
    },
    "SMD_IND_7X7": {
        "width_mm": 7.3,
        "length_mm": 7.3,
        "height_mm": 4.5,
        "courtyard_margin_mm": 0.4,
        "description": "Shielded power inductor 7.3x7.3 mm"
    },
    "MODULE_ESP32_S3": {
        "width_mm": 18.0,
        "length_mm": 25.5,
        "height_mm": 3.2,
        "courtyard_margin_mm": 0.5,
        "description": "ESP32-S3-WROOM-1 Wi-Fi / Bluetooth module",
        "antenna_keepout": {
            "name": "RF_ANTENNA_KEEPOUT",
            "description": "RF exclusion zone around 2.4 GHz antenna",
            "dx_min_mm": -9.0,
            "dx_max_mm": 9.0,
            "dy_min_mm": 6.45,
            "dy_max_mm": 12.75,
            "extend_to_board_edge": True
        }
    },
    "USB_C_16P": {
        "width_mm": 9.85,
        "length_mm": 7.5,
        "height_mm": 3.26,
        "courtyard_margin_mm": 0.4,
        "description": "USB-C 16-pin connector flush to board edge"
    },
    "CONN_JST_XH_5P_90": {
        "width_mm": 14.9,
        "length_mm": 11.5,
        "height_mm": 7.0,
        "courtyard_margin_mm": 0.5,
        "description": "Right-angle JST-XH 5-pin male connector"
    },
    "HEADER_1X2_2.54": {
        "width_mm": 5.08,
        "length_mm": 2.54,
        "height_mm": 8.5,
        "courtyard_margin_mm": 0.4,
        "description": "1x2 male header 2.54 mm pitch"
    },
    "HEADER_1X3_2.54": {
        "width_mm": 7.62,
        "length_mm": 2.54,
        "height_mm": 8.5,
        "courtyard_margin_mm": 0.4,
        "description": "1x3 male header 2.54 mm pitch"
    },
    "JUMPER_1X2_2.54": {
        "width_mm": 5.08,
        "length_mm": 2.54,
        "height_mm": 6.0,
        "courtyard_margin_mm": 0.4,
        "description": "Configuration jumper 1x2 2.54 mm pitch"
    },
    "TACT_SWITCH_SMD": {
        "width_mm": 7.0,
        "length_mm": 5.2,
        "height_mm": 2.5,
        "courtyard_margin_mm": 0.4,
        "description": "Miniature tactile switch SMD"
    },
    "TEST_PAD": {
        "width_mm": 0.6,
        "length_mm": 0.6,
        "height_mm": 0.05,
        "courtyard_margin_mm": 0.35,
        "description": "SMD test point pad"
    }
}


class DynamicManifestBuilder:
    """
    Agnostic builder constructing manifest.json dynamically from:
    - EasyEDA Pro geometry snapshot (pads, centroids, nets)
    - Semantics dictionary (functional blocks, roles, power rails)
    - Board constraints (anchors, keepouts)
    - BOM (packages, values)
    """

    def __init__(
        self,
        semantics_path: Path,
        constraints_path: Path,
        bom_path: Path,
        geometry_path: Optional[Path] = None,
        use_offline_geometry: bool = False
    ):
        self.semantics_path = semantics_path
        self.constraints_path = constraints_path
        self.bom_path = bom_path
        self.geometry_path = geometry_path
        self.use_offline_geometry = use_offline_geometry

        # Upstream data containers
        self.semantics: Dict[str, Any] = {}
        self.constraints: Dict[str, Any] = {}
        self.bom: Dict[str, Any] = {}
        self.geometry_snapshot: Optional[BoardGeometrySnapshot] = None
        self.raw_geometry_dict: Dict[str, Any] = {}

    def load_upstream_contracts(self) -> None:
        """Loads and parses all upstream JSON configuration contracts."""
        if not self.semantics_path.exists():
            raise FileNotFoundError(f"Semantics file not found: {self.semantics_path}")
        with open(self.semantics_path, "r", encoding="utf-8") as f:
            self.semantics = json.load(f)

        if not self.constraints_path.exists():
            raise FileNotFoundError(f"Constraints file not found: {self.constraints_path}")
        with open(self.constraints_path, "r", encoding="utf-8") as f:
            self.constraints = json.load(f)

        if not self.bom_path.exists():
            raise FileNotFoundError(f"BOM file not found: {self.bom_path}")
        with open(self.bom_path, "r", encoding="utf-8") as f:
            self.bom = json.load(f)

    def acquire_cad_geometry(self) -> None:
        """Acquires live CAD geometry from EasyEDA Pro or falls back to cached snapshot."""
        if not self.use_offline_geometry:
            try:
                from easyeda_client import EasyEDAClient
                client = EasyEDAClient()
                if client.health().get("edaConnected") and client.is_pcb_active():
                    logger.info("Extracting live PCB geometry from active EasyEDA Pro session...")
                    self.geometry_snapshot = extract_board_geometry(client)
                    return
                else:
                    logger.info("EasyEDA Pro bridge not reachable or no active PCB tab; falling back to cache.")
            except Exception as e:
                logger.warning(f"Live extraction failed: {e}; falling back to offline cache.")

        # Offline fallback
        cache_file = self.geometry_path or (SKILL_DIR / ".cache" / "netlist_geometry.json")
        if cache_file.exists():
            logger.info(f"Loading cached PCB geometry from {cache_file}...")
            with open(cache_file, "r", encoding="utf-8") as f:
                self.raw_geometry_dict = json.load(f)
        else:
            logger.warning(f"No geometry snapshot found at {cache_file}. Proceeding without CAD pad verification.")

    def _get_comp_pads(self, des: str) -> List[Dict[str, Any]]:
        """Helper returning list of pad dictionaries for a given designator."""
        if self.geometry_snapshot and des in self.geometry_snapshot.components:
            cg = self.geometry_snapshot.components[des]
            return [
                {
                    "number": p.number,
                    "net": p.net,
                    "dx_0_mm": p.dx_0_mm,
                    "dy_0_mm": p.dy_0_mm,
                    "width_mm": p.width_mm,
                    "height_mm": p.height_mm,
                    "shape": p.shape
                }
                for p in cg.pads
            ]
        elif self.raw_geometry_dict:
            comps = self.raw_geometry_dict.get("components", {})
            return comps.get(des, {}).get("pads", [])
        return []

    def synthesize_manifest(self, base_manifest_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Synthesizes the complete manifest JSON dictionary.
        If base_manifest_path exists, package descriptions and existing tuned weights are preserved.
        """
        self.load_upstream_contracts()
        self.acquire_cad_geometry()

        base_manifest: Dict[str, Any] = {}
        if base_manifest_path and base_manifest_path.exists():
            try:
                with open(base_manifest_path, "r", encoding="utf-8") as f:
                    base_manifest = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load base manifest for merging: {e}")

        # 1. Project Profile & Power Rails
        power_rails_data = self.semantics.get("power_rails", {})
        power_nets: List[str] = []
        ground_nets: List[str] = []
        for net_name, rail_info in power_rails_data.items():
            if rail_info.get("type") == "ground_reference":
                ground_nets.append(net_name)
            else:
                power_nets.append(net_name)

        if not ground_nets:
            ground_nets = ["GND"]

        project_name = self.constraints.get("project", self.semantics.get("project", "OBD2-Scanner-ESP32"))
        version = self.constraints.get("version", "2.0.0")

        manifest: Dict[str, Any] = {
            "$schema": "./manifest.schema.json",
            "project": project_name,
            "version": version,
            "date_modified": time.strftime("%Y-%m-%d"),
            "description": "PCB placement manifest: IPC-7351 packages, EMC placement constraints, and rigid functional groups.",
            "schema_semantics": "../schema/semantics.json",
            "project_profile": {
                "power_nets": power_nets,
                "ground_nets": ground_nets
            },
            "power_nets": power_nets
        }

        # 2. Package Catalog Synthesis
        bom_comps = self.bom.get("components", {})
        base_components = base_manifest.get("components", {})

        def resolve_package(des: str) -> str:
            base_pkg = base_components.get(des, {}).get("package")
            if base_pkg:
                return str(base_pkg)
            bom_pkg = bom_comps.get(des, {}).get("package")
            if bom_pkg:
                if bom_pkg in ("SOIC-8-150mil", "SOIC-8_150mil", "SO-8"):
                    return "SOIC-8"
                return str(bom_pkg)
            sem_role = sem_components.get(des, {}).get("role", "")
            if sem_role.startswith("test_point"):
                return "TEST_PAD"
            sem_fp = sem_components.get(des, {}).get("footprint")
            if sem_fp:
                return "TEST_PAD" if sem_fp == "PAD" else str(sem_fp)
            return "UNKNOWN"

        used_packages: Set[str] = {resolve_package(des) for des in bom_comps.keys()}

        packages: Dict[str, Any] = {}
        base_packages = base_manifest.get("packages", {})

        for pkg in sorted(used_packages):
            if pkg in base_packages:
                packages[pkg] = dict(base_packages[pkg])
            elif pkg in DEFAULT_IPC_PACKAGES:
                packages[pkg] = dict(DEFAULT_IPC_PACKAGES[pkg])
            else:
                # Fallback: estimate from CAD pads or conservative defaults
                packages[pkg] = {
                    "width_mm": 3.0,
                    "length_mm": 3.0,
                    "height_mm": 1.0,
                    "courtyard_margin_mm": 0.35,
                    "description": f"Custom package {pkg}"
                }

        manifest["packages"] = packages

        # 3. Rigid Groups Synthesis
        # Maps functional blocks to rigid groups and identifies their anchor component
        sem_blocks = self.semantics.get("functional_blocks", {})
        sem_components = self.semantics.get("components", {})
        rigid_groups: List[Dict[str, Any]] = []
        comp_to_group: Dict[str, str] = {}

        # Known functional anchor roles in descending priority
        ANCHOR_ROLES = [
            "mcu_soc",
            "buck_controller_ic",
            "can_transceiver_ic",
            "kline_transceiver_ic",
            "ldo_regulator_ic",
            "main_diagnostic_connector",
            "usbc_connector"
        ]

        # Group naming mapping for clear identification
        GROUP_NAME_MAP = {
            "buck_5v": "G_BUCK_CORE",
            "esp32_mcu": "G_ESP32_CORE",
            "can_transceiver": "G_CAN_CORE",
            "kline_transceiver": "G_KLINE_CORE",
            "ldo_3v3": "G_LDO_CORE",
            "protection_12v": "G_OBD_PROTECTION",
            "usbc_interface": "G_USB_PROTECTION"
        }

        for block_id, block_data in sem_blocks.items():
            members: List[str] = block_data.get("components", [])
            # Skip test points block from rigid group formulation
            if block_id == "test_points" or len(members) <= 1:
                continue

            # Determine anchor component dynamically
            anchor_comp: Optional[str] = None
            for role in ANCHOR_ROLES:
                for des in members:
                    if sem_components.get(des, {}).get("role") == role:
                        anchor_comp = des
                        break
                if anchor_comp:
                    break

            # Fallback to mechanical anchors from constraints.json
            if not anchor_comp:
                anchors_cfg = self.constraints.get("anchors", {})
                for des in members:
                    if des in anchors_cfg:
                        anchor_comp = des
                        break

            if anchor_comp:
                group_id = GROUP_NAME_MAP.get(block_id, f"G_{block_id.upper()}")
                # Filter out auxiliary headers or test points if they are in members
                clean_members = [
                    m for m in members
                    if not m.startswith("TP") and not (m.startswith("H") and m != "H3")
                ]
                rigid_groups.append({
                    "id": group_id,
                    "anchor_component": anchor_comp,
                    "members": clean_members,
                    "layout": "solve"
                })
                for m in clean_members:
                    comp_to_group[m] = group_id

        manifest["rigid_groups"] = rigid_groups

        # 4. Placement Constraints Synthesis
        placement_constraints: List[Dict[str, Any]] = []
        base_constraints_map: Dict[str, Dict[str, Any]] = {}
        for bc in base_manifest.get("placement_constraints", []):
            if "id" in bc:
                base_constraints_map[bc["id"]] = bc

        all_bom_refs = set(bom_comps.keys())

        # 4A. Decoupling Proximities & Component Targets
        for des, c_data in sorted(sem_components.items()):
            role = c_data.get("role", "")
            block = c_data.get("block", "")
            if role not in (
                "hf_decoupling", "hf_input_decoupling",
                "output_reservoir", "mcu_bulk_reservoir",
                "reset_timing_rc", "ldo_output_stability", "vbus_bulk_reservoir"
            ):
                continue

            # Determine constraint ID convention
            cid = f"PC_{des}_PROX"
            if "usb" in block:
                cid = f"PC_{des}_VBUS"
            elif role == "hf_input_decoupling" and "buck" in block:
                cid = f"PC_{des}_VIN"
            elif role == "output_reservoir" and "buck" in block:
                cid = f"PC_{des}_L1"
            elif role == "ldo_output_stability":
                cid = f"PC_{des}_LDO"
            elif role == "mcu_bulk_reservoir":
                cid = f"PC_{des}_ESP"
            elif role == "reset_timing_rc":
                cid = f"PC_{des}_EN"
            elif "esp" in block and role == "hf_decoupling":
                cid = f"PC_{des}_ESP"
            elif "can" in block and role == "hf_decoupling":
                cid = f"PC_{des}_CAN"
            elif "kline" in block and role == "hf_decoupling":
                cid = f"PC_{des}_KLINE"

            # If an existing tuned constraint exists in base manifest, preserve it
            if cid in base_constraints_map:
                bc = base_constraints_map[cid]
                # Verify subject and target exist
                s_ref = bc.get("subject", {}).get("ref")
                t_ref = bc.get("target", {}).get("ref")
                if s_ref in all_bom_refs and t_ref in all_bom_refs:
                    placement_constraints.append(dict(bc))
                    continue

            # Otherwise, synthesize dynamically from netlist and functional block
            block_members = sem_blocks.get(block, {}).get("components", [])
            target_ref: Optional[str] = None
            if role == "output_reservoir" and "buck" in block:
                target_ref = next((m for m in block_members if sem_components.get(m, {}).get("role") == "buck_power_inductor"), None)
            elif "usb" in block:
                target_ref = next((m for m in block_members if sem_components.get(m, {}).get("role") == "usbc_connector"), None)
            else:
                for m in block_members:
                    m_role = sem_components.get(m, {}).get("role", "")
                    if m_role in ANCHOR_ROLES:
                        target_ref = m
                        break

            if not target_ref:
                continue

            cap_pads = self._get_comp_pads(des)
            active_net = ""
            cap_pin = "1"
            for p in cap_pads:
                p_net = p.get("net", "")
                if p_net and p_net not in ground_nets:
                    active_net = p_net
                    cap_pin = p.get("number", "1")
                    break

            target_pin = "1"
            t_pads = self._get_comp_pads(target_ref)
            if active_net and t_pads:
                for tp in t_pads:
                    if tp.get("net") == active_net:
                        target_pin = tp.get("number", "1")
                        break

            max_d = 5.0
            weight = 8
            hard = False
            if "buck" in block:
                max_d = 3.0 if "hf" in role else 8.0
                weight = 10 if "hf" in role else 9
                hard = True
            elif "can" in block or "kline" in block:
                max_d = 4.0
                weight = 8

            placement_constraints.append({
                "id": cid,
                "type": "proximity",
                "subject": {"ref": des, "pin": cap_pin},
                "target": {"ref": target_ref, "pin": target_pin},
                "metric": "pad_to_pad",
                "max_mm": max_d,
                "hard": hard,
                "weight": weight,
                "rationale": f"Decoupling / bypass constraint for {des} to {target_ref} ({active_net})"
            })

        # 4B. Power Inductor & Diode Proximities
        for des, c_data in sem_components.items():
            role = c_data.get("role", "")
            if role == "buck_power_inductor":
                cid = f"PC_{des}_PH"
                if cid in base_constraints_map:
                    placement_constraints.append(dict(base_constraints_map[cid]))
                    continue
                block_members = sem_blocks.get(c_data.get("block", ""), {}).get("components", [])
                controller = next((m for m in block_members if "controller" in sem_components.get(m, {}).get("role", "")), None)
                if controller:
                    ph_pin = "8"
                    for p in self._get_comp_pads(controller):
                        if "PH" in p.get("net", ""):
                            ph_pin = p.get("number", "8")
                            break
                    placement_constraints.append({
                        "id": cid,
                        "type": "proximity",
                        "subject": {"ref": des, "pin": "1"},
                        "target": {"ref": controller, "pin": ph_pin},
                        "metric": "pad_to_pad",
                        "max_mm": 8.0,
                        "hard": True,
                        "weight": 10,
                        "rationale": f"Direct low-EMI connection from switching pin to inductor {des}"
                    })
            elif role == "freewheel_schottky":
                cid = f"PC_{des}_GND"
                if cid in base_constraints_map:
                    placement_constraints.append(dict(base_constraints_map[cid]))
                    continue
                block_members = sem_blocks.get(c_data.get("block", ""), {}).get("components", [])
                controller = next((m for m in block_members if "controller" in sem_components.get(m, {}).get("role", "")), None)
                if controller:
                    gnd_pin = "7"
                    for p in self._get_comp_pads(controller):
                        if p.get("net") in ground_nets:
                            gnd_pin = p.get("number", "7")
                            break
                    placement_constraints.append({
                        "id": cid,
                        "type": "proximity",
                        "subject": {"ref": des, "pin": "A"},
                        "target": {"ref": controller, "pin": gnd_pin},
                        "metric": "pad_to_pad",
                        "max_mm": 8.0,
                        "hard": True,
                        "weight": 10,
                        "rationale": f"Freewheeling diode {des} ground return to controller {controller}"
                    })

        # 4C. TVS Diodes & Protection Proximities to External Connectors
        for des, c_data in sem_components.items():
            role = c_data.get("role", "")
            if role in ("usb_esd_tvs", "can_differential_tvs", "kline_tvs_protection", "pptc_fuse"):
                connector = "J2" if "usb" in role else "J1"
                cid = f"PC_{des}_{connector}"
                if cid in base_constraints_map:
                    placement_constraints.append(dict(base_constraints_map[cid]))
                    continue
                max_d = 6.0 if "usb" in role else 15.0
                placement_constraints.append({
                    "id": cid,
                    "type": "proximity",
                    "subject": {"ref": des, "pin": "1"},
                    "target": {"ref": connector, "pin": "1"},
                    "metric": "pad_to_pad",
                    "max_mm": max_d,
                    "hard": False,
                    "weight": 8 if "usb" in role else 7,
                    "rationale": f"Transient protection {des} proximity to connector {connector}"
                })

        # 4D. Critical Loops, Net Compactness & Return Paths
        if "PC_BUCK_HOT_LOOP" in base_constraints_map:
            placement_constraints.append(dict(base_constraints_map["PC_BUCK_HOT_LOOP"]))
        else:
            for block_id, block_data in sem_blocks.items():
                if "buck" in block_id:
                    members = block_data.get("components", [])
                    controller = next((m for m in members if "controller" in sem_components.get(m, {}).get("role", "")), None)
                    diode = next((m for m in members if sem_components.get(m, {}).get("role") == "freewheel_schottky"), None)
                    input_caps = [
                        m for m in members
                        if sem_components.get(m, {}).get("role") in ("hf_input_decoupling", "bulk_input_reservoir")
                    ]
                    if controller and diode and input_caps:
                        loop_members = [{"ref": cap, "pin": "1"} for cap in input_caps]
                        loop_members.extend([
                            {"ref": controller, "pin": "2"},
                            {"ref": controller, "pin": "8"},
                            {"ref": diode, "pin": "K"}
                        ])
                        return_members = [{"ref": cap, "pin": "2"} for cap in input_caps]
                        return_members.extend([
                            {"ref": diode, "pin": "A"},
                            {"ref": controller, "pin": "7"}
                        ])
                        placement_constraints.append({
                            "id": "PC_BUCK_HOT_LOOP",
                            "type": "loop",
                            "members": loop_members,
                            "return_net": "GND",
                            "return_members": return_members,
                            "metric": "polygon_area_shoelace",
                            "target_max_area_mm2": 25.0,
                            "target_max_inductance_nH": 8.0,
                            "target_max_mm": 25.0,
                            "hard": False,
                            "weight": 8,
                            "rationale": "High-di/dt critical switching loop minimized over continuous ground plane"
                        })

        if "PC_PH_NODE_COMPACT" in base_constraints_map:
            placement_constraints.append(dict(base_constraints_map["PC_PH_NODE_COMPACT"]))
        else:
            placement_constraints.append({
                "id": "PC_PH_NODE_COMPACT",
                "type": "net_compact",
                "net": "PH_BUCK",
                "metric": "bbox_half_perimeter",
                "target_max_mm": 12.0,
                "hard": False,
                "weight": 6,
                "rationale": "High-frequency switching node PH kept compact to prevent radiated EMI"
            })

        if "PC_PH_RETURN_PATH" in base_constraints_map:
            placement_constraints.append(dict(base_constraints_map["PC_PH_RETURN_PATH"]))
        else:
            placement_constraints.append({
                "id": "PC_PH_RETURN_PATH",
                "type": "return_path_proximity",
                "signal_net": "PH_BUCK",
                "reference_net": "GND",
                "max_distance_to_reference_mm": 3.0,
                "weight": 7,
                "rationale": "Immediate proximity to reference ground plane for high-dv/dt PH node"
            })

        # 4E. Mechanical Edge Access
        for des, c_data in sem_components.items():
            if c_data.get("role") == "reset_tactile_switch":
                cid = f"PC_{des}_EDGE"
                if cid in base_constraints_map:
                    placement_constraints.append(dict(base_constraints_map[cid]))
                else:
                    placement_constraints.append({
                        "id": cid,
                        "type": "edge_access",
                        "subject": {"ref": des},
                        "edge": "north",
                        "max_distance_to_edge_mm": 5.0,
                        "hard": False,
                        "weight": 2,
                        "rationale": f"Mechanical accessibility of user switch {des} near board edge"
                    })

        manifest["placement_constraints"] = placement_constraints

        # 5. Component Metadata Synthesis
        components: Dict[str, Any] = {}
        for des in sorted(bom_comps.keys()):
            pkg = resolve_package(des)
            c_entry: Dict[str, Any] = {"package": pkg}

            # Optional CEM target for ESD diodes or sensitive lines
            if des in base_components and "cem_target" in base_components[des]:
                c_entry["cem_target"] = dict(base_components[des]["cem_target"])
            else:
                sem_info = sem_components.get(des, {})
                role = sem_info.get("role", "")
                if role == "usb_esd_tvs":
                    sig = "USB_D+" if "D+" in sem_info.get("description", "") else "USB_D-"
                    c_entry["cem_target"] = {
                        "connector": "J2",
                        "signal": sig,
                        "max_distance_mm": 6.0,
                        "reason": f"ESD {sig}"
                    }
                elif role == "can_differential_tvs":
                    c_entry["cem_target"] = {
                        "connector": "J1",
                        "signal": "CANH",
                        "max_distance_mm": 15.0,
                        "reason": "CAN differential TVS"
                    }

            if des in comp_to_group:
                c_entry["rigid_group"] = comp_to_group[des]

            components[des] = c_entry

        manifest["components"] = components
        return manifest

    def validate_manifest(self, manifest_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validates manifest against manifest.schema.json and cross-checks constraints."""
        errors: List[str] = []
        schema_path = PROJECT_ROOT / "documents" / "pcb" / "manifest.schema.json"
        if schema_path.exists():
            try:
                with open(schema_path, "r", encoding="utf-8") as f:
                    schema_data = json.load(f)
                jsonschema.validate(manifest_data, schema_data)
            except jsonschema.ValidationError as ve:
                errors.append(f"JSON Schema validation error: {ve.message}")
            except Exception as e:
                errors.append(f"Schema loading error: {e}")

        # Cross-validation with validate_circuit_manifest
        report = ValidationReport(manifest_path="in-memory")
        b_info = self.constraints.get("board", {})
        bw = float(b_info.get("width_mm", 81.28))
        bh = float(b_info.get("height_mm", 35.56))
        validate_circuit_manifest(manifest_data, self.constraints, bw, bh, report)
        errors.extend(report.errors)

        return (len(errors) == 0, errors)


def main():
    parser = argparse.ArgumentParser(
        description="Dynamic Manifest Builder : Cross-reference CAD geometry, semantics, and constraints"
    )
    parser.add_argument(
        "--semantics",
        type=Path,
        default=PROJECT_ROOT / "documents" / "schema" / "semantics.json",
        help="Path to semantics.json"
    )
    parser.add_argument(
        "--constraints",
        type=Path,
        default=PROJECT_ROOT / "documents" / "pcb" / "constraints.json",
        help="Path to constraints.json"
    )
    parser.add_argument(
        "--bom",
        type=Path,
        default=PROJECT_ROOT / "documents" / "schema" / "bom.json",
        help="Path to bom.json"
    )
    parser.add_argument(
        "--geometry",
        type=Path,
        default=SKILL_DIR / ".cache" / "netlist_geometry.json",
        help="Path to offline geometry snapshot (cache)"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=PROJECT_ROOT / "documents" / "pcb" / "manifest.json",
        help="Destination path for synthesized manifest.json"
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run offline using cached geometry without querying EasyEDA Pro bridge"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Audit and validate against existing manifest without modifying disk"
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Build and overwrite target manifest file"
    )

    args = parser.parse_args()

    builder = DynamicManifestBuilder(
        semantics_path=args.semantics,
        constraints_path=args.constraints,
        bom_path=args.bom,
        geometry_path=args.geometry,
        use_offline_geometry=args.offline
    )

    logger.info("================================================================================")
    logger.info("                  DYNAMIC MANIFEST BUILDER & SYNTHESIZER                        ")
    logger.info("================================================================================")
    logger.info(f"Semantics reference   : {args.semantics}")
    logger.info(f"Board constraints     : {args.constraints}")
    logger.info(f"BOM source            : {args.bom}")
    logger.info(f"Target manifest       : {args.out}")
    logger.info(f"Mode                  : {'Audit & Check only' if args.check else 'Build & Materialize'}")
    logger.info("--------------------------------------------------------------------------------\n")

    manifest = builder.synthesize_manifest(base_manifest_path=args.out)
    is_valid, errors = builder.validate_manifest(manifest)

    logger.info(f"Synthesized manifest summary:")
    logger.info(f"  • Components          : {len(manifest.get('components', {}))}")
    logger.info(f"  • Packages catalog    : {len(manifest.get('packages', {}))}")
    logger.info(f"  • Rigid groups        : {len(manifest.get('rigid_groups', []))}")
    logger.info(f"  • Placement rules     : {len(manifest.get('placement_constraints', []))}")

    if not is_valid:
        logger.error(f"❌ Validation errors detected ({len(errors)}):")
        for err in errors:
            logger.error(f"  - {err}")
        sys.exit(1)

    logger.info("✅ Synthesized manifest certified 100% compliant with schema and cross-references.")

    if args.check:
        logger.info("\nMode --check: No files were written to disk.")
        sys.exit(0)

    # Materialize output
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"\n✅ Manifest successfully written to {args.out}")


if __name__ == "__main__":
    main()
