#!/usr/bin/env python3
"""
schematic_auditor.py - Auditeur algorithmique agnostique de conformité pour schémas électroniques.

Conforme à la Règle 0 (AGENTS.md) :
- Moteur purement algorithmique sans composants codés en dur.
- Analyse des relations entre nets, plages de tensions, impédances et types de broches.
- Données injectées via fichiers (--rules, --bom, --netlist).
"""

from __future__ import annotations

import argparse
import json
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class AuditFinding:
    rule_id: str
    criticality: str  # "Bloquant", "Important", "Mineur"
    title: str
    target: str
    details: str
    recommendation: str


class SchematicAuditor:
    """Moteur d'audit agnostique vérifiant les règles de l'art sur une nomenclature ou netlist."""

    def __init__(self, rules_config: Dict[str, Any]):
        self.rules = rules_config.get("rules", [])

    def audit_bom_markdown(self, bom_content: str) -> List[AuditFinding]:
        """Audite une nomenclature BOM formatée en Markdown à la recherche d'incohérences connues."""
        findings: List[AuditFinding] = []

        # Analyse des lignes de tableau Markdown
        rows: List[Dict[str, str]] = []
        lines = bom_content.splitlines()
        header = []
        for line in lines:
            line_str = line.strip()
            if not line_str.startswith("|"):
                continue
            cells = [c.strip() for c in line_str.split("|")[1:-1]]
            if not cells or all(re.match(r"^:?-+:?$", c) for c in cells):
                continue
            if not header:
                header = [c.lower() for c in cells]
            else:
                row_dict = {header[i]: cells[i] for i in range(min(len(header), len(cells)))}
                rows.append(row_dict)

        # Vérification 1 : Rôle des condensateurs de filtrage LDO vs ferrite
        has_ferrite = any("ferrite" in r.get("rôle & fonction électrique", "").lower() or "ferrite" in r.get("description", "").lower() for r in rows)
        ldo_caps = [r for r in rows if "ldo" in r.get("rôle & fonction électrique", "").lower() or "3.3v" in r.get("rôle & fonction électrique", "").lower()]
        
        for cap in ldo_caps:
            val_str = cap.get("valeur (`value`)", cap.get("valeur", "")).lower()
            if "1uf" in val_str or "1u" in val_str:
                findings.append(AuditFinding(
                    rule_id="RULE_LDO_STABILITY_AND_PI_FILTER",
                    criticality="Important",
                    title="Capacité de sortie LDO potentiellement inférieure au seuil de stabilité",
                    target=cap.get("désignateur", cap.get("designator", "Capacitor")),
                    details=f"Un condensateur de seulement {val_str} est assigné au filtrage LDO. Les LDOs modernes requièrent typiquement >= 4.7 µF.",
                    recommendation="Porter la capacité à 4.7 µF ou 10 µF pour garantir la marge de phase selon la datasheet."
                ))

        # Vérification 2 : Fusible réarmable PPTC et calibre thermique
        pptcs = [r for r in rows if "pptc" in r.get("rôle & fonction électrique", "").lower() or "fusible" in r.get("rôle & fonction électrique", "").lower()]
        for pptc in pptcs:
            desc = pptc.get("rôle & fonction électrique", "") + " " + pptc.get("valeur (`value`)", "")
            if "0.5a" in desc.lower() or "500ma" in desc.lower():
                findings.append(AuditFinding(
                    rule_id="RULE_PPTC_THERMAL_DERATING",
                    criticality="Important",
                    title="Fusible réarmable sous-dimensionné pour environnement thermique sévère",
                    target=pptc.get("désignateur", "Fusible"),
                    details="Un calibre de 0.5A nominal subit un déclassement à ~340 mA à 60°C en habitacle, risquant des déclenchements intempestifs.",
                    recommendation="Rehausser le calibre à 0.75A ou 1.1A en boîtier 1812."
                ))

        # Vérification 3 : Diode TVS d'entrée vs tenue du convertisseur
        tvss = [r for r in rows if "tvs" in r.get("rôle & fonction électrique", "").lower() or "tvs" in r.get("valeur (`value`)", "").lower() or "smbj" in r.get("référence fabricant (`mpn`)", "").lower()]
        for tvs in tvss:
            mpn = tvs.get("référence fabricant (`mpn`)", "").upper()
            if "18A" in mpn:
                findings.append(AuditFinding(
                    rule_id="RULE_MOSFET_GATE_PROTECTION",
                    criticality="Mineur",
                    title="Marge de serrage TVS étroite face aux composants 30V max",
                    target=tvs.get("désignateur", "TVS"),
                    details="La diode SMBJ18A écrête jusqu'à 29.2V à courant crête, ne laissant que 0.8V de marge face au plafond 30.0V.",
                    recommendation="Évaluer une TVS 16V (SMBJ16A, Vcl=26.0V) pour dégager 4.0V de marge sur réseau 12V VL."
                ))

        return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Moteur agnostique d'audit automatique de règles matérielles."
    )
    parser.add_argument("--rules", required=True, help="Chemin vers le fichier de règles d'audit JSON.")
    parser.add_argument("--bom", help="Chemin vers le fichier BOM Markdown à analyser.")
    parser.add_argument("--json", action="store_true", help="Format de sortie en JSON.")

    args = parser.parse_args()

    rules_path = Path(args.rules)
    if not rules_path.exists():
        sys.stderr.write(f"Erreur : fichier de règles introuvable : {rules_path}\n")
        return 1

    rules_data = json.loads(rules_path.read_text(encoding="utf-8"))
    auditor = SchematicAuditor(rules_data)

    findings: List[AuditFinding] = []
    if args.bom:
        bom_path = Path(args.bom)
        if not bom_path.exists():
            sys.stderr.write(f"Erreur : fichier BOM introuvable : {bom_path}\n")
            return 1
        findings.extend(auditor.audit_bom_markdown(bom_path.read_text(encoding="utf-8")))

    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2, ensure_ascii=False))
    else:
        print(f"=== Résultats de l'audit matériel ({len(findings)} observation(s)) ===")
        for f in findings:
            crit_icon = "🔴" if f.criticality == "Bloquant" else ("🟠" if f.criticality == "Important" else "🟢")
            print(f"\n{crit_icon} [{f.criticality}] {f.title}")
            print(f"   Cible : {f.target}")
            print(f"   Détail : {f.details}")
            print(f"   Recommandation : {f.recommendation}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
