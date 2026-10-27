#!/usr/bin/env python3
"""
Générateur de Rapports d'Audit DFM & SMT
=======================================
Skill: pcb-dfm
Règle 1: Moteur agnostique, zéro composant codé en dur, exécution uv run.
Règle 6: Pas de balisage LaTeX pour les composants ou valeurs.
Produit un rapport de synthèse professionnel en Markdown et JSON.
"""

import sys
import json
import logging
from datetime import datetime
from typing import Dict, Any, List

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logger = logging.getLogger("pcb_dfm.reporter")


class DfmReportGenerator:
    """Générateur de rapports d'audit DFM et SMT structurés."""

    def __init__(self, pcb_results: Dict[str, Any], smt_results: Dict[str, Any], metadata: Dict[str, Any]):
        self.pcb_results = pcb_results
        self.smt_results = smt_results
        self.metadata = metadata

    def generate_json_report(self) -> Dict[str, Any]:
        """Génère la structure JSON complète pour intégration dans pcb-synthesizer."""
        all_violations = self.pcb_results.get("violations", []) + self.smt_results.get("violations", [])
        danger_count = sum(1 for v in all_violations if v["severity"] == "DANGER")
        warning_count = sum(1 for v in all_violations if v["severity"] == "WARNING")
        info_count = sum(1 for v in all_violations if v["severity"] == "INFO")

        verdict = "PASSED" if danger_count == 0 and warning_count == 0 else (
            "PASSED_WITH_WARNINGS" if danger_count == 0 else "FAILED"
        )

        return {
            "timestamp": datetime.now().isoformat(),
            "verdict": verdict,
            "summary": {
                "total_violations": len(all_violations),
                "danger_count": danger_count,
                "warning_count": warning_count,
                "info_count": info_count
            },
            "pcb_dfm": {
                "passed": self.pcb_results.get("passed", False),
                "danger_count": self.pcb_results.get("danger_count", 0),
                "warning_count": self.pcb_results.get("warning_count", 0),
                "violations": self.pcb_results.get("violations", [])
            },
            "smt_dfm": {
                "passed": self.smt_results.get("passed", False),
                "danger_count": self.smt_results.get("danger_count", 0),
                "warning_count": self.smt_results.get("warning_count", 0),
                "smt_summary": self.smt_results.get("smt_summary", {}),
                "violations": self.smt_results.get("violations", [])
            },
            "metadata": self.metadata
        }

    def generate_markdown_report(self) -> str:
        """Génère un rapport textuel Markdown conforme aux directives du projet."""
        all_violations = self.pcb_results.get("violations", []) + self.smt_results.get("violations", [])
        danger_count = sum(1 for v in all_violations if v["severity"] == "DANGER")
        warning_count = sum(1 for v in all_violations if v["severity"] == "WARNING")
        info_count = sum(1 for v in all_violations if v["severity"] == "INFO")

        if danger_count == 0 and warning_count == 0:
            verdict_badge = "🟢 Certifié Conforme DFM / SMT"
        elif danger_count == 0:
            verdict_badge = "🟠 Approuvé avec Réserves (Warnings DFM uniquement)"
        else:
            verdict_badge = "🔴 Rejet DFM : Anomalies Critiques Détectées"

        smt_summary = self.smt_results.get("smt_summary", {})

        md = []
        md.append(f"# Rapport d'Audit Fabricabilité DFM & Assemblage SMT")
        md.append(f"")
        md.append(f"- **Date de l'audit :** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        md.append(f"- **Verdict Global :** {verdict_badge}")
        md.append(f"- **Fabricant cible :** {self.metadata.get('vendor', 'JLCPCB')} (Stackup {self.metadata.get('stackup', 'JLC2313')})")
        md.append(f"")
        md.append(f"---")
        md.append(f"")
        md.append(f"## 1. Synthèse Métrologique")
        md.append(f"")
        md.append(f"| Domaine | Statut | Danger (Bloquant) | Warning (Avertissement) | Info / Recommandation |")
        md.append(f"| :--- | :---: | :---: | :---: | :---: |")
        
        pcb_pass = "✅ CONFORME" if self.pcb_results.get("danger_count", 0) == 0 else "❌ NON CONFORME"
        md.append(
            f"| **PCB DFM (Nu)** | {pcb_pass} | {self.pcb_results.get('danger_count', 0)} | "
            f"{self.pcb_results.get('warning_count', 0)} | {self.pcb_results.get('info_count', 0)} |"
        )
        
        smt_pass = "✅ CONFORME" if self.smt_results.get("danger_count", 0) == 0 else "❌ NON CONFORME"
        md.append(
            f"| **SMT DFM (Assemblage)** | {smt_pass} | {self.smt_results.get('danger_count', 0)} | "
            f"{self.smt_results.get('warning_count', 0)} | {self.smt_results.get('info_count', 0)} |"
        )
        md.append(f"")
        md.append(f"### Répartition de l'Assemblage :")
        md.append(f"- Composants CMS (Automated Pick & Place) : **{smt_summary.get('smt_pick_and_place_count', 0)}**")
        md.append(f"- Composants Traversants THT (Soudure manuelle / sélective) : **{smt_summary.get('tht_manual_assembly_count', 0)}** ({', '.join(smt_summary.get('tht_designators', []))})")
        md.append(f"")
        md.append(f"---")
        md.append(f"")

        # Section Alertes DANGER
        dangers = [v for v in all_violations if v["severity"] == "DANGER"]
        if dangers:
            md.append(f"## 2. 🔴 Anomalies Critiques (DANGER - À corriger avant commande)")
            md.append(f"")
            md.append(f"| # | Catégorie | Description Technique | Valeur | Seuil | Coordonnées (X, Y) |")
            md.append(f"| :---: | :--- | :--- | :---: | :---: | :---: |")
            for idx, d in enumerate(dangers, 1):
                coords = f"({d['coordinates']['x_mm']:.2f}, {d['coordinates']['y_mm']:.2f}) mm"
                md.append(f"| {idx} | `{d['category']}` | {d['description']} | {d['actual_value_mm']} mm | {d['threshold_mm']} mm | {coords} |")
            md.append(f"")
        else:
            md.append(f"## 2. 🟢 Zéro Anomalie Critique (0 Alerte DANGER)")
            md.append(f"Aucun risque de siphonnage d'étain destructeur, court-circuit ou violation dimensionnelle majeure.")
            md.append(f"")

        # Section Alertes WARNING
        warnings = [v for v in all_violations if v["severity"] == "WARNING"]
        if warnings:
            md.append(f"## 3. 🟠 Avertissements DFM (WARNING - Tolérances limites)")
            md.append(f"")
            md.append(f"| # | Catégorie | Observation | Mesure | Seuil Standard | Coordonnées |")
            md.append(f"| :---: | :--- | :--- | :---: | :---: | :---: |")
            for idx, w in enumerate(warnings[:25], 1):  # Limité aux 25 premiers pour concision
                coords = f"({w['coordinates']['x_mm']:.2f}, {w['coordinates']['y_mm']:.2f}) mm"
                md.append(f"| {idx} | `{w['category']}` | {w['description']} | {w['actual_value_mm']} mm | {w['threshold_mm']} mm | {coords} |")
            if len(warnings) > 25:
                md.append(f"| ... | ... | *(et {len(warnings) - 25} autres avertissements similaires)* | ... | ... | ... |")
            md.append(f"")

        # Section Recommandations d'actions correctives
        md.append(f"## 4. Recommandations d'Actions Correctives Immédiates")
        md.append(f"")
        if any("SOLDERMASK" in d["category"] for d in dangers + warnings):
            md.append(f"- **Vernis épargne :** Ajuster l'expansion de masque à 0.02–0.03 mm sur les composants denses pour restaurer un barrage physique >= 0.10 mm.")
        if any("VIA_TO_PAD" in d["category"] or "VIA_IN_PAD" in d["category"] for d in dangers + warnings):
            md.append(f"- **Vias collés aux pastilles :** Insérer un col de piste dog-bone >= 0.15 mm ou certifier le tenting 100% pour stopper l'aspiration d'étain.")
        if any("SILKSCREEN" in d["category"] for d in warnings):
            md.append(f"- **Sérigraphie :** Éloigner les textes à >= 0.15 mm des pastilles et configurer une épaisseur de trait >= 0.18 mm.")
        if any("FIDUCIAL" in d["category"] for d in warnings):
            md.append(f"- **Repères fiduciaires :** Prévoir 3 repères optiques de 1.0 mm sur le PCB ou confirmer la fourniture de bandes de rive techniques lors de la panélisation usine.")
        md.append(f"")

        return "\n".join(md)
