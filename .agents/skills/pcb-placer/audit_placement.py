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

import json
from pathlib import Path

from easyeda_client import EasyEDAClient
from placement_constraints import (
    FloorplanConfig,
    load_floorplan,
    mil_to_mm,
    mm_to_mil
)
from score import (
    RectBox,
    get_component_courtyard_box,
    get_all_keepouts
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PCBAuditor")


class PCBAuditor:
    """Auditeur géométrique et CEM agnostique pour PCB sous EasyEDA Pro."""

    def __init__(
        self,
        config: FloorplanConfig,
        client: Optional[EasyEDAClient] = None,
        placement_path: Optional[Path] = None
    ):
        self.config = config
        self.client = client or EasyEDAClient()
        self.placement_path = placement_path

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

        components = []
        pads = []

        if self.placement_path and self.placement_path.is_file():
            logger.info(f"Mode audit hors-ligne : chargement de {self.placement_path.name}...")
            report["connected"] = True
            with open(self.placement_path, "r", encoding="utf-8") as f:
                pdata = json.load(f)
            comps_dict = pdata.get("components", {})
            for des, cp in comps_dict.items():
                x_mm = float(cp.get("x_mm", cp.get("x", 0.0)))
                y_mm = float(cp.get("y_mm", cp.get("y", 0.0)))
                rot = float(cp.get("rotation", cp.get("rot", 0.0)))
                components.append({
                    "designator": des,
                    "x": mm_to_mil(x_mm),
                    "y": mm_to_mil(y_mm),
                    "rotation": rot,
                    "pads": []
                })
        else:
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

        packages = self.config.manifest.get("packages", {})
        manifest_comps = self.config.manifest.get("components", {})

        comp_positions: Dict[str, Tuple[float, float, float]] = {}
        comp_boxes: Dict[str, RectBox] = {}

        for des, comp in comp_map.items():
            cx_mm = mil_to_mm(comp.get("x", 0.0))
            cy_mm = mil_to_mm(comp.get("y", 0.0))
            rot = float(comp.get("rotation", 0.0))
            comp_positions[des] = (cx_mm, cy_mm, rot)

            comp_meta = manifest_comps.get(des, {})
            pkg_name = comp_meta.get("package") or comp_meta.get("footprint", "0603")
            pkg_info = packages.get(pkg_name, {"width_mm": 1.6, "length_mm": 0.8, "courtyard_margin_mm": 0.25})
            comp_boxes[des] = get_component_courtyard_box(cx_mm, cy_mm, rot, pkg_info)

        # 0. Vérification du Contour Mécanique (Layer 11)
        if not self.placement_path:
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
        expected_holes = getattr(self.config.board, "mounting_holes", [])
        if expected_holes:
            report["rules_checked"] += 1
            if pads:
                mh_pads = {p.get("number"): p for p in pads if p.get("number") and str(p.get("number")).startswith("MH")}
                missing_holes = [h["id"] for h in expected_holes if h["id"] not in mh_pads]
                if missing_holes:
                    report["violations"].append(
                        f"VIOLATION FIXATION : Trou(s) de montage manquant(s) sur le PCB : {', '.join(missing_holes)}"
                    )
                else:
                    report["rules_passed"] += 1
            else:
                report["rules_passed"] += 1

            # Dégagement tête de vis (4.5 mm diamètre / 2.25 mm rayon) avec test du courtyard complet
            report["rules_checked"] += 1
            screw_encroachments = []
            for h in expected_holes:
                hx_mm = float(h.get("x_mm", mil_to_mm(h.get("x_mil", 0.0))))
                hy_mm = float(h.get("y_mm", mil_to_mm(h.get("y_mil", 0.0))))
                head_r_mm = float(h.get("head_clearance_mm", (h.get("head_clearance_mil", 177.2) / 2.0) * 0.0254)) / 2.0
                hole_box = RectBox(hx_mm - head_r_mm, hx_mm + head_r_mm, hy_mm - head_r_mm, hy_mm + head_r_mm)

                for des, box in comp_boxes.items():
                    if des in self.config.anchors:
                        continue
                    if box.intersects(hole_box):
                        area = box.intersection_area(hole_box)
                        if area > 0.01:
                            cx, cy = comp_positions[des][0], comp_positions[des][1]
                            dist_mm = math.hypot(cx - hx_mm, cy - hy_mm)
                            screw_encroachments.append(f"{des} à {dist_mm:.1f} mm de {h.get('id', 'MH')} (collision courtyard : {area:.2f} mm²)")

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

        # 3. Vérification des Zones d'Exclusion (Keepouts statiques et dynamiques via Courtyard)
        raw_board = self.config.raw_data or {
            "keepout_zones": [
                {
                    "name": kz.name,
                    "rect_mm": {
                        "x_min": mil_to_mm(kz.x_min_mil),
                        "x_max": mil_to_mm(kz.x_max_mil),
                        "y_min": mil_to_mm(kz.y_min_mil),
                        "y_max": mil_to_mm(kz.y_max_mil)
                    }
                } for kz in self.config.keepout_zones
            ],
            "board": {
                "width_mm": self.config.board.width_mm,
                "height_mm": self.config.board.height_mm
            }
        }
        all_keepouts = get_all_keepouts(raw_board, self.config.manifest, comp_positions)

        for kz in all_keepouts:
            kname = kz.get("name", "KEEPOUT")
            rect = kz.get("rect_mm", {})
            kbox = RectBox(
                x_min=rect.get("x_min", 0.0),
                x_max=rect.get("x_max", 0.0),
                y_min=rect.get("y_min", 0.0),
                y_max=rect.get("y_max", 0.0)
            )
            exempt = set(kz.get("exempt_refs", []))

            for des, box in comp_boxes.items():
                if des in exempt or des in self.config.anchors:
                    continue
                report["rules_checked"] += 1
                if box.intersects(kbox):
                    area = box.intersection_area(kbox)
                    if area > 0.01:
                        report["violations"].append(
                            f"VIOLATION KEEPOUT : Composant {des} empiète sur la zone interdite '{kname}' "
                            f"(courtyard en collision : {area:.2f} mm²)"
                        )
                    else:
                        report["rules_passed"] += 1
                else:
                    report["rules_passed"] += 1

        # 4. Vérification de la Marge de Bord de Carte (Edge Clearance via Courtyard)
        edge_clearance_mm = self.config.board.edge_clearance_mm
        board_w_mm = self.config.board.width_mm
        board_h_mm = self.config.board.height_mm
        for des, box in comp_boxes.items():
            if des in self.config.anchors:
                continue
            report["rules_checked"] += 1
            if (box.x_min < edge_clearance_mm or box.x_max > (board_w_mm - edge_clearance_mm) or
                box.y_min < edge_clearance_mm or box.y_max > (board_h_mm - edge_clearance_mm)):
                report["warnings"].append(
                    f"Composant {des} situé trop près du bord de carte "
                    f"(courtyard [{box.x_min:.1f}, {box.x_max:.1f}, {box.y_min:.1f}, {box.y_max:.1f}] mm "
                    f"enfreint la marge requise de {edge_clearance_mm:.1f} mm)"
                )
            else:
                report["rules_passed"] += 1

        # 5. Vérification de la Cohésion des Blocs Fonctionnels (Clusters)
        clusters = getattr(self.config, "functional_clusters", {})
        cluster_max_radius_mm = 12.0
        for cluster_name, members in clusters.items():
            valid_m = [m for m in members if m in comp_map and m not in self.config.anchors]
            if len(valid_m) <= 1:
                continue

            # Trouver le composant maître du cluster (IC 'U*')
            anchor_candidates = [m for m in valid_m if m.startswith("U")]
            anchor_des = anchor_candidates[0] if anchor_candidates else valid_m[0]
            anchor_comp = comp_map[anchor_des]
            ax_mil = anchor_comp.get("x", 0.0)
            ay_mil = anchor_comp.get("y", 0.0)

            for m in valid_m:
                if m == anchor_des:
                    continue
                report["rules_checked"] += 1
                c = comp_map[m]
                mx_mil = c.get("x", 0.0)
                my_mil = c.get("y", 0.0)
                dist_mm = mil_to_mm(math.hypot(mx_mil - ax_mil, my_mil - ay_mil))
                if dist_mm > cluster_max_radius_mm:
                    report["warnings"].append(
                        f"COHÉSION DE BLOC : Composant {m} du bloc '{cluster_name}' dispersé à {dist_mm:.1f} mm "
                        f"de son ancre {anchor_des} (seuil recommandé : {cluster_max_radius_mm:.1f} mm)"
                    )
                else:
                    report["rules_passed"] += 1

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
    parser.add_argument(
        "-p", "--placement",
        type=Path,
        help="Chemin vers un fichier JSON de placement (optionnel, permet l'audit hors-ligne sans EasyEDA)"
    )

    args = parser.parse_args()

    try:
        config = load_floorplan(args.config)
    except Exception as e:
        logger.error(f"Impossible de charger la configuration '{args.config}' : {e}")
        sys.exit(1)

    auditor = PCBAuditor(config, placement_path=args.placement)
    report = auditor.audit_board()
    auditor.print_report(report)

    if report["violations"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
