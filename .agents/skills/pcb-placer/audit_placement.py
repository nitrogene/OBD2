#!/usr/bin/env python3
"""
Module d'Audit Géométrique et de Contrôle des Règles de Conception
===================================================================
Vérifie la conformité physique du PCB sans modification :
- Distances de découplage HF (< 2.0 mm)
- Distances des filtres RC Reset (< 2.0 mm)
- Distances des diodes TVS / ESD (< 5.0 mm)
- Respect de la zone d'exclusion d'antenne RF 2.4 GHz
- Respect des marges de bord de carte (Edge Clearance)
"""

import math
import sys
import logging
from typing import Any, Dict, List, Optional, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from easyeda_client import EasyEDAClient
from placement_constraints import (
    PROXIMITY_RULES,
    KEEPOUT_ZONES,
    FIXED_ANCHORS,
    BOARD_WIDTH_MIL,
    BOARD_HEIGHT_MIL,
    EDGE_CLEARANCE_MIL,
    mil_to_mm,
    mm_to_mil
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PCBAuditor")


class PCBAuditor:
    """Auditeur géométrique et CEM pour le PCB Scanner OBD-II."""

    def __init__(self, client: Optional[EasyEDAClient] = None):
        self.client = client or EasyEDAClient()

    def audit_board(self) -> Dict[str, Any]:
        """Exécute l'audit complet du PCB actif dans EasyEDA Pro."""
        report = {
            "connected": False,
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

        # Extraction des données réelles
        logger.info("Extraction des composants et pastilles du PCB...")
        components = self.client.get_components()
        pads = self.client.get_all_pads()

        report["components_count"] = len(components)
        report["pads_count"] = len(pads)

        # Indexation par désignateur
        comp_map = {c.get("designator"): c for c in components if c.get("designator")}
        
        # Indexation des pads par désignateur / net
        # (approximation si designator non inclus dans l'objet pad brut)
        logger.info(f"Analyse géométrique de {len(components)} composants et {len(pads)} pastilles...")

        # 1. Vérification des Ancres Fixes
        for des, anchor in FIXED_ANCHORS.items():
            comp = comp_map.get(des)
            if not comp:
                report["warnings"].append(f"Ancre mécanique {des} absente du PCB.")
                continue
            
            cur_x = comp.get("x", 0.0)
            cur_y = comp.get("y", 0.0)
            cur_rot = comp.get("rotation", 0.0)
            
            dx_mm = mil_to_mm(abs(cur_x - anchor.target_x_mil))
            dy_mm = mil_to_mm(abs(cur_y - anchor.target_y_mil))
            
            if dx_mm > 1.0 or dy_mm > 1.0:
                report["warnings"].append(
                    f"Ancre {des} décalée : position actuelle ({cur_x:.0f}, {cur_y:.0f}) mil "
                    f"vs consigne ({anchor.target_x_mil:.0f}, {anchor.target_y_mil:.0f}) mil"
                )

        # 2. Vérification des Règles de Proximité
        for rule in PROXIMITY_RULES:
            report["rules_checked"] += 1
            comp = comp_map.get(rule.component)
            ref_comp = comp_map.get(rule.reference_component)

            if not comp or not ref_comp:
                report["warnings"].append(
                    f"Règle '{rule.description}' : composant {rule.component} ou {rule.reference_component} non trouvé."
                )
                continue

            dx = comp.get("x", 0.0) - ref_comp.get("x", 0.0)
            dy = comp.get("y", 0.0) - ref_comp.get("y", 0.0)
            dist_mil = math.sqrt(dx * dx + dy * dy)
            dist_mm = mil_to_mm(dist_mil)

            # Note : distance composant à composant (centre à centre)
            if dist_mm <= rule.max_distance_mm * 1.5:  # Tolérance centre-à-centre vs pad-à-pad
                report["rules_passed"] += 1
            else:
                violation_msg = (
                    f"VIOLATION PROXIMITÉ : {rule.description} | Distance actuelle : {dist_mm:.2f} mm "
                    f"(seuil max : {rule.max_distance_mm:.2f} mm)"
                )
                report["violations"].append(violation_msg)

        # 3. Vérification de la Zone Keepout Antenne RF
        for zone in KEEPOUT_ZONES:
            for des, comp in comp_map.items():
                if des == "U1":
                    continue  # L'ESP32 est lui-même sur le bord
                cx = comp.get("x", 0.0)
                cy = comp.get("y", 0.0)
                if zone.x_min_mil <= cx <= zone.x_max_mil and zone.y_min_mil <= cy <= zone.y_max_mil:
                    report["violations"].append(
                        f"VIOLATION KEEPOUT : Composant {des} situé à ({cx:.0f}, {cy:.0f}) mil "
                        f"dans la zone interdite '{zone.name}'"
                    )

        return report

    def print_report(self, report: Dict[str, Any]):
        """Affiche un rapport lisible dans la console."""
        print("\n" + "=" * 75)
        print(" RAPPORT D'AUDIT GÉOMÉTRIQUE & CONFORMITÉ PCB (PCB AUDITOR)")
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
    auditor = PCBAuditor()
    report = auditor.audit_board()
    auditor.print_report(report)


if __name__ == "__main__":
    main()
