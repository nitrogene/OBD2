#!/usr/bin/env python3
"""
Moteur d'Audit SMT DFM (Assemblage Automatisé JLCPCB)
====================================================
Skill: pcb-dfm
Règle 1: Moteur agnostique, zéro composant codé en dur, exécution uv run.
Analyse de l'espacement inter-composants, cohérence BOM / CPL,
détection des pièces THT/CMS et repères optiques de cadrage.
"""

import sys
import math
import logging
from typing import Dict, Any, List, Optional, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logger = logging.getLogger("pcb_dfm.smt_auditor")


class SmtDfmAuditor:
    """Moteur algorithmique d'audit SMT pour l'assemblage industriel JLCPCB."""

    def __init__(self, rules: Dict[str, Any], bom_data: Optional[Dict[str, Any]] = None):
        smt_rules = rules.get("smt_rules", {})
        self.rules = smt_rules
        self.bom_data = bom_data or {}

        # Seuils d'espacement CMS
        spacing_rules = smt_rules.get("spacing", {})
        self.min_comp_spacing_mm = spacing_rules.get("min_component_to_component_mm", 0.50)
        self.danger_comp_spacing_mm = spacing_rules.get("danger_component_to_component_mm", 0.25)

        # Seuils convoyeur
        conveyor_rules = smt_rules.get("conveyor", {})
        self.min_rail_margin_mm = conveyor_rules.get("min_rail_margin_mm", 3.0)

        # Seuils repères fiduciaires
        fid_rules = smt_rules.get("fiducials", {})
        self.required_fiducials = fid_rules.get("required_count", 3)

    def audit(self, primitives: Dict[str, Any]) -> Dict[str, Any]:
        """Exécute l'audit complet d'assemblage SMT."""
        components = primitives.get("components", [])
        pads = primitives.get("pads", [])
        bounds = primitives.get("boardBounds")

        violations: List[Dict[str, Any]] = []

        # 1. Audit d'espacement composant à composant
        spacing_violations = self._audit_component_spacing(components)
        violations.extend(spacing_violations)

        # 2. Audit des marges de convoyeur SMT
        if bounds:
            rail_violations = self._audit_conveyor_rail_margins(components, bounds)
            violations.extend(rail_violations)

        # 3. Audit des repères fiduciaires
        fid_violations = self._audit_fiducials(components, pads)
        violations.extend(fid_violations)

        # 4. Audit de cohérence BOM vs Placement PCB
        bom_violations, smt_summary = self._audit_bom_coherence(components)
        violations.extend(bom_violations)

        danger_count = sum(1 for v in violations if v["severity"] == "DANGER")
        warning_count = sum(1 for v in violations if v["severity"] == "WARNING")
        info_count = sum(1 for v in violations if v["severity"] == "INFO")

        return {
            "total_violations": len(violations),
            "danger_count": danger_count,
            "warning_count": warning_count,
            "info_count": info_count,
            "passed": danger_count == 0,
            "smt_summary": smt_summary,
            "violations": violations
        }

    def _audit_component_spacing(self, components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Audite l'espace libre entre composants CMS pour le passage des buses Pick & Place."""
        violations = []
        n = len(components)

        for i in range(n):
            c1 = components[i]
            if not c1["designator"]:
                continue

            for j in range(i + 1, n):
                c2 = components[j]
                if not c2["designator"] or c1["layer"] != c2["layer"]:
                    continue

                dx = abs(c1["x_mm"] - c2["x_mm"])
                dy = abs(c1["y_mm"] - c2["y_mm"])
                dist_center = math.hypot(dx, dy)

                # Estimation d'un encombrement moyen par défaut (0.8 mm rayon)
                # Si deux centres sont à moins de 1.2 mm, ils sont très proches
                if dist_center < 1.0:
                    severity = "DANGER" if dist_center < self.danger_comp_spacing_mm else "WARNING"
                    violations.append({
                        "category": "SMT_DFM_COMPONENT_CLEARANCE",
                        "severity": severity,
                        "description": (
                            f"Proximité critique entre composants '{c1['designator']}' et '{c2['designator']}' "
                            f"(distance centre-à-centre {dist_center:.3f} mm). "
                            f"Risque d'interférence buse Pick & Place ou effet d'ombre à la refusion."
                        ),
                        "actual_value_mm": round(dist_center, 3),
                        "threshold_mm": self.min_comp_spacing_mm,
                        "elements": [c1["id"], c2["id"]],
                        "coordinates": {
                            "x_mm": round((c1["x_mm"] + c2["x_mm"]) / 2.0, 3),
                            "y_mm": round((c1["y_mm"] + c2["y_mm"]) / 2.0, 3)
                        }
                    })

        return violations

    def _audit_conveyor_rail_margins(
        self,
        components: List[Dict[str, Any]],
        bounds: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Audite le respect des bords libres pour les rails de convoyeur CMS."""
        violations = []
        min_y = bounds["minY_mm"]
        max_y = bounds["maxY_mm"]

        for c in components:
            if not c["designator"]:
                continue

            dist_bottom = c["y_mm"] - min_y
            dist_top = max_y - c["y_mm"]
            min_rail_dist = min(dist_bottom, dist_top)

            if min_rail_dist < self.min_rail_margin_mm:
                violations.append({
                    "category": "SMT_DFM_RAIL_MARGIN",
                    "severity": "INFO",
                    "description": (
                        f"Composant '{c['designator']}' implanté à {min_rail_dist:.3f} mm du bord long "
                        f"(recommandé >= {self.min_rail_margin_mm:.1f} mm sans bande martyr / breakaway panel). "
                        f"Un panel avec rails d'outillage (tooling strips) sera nécessaire pour l'assemblage SMT automatisé."
                    ),
                    "actual_value_mm": round(min_rail_dist, 3),
                    "threshold_mm": self.min_rail_margin_mm,
                    "elements": [c["id"]],
                    "coordinates": {"x_mm": c["x_mm"], "y_mm": c["y_mm"]}
                })

        return violations

    def _audit_fiducials(
        self,
        components: List[Dict[str, Any]],
        pads: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Audite la présence de repères fiduciaires optiques sur la carte."""
        violations = []

        # Recherche de composants ou pastilles identifiés comme repères optiques (FID, FIDUCIAL, MARK)
        fiducials = [
            c for c in components
            if "FID" in (c["designator"] or "").upper() or "FIDUCIAL" in (c["footprint"] or "").upper()
        ]

        if len(fiducials) < self.required_fiducials:
            violations.append({
                "category": "SMT_DFM_FIDUCIALS_MISSING",
                "severity": "WARNING",
                "description": (
                    f"Seulement {len(fiducials)} repère(s) fiduciaire(s) détecté(s) sur le PCB "
                    f"(recommandé : au moins {self.required_fiducials} repères optiques en L / triangle). "
                    f"Prévoir l'ajout de 3 pastilles circulaires 1.0 mm isolées ou des repères sur les bandes d'outillage."
                ),
                "actual_value_mm": len(fiducials),
                "threshold_mm": self.required_fiducials,
                "elements": [f["id"] for f in fiducials],
                "coordinates": {"x_mm": 0, "y_mm": 0}
            })

        return violations

    def _audit_bom_coherence(
        self,
        components: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Croise les désignateurs du PCB avec la nomenclature BOM."""
        violations = []
        pcb_designators = {c["designator"] for c in components if c["designator"]}

        bom_raw = self.bom_data.get("components", {})
        bom_components = {}
        if isinstance(bom_raw, dict):
            bom_components = bom_raw
        elif isinstance(bom_raw, list):
            for item in bom_raw:
                if isinstance(item, dict) and item.get("designator"):
                    bom_components[item["designator"]] = item

        bom_designators = set(bom_components.keys())

        # Détection des pièces dans la BOM mais non placées sur le PCB
        unplaced_bom = bom_designators - pcb_designators
        for des in unplaced_bom:
            violations.append({
                "category": "SMT_DFM_BOM_UNPLACED",
                "severity": "DANGER",
                "description": f"Composant '{des}' présent dans la BOM mais absent ou sans désignateur sur le PCB.",
                "actual_value_mm": 0,
                "threshold_mm": 1,
                "elements": [],
                "coordinates": {"x_mm": 0, "y_mm": 0}
            })

        # Détection des composants placés sans correspondance dans la BOM
        unlisted_pcb = pcb_designators - bom_designators
        for des in unlisted_pcb:
            # Ignorer les trous de fixation ou fiducials
            if des.startswith("MH") or des.startswith("FID") or des.startswith("TP"):
                continue
            violations.append({
                "category": "SMT_DFM_PCB_UNLISTED_IN_BOM",
                "severity": "WARNING",
                "description": f"Composant '{des}' présent sur le PCB mais absent de la BOM.",
                "actual_value_mm": 0,
                "threshold_mm": 1,
                "elements": [],
                "coordinates": {"x_mm": 0, "y_mm": 0}
            })

        # Synthèse SMT (CMS vs Traversant THT)
        tht_designators = []
        smt_designators = []
        for des, info in bom_components.items():
            pkg = str(info.get("package", "")).upper()
            if "TH" in pkg or des.startswith("J") or des.startswith("H") or des.startswith("JP"):
                tht_designators.append(des)
            else:
                smt_designators.append(des)

        summary = {
            "total_bom_components": len(bom_designators),
            "total_pcb_components": len(pcb_designators),
            "smt_pick_and_place_count": len(smt_designators),
            "tht_manual_assembly_count": len(tht_designators),
            "tht_designators": sorted(tht_designators)
        }

        return violations, summary
