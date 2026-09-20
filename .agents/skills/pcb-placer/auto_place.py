#!/usr/bin/env python3
"""
Moteur d'Auto-Placement par Contraintes en une passe (Moteur Agnostique)
=======================================================================
Calcule et applique les coordonnées 2D (X, Y, rotation, couche) de l'ensemble
des composants d'un circuit imprimé à partir d'un fichier de configuration formel (ex: floorplan.json).

Ce script ne comporte aucune référence en dur à un projet ou à des composants particuliers.
Le paramètre --config est obligatoire.
"""

import argparse
import json
import logging
import sys
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
from audit_placement import PCBAuditor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AutoPlacer")


class AutoPlacer:
    """Moteur générique d'optimisation et d'injection du placement PCB."""

    def __init__(self, config: FloorplanConfig, client: Optional[EasyEDAClient] = None):
        self.config = config
        self.client = client or EasyEDAClient()

    def generate_placement_plan(self) -> List[Dict[str, Any]]:
        """Génère la liste structurée des ajustements à partir de la configuration."""
        plan = []
        for des, comp in self.config.components.items():
            plan.append({
                "designator": des,
                "x": comp.x_mil,
                "y": comp.y_mil,
                "rotation": comp.rotation,
                "layer": comp.layer,
                "desc": comp.description
            })
        return plan

    def print_plan_summary(self, plan: List[Dict[str, Any]]):
        """Affiche un résumé clair du plan d'implantation."""
        print("\n" + "=" * 80)
        print(f" PLAN D'IMPLANTATION : {self.config.project_name} ({len(plan)} COMPOSANTS)")
        print("=" * 80)
        print(f"{'Désignateur':<12} | {'X (mil)':<9} | {'Y (mil)':<9} | {'Rot (°)':<8} | Description")
        print("-" * 80)
        for item in plan:
            print(f"{item['designator']:<12} | {item['x']:<9.1f} | {item['y']:<9.1f} | {item['rotation']:<8.0f} | {item.get('desc', '')}")
        print("=" * 80 + "\n")

    def apply_plan(self, plan: List[Dict[str, Any]]) -> bool:
        """Injecte le plan de placement en une passe dans EasyEDA Pro."""
        logger.info(f"Démarrage de l'injection par lot de {len(plan)} composants pour '{self.config.project_name}'...")
        try:
            res = self.client.batch_move_components(plan)
            logger.info(f"Résultat de l'injection : {res.get('modifiedCount', 0)} composants déplacés.")

            logger.info("Exécution du contrôle DRC physique...")
            drc_res = self.client.run_drc()
            err_count = drc_res.get("errorCount", 0)
            logger.info(f"Contrôle DRC : {err_count} erreur(s) détectée(s).")

            logger.info("Sauvegarde automatique du PCB...")
            self.client.save_pcb()
            print("✅ Injection réussie, DRC exécuté et document PCB sauvegardé !")
            return True
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'application du placement : {e}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Moteur d'auto-placement agnostique pour PCB EasyEDA Pro."
    )
    parser.add_argument(
        "-c", "--config",
        required=True,
        help="Chemin vers le fichier de configuration JSON (ex: floorplan.json)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Appliquer réellement le placement dans le PCB ouvert sous EasyEDA Pro (par défaut: simulation)"
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Lancer l'audit de conformité après le placement"
    )

    args = parser.parse_args()

    try:
        config = load_floorplan(args.config)
    except Exception as e:
        logger.error(f"Impossible de charger la configuration '{args.config}' : {e}")
        sys.exit(1)

    placer = AutoPlacer(config)
    plan = placer.generate_placement_plan()

    placer.print_plan_summary(plan)

    if args.apply:
        print("⚡ Mode --apply détecté : injection directe dans EasyEDA Pro...")
        success = placer.apply_plan(plan)
        if not success:
            sys.exit(2)
        if args.audit:
            print("\n🔍 Exécution de l'audit de conformité post-placement...")
            auditor = PCBAuditor(config)
            report = auditor.audit_board()
            auditor.print_report(report)
    else:
        print("ℹ️  Mode simulation (dry-run). Pour injecter dans EasyEDA Pro :")
        print(f"   uv run .agents/skills/pcb-placer/auto_place.py --config {args.config} --apply")


if __name__ == "__main__":
    main()
