#!/usr/bin/env python3
"""
apply_placement.py - Actionneur d'Injection par Lot & Certification DRC (Agnostique)
===================================================================================
Conforme aux Règles AGENTS.md :
- Règle 0 : Aucun composant codé en dur. Les coordonnées proviennent exclusivement
  du fichier de placement (--placement placement_candidate.json).
- Règle 1 : Transparence et sécurité sur le pont EasyEDA.
- Règle 4 : Validation DRC et sauvegarde automatique.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from easyeda_client import EasyEDAClient

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("PlacementApplier")

MM_TO_MIL = 1.0 / 0.0254


class DRCOnPlacementError(RuntimeError):
    """Exception levée en cas de violations DRC après injection du placement."""
    def __init__(self, message: str, error_count: int = 0, warning_count: int = 0):
        super().__init__(message)
        self.error_count = error_count
        self.warning_count = warning_count


def apply_placement_to_pcb(
    placement_path: Path,
    dry_run: bool = False,
    run_drc: bool = True,
    save: bool = True,
    rollback_on_drc_error: bool = True,
    ignore_drc_errors: bool = False,
    force_save: bool = False,
    client: Optional[EasyEDAClient] = None
) -> Dict[str, Any]:
    """
    Lit un fichier de placement JSON (contenant les coordonnées x_mm, y_mm, rotation)
    et applique en une transaction par lot les nouvelles positions dans EasyEDA Pro.
    Effectue un snapshot initial pour rollback automatique en cas de violations DRC.
    """
    if not placement_path.is_file():
        raise FileNotFoundError(f"Fichier de placement introuvable : {placement_path}")

    with open(placement_path, "r", encoding="utf-8") as f:
        placement_data = json.load(f)

    comps_to_place = placement_data.get("components", {})
    if not comps_to_place:
        raise ValueError(f"Aucun composant trouvé dans '{placement_path}' (section 'components' vide)")

    client = client or EasyEDAClient()
    health = client.health()
    if not health.get("edaConnected"):
        raise ConnectionError("EasyEDA Pro n'est pas connecté au serveur pont local.")

    # 1. Extraction des composants actuels du PCB
    current_comps = client.get_components()
    current_map = {c.get("designator"): c for c in current_comps if c.get("designator")}

    logger.info(f"Composants détectés sur le PCB : {len(current_map)}")
    logger.info(f"Composants à appliquer depuis {placement_path.name} : {len(comps_to_place)}")

    # Snapshot des positions initiales pour rollback en cas d'échec DRC
    snapshot = []
    for des in comps_to_place.keys():
        if des in current_map:
            c = current_map[des]
            snap_item: Dict[str, Any] = {
                "designator": des,
                "x": c.get("x"),
                "y": c.get("y"),
                "rotation": c.get("rotation", 0)
            }
            if "layer" in c:
                snap_item["layer"] = c["layer"]
            if "locked" in c:
                snap_item["locked"] = c["locked"]
            snapshot.append(snap_item)

    adjustments = []
    skipped = []

    for des, target in comps_to_place.items():
        if des not in current_map:
            skipped.append(des)
            continue

        x_mm = float(target.get("x_mm", target.get("x", 0.0)))
        y_mm = float(target.get("y_mm", target.get("y", 0.0)))
        rot_deg = float(target.get("rotation", target.get("rot", 0.0)))

        # Conversion mm vers mil
        x_mil = round(x_mm * MM_TO_MIL, 1)
        y_mil = round(y_mm * MM_TO_MIL, 1)
        norm_rot = int(round(rot_deg)) % 360

        adjustments.append({
            "designator": des,
            "x": x_mil,
            "y": y_mil,
            "rotation": norm_rot
        })

    if skipped:
        logger.warning(f"⚠️ Composants absents du PCB ({len(skipped)}) : {', '.join(skipped)}")

    logger.info(f"⚡ Préparation du déplacement par lot pour {len(adjustments)} composants...")

    if dry_run:
        logger.info("🔍 Mode simulation (--dry-run) : aucun composant n'a été modifié.")
        return {"dry_run": True, "count": len(adjustments)}

    # 2. Application en lot via l'API EasyEDA Pro
    t0 = time.time()
    batch_res = client.batch_move_components(adjustments)
    elapsed = time.time() - t0

    if not batch_res.get("success", False):
        raise RuntimeError(f"Échec du déplacement par lot : {batch_res.get('error')}")

    modified_count = batch_res.get("modifiedCount", 0)
    logger.info(f"✅ {modified_count} composants repositionnés avec succès en {elapsed:.2f} s !")

    drc_summary = {}
    drc_failed = False
    if run_drc:
        logger.info("🔍 Exécution du contrôle DRC natif EasyEDA Pro...")
        drc_res = client.run_drc()
        error_count = drc_res.get("errorCount", 0)
        warning_count = drc_res.get("warningCount", 0)
        drc_summary = {"errorCount": error_count, "warningCount": warning_count, "raw": drc_res}
        logger.info(f"   Résultat DRC : {error_count} erreur(s), {warning_count} avertissement(s)")

        if error_count > 0:
            drc_failed = True
            logger.error(f"❌ Violation DRC bloquante : {error_count} erreur(s) détectée(s) après injection !")

            if not ignore_drc_errors:
                if rollback_on_drc_error:
                    logger.warning(f"🔄 Déclenchement du ROLLBACK : restauration de {len(snapshot)} composants...")
                    try:
                        rb_res = client.batch_move_components(snapshot)
                        if rb_res.get("success"):
                            logger.info("✅ Rollback terminé : état d'origine rétabli sur le PCB.")
                        else:
                            logger.error(f"❌ Échec de la restauration par rollback : {rb_res.get('error')}")
                    except Exception as e_rb:
                        logger.error(f"❌ Erreur critique lors du rollback : {e_rb}")
                else:
                    logger.warning("⚠️ Option --no-rollback active : positions en violation maintenues pour analyse.")

                logger.warning("⛔ Sauvegarde automatique bloquée (Règles 2 & 5 AGENTS.md).")
                raise DRCOnPlacementError(
                    f"DRC bloquant : {error_count} erreur(s) détectée(s) après injection du placement. "
                    f"Sauvegarde annulée{' et rollback appliqué' if rollback_on_drc_error else ''}.",
                    error_count=error_count,
                    warning_count=warning_count
                )

    if save:
        if drc_failed and not force_save and not ignore_drc_errors:
            logger.warning("⛔ Sauvegarde automatique annulée en raison d'erreurs DRC non résolues.")
        else:
            logger.info("💾 Sauvegarde du document PCB actif...")
            saved = client.save_pcb()
            if saved:
                logger.info("✅ Document PCB sauvegardé.")
            else:
                logger.warning("⚠️ Impossible de confirmer la sauvegarde automatique du document.")

    return {
        "success": not drc_failed,
        "modifiedCount": modified_count,
        "elapsed_sec": elapsed,
        "drc": drc_summary,
        "rolled_back": drc_failed and rollback_on_drc_error and not ignore_drc_errors
    }


def main():
    parser = argparse.ArgumentParser(
        description="Actionneur d'Injection par Lot de Placement PCB (Agnostique)"
    )
    parser.add_argument(
        "--placement",
        type=Path,
        default=Path("placement_candidate.json"),
        help="Chemin du fichier de placement JSON (défaut : placement_candidate.json)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simuler sans modifier le document PCB"
    )
    parser.add_argument(
        "--no-drc",
        action="store_true",
        help="Ne pas exécuter le DRC natif après injection"
    )
    parser.add_argument(
        "--no-rollback",
        action="store_true",
        help="Désactiver le rollback automatique en cas de violations DRC (conserve l'état pour inspection)"
    )
    parser.add_argument(
        "--ignore-drc-errors",
        action="store_true",
        help="Tolérer les erreurs DRC sans interrompre l'exécution ni effectuer de rollback"
    )
    parser.add_argument(
        "--force-save",
        action="store_true",
        help="Forcer la sauvegarde du document PCB même si des erreurs DRC subsistent"
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Ne pas sauvegarder automatiquement le document PCB"
    )

    args = parser.parse_args()

    try:
        apply_placement_to_pcb(
            placement_path=args.placement,
            dry_run=args.dry_run,
            run_drc=not args.no_drc,
            save=not args.no_save,
            rollback_on_drc_error=not args.no_rollback,
            ignore_drc_errors=args.ignore_drc_errors,
            force_save=args.force_save
        )
    except DRCOnPlacementError as e:
        logger.error(f"❌ {e}")
        sys.exit(2)
    except Exception as e:
        logger.error(f"❌ Erreur : {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
