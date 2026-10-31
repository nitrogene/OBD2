#!/usr/bin/env python3
"""
dsn_updater.py - Mise à jour agnostique des coordonnées de placement dans un Specctra DSN
========================================================================================
Skill: freerouting / pcb-synthesizer
Règle 0 (AGENTS.md) :
- Zéro composant ou valeur en dur.
- Reçoit le snapshot géométrique (netlist_geometry.json ou BoardGeometrySnapshot)
  et le dictionnaire de placement candidat (candidate_placement.json).
- Calcule la nouvelle position (x_mil, y_mil) et rotation de chaque pastille.
- Réinjecte ces coordonnées chirurgicalement dans le Specctra DSN sans appel HTTP.
"""

from __future__ import annotations

import json
import logging
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

logger = logging.getLogger("DsnUpdater")

MM_TO_MIL = 1000.0 / 25.4
MIL_TO_MM = 25.4 / 1000.0


def rotate_vector(dx: float, dy: float, angle_deg: float) -> Tuple[float, float]:
    """Applique une rotation 2D d'angle angle_deg (degrés anti-horaires)."""
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    return (dx * cos_a - dy * sin_a, dx * sin_a + dy * cos_a)


class DsnPlacementUpdater:
    """Moteur de mise à jour des pastilles d'un fichier Specctra DSN depuis un placement candidat."""

    def __init__(self, baseline_dsn_content: str, geometry_data: Dict[str, Any]):
        self.baseline_dsn = baseline_dsn_content
        self.geometry_data = geometry_data
        # Corrélation : designator -> list de pads {pad_id, shape, dx_0_mm, dy_0_mm, baseline_comp_rot}
        self.comp_to_pads: Dict[str, List[Dict[str, Any]]] = {}
        self.total_correlated_pads = 0
        self._build_correlation_map()

    def _build_correlation_map(self):
        """Associe de façon unique chaque pastille du modèle géométrique à son entrée (pin ...) dans le DSN."""
        # 1. Extraire toutes les pins du DSN de référence
        # Format : (pin <shape_id> <pad_id> <x_mil> <y_mil> [(rotate <deg>)])
        pin_pattern = re.compile(
            r'\(pin\s+([^\s\)]+)\s+([^\s\)]+)\s+([0-9.-]+)\s+([0-9.-]+)(?:\s+\(rotate\s+([0-9.-]+)\))?\)',
            re.IGNORECASE
        )
        dsn_pins: List[Dict[str, Any]] = []
        for m in pin_pattern.finditer(self.baseline_dsn):
            dsn_pins.append({
                "shape": m.group(1),
                "pad_id": m.group(2),
                "x_mil": float(m.group(3)),
                "y_mil": float(m.group(4)),
                "rot": float(m.group(5)) if m.group(5) else 0.0,
                "full_match": m.group(0),
                "used": False
            })

        # 2. Corrélation spatiale avec les composants de geometry_data
        comps = self.geometry_data.get("components", {})
        matched_count = 0
        total_pads = 0

        for des, comp_info in comps.items():
            base_comp_rot = float(comp_info.get("rotation", 0.0))
            pads = comp_info.get("pads", [])
            self.comp_to_pads[des] = []

            for pad in pads:
                total_pads += 1
                p_num = str(pad.get("number", ""))
                px_mm = float(pad.get("x_mm", 0.0))
                py_mm = float(pad.get("y_mm", 0.0))
                dx_0 = float(pad.get("dx_0_mm", 0.0))
                dy_0 = float(pad.get("dy_0_mm", 0.0))

                px_mil = px_mm * MM_TO_MIL
                py_mil = py_mm * MM_TO_MIL

                # Trouver la pin DSN non encore utilisée la plus proche
                best_pin = None
                best_dist_sq = 1e9
                for dp in dsn_pins:
                    if dp["used"]:
                        continue
                    d_sq = (dp["x_mil"] - px_mil) ** 2 + (dp["y_mil"] - py_mil) ** 2
                    if d_sq < best_dist_sq:
                        best_dist_sq = d_sq
                        best_pin = dp

                if best_pin and best_dist_sq <= 1.5:  # Tolérance 1.5 mil (~38 µm)
                    best_pin["used"] = True
                    matched_count += 1
                    self.comp_to_pads[des].append({
                        "number": p_num,
                        "pad_id": best_pin["pad_id"],
                        "shape": best_pin["shape"],
                        "baseline_x_mil": best_pin["x_mil"],
                        "baseline_y_mil": best_pin["y_mil"],
                        "baseline_comp_rot": base_comp_rot,
                        "dx_0_mm": dx_0,
                        "dy_0_mm": dy_0
                    })
                else:
                    logger.warning(f"Pastille non corrélée : {des}.{p_num} à ({px_mil:.2f}, {py_mil:.2f}) mil (dist_sq min={best_dist_sq:.4f})")

        self.total_correlated_pads = matched_count
        logger.info(f"DsnPlacementUpdater : {matched_count}/{total_pads} pastilles corrélées avec le DSN.")

    def update_placement(self, placement: Dict[str, Any]) -> str:
        """
        Génère un nouveau contenu Specctra DSN où toutes les pastilles des composants
        déplacés sont mises à jour avec leurs nouvelles coordonnées (x, y) et rotation.
        """
        replacements: Dict[str, str] = {}
        comps_placement = placement.get("components", placement)

        for des, pads_list in self.comp_to_pads.items():
            if des not in comps_placement:
                continue

            c_target = comps_placement[des]
            cand_x_mm = float(c_target.get("x_mm", 0.0))
            cand_y_mm = float(c_target.get("y_mm", 0.0))
            cand_rot = float(c_target.get("rotation", 0.0))

            for p_info in pads_list:
                dx_0 = p_info["dx_0_mm"]
                dy_0 = p_info["dy_0_mm"]

                # Rotation du décalage relatif par la nouvelle orientation du composant
                rx, ry = rotate_vector(dx_0, dy_0, cand_rot)
                new_pad_x_mm = cand_x_mm + rx
                new_pad_y_mm = cand_y_mm + ry

                new_x_mil = round(new_pad_x_mm * MM_TO_MIL, 2)
                new_y_mil = round(new_pad_y_mm * MM_TO_MIL, 2)

                delta_rot = round((cand_rot - p_info["baseline_comp_rot"]) % 360, 2)

                pad_id = p_info["pad_id"]
                shape = p_info["shape"]

                if delta_rot != 0.0:
                    new_pin_str = f"(pin {shape} {pad_id} {new_x_mil} {new_y_mil} (rotate {delta_rot}))"
                else:
                    new_pin_str = f"(pin {shape} {pad_id} {new_x_mil} {new_y_mil})"

                replacements[pad_id] = new_pin_str

        # 1. Remplacement direct de (wiring ...) par (wiring) pour garantir une carte 100% vierge (Tabula Rasa)
        m_w = re.search(r'\(wiring\b', self.baseline_dsn)
        if m_w:
            s_idx = m_w.start()
            depth = 0
            e_idx = s_idx
            for i in range(s_idx, len(self.baseline_dsn)):
                if self.baseline_dsn[i] == '(':
                    depth += 1
                elif self.baseline_dsn[i] == ')':
                    depth -= 1
                    if depth == 0:
                        e_idx = i + 1
                        break
            clean_dsn = self.baseline_dsn[:s_idx] + '(wiring)' + self.baseline_dsn[e_idx:]
        else:
            clean_dsn = self.baseline_dsn

        # 2. Remplacement direct et rapide des positions de pastilles par regex dans le contenu DSN
        def replace_pin(match: re.Match) -> str:
            pid = match.group(2)
            if pid in replacements:
                return replacements[pid]
            return match.group(0)

        pin_replace_pattern = re.compile(
            r'\(pin\s+([^\s\)]+)\s+([^\s\)]+)\s+[0-9.-]+\s+[0-9.-]+(?:\s+\(rotate\s+[0-9.-]+\))?\)',
            re.IGNORECASE
        )
        return pin_replace_pattern.sub(replace_pin, clean_dsn)


