#!/usr/bin/env python3
"""
sync_semantics.py - Outil agnostique de synchronisation et d'audit entre la BOM et circuit_semantics.json.

Conforme à la Règle 0 (AGENTS.md) :
- Aucune référence en dur à des composants, broches ou valeurs spécifiques du projet.
- Manipulation d'abstractions (listes de composants, désignateurs, rôles sémantiques, contraintes).
- Données injectées via arguments CLI (--bom, --semantics).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


@dataclass
class BomItem:
    designator: str
    value: str
    mpn: str
    lcsc: str
    type_status: str  # "Basic Part", "Extended Part", "—"
    footprint: str
    description: str


def parse_markdown_bom(content: str) -> Dict[str, BomItem]:
    """Extrait les composants d'un tableau Markdown de nomenclature."""
    items: Dict[str, BomItem] = {}
    lines = content.splitlines()
    in_table = False
    
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        
        cells = [c.strip() for c in stripped.split("|")[1:-1]]
        if len(cells) < 6:
            continue
        
        # Détection de ligne d'en-tête ou de séparation
        first = cells[0].replace("*", "").strip()
        if first.lower() in ("désignateur", "designator", "ref", "reference") or first.startswith(":-"):
            in_table = True
            continue
        
        if not in_table or not first:
            continue

        desig = first
        val = cells[1].strip() if len(cells) > 1 else ""
        mpn = cells[2].replace("`", "").strip() if len(cells) > 2 else ""
        lcsc = cells[3].replace("`", "").strip() if len(cells) > 3 else ""
        status = cells[4].replace("*", "").strip() if len(cells) > 4 else ""
        pkg = cells[5].replace("`", "").strip() if len(cells) > 5 else ""
        desc = cells[6].strip() if len(cells) > 6 else ""

        items[desig] = BomItem(
            designator=desig,
            value=val,
            mpn=mpn,
            lcsc=lcsc,
            type_status=status,
            footprint=pkg,
            description=desc,
        )
    return items


def parse_csv_bom(content: str) -> Dict[str, BomItem]:
    """Extrait les composants d'un export CSV de nomenclature."""
    items: Dict[str, BomItem] = {}
    reader = csv.DictReader(content.splitlines())
    for row in reader:
        # Trouver la colonne désignateur
        desig = (
            row.get("Designator")
            or row.get("Désignateur")
            or row.get("Device")
            or row.get("Comment")
            or ""
        ).strip()
        if not desig:
            continue
        val = row.get("Value") or row.get("Valeur") or ""
        mpn = row.get("MPN") or row.get("Manufacturer Part Number") or ""
        lcsc = row.get("LCSC Part #") or row.get("LCSC") or row.get("Code LCSC") or ""
        status = row.get("Type") or row.get("Status") or row.get("Statut") or ""
        pkg = row.get("Footprint") or row.get("Package") or row.get("Empreinte") or ""
        desc = row.get("Description") or ""

        items[desig] = BomItem(
            designator=desig,
            value=val,
            mpn=mpn,
            lcsc=lcsc,
            type_status=status,
            footprint=pkg,
            description=desc,
        )
    return items


def load_bom(bom_path: Path) -> Dict[str, BomItem]:
    """Charge la BOM depuis un fichier Markdown ou CSV."""
    if not bom_path.exists():
        raise FileNotFoundError(f"Fichier BOM introuvable : {bom_path}")
    content = bom_path.read_text(encoding="utf-8")
    if bom_path.suffix.lower() in (".csv", ".tsv"):
        return parse_csv_bom(content)
    return parse_markdown_bom(content)


def load_semantics(semantics_path: Path) -> Dict[str, Any]:
    """Charge le fichier JSON sémantique du circuit."""
    if not semantics_path.exists():
        raise FileNotFoundError(f"Fichier sémantique introuvable : {semantics_path}")
    return json.loads(semantics_path.read_text(encoding="utf-8"))


def audit_sync(bom_items: Dict[str, BomItem], semantics_data: Dict[str, Any]) -> Dict[str, Any]:
    """Compare rigoureusement la BOM et circuit_semantics.json."""
    sem_comps: Dict[str, Any] = semantics_data.get("components", {})

    bom_set: Set[str] = set(bom_items.keys())
    sem_set: Set[str] = set(sem_comps.keys())

    missing_in_semantics = sorted(list(bom_set - sem_set))
    missing_in_bom = sorted(list(sem_set - bom_set))

    value_mismatches = []
    footprint_mismatches = []

    for d in sorted(list(bom_set & sem_set)):
        b_item = bom_items[d]
        s_item = sem_comps[d]

        s_val = str(s_item.get("value", "")).strip()
        b_val = str(b_item.value).strip()

        # Nettoyage comparatif (ex: 100nF vs 100 nF, 10k vs 10kΩ)
        norm_s_val = re.sub(r"[\sΩ]", "", s_val.lower())
        norm_b_val = re.sub(r"[\sΩ]", "", b_val.lower())

        if norm_s_val and norm_b_val and norm_s_val != norm_b_val and norm_b_val != "—":
            value_mismatches.append({
                "designator": d,
                "bom_value": b_val,
                "semantics_value": s_val,
            })

        s_pkg = str(s_item.get("footprint", "")).strip().lower()
        b_pkg = str(b_item.footprint).strip().lower()

        if s_pkg and b_pkg and s_pkg != b_pkg and b_pkg != "—" and s_pkg != "pad":
            footprint_mismatches.append({
                "designator": d,
                "bom_footprint": b_item.footprint,
                "semantics_footprint": s_item.get("footprint", ""),
            })

    is_synced = (
        len(missing_in_semantics) == 0
        and len(missing_in_bom) == 0
        and len(value_mismatches) == 0
    )

    return {
        "is_synced": is_synced,
        "bom_count": len(bom_set),
        "semantics_count": len(sem_set),
        "common_count": len(bom_set & sem_set),
        "missing_in_semantics": missing_in_semantics,
        "missing_in_bom": missing_in_bom,
        "value_mismatches": value_mismatches,
        "footprint_mismatches": footprint_mismatches,
    }


