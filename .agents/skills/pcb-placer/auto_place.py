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

    def ensure_board_outline(self) -> bool:
        """Vérifie ou crée le contour de carte mécanique (Layer 11) et les trous de fixation."""
        outline = self.client.get_board_outline()
        bbox = outline.get("boundingBox")
        if not bbox or outline.get("segmentsCount", 0) == 0:
            logger.info(
                f"Contour mécanique absent. Création du contour {self.config.board.width_mm:.2f} × "
                f"{self.config.board.height_mm:.2f} mm ({self.config.board.width_mil:.0f} × {self.config.board.height_mil:.0f} mil)..."
            )
            self.client.create_board_outline(self.config.board.width_mil, self.config.board.height_mil)
        else:
            logger.info(f"Contour mécanique existant détecté : {bbox['width_mm']:.2f} × {bbox['height_mm']:.2f} mm.")

        holes = getattr(self.config.board, "mounting_holes", [])
        if holes:
            logger.info(f"Vérification et instanciation des {len(holes)} trous de fixation mécaniques...")
            self.client.ensure_mounting_holes(holes)
        return True

    def analyze_placement_state(self, plan: List[Dict[str, Any]], force: bool = False) -> Dict[str, Any]:
        """
        Analyse l'état réel des composants sur le PCB et classe automatiquement chaque composant :
        - OUTSIDE_UNPLACED : nouveau composant en zone tampon hors contour
        - DISPLACED : composant dans le contour mais dont les coordonnées ont changé dans la config
        - CONFORM_PLACED : déjà en place et conforme (aucun déplacement requis)
        - MISSING_ON_PCB : présent dans le plan mais introuvable sur le PCB
        
        Déduit le mode d'action optimal :
        - INITIAL_FULL : carte vierge ou non placée, déploiement complet
        - SURGICAL_ECO : intervention chirurgicale uniquement sur les composants hors place
        - ALREADY_SYNCHRONIZED : aucun mouvement requis
        """
        existing = {c["designator"]: c for c in self.client.get_components()}
        outline = self.client.get_board_outline()
        bbox = outline.get("boundingBox") or {
            "minX": 0.0, "maxX": self.config.board.width_mil,
            "minY": 0.0, "maxY": self.config.board.height_mil
        }

        min_x, max_x = bbox["minX"] - 50.0, bbox["maxX"] + 50.0
        min_y, max_y = bbox["minY"] - 50.0, bbox["maxY"] + 50.0

        outside_unplaced = []
        displaced = []
        conform_placed = []
        missing = []

        for item in plan:
            des = item["designator"]
            if des not in existing:
                missing.append(item)
                continue

            curr = existing[des]
            cx, cy = curr.get("x", 0.0), curr.get("y", 0.0)
            crot = curr.get("rotation", 0.0)

            is_inside = (min_x <= cx <= max_x) and (min_y <= cy <= max_y)

            dx = abs(cx - item["x"])
            dy = abs(cy - item["y"])
            drot = abs(crot - item["rotation"]) % 360

            if not is_inside:
                outside_unplaced.append(item)
            elif dx > 10.0 or dy > 10.0 or drot > 1.0:
                displaced.append(item)
            else:
                conform_placed.append(item)

        if force or len(conform_placed) == 0:
            mode = "INITIAL_FULL"
            action_items = plan
        elif len(outside_unplaced) > 0 or len(displaced) > 0:
            mode = "SURGICAL_ECO"
            action_items = outside_unplaced + displaced
        else:
            mode = "ALREADY_SYNCHRONIZED"
            action_items = []

        return {
            "mode": mode,
            "action_items": action_items,
            "outside_unplaced": outside_unplaced,
            "displaced": displaced,
            "conform_placed": conform_placed,
            "missing": missing,
            "total": len(plan)
        }

    def apply_plan(self, plan: List[Dict[str, Any]], force: bool = False) -> bool:
        """Injecte le plan de placement de manière auto-adaptative (Initial vs Chirurgical/ECO)."""
        logger.info(f"Analyse de l'état du placement pour '{self.config.project_name}'...")
        try:
            self.ensure_board_outline()
            analysis = self.analyze_placement_state(plan, force=force)
            mode = analysis["mode"]
            action_items = analysis["action_items"]

            print("\n" + "=" * 80)
            print(f" DÉCISION AUTOMATIQUE DU MOTEUR : {mode}")
            print("=" * 80)
            print(f" • Composants déjà conformes sur le PCB : {len(analysis['conform_placed'])}")
            print(f" • Composants hors contour (à implanter)  : {len(analysis['outside_unplaced'])}")
            print(f" • Composants décalés (à recaler)        : {len(analysis['displaced'])}")
            if analysis['missing']:
                print(f" ⚠️ Composants absents du PCB            : {len(analysis['missing'])} ({', '.join(x['designator'] for x in analysis['missing'])})")
            print(f" -> Action retenue : {len(action_items)} composant(s) à positionner.")
            print("=" * 80 + "\n")

            if not action_items:
                print("✨ Tous les composants sont déjà en place et parfaitement conformes. Aucun déplacement requis !")
                return True

            logger.info(f"Injection en cours ({len(action_items)} composants)...")
            res = self.client.batch_move_components(action_items)
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
        description="Moteur d'auto-placement agnostique et auto-adaptatif pour PCB EasyEDA Pro."
    )
    parser.add_argument(
        "-c", "--config",
        required=True,
        help="Chemin vers le fichier de configuration JSON (ex: floorplan.json)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Appliquer réellement le placement dans le PCB (par défaut: simulation)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Forcer le repositionnement de l'ensemble des composants même s'ils sont déjà conformes"
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Lancer l'audit de conformité après le placement"
    )
    parser.add_argument(
        "--suggest-size",
        action="store_true",
        help="Calculer et suggérer les dimensions optimales du PCB selon les composants et keepouts"
    )
    parser.add_argument(
        "--layers",
        type=int,
        default=2,
        choices=[2, 4, 6],
        help="Nombre de couches pour l'estimation dimensionnelle (par défaut: 2)"
    )

    args = parser.parse_args()

    try:
        config = load_floorplan(args.config)
    except Exception as e:
        logger.error(f"Impossible de charger la configuration '{args.config}' : {e}")
        sys.exit(1)

    if args.suggest_size:
        from size_estimator import PCBSizeEstimator
        estimator = PCBSizeEstimator()
        estimate, comparison = estimator.estimate_from_floorplan(args.config, layers=args.layers)
        estimator.print_report(estimate, comparison)
        return

    placer = AutoPlacer(config)
    plan = placer.generate_placement_plan()

    placer.print_plan_summary(plan)

    if args.apply:
        print("⚡ Mode --apply détecté : injection directe dans EasyEDA Pro...")
        success = placer.apply_plan(plan, force=args.force)
        if not success:
            sys.exit(2)
        if args.audit:
            print("\n🔍 Exécution de l'audit de conformité post-placement...")
            auditor = PCBAuditor(config)
            report = auditor.audit_board()
            auditor.print_report(report)
    else:
        print("ℹ️  Mode simulation (dry-run). Diagnostic d'état actuel sur le PCB :")
        analysis = placer.analyze_placement_state(plan, force=args.force)
        print(f"   • Décision calculée        : Mode {analysis['mode']}")
        print(f"   • Composants déjà conformes : {len(analysis['conform_placed'])}")
        print(f"   • Composants hors contour   : {len(analysis['outside_unplaced'])}")
        print(f"   • Composants décalés        : {len(analysis['displaced'])}")
        print(f"   -> Action prévue : {len(analysis['action_items'])} composant(s) à positionner.")
        print(f"\nPour injecter réellement dans EasyEDA Pro :")
        print(f"   uv run .agents/skills/pcb-placer/auto_place.py --config {args.config} --apply --audit")


if __name__ == "__main__":
    main()
