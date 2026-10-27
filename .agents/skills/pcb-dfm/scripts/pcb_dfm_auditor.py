#!/usr/bin/env python3
"""
Moteur d'Audit PCB DFM (Fabricabilité Usine JLCPCB)
==================================================
Skill: pcb-dfm
Règle 1: Moteur agnostique, zéro composant codé en dur, exécution uv run.
Analyse géométrique des pastilles, vias, sérigraphie et limites mécaniques.
"""

import sys
import math
import logging
from typing import Dict, Any, List, Tuple, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logger = logging.getLogger("pcb_dfm.pcb_auditor")


class PcbDfmAuditor:
    """Moteur algorithmique d'audit géométrique DFM pour PCB nu selon les règles JLCPCB."""

    def __init__(self, rules: Dict[str, Any]):
        pcb_rules = rules.get("pcb_rules", {})
        self.rules = pcb_rules

        # Seuils pont de vernis
        sm_rules = pcb_rules.get("soldermask_bridge", {})
        self.min_sm_bridge_mm = sm_rules.get("min_green_mm", 0.10)
        self.danger_sm_bridge_mm = sm_rules.get("danger_threshold_mm", 0.08)

        # Seuils via-to-pad
        vp_rules = pcb_rules.get("via_to_pad", {})
        self.min_via_to_pad_mm = vp_rules.get("min_clearance_mm", 0.15)
        self.danger_via_to_pad_mm = vp_rules.get("danger_threshold_mm", 0.05)
        self.allow_thermal_pad_vias = vp_rules.get("allow_thermal_pad_vias", True)

        # Seuils sérigraphie
        silk_rules = pcb_rules.get("silkscreen", {})
        self.min_silk_to_pad_mm = silk_rules.get("min_to_pad_clearance_mm", 0.15)
        self.min_silk_to_hole_mm = silk_rules.get("min_to_hole_clearance_mm", 0.15)
        self.min_silk_stroke_mm = silk_rules.get("min_text_stroke_mm", 0.15)

        # Seuils cuivre et bord de carte
        copper_rules = pcb_rules.get("copper", {})
        self.min_copper_to_edge_mm = copper_rules.get("min_copper_to_board_edge_mm", 0.30)
        self.danger_copper_to_edge_mm = copper_rules.get("danger_copper_to_edge_mm", 0.20)

        # Seuils perçage
        drill_rules = pcb_rules.get("drilling", {})
        self.min_via_drill_mm = drill_rules.get("min_via_drill_mm", 0.30)
        self.min_annular_ring_mm = drill_rules.get("min_annular_ring_mm", 0.13)
        self.danger_annular_ring_mm = drill_rules.get("danger_annular_ring_mm", 0.10)

    def audit(self, primitives: Dict[str, Any]) -> Dict[str, Any]:
        """Exécute la suite complète d'audits géométriques DFM."""
        pads = primitives.get("pads", [])
        vias = primitives.get("vias", [])
        strings = primitives.get("strings", [])
        bounds = primitives.get("boardBounds")

        violations: List[Dict[str, Any]] = []

        # 1. Audit des ponts de vernis épargne
        sm_violations = self._audit_soldermask_bridges(pads)
        violations.extend(sm_violations)

        # 2. Audit de proximité Via to Pad (solder wicking)
        vp_violations = self._audit_via_to_pad(pads, vias)
        violations.extend(vp_violations)

        # 3. Audit sérigraphie (stroke, distance aux pastilles et trous)
        silk_violations = self._audit_silkscreen(strings, pads, vias)
        violations.extend(silk_violations)

        # 4. Audit bord de carte
        if bounds:
            edge_violations = self._audit_copper_to_board_edge(pads, vias, bounds)
            violations.extend(edge_violations)

        # 5. Audit perçages et anneaux résiduels
        drill_violations = self._audit_drilling_and_annular_rings(vias)
        violations.extend(drill_violations)

        # Synthèse par niveau de criticité
        danger_count = sum(1 for v in violations if v["severity"] == "DANGER")
        warning_count = sum(1 for v in violations if v["severity"] == "WARNING")
        info_count = sum(1 for v in violations if v["severity"] == "INFO")

        return {
            "total_violations": len(violations),
            "danger_count": danger_count,
            "warning_count": warning_count,
            "info_count": info_count,
            "passed": danger_count == 0,
            "violations": violations
        }

    def _audit_soldermask_bridges(self, pads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Audite la largeur du pont de vernis épargne entre pastilles CMS adjacentes."""
        violations = []
        n = len(pads)

        for i in range(n):
            p1 = pads[i]
            # Pastilles CMS de surface (layer 1 Top ou layer 2 Bottom)
            if p1["layer"] not in (1, 2) or p1["holeDiameter_mm"] > 0:
                continue

            exp1 = p1["topExpansion_mm"] if p1["layer"] == 1 else p1["bottomExpansion_mm"]

            for j in range(i + 1, n):
                p2 = pads[j]
                if p2["layer"] != p1["layer"] or p2["holeDiameter_mm"] > 0:
                    continue

                dx = abs(p1["x_mm"] - p2["x_mm"])
                dy = abs(p1["y_mm"] - p2["y_mm"])
                dist_center = math.hypot(dx, dy)

                # Si les pastilles sont très éloignées (> 4.0 mm), aucun risque de pont
                if dist_center > 4.0:
                    continue

                # Approximation de l'espacement bord à bord le long des axes
                r1_x = p1["width_mm"] / 2.0
                r1_y = p1["height_mm"] / 2.0
                r2_x = p2["width_mm"] / 2.0
                r2_y = p2["height_mm"] / 2.0

                edge_clearance_x = max(0.0, dx - (r1_x + r2_x))
                edge_clearance_y = max(0.0, dy - (r1_y + r2_y))
                edge_clearance = max(edge_clearance_x, edge_clearance_y)

                if dx < (r1_x + r2_x):
                    edge_clearance = edge_clearance_y
                elif dy < (r1_y + r2_y):
                    edge_clearance = edge_clearance_x
                else:
                    edge_clearance = math.hypot(edge_clearance_x, edge_clearance_y)

                exp2 = p2["topExpansion_mm"] if p2["layer"] == 1 else p2["bottomExpansion_mm"]

                # Espace de masque de soudure effectif entre ouvertures
                mask_bridge = edge_clearance - (exp1 + exp2)

                # Si l'espace physique entre cuivre est faible (< 0.8 mm) et que le pont de vernis est insuffisant
                if edge_clearance < 0.80 and mask_bridge < self.min_sm_bridge_mm:
                    severity = "DANGER" if mask_bridge < self.danger_sm_bridge_mm else "WARNING"
                    violations.append({
                        "category": "PCB_DFM_SOLDERMASK_BRIDGE",
                        "severity": severity,
                        "description": (
                            f"Pont de vernis épargne insuffisant ({mask_bridge:.3f} mm < {self.min_sm_bridge_mm:.2f} mm) "
                            f"entre pastilles '{p1['padNumber']}' et '{p2['padNumber']}' (layer {p1['layer']}). "
                            f"Risque d'arrachement de vernis / gang mask."
                        ),
                        "actual_value_mm": round(mask_bridge, 3),
                        "threshold_mm": self.min_sm_bridge_mm,
                        "elements": [p1["id"], p2["id"]],
                        "coordinates": {
                            "x_mm": round((p1["x_mm"] + p2["x_mm"]) / 2.0, 3),
                            "y_mm": round((p1["y_mm"] + p2["y_mm"]) / 2.0, 3)
                        }
                    })

        return violations

    def _audit_via_to_pad(self, pads: List[Dict[str, Any]], vias: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Audite le risque de siphonnage d'étain (solder wicking) entre pastilles CMS et vias."""
        violations = []

        for p in pads:
            # Seulement les pastilles CMS (pas de perçage traversant)
            if p["holeDiameter_mm"] > 0:
                continue

            pad_radius = max(p["width_mm"], p["height_mm"]) / 2.0
            is_thermal_pad = p["width_mm"] > 2.0 and p["height_mm"] > 2.0

            for v in vias:
                dx = abs(p["x_mm"] - v["x_mm"])
                dy = abs(p["y_mm"] - v["y_mm"])
                dist_center = math.hypot(dx, dy)

                if dist_center > (pad_radius + 1.5):
                    continue

                via_radius = v["diameter_mm"] / 2.0
                clearance = dist_center - (pad_radius + via_radius)

                # Via chevauchant ou collé à la pastille
                if clearance < 0:
                    if is_thermal_pad and self.allow_thermal_pad_vias:
                        # Vias thermiques acceptables sur dissipateur
                        continue
                    violations.append({
                        "category": "PCB_DFM_VIA_IN_PAD",
                        "severity": "DANGER",
                        "description": (
                            f"Via chevauche directement la pastille CMS '{p['padNumber']}' "
                            f"(distance bord = {clearance:.3f} mm). Risque majeur de siphonnage de brasure."
                        ),
                        "actual_value_mm": round(clearance, 3),
                        "threshold_mm": 0.0,
                        "elements": [p["id"], v["id"]],
                        "coordinates": {"x_mm": v["x_mm"], "y_mm": v["y_mm"]}
                    })
                elif clearance < self.min_via_to_pad_mm:
                    severity = "DANGER" if clearance < self.danger_via_to_pad_mm else "WARNING"
                    violations.append({
                        "category": "PCB_DFM_VIA_TO_PAD_PROXIMITY",
                        "severity": severity,
                        "description": (
                            f"Via trop proche de la pastille CMS '{p['padNumber']}' "
                            f"({clearance:.3f} mm < {self.min_via_to_pad_mm:.2f} mm). "
                            f"Insérer un col de piste dog-bone >= {self.min_via_to_pad_mm:.2f} mm."
                        ),
                        "actual_value_mm": round(clearance, 3),
                        "threshold_mm": self.min_via_to_pad_mm,
                        "elements": [p["id"], v["id"]],
                        "coordinates": {"x_mm": v["x_mm"], "y_mm": v["y_mm"]}
                    })

        return violations

    def _audit_silkscreen(
        self,
        strings: List[Dict[str, Any]],
        pads: List[Dict[str, Any]],
        vias: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Audite l'épaisseur des traits de sérigraphie et le dégagement face au cuivre nu et perçages."""
        violations = []

        for s in strings:
            # 1. Épaisseur de trait de sérigraphie
            if 0 < s["strokeWidth_mm"] < self.min_silk_stroke_mm:
                violations.append({
                    "category": "PCB_DFM_SILKSCREEN_STROKE",
                    "severity": "WARNING",
                    "description": (
                        f"Trait de sérigraphie trop fin pour le texte '{s['text']}' "
                        f"({s['strokeWidth_mm']:.3f} mm < {self.min_silk_stroke_mm:.2f} mm). "
                        f"Augmenter à >= 0.18 mm pour un rendu net."
                    ),
                    "actual_value_mm": s["strokeWidth_mm"],
                    "threshold_mm": self.min_silk_stroke_mm,
                    "elements": [s["id"]],
                    "coordinates": {"x_mm": s["x_mm"], "y_mm": s["y_mm"]}
                })

            # Estimation de la bounding box du texte
            char_count = max(1, len(s["text"]))
            est_width = s["height_mm"] * 0.7 * char_count
            est_height = s["height_mm"]
            silk_radius = math.hypot(est_width / 2.0, est_height / 2.0)

            # Dégagement face aux pastilles de cuivre
            for p in pads:
                dist = math.hypot(s["x_mm"] - p["x_mm"], s["y_mm"] - p["y_mm"])
                pad_r = max(p["width_mm"], p["height_mm"]) / 2.0
                clearance = dist - (silk_radius + pad_r)

                if clearance < self.min_silk_to_pad_mm:
                    violations.append({
                        "category": "PCB_DFM_SILKSCREEN_TO_PAD",
                        "severity": "WARNING",
                        "description": (
                            f"Texte de sérigraphie '{s['text']}' trop proche de la pastille '{p['padNumber']}' "
                            f"({clearance:.3f} mm < {self.min_silk_to_pad_mm:.2f} mm). "
                            f"Risque d'auto-clipping ou de bavure."
                        ),
                        "actual_value_mm": round(clearance, 3),
                        "threshold_mm": self.min_silk_to_pad_mm,
                        "elements": [s["id"], p["id"]],
                        "coordinates": {"x_mm": s["x_mm"], "y_mm": s["y_mm"]}
                    })
                    break  # Une alerte par chaîne de texte suffit

        return violations

    def _audit_copper_to_board_edge(
        self,
        pads: List[Dict[str, Any]],
        vias: List[Dict[str, Any]],
        bounds: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Audite le recul du cuivre par rapport au contour mécanique de la carte."""
        violations = []
        min_x = bounds["minX_mm"]
        max_x = bounds["maxX_mm"]
        min_y = bounds["minY_mm"]
        max_y = bounds["maxY_mm"]

        for v in vias:
            r = v["diameter_mm"] / 2.0
            dist_left = v["x_mm"] - r - min_x
            dist_right = max_x - (v["x_mm"] + r)
            dist_bottom = v["y_mm"] - r - min_y
            dist_top = max_y - (v["y_mm"] + r)

            min_edge_dist = min(dist_left, dist_right, dist_bottom, dist_top)

            if min_edge_dist < self.min_copper_to_edge_mm:
                severity = "DANGER" if min_edge_dist < self.danger_copper_to_edge_mm else "WARNING"
                violations.append({
                    "category": "PCB_DFM_COPPER_TO_EDGE",
                    "severity": severity,
                    "description": (
                        f"Via trop proche du bord de carte ({min_edge_dist:.3f} mm < {self.min_copper_to_edge_mm:.2f} mm). "
                        f"Risque de sectionnement lors du fraisage / dépyranage."
                    ),
                    "actual_value_mm": round(min_edge_dist, 3),
                    "threshold_mm": self.min_copper_to_edge_mm,
                    "elements": [v["id"]],
                    "coordinates": {"x_mm": v["x_mm"], "y_mm": v["y_mm"]}
                })

        return violations

    def _audit_drilling_and_annular_rings(self, vias: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Audite les diamètres minimaux de perçage et la bague de cuivre (annular ring)."""
        violations = []

        for v in vias:
            # Perçage minimal
            if v["holeDiameter_mm"] < self.min_via_drill_mm:
                violations.append({
                    "category": "PCB_DFM_MIN_DRILL",
                    "severity": "WARNING",
                    "description": (
                        f"Perçage de via {v['holeDiameter_mm']:.3f} mm inférieur au seuil standard "
                        f"de {self.min_via_drill_mm:.2f} mm. Surcoût fabrication micro-perçage."
                    ),
                    "actual_value_mm": v["holeDiameter_mm"],
                    "threshold_mm": self.min_via_drill_mm,
                    "elements": [v["id"]],
                    "coordinates": {"x_mm": v["x_mm"], "y_mm": v["y_mm"]}
                })

            # Bague de cuivre (annular ring)
            if v["annularRing_mm"] < self.min_annular_ring_mm:
                severity = "DANGER" if v["annularRing_mm"] < self.danger_annular_ring_mm else "WARNING"
                violations.append({
                    "category": "PCB_DFM_ANNULAR_RING",
                    "severity": severity,
                    "description": (
                        f"Bague de cuivre (annular ring) insuffisante ({v['annularRing_mm']:.3f} mm < {self.min_annular_ring_mm:.2f} mm). "
                        f"Risque de rupture électrique lors du désalignement de perçage."
                    ),
                    "actual_value_mm": v["annularRing_mm"],
                    "threshold_mm": self.min_annular_ring_mm,
                    "elements": [v["id"]],
                    "coordinates": {"x_mm": v["x_mm"], "y_mm": v["y_mm"]}
                })

        return violations
