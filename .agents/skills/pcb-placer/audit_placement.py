#!/usr/bin/env python3
"""
Module d'Audit Géométrique et de Contrôle des Règles de Conception (Agnostique)
================================================================================
Vérifie la conformité physique du PCB actif dans EasyEDA Pro par rapport à un
fichier de configuration formel (ex: floorplan.json) passé obligatoirement en paramètre :
- Position des ancres mécaniques
- Distances de découplage HF, reset, TVS/ESD
- Respect des zones d'exclusion (Keepouts)
- Marges de bord de carte (Edge Clearance)
"""

import argparse
import math
import sys
import logging
from typing import Any, Dict, List, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from easyeda_client import EasyEDAClient
from placement_constraints import (
    FloorplanConfig,
    load_floorplan,
    mil_to_mm,
    mm_to_mil
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PCBAuditor")


class PCBAuditor:
    """Auditeur géométrique et CEM agnostique pour PCB sous EasyEDA Pro."""

    def __init__(self, config: FloorplanConfig, client: Optional[EasyEDAClient] = None):
        self.config = config
        self.client = client or EasyEDAClient()

    def audit_board(self) -> Dict[str, Any]:
        """Exécute l'audit complet du PCB actif contre la configuration chargée."""
        report = {
            "connected": False,
            "project_name": self.config.project_name,
            "components_count": 0,
            "pads_count": 0,
            "rules_checked": 0,
            "rules_passed": 0,
            "violations": [],
            "warnings": []
        }

        try:
            h = self.client.health()
            if not h.get("edaConnected"):
                logger.warning("Client EasyEDA Pro non connecté. Impossible d'auditer le layout live.")
                return report
            report["connected"] = True
        except Exception as e:
            logger.error(f"Erreur de communication avec le pont : {e}")
            return report

        try:
            logger.info("Extraction des composants et pastilles du PCB...")
            components = self.client.get_components_with_pads()
            pads = self.client.get_all_pads()
        except Exception as e:
            logger.warning(f"Impossible de lire les éléments PCB : {e}")
            report["warnings"].append(
                "Impossible d'extraire les éléments du PCB depuis EasyEDA Pro. "
                "Assurez-vous qu'un document PCB est bien ouvert au premier plan dans EasyEDA Pro."
            )
            return report

        report["components_count"] = len(components)
        report["pads_count"] = len(pads)

        comp_map = {c.get("designator"): c for c in components if c.get("designator")}
        logger.info(f"Analyse géométrique de {len(components)} composants pour le projet '{self.config.project_name}'...")

        # 0. Vérification du Contour Mécanique (Layer 11)
        outline = self.client.get_board_outline() or {}
        bbox = outline.get("boundingBox")
        report["rules_checked"] += 1
        if not bbox:
            report["warnings"].append("Contour de carte mécanique (Layer 11) non détecté sur le PCB.")
        else:
            w_diff = abs(bbox["width_mm"] - self.config.board.width_mm)
            h_diff = abs(bbox["height_mm"] - self.config.board.height_mm)
            if w_diff > 0.5 or h_diff > 0.5:
                report["warnings"].append(
                    f"Contour mécanique ({bbox['width_mm']:.2f} × {bbox['height_mm']:.2f} mm) "
                    f"diffère du gabarit cible ({self.config.board.width_mm:.2f} × {self.config.board.height_mm:.2f} mm)"
                )
            else:
                report["rules_passed"] += 1

        # 0.bis Vérification des Trous de Fixation Mécaniques
        mh_pads = {p.get("number"): p for p in pads if p.get("number") and str(p.get("number")).startswith("MH")}
        expected_holes = getattr(self.config.board, "mounting_holes", [])
        if expected_holes:
            report["rules_checked"] += 1
            missing_holes = [h["id"] for h in expected_holes if h["id"] not in mh_pads]
            if missing_holes:
                report["violations"].append(
                    f"VIOLATION FIXATION : Trou(s) de montage manquant(s) sur le PCB : {', '.join(missing_holes)}"
                )
            else:
                report["rules_passed"] += 1

            # Dégagement tête de vis (4.5 mm diamètre / 2.25 mm rayon)
            report["rules_checked"] += 1
            screw_encroachments = []
            for h in expected_holes:
                hx, hy = h.get("x_mil", 0.0), h.get("y_mil", 0.0)
                head_r_mm = (h.get("head_clearance_mil", 177.2) / 2.0) * 0.0254
                for des, comp in comp_map.items():
                    if des in self.config.anchors:
                        continue
                    cx, cy = comp.get("x", 0.0), comp.get("y", 0.0)
                    dist_mm = mil_to_mm(math.sqrt((cx - hx) ** 2 + (cy - hy) ** 2))
                    if dist_mm < head_r_mm:
                        screw_encroachments.append(f"{des} à {dist_mm:.1f} mm de {h['id']}")
            if screw_encroachments:
                report["violations"].append(
                    f"VIOLATION DÉGAGEMENT VIS : Composant(s) sous tête de vis : {', '.join(screw_encroachments)}"
                )
            else:
                report["rules_passed"] += 1

        # 1. Vérification des Ancres Fixes
        for des, anchor in self.config.anchors.items():
            comp = comp_map.get(des)
            if not comp:
                report["warnings"].append(f"Ancre mécanique {des} absente du PCB.")
                continue

            cur_x = comp.get("x", 0.0)
            cur_y = comp.get("y", 0.0)

            dx_mm = mil_to_mm(abs(cur_x - anchor.target_x_mil))
            dy_mm = mil_to_mm(abs(cur_y - anchor.target_y_mil))

            if dx_mm > 1.0 or dy_mm > 1.0:
                report["warnings"].append(
                    f"Ancre {des} décalée : position actuelle ({cur_x:.0f}, {cur_y:.0f}) mil "
                    f"vs consigne ({anchor.target_x_mil:.0f}, {anchor.target_y_mil:.0f}) mil"
                )

        # 2. Vérification des Règles de Proximité (Pad-à-Pad réel)
        for rule in self.config.proximity_rules:
            report["rules_checked"] += 1
            comp = comp_map.get(rule.component)
            ref_comp = comp_map.get(rule.reference_component)

            if not comp or not ref_comp:
                report["warnings"].append(
                    f"Règle '{rule.description}' : composant {rule.component} ou {rule.reference_component} non trouvé."
                )
                continue

            c_pads = comp.get("pads", [])
            ref_pads = ref_comp.get("pads", [])
            dist_mil = float("inf")
            method = "centre-à-centre"

            if c_pads and ref_pads:
                # Priorité 1 : Pastilles partageant explicitement target_net
                if rule.target_net:
                    cp_target = [p for p in c_pads if p.get("net") == rule.target_net]
                    rp_target = [p for p in ref_pads if p.get("net") == rule.target_net]
                    if cp_target and rp_target:
                        dist_mil = min(
                            math.hypot(p1["x"] - p2["x"], p1["y"] - p2["y"])
                            for p1 in cp_target for p2 in rp_target
                        )
                        method = f"net({rule.target_net})"

                # Priorité 2 : Pastilles partageant un net de signal commun
                if dist_mil == float("inf"):
                    c_nets = set(p.get("net") for p in c_pads if p.get("net"))
                    ref_nets = set(p.get("net") for p in ref_pads if p.get("net"))
                    common_nets = c_nets.intersection(ref_nets)
                    signal_common = [n for n in common_nets if n not in ("GND", "DGND", "AGND")]
                    nets_to_check = signal_common if signal_common else list(common_nets)
                    if nets_to_check:
                        best_d = float("inf")
                        best_n = None
                        for net in nets_to_check:
                            cp_n = [p for p in c_pads if p.get("net") == net]
                            rp_n = [p for p in ref_pads if p.get("net") == net]
                            d = min(
                                math.hypot(p1["x"] - p2["x"], p1["y"] - p2["y"])
                                for p1 in cp_n for p2 in rp_n
                            )
                            if d < best_d:
                                best_d = d
                                best_n = net
                        dist_mil = best_d
                        method = f"net_commun({best_n})"

                # Priorité 3 : Distance minimale entre n'importe quelle paire de pastilles
                if dist_mil == float("inf"):
                    dist_mil = min(
                        math.hypot(p1["x"] - p2["x"], p1["y"] - p2["y"])
                        for p1 in c_pads for p2 in ref_pads
                    )
                    method = "min_pad"
            else:
                dist_mil = math.hypot(
                    comp.get("x", 0.0) - ref_comp.get("x", 0.0),
                    comp.get("y", 0.0) - ref_comp.get("y", 0.0)
                )

            dist_mm = mil_to_mm(dist_mil)

            if dist_mm <= rule.max_distance_mm:
                report["rules_passed"] += 1
            else:
                violation_msg = (
                    f"VIOLATION PROXIMITÉ : {rule.description} | Distance actuelle : {dist_mm:.2f} mm "
                    f"(seuil max : {rule.max_distance_mm:.2f} mm, mesure : {method})"
                )
                report["violations"].append(violation_msg)

        # 3. Vérification des Zones d'Exclusion (Keepouts)
        for zone in self.config.keepout_zones:
            for des, comp in comp_map.items():
                if des in self.config.anchors:
                    continue
                cx = comp.get("x", 0.0)
                cy = comp.get("y", 0.0)
                if zone.x_min_mil <= cx <= zone.x_max_mil and zone.y_min_mil <= cy <= zone.y_max_mil:
                    report["violations"].append(
                        f"VIOLATION KEEPOUT : Composant {des} situé à ({cx:.0f}, {cy:.0f}) mil "
                        f"dans la zone interdite '{zone.name}'"
                    )

        # 4. Vérification de la Marge de Bord de Carte (Edge Clearance)
        edge_clearance_mil = self.config.board.edge_clearance_mil
        board_w_mil = self.config.board.width_mil
        board_h_mil = self.config.board.height_mil
        for des, comp in comp_map.items():
            if des in self.config.anchors:
                continue
            cx = comp.get("x", 0.0)
            cy = comp.get("y", 0.0)
            if (cx < edge_clearance_mil or cx > (board_w_mil - edge_clearance_mil) or
                cy < edge_clearance_mil or cy > (board_h_mil - edge_clearance_mil)):
                report["warnings"].append(
                    f"Composant {des} situé à ({cx:.0f}, {cy:.0f}) mil trop près du bord de carte "
                    f"(marge requise : {self.config.board.edge_clearance_mm:.1f} mm / {edge_clearance_mil:.0f} mil)"
                )

        return report

    def print_report(self, report: Dict[str, Any]):
        """Affiche un rapport lisible dans la console."""
        print("\n" + "=" * 75)
        print(f" RAPPORT D'AUDIT GÉOMÉTRIQUE & CEM : {report.get('project_name', 'PCB')} ")
        print("=" * 75)

        if not report.get("connected"):
            print("⚠️  EasyEDA Pro non connecté : activez le pont et ouvrez le document PCB.")
            print("=" * 75)
            return

        print(f"Composants analysés  : {report['components_count']}")
        print(f"Pastilles détectées  : {report['pads_count']}")
        print(f"Règles contrôlées    : {report['rules_checked']}")
        print(f"Règles validées      : {report['rules_passed']} / {report['rules_checked']}")
        print(f"Violations critiques : {len(report['violations'])}")
        print(f"Avertissements       : {len(report['warnings'])}")
        print("-" * 75)

        if report["violations"]:
            print("❌ VIOLATIONS CRITIQUES :")
            for v in report["violations"]:
                print(f"   • {v}")
        else:
            print("✅ Aucune violation critique détectée.")

        if report["warnings"]:
            print("\n⚠️  AVERTISSEMENTS :")
            for w in report["warnings"]:
                print(f"   • {w}")

        print("=" * 75 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Auditeur géométrique et CEM pour PCB EasyEDA Pro (moteur agnostique)."
    )
    parser.add_argument(
        "-c", "--config",
        required=True,
        help="Chemin vers le fichier JSON de contraintes/floorplan (ex: floorplan.json)"
    )

    args = parser.parse_args()

    try:
        config = load_floorplan(args.config)
    except Exception as e:
        logger.error(f"Impossible de charger la configuration '{args.config}' : {e}")
        sys.exit(1)

    auditor = PCBAuditor(config)
    report = auditor.audit_board()
    auditor.print_report(report)

    if report["violations"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
