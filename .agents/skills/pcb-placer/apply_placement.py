#!/usr/bin/env python3
"""
Actionneur d'Injection par Lot & Certification DRC (Agnostique)
==============================================================
Script d'exécution direct pour l'injection du placement dans EasyEDA Pro :
1. Charge le fichier de configuration formel (--config <fichier.json>)
2. Affiche le récapitulatif prévisionnel des déplacements
3. Applique les coordonnées par lot via l'API EasyEDA Pro
4. Déclenche le DRC physique
5. Sauvegarde le document PCB
"""

import argparse
import logging
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from easyeda_client import EasyEDAClient
from placement_constraints import load_floorplan
from auto_place import AutoPlacer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ApplyPlacement")


def main():
    parser = argparse.ArgumentParser(
        description="Actionneur d'injection de placement PCB sous EasyEDA Pro."
    )
    parser.add_argument(
        "-c", "--config",
        required=True,
        help="Chemin vers le fichier de configuration JSON (ex: floorplan.json)"
    )

    args = parser.parse_args()

    print("=" * 80)
    print(" INJECTION PAR LOT DU PLACEMENT PCB (EASYEDA PRO)")
    print("=" * 80)

    try:
        config = load_floorplan(args.config)
    except Exception as e:
        logger.error(f"Impossible de charger la configuration '{args.config}' : {e}")
        sys.exit(1)

    client = EasyEDAClient()
    try:
        h = client.health()
        if not h.get("edaConnected"):
            print("❌ Erreur : Le client EasyEDA Pro n'est pas connecté au pont.")
            print("   Vérifiez que le document PCB est ouvert et que 'run-api-gateway' est active.")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Erreur de connexion au pont : {e}")
        sys.exit(1)

    placer = AutoPlacer(config=config, client=client)
    plan = placer.generate_placement_plan()

    placer.print_plan_summary(plan)

    print("⚡ Application des coordonnées en une passe dans EasyEDA Pro...")
    success = placer.apply_plan(plan)
    if success:
        print("✅ Opération terminée avec succès !")
    else:
        print("❌ L'opération a rencontré des erreurs.")
        sys.exit(1)


if __name__ == "__main__":
    main()
