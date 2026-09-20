#!/usr/bin/env python3
"""
Actionneur d'Injection par Lot & Certification DRC (apply_placement.py)
======================================================================
Script d'exécution direct :
1. Affiche le récapitulatif prévisionnel des déplacements
2. Applique les coordonnées par lot via l'API EasyEDA Pro
3. Déclenche le DRC et valide l'absence d'erreurs
4. Sauvegarde le document PCB
"""

import sys
import logging

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from easyeda_client import EasyEDAClient
from auto_place import AutoPlacer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ApplyPlacement")


def main():
    print("=" * 75)
    print(" INJECTION PAR LOT DU PLACEMENT PCB (EASYEDA PRO)")
    print("=" * 75)

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

    placer = AutoPlacer(client=client)
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