def update_dsn_from_placement(
    baseline_dsn_path: Path,
    geometry_path: Path,
    placement_path: Path,
    output_dsn_path: Path
) -> Path:
    """Fonction utilitaire principale pour mettre à jour un fichier DSN depuis les fichiers JSON."""
    baseline_text = baseline_dsn_path.read_text(encoding="utf-8")
    with open(geometry_path, "r", encoding="utf-8") as f:
        geom_data = json.load(f)
    with open(placement_path, "r", encoding="utf-8") as f:
        place_data = json.load(f)

    updater = DsnPlacementUpdater(baseline_text, geom_data)
    updated_dsn = updater.update_placement(place_data)

    output_dsn_path.parent.mkdir(parents=True, exist_ok=True)
    output_dsn_path.write_text(updated_dsn, encoding="utf-8")
    logger.info(f"DSN mis à jour avec le placement candidat -> {output_dsn_path}")
    return output_dsn_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Mise à jour des pastilles DSN depuis un placement candidat")
    parser.add_argument("--baseline-dsn", type=Path, required=True, help="DSN de référence")
    parser.add_argument("--geometry", type=Path, required=True, help="JSON de géométrie (netlist_geometry.json)")
    parser.add_argument("--placement", type=Path, required=True, help="JSON de placement candidat")
    parser.add_argument("--out", type=Path, required=True, help="DSN de sortie mis à jour")
    args = parser.parse_args()

    update_dsn_from_placement(args.baseline_dsn, args.geometry, args.placement, args.out)
