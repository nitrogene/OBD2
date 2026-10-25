#!/usr/bin/env python3
"""
convert_step_to_stl.py - Convertisseur & Optimiseur 3D STEP -> STL pour GitHub WebGL
===================================================================================
Convertit un modèle solide STEP (ISO 10303) en maillage STL haute résolution
optimisé pour le visualiseur 3D interactif WebGL de GitHub (< 20 MB).

Usage :
  uv run --with build123d python scripts/convert_step_to_stl.py
  uv run --with build123d python scripts/convert_step_to_stl.py --input documents/pcb/scanner.step --output documents/pcb/scanner.stl
"""

import argparse
import logging
import sys
import time
from pathlib import Path

import build123d as bd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("StepToStl")


def convert_step_to_stl(step_path: Path, stl_path: Path, tolerance: float = 0.15, angular_tolerance: float = 0.3) -> Path:
    """Charge un fichier STEP et l'exporte en STL optimisé pour le WebGL."""
    if not step_path.exists():
        raise FileNotFoundError(f"Fichier STEP source introuvable : {step_path}")

    step_size_mb = step_path.stat().st_size / (1024 * 1024)
    logger.info(f"📦 Chargement du solide STEP : {step_path.name} ({step_size_mb:.1f} MB)...")
    t0 = time.time()
    part = bd.import_step(str(step_path))
    t1 = time.time()
    logger.info(f"   -> Solide importé avec succès en {t1 - t0:.1f} s.")

    logger.info(f"🔨 Génération du maillage STL optimisé (tolérance: {tolerance} mm)...")
    stl_path.parent.mkdir(parents=True, exist_ok=True)
    bd.export_stl(part, str(stl_path), tolerance=tolerance, angular_tolerance=angular_tolerance)
    t2 = time.time()

    stl_size_mb = stl_path.stat().st_size / (1024 * 1024)
    logger.info(f"✅ Export terminé en {t2 - t1:.1f} s : {stl_path.name} ({stl_size_mb:.2f} MB)")
    if stl_size_mb > 25.0:
        logger.warning("⚠️ Attention : le STL dépasse 25 MB et pourrait être ralenti dans le visualiseur WebGL GitHub.")
    return stl_path


def main():
    parser = argparse.ArgumentParser(description="Conversion et optimisation STEP vers STL")
    parser.add_argument("--input", default="documents/pcb/scanner.step", help="Chemin du fichier STEP source")
    parser.add_argument("--output", default="documents/pcb/scanner.stl", help="Chemin du fichier STL de sortie")
    parser.add_argument("--tolerance", type=float, default=0.15, help="Tolérance de déflection linéaire (mm)")
    parser.add_argument("--angular-tolerance", type=float, default=0.3, help="Tolérance angulaire (rad)")
    parser.add_argument("--clean-step", action="store_true", default=True, help="Supprime le fichier STEP source après conversion pour alléger le dépôt Git")
    args = parser.parse_args()

    step_file = Path(args.input).resolve()
    stl_file = Path(args.output).resolve()

    try:
        convert_step_to_stl(step_file, stl_file, tolerance=args.tolerance, angular_tolerance=args.angular_tolerance)
        if args.clean_step and step_file.exists():
            step_file.unlink()
            logger.info(f"🧹 Fichier STEP source supprimé pour économiser l'espace Git : {step_file.name}")
    except Exception as e:
        logger.error(f"❌ Erreur lors de la conversion : {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