def scaffold_semantics_for_item(item: BomItem) -> Dict[str, Any]:
    """Génère un squelette sémantique par défaut à partir d'un élément de BOM."""
    d = item.designator
    prefix = re.match(r"^([A-Za-z]+)", d)
    prefix_str = prefix.group(1).upper() if prefix else ""

    substitutability = "direct_1to1"
    role = "generic_passive"
    block = "unknown"

    if prefix_str == "R":
        role = "resistor"
    elif prefix_str == "C":
        role = "capacitor"
    elif prefix_str == "D":
        role = "diode"
    elif prefix_str == "Q":
        role = "transistor"
    elif prefix_str == "L":
        role = "inductor"
    elif prefix_str == "U":
        role = "integrated_circuit"
        substitutability = "locked"
    elif prefix_str in ("J", "JP"):
        role = "connector"
        substitutability = "locked"
    elif prefix_str == "TP":
        role = "test_point"
        substitutability = "locked"

    return {
        "block": block,
        "role": role,
        "description": item.description or f"Composant {d}",
        "value": item.value,
        "footprint": item.footprint,
        "substitutability": substitutability,
        "constraints": {},
    }


def cmd_check(args: argparse.Namespace) -> int:
    bom_path = Path(args.bom)
    sem_path = Path(args.semantics)

    try:
        bom_items = load_bom(bom_path)
        semantics = load_semantics(sem_path)
    except Exception as e:
        sys.stderr.write(f"Erreur de chargement : {e}\n")
        return 1

    report = audit_sync(bom_items, semantics)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["is_synced"] else 1

    print(f"=== Audit de Synchronisation Sémantique ===")
    print(f"BOM Source       : {bom_path} ({report['bom_count']} composants)")
    print(f"Sémantique Cible : {sem_path} ({report['semantics_count']} composants)")
    print(f"Composants communs validés : {report['common_count']}")

    if report["missing_in_semantics"]:
        print(f"\n❌ Composants présents dans la BOM mais ABSENTS de la sémantique ({len(report['missing_in_semantics'])}) :")
        for m in report["missing_in_semantics"]:
            print(f"  - {m}")

    if report["missing_in_bom"]:
        print(f"\n❌ Composants fantômes dans la sémantique mais ABSENTS de la BOM ({len(report['missing_in_bom'])}) :")
        for m in report["missing_in_bom"]:
            print(f"  - {m}")

    if report["value_mismatches"]:
        print(f"\n⚠️ Divergences de valeur détectées ({len(report['value_mismatches'])}) :")
        for vm in report["value_mismatches"]:
            print(f"  - [{vm['designator']}] BOM: '{vm['bom_value']}' ≠ Sémantique: '{vm['semantics_value']}'")

    if report["footprint_mismatches"]:
        print(f"\nℹ️ Divergences d'empreinte détectées ({len(report['footprint_mismatches'])}) :")
        for fm in report["footprint_mismatches"]:
            print(f"  - [{fm['designator']}] BOM: '{fm['bom_footprint']}' ≠ Sémantique: '{fm['semantics_footprint']}'")

    if report["is_synced"]:
        print("\n✅ Synchronisation 100% conforme : la sémantique reflète rigoureusement la BOM.")
        return 0
    else:
        print("\n❌ Des anomalies de synchronisation doivent être corrigées.")
        return 1


def cmd_scaffold(args: argparse.Namespace) -> int:
    bom_path = Path(args.bom)
    sem_path = Path(args.semantics)

    try:
        bom_items = load_bom(bom_path)
        semantics = load_semantics(sem_path) if sem_path.exists() else {"components": {}}
    except Exception as e:
        sys.stderr.write(f"Erreur : {e}\n")
        return 1

    sem_comps = semantics.setdefault("components", {})
    added_count = 0

    for desig, item in bom_items.items():
        if desig not in sem_comps:
            sem_comps[desig] = scaffold_semantics_for_item(item)
            added_count += 1
            print(f"  + Ajout de l'ébauche sémantique pour : {desig} ({item.value})")

    if added_count > 0:
        sem_path.write_text(json.dumps(semantics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\n✅ {added_count} composant(s) scaffoldé(s) dans {sem_path}.")
    else:
        print(f"Aucun nouveau composant à scaffolder dans {sem_path}.")

    return 0


def main() -> int:
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--bom", default="BOM.md", help="Chemin vers le fichier BOM (Markdown ou CSV).")
    parent_parser.add_argument("--semantics", default="circuit_semantics.json", help="Chemin vers circuit_semantics.json.")

    parser = argparse.ArgumentParser(
        description="Outil agnostique de synchronisation et vérification entre BOM et circuit_semantics.json."
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommande check
    parser_check = subparsers.add_parser("check", parents=[parent_parser], help="Contrôle la cohérence stricte entre BOM et sémantique.")
    parser_check.add_argument("--json", action="store_true", help="Sortie structurée en JSON.")

    # Subcommande scaffold
    parser_scaffold = subparsers.add_parser("scaffold", parents=[parent_parser], help="Génère des ébauches sémantiques pour les composants orphelins de la BOM.")

    args = parser.parse_args()

    if args.command == "check":
        return cmd_check(args)
    elif args.command == "scaffold":
        return cmd_scaffold(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
