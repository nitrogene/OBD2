#!/usr/bin/env python3
"""
validate.py - Contrôleur d'intégrité et de cohérence des données PCB (Agnostique)
===================================================================================
Conforme à la Règle 0 (AGENTS.md) :
- Aucune référence en dur à des composants, broches ou valeurs spécifiques du projet.
- Manipulation d'abstractions (composants, packages, ancres, keepouts, contraintes).
- Données injectées via arguments CLI (--manifest, --board, --bom).

Vérifie l'intégrité croisée :
1. circuit_manifest.json : intégrité des boîtiers, contraintes CEM, clusters rigides.
2. board_constraints.json : dimensions, 100% millimètres, trous de vis, ancres, keepouts.
3. Cohérence croisée : les ancres mécaniques et cibles CEM existent dans le manifeste.
4. Synchronisation optionnelle face à BOM.md (100% de concordance des désignateurs).
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("Validator")


@dataclass
class ValidationReport:
    manifest_path: str = ""
    board_path: str = ""
    bom_path: Optional[str] = None
    components_count: int = 0
    packages_count: int = 0
    anchors_count: int = 0
    holes_count: int = 0
    keepouts_count: int = 0
    constraints_count: int = 0
    rigid_groups_count: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


def load_json_file(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Fichier introuvable : {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_markdown_bom_designators(bom_path: Path) -> Set[str]:
    """Extrait l'ensemble des désignateurs uniques d'un fichier BOM Markdown."""
    if not bom_path.is_file():
        raise FileNotFoundError(f"BOM introuvable : {bom_path}")

    designators: Set[str] = set()
    with open(bom_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    in_table = False
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.split("|")[1:-1]]
        if len(cells) < 4:
            continue
        first = cells[0].replace("*", "").strip()
        if first.lower() in ("désignateur", "designator", "ref", "reference") or first.startswith(":-"):
            in_table = True
            continue
        if in_table and first:
            # Séparation si plusieurs désignateurs par cellule (ex: R1, R2)
            parts = [p.strip() for p in first.replace(";", ",").split(",") if p.strip()]
            for p in parts:
                designators.add(p)
    return designators


def validate_board_constraints(board_data: Dict[str, Any], report: ValidationReport) -> Tuple[float, float]:
    """Valide la structure et les plages physiques de board_constraints.json."""
    # 1. Vérification de l'unité
    frame = board_data.get("frame", {})
    unit = frame.get("unit")
    if unit != "mm":
        report.errors.append(f"[Board] L'unité déclarée dans frame.unit doit être 'mm' (reçu: '{unit}')")

    # 2. Dimensions de la carte
    board = board_data.get("board", {})
    width_mm = board.get("width_mm", 0.0)
    height_mm = board.get("height_mm", 0.0)

    if width_mm <= 0 or height_mm <= 0:
        report.errors.append(f"[Board] Dimensions de carte invalides : {width_mm} x {height_mm} mm")

    outline_poly = board.get("outline_polygon_mm", [])
    if len(outline_poly) < 3:
        report.errors.append(f"[Board] Le polygone de contour doit comporter au moins 3 points.")

    # 3. Trous de fixation
    holes = board.get("mounting_holes", [])
    report.holes_count = len(holes)
    for h in holes:
        hid = h.get("id", "UNKNOWN")
        hx = h.get("x_mm", -1.0)
        hy = h.get("y_mm", -1.0)
        drill = h.get("drill_mm", 0.0)
        pad = h.get("pad_mm", 0.0)

        if not (0 <= hx <= width_mm and 0 <= hy <= height_mm):
            report.errors.append(f"[Board] Trou {hid} hors limites carte : ({hx}, {hy}) mm")
        if drill <= 0:
            report.errors.append(f"[Board] Trou {hid} diamètre de perçage invalide : {drill} mm")
        if pad < drill:
            report.errors.append(f"[Board] Trou {hid} tête/pastille ({pad} mm) plus petite que le perçage ({drill} mm)")

    # 4. Keepouts
    keepouts = board_data.get("keepout_zones", [])
    report.keepouts_count = len(keepouts)
    for kz in keepouts:
        kname = kz.get("name", "ANONYMOUS")
        rect = kz.get("rect_mm", {})
        xmin = rect.get("x_min", 0.0)
        xmax = rect.get("x_max", 0.0)
        ymin = rect.get("y_min", 0.0)
        ymax = rect.get("y_max", 0.0)

        if xmin >= xmax or ymin >= ymax:
            report.errors.append(f"[Board] Keepout {kname} boîte englobante invalide : [{xmin}, {xmax}] x [{ymin}, {ymax}] mm")
        if not (0 <= xmin <= width_mm and 0 <= xmax <= width_mm and 0 <= ymin <= height_mm and 0 <= ymax <= height_mm):
            report.warnings.append(f"[Board] Keepout {kname} déborde ou est en bordure extrême du gabarit.")

    return width_mm, height_mm


def validate_circuit_manifest(
    manifest_data: Dict[str, Any],
    board_data: Dict[str, Any],
    board_w: float,
    board_h: float,
    report: ValidationReport
):
    """Valide circuit_manifest.json et sa cohérence croisée avec board_constraints.json."""
    packages = manifest_data.get("packages", {})
    report.packages_count = len(packages)

    if not packages:
        report.errors.append("[Manifest] Aucun dictionnaire de 'packages' défini.")

    for pkg_name, pkg in packages.items():
        w = pkg.get("width_mm", 0.0)
        l = pkg.get("length_mm", 0.0)
        if w <= 0 or l <= 0:
            report.errors.append(f"[Manifest] Package '{pkg_name}' dimensions invalides : {w} x {l} mm")

    components = manifest_data.get("components", {})
    report.components_count = len(components)

    if not components:
        report.errors.append("[Manifest] Aucun composant défini dans 'components'.")

    # Vérification des composants et de leurs packages
    for des, comp in components.items():
        pkg_key = comp.get("package") or comp.get("footprint")
        if not pkg_key:
            report.errors.append(f"[Manifest] Composant {des} sans package ni footprint spécifié.")
        elif pkg_key not in packages:
            report.errors.append(f"[Manifest] Composant {des} référence le package inconnu '{pkg_key}'.")

        # Cibles CEM
        cem = comp.get("cem_target")
        if cem:
            target_comp = cem.get("component")
            target_conn = cem.get("connector")
            max_d = cem.get("max_distance_mm", 0.0)

            if max_d <= 0:
                report.errors.append(f"[Manifest] Composant {des} règle cem_target avec max_distance_mm <= 0 ({max_d})")

            if target_comp and target_comp not in components and target_comp not in board_data.get("anchors", {}):
                report.errors.append(f"[Manifest] Composant {des} cible un composant inexistant : '{target_comp}'")

            if target_conn and target_conn not in board_data.get("anchors", {}) and target_conn not in components:
                report.errors.append(f"[Manifest] Composant {des} cible un connecteur inexistant : '{target_conn}'")

    # Cohérence des ancres définies dans board_constraints face au manifeste
    anchors = board_data.get("anchors", {})
    report.anchors_count = len(anchors)
    for anchor_des, anchor_cfg in anchors.items():
        if anchor_des not in components:
            report.errors.append(f"[Cohérence] L'ancre mécanique '{anchor_des}' n'existe pas dans circuit_manifest.json")
        ax = anchor_cfg.get("x_mm", -1.0)
        ay = anchor_cfg.get("y_mm", -1.0)
        if not (0 <= ax <= board_w and 0 <= ay <= board_h):
            report.errors.append(f"[Cohérence] L'ancre '{anchor_des}' coordonnées ({ax}, {ay}) mm hors gabarit carte")

    # Contraintes de placement explicites
    constraints = manifest_data.get("placement_constraints", [])
    report.constraints_count = len(constraints)
    for c in constraints:
        cid = c.get("id", "ANONYMOUS")
        ctype = c.get("type")

        if ctype == "proximity":
            sub = c.get("subject", {}).get("ref")
            tgt = c.get("target", {}).get("ref")
            if sub and sub not in components:
                report.errors.append(f"[Contrainte {cid}] Subject '{sub}' non trouvé dans les composants.")
            if tgt and tgt not in components and tgt not in anchors:
                report.errors.append(f"[Contrainte {cid}] Target '{tgt}' non trouvé dans les composants.")
        elif ctype == "loop":
            members = c.get("members", [])
            for m in members:
                mref = m.get("ref")
                if mref and mref not in components:
                    report.errors.append(f"[Contrainte {cid}] Membre de boucle '{mref}' non trouvé.")
        elif ctype == "edge_access":
            sub = c.get("subject", {}).get("ref")
            if sub and sub not in components:
                report.errors.append(f"[Contrainte {cid}] Subject '{sub}' non trouvé.")

    # Groupes rigides (Étage A)
    rigid_groups = manifest_data.get("rigid_groups", [])
    report.rigid_groups_count = len(rigid_groups)
    for rg in rigid_groups:
        gid = rg.get("id", "GROUP")
        anchor = rg.get("anchor_component")
        members = rg.get("members", [])

        if anchor not in components and anchor not in anchors:
            report.errors.append(f"[RigidGroup {gid}] Ancre '{anchor}' non trouvée dans les composants.")
        if anchor not in members:
            report.errors.append(f"[RigidGroup {gid}] L'ancre '{anchor}' doit figurer dans la liste des membres.")

        for m in members:
            if m not in components:
                report.errors.append(f"[RigidGroup {gid}] Membre '{m}' non trouvé dans les composants.")


def validate_against_bom(manifest_data: Dict[str, Any], bom_path: Path, report: ValidationReport):
    """Vérifie la correspondance stricte 1-pour-1 des désignateurs face à BOM.md."""
    bom_designators = parse_markdown_bom_designators(bom_path)
    manifest_designators = set(manifest_data.get("components", {}).keys())

    missing_in_manifest = bom_designators - manifest_designators
    missing_in_bom = manifest_designators - bom_designators

    if missing_in_manifest:
        report.errors.append(f"[BOM Sync] {len(missing_in_manifest)} composants de la BOM absents du manifeste : {sorted(missing_in_manifest)}")
    if missing_in_bom:
        report.errors.append(f"[BOM Sync] {len(missing_in_bom)} composants du manifeste absents de la BOM : {sorted(missing_in_bom)}")


def run_validation(
    manifest_file: Path,
    board_file: Path,
    bom_file: Optional[Path] = None
) -> ValidationReport:
    """Orchestre la validation complète des fichiers de spécification."""
    report = ValidationReport(
        manifest_path=str(manifest_file),
        board_path=str(board_file),
        bom_path=str(bom_file) if bom_file else None
    )

    try:
        board_data = load_json_file(board_file)
        board_w, board_h = validate_board_constraints(board_data, report)
    except Exception as e:
        report.errors.append(f"Échec de lecture board_constraints : {e}")
        return report

    try:
        manifest_data = load_json_file(manifest_file)
        validate_circuit_manifest(manifest_data, board_data, board_w, board_h, report)
    except Exception as e:
        report.errors.append(f"Échec de lecture circuit_manifest : {e}")
        return report

    if bom_file:
        try:
            validate_against_bom(manifest_data, bom_file, report)
        except Exception as e:
            report.errors.append(f"Échec de synchronisation avec la BOM : {e}")

    return report


def print_report(report: ValidationReport):
    logger.info("================================================================================")
    logger.info("               AUDIT DE COHÉRENCE GÉOMÉTRIQUE & SÉMANTIQUE                     ")
    logger.info("================================================================================")
    logger.info(f"Manifeste Sémantique & CEM : {report.manifest_path}")
    logger.info(f"Contraintes Mécaniques     : {report.board_path}")
    if report.bom_path:
        logger.info(f"Nomenclature BOM Source    : {report.bom_path}")
    logger.info("--------------------------------------------------------------------------------")
    logger.info(f"  • Composants validés      : {report.components_count}")
    logger.info(f"  • Boîtiers IPC répertoriés: {report.packages_count}")
    logger.info(f"  • Ancres mécaniques fixes : {report.anchors_count}")
    logger.info(f"  • Trous de vis M2 (châssis): {report.holes_count}")
    logger.info(f"  • Zones d'exclusion (Keep): {report.keepouts_count}")
    logger.info(f"  • Contraintes explicites  : {report.constraints_count}")
    logger.info(f"  • Micro-clusters rigides  : {report.rigid_groups_count}")
    logger.info("--------------------------------------------------------------------------------")

    if report.warnings:
        logger.info(f"⚠️ Avertissements ({len(report.warnings)}) :")
        for w in report.warnings:
            logger.info(f"   - {w}")

    if report.errors:
        logger.info(f"❌ Erreurs Bloquantes ({len(report.errors)}) :")
        for e in report.errors:
            logger.info(f"   - {e}")
        logger.info("--------------------------------------------------------------------------------")
        logger.info("Statut : ÉCHEC - Spécifications incohérentes ou incomplètes.")
    else:
        logger.info("Statut : SUCCÈS - Toutes les contraintes et spécifications sont 100% cohérentes.")
    logger.info("================================================================================\n")


def main():
    parser = argparse.ArgumentParser(
        description="Contrôleur d'intégrité et de cohérence des données pour pcb-placer (Agnostique)"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("circuit_manifest.json"),
        help="Chemin vers le fichier de manifeste schéma/CEM (ex: circuit_manifest.json)"
    )
    parser.add_argument(
        "--board",
        type=Path,
        default=Path("board_constraints.json"),
        help="Chemin vers le fichier des contraintes mécaniques (ex: board_constraints.json)"
    )
    parser.add_argument(
        "--bom",
        type=Path,
        default=Path("BOM.md"),
        help="Chemin optionnel vers la nomenclature Markdown pour audit croisé (ex: BOM.md)"
    )

    args = parser.parse_args()

    report = run_validation(args.manifest, args.board, args.bom)
    print_report(report)

    sys.exit(0 if report.is_valid else 1)


if __name__ == "__main__":
    main()
