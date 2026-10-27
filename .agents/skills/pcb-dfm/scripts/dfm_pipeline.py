#!/usr/bin/env python3
"""
Pipeline Maître d'Audit DFM & SMT Automatisé
============================================
Skill: pcb-dfm
Règle 1: Moteur agnostique, zéro composant codé en dur, exécution uv run.
Orchestre l'extraction des primitives EasyEDA, l'audit physique PCB nu,
l'audit d'assemblage SMT et la génération des rapports formels.
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

from drc_bridge import EasyEdaBridgeClient
from pcb_dfm_auditor import PcbDfmAuditor
from smt_dfm_auditor import SmtDfmAuditor
from report_generator import DfmReportGenerator

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pcb_dfm.pipeline")


def load_json(path_str: str) -> Dict[str, Any]:
    """Charge un fichier JSON en toute sécurité avec encodage UTF-8."""
    path = Path(path_str)
    if not path.is_file():
        logger.warning(f"Fichier introuvable : {path_str}")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_dfm_pipeline(
    config_path: str,
    bom_path: Optional[str] = None,
    output_json_path: Optional[str] = None,
    output_md_path: Optional[str] = None,
    port: int = 49620,
    pcb_only: bool = False,
    smt_only: bool = False,
    strict: bool = False
) -> int:
    """Exécute l'intégralité du pipeline d'audit DFM/SMT et retourne le code d'état d'ingénierie."""
    logger.info("==================================================")
    logger.info("Démarrage du Pipeline DFM & SMT JLCPCB")
    logger.info(f"Règles d'audit : {config_path}")

    rules = load_json(config_path)
    if not rules:
        logger.error(f"Impossible de charger les règles depuis {config_path}")
        return 2

    # 1. Connexion au Pont EasyEDA Pro
    client = EasyEdaBridgeClient(port=port)
    if not client.check_health():
        logger.error(f"Le pont EasyEDA Pro sur le port {port} n'est pas accessible ou aucun document PCB n'est ouvert.")
        return 3

    logger.info("Connexion établie avec EasyEDA Pro. Extraction des primitives PCB en cours...")
    primitives = client.extract_full_pcb_primitives()
    logger.info(
        f"Primitives extraites : {len(primitives.get('pads', []))} pastilles, "
        f"{len(primitives.get('vias', []))} vias, "
        f"{len(primitives.get('components', []))} composants, "
        f"{len(primitives.get('strings', []))} chaînes sérigraphie."
    )

    pcb_results: Dict[str, Any] = {"passed": True, "danger_count": 0, "warning_count": 0, "info_count": 0, "violations": []}
    smt_results: Dict[str, Any] = {"passed": True, "danger_count": 0, "warning_count": 0, "info_count": 0, "violations": []}

    # 2. Audit PCB DFM
    if not smt_only:
        logger.info("Exécution de l'audit PCB DFM (ponts de vernis, vias-to-pad, sérigraphie, perçages)...")
        pcb_auditor = PcbDfmAuditor(rules)
        pcb_results = pcb_auditor.audit(primitives)
        logger.info(
            f"Résultat PCB DFM : {pcb_results['danger_count']} Danger(s), "
            f"{pcb_results['warning_count']} Warning(s), "
            f"{pcb_results['info_count']} Info(s)"
        )

    # 3. Audit SMT DFM
    if not pcb_only:
        logger.info("Exécution de l'audit SMT DFM (espacement CMS, marges convoyeur, fiducials, BOM)...")
        bom_data = load_json(bom_path) if bom_path else {}
        smt_auditor = SmtDfmAuditor(rules, bom_data=bom_data)
        smt_results = smt_auditor.audit(primitives)
        logger.info(
            f"Résultat SMT DFM : {smt_results['danger_count']} Danger(s), "
            f"{smt_results['warning_count']} Warning(s), "
            f"{smt_results['info_count']} Info(s)"
        )

    # 4. Génération des Rapports
    metadata = {
        "vendor": rules.get("vendor", "JLCPCB"),
        "stackup": rules.get("stackup", "JLC2313"),
        "rules_file": config_path
    }
    reporter = DfmReportGenerator(pcb_results, smt_results, metadata)

    json_report = reporter.generate_json_report()
    md_report = reporter.generate_markdown_report()

    if output_json_path:
        out_json = Path(output_json_path)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(json_report, f, indent=2, ensure_ascii=False)
        logger.info(f"Rapport JSON sauvegardé : {output_json_path}")

    if output_md_path:
        out_md = Path(output_md_path)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        with open(out_md, "w", encoding="utf-8") as f:
            f.write(md_report)
        logger.info(f"Rapport Markdown sauvegardé : {output_md_path}")

    total_danger = pcb_results["danger_count"] + smt_results["danger_count"]
    total_warning = pcb_results["warning_count"] + smt_results["warning_count"]

    print("\n" + md_report)

    if total_danger > 0:
        logger.error(f"Échec DFM : {total_danger} violation(s) critique(s) DANGER détectée(s).")
        return 1
    elif strict and total_warning > 0:
        logger.warning(f"Échec DFM (Mode Strict) : {total_warning} avertissement(s) WARNING détecté(s).")
        return 1
    else:
        logger.info("Audit DFM & SMT terminé avec succès.")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Moteur d'Audit DFM & SMT JLCPCB pour EasyEDA Pro")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parent.parent / "config" / "rules_jlcpcb.json"),
        help="Chemin vers le fichier de règles JSON (par défaut config/rules_jlcpcb.json)"
    )
    parser.add_argument(
        "--bom",
        default="documents/schema/bom.json",
        help="Chemin vers le fichier de nomenclature BOM (défaut: documents/schema/bom.json)"
    )
    parser.add_argument(
        "--output-json",
        default="documents/pcb/dfm_report.json",
        help="Chemin de sortie du rapport JSON (défaut: documents/pcb/dfm_report.json)"
    )
    parser.add_argument(
        "--output-md",
        default="documents/pcb/dfm_report.md",
        help="Chemin de sortie du rapport Markdown (défaut: documents/pcb/dfm_report.md)"
    )
    parser.add_argument("--port", type=int, default=49620, help="Port du pont HTTP EasyEDA Pro (défaut: 49620)")
    parser.add_argument("--pcb-only", action="store_true", help="Auditer uniquement le PCB nu")
    parser.add_argument("--smt-only", action="store_true", help="Auditer uniquement l'assemblage SMT")
    parser.add_argument("--strict", action="store_true", help="Considérer les avertissements comme bloquants")

    args = parser.parse_args()
    exit_code = run_dfm_pipeline(
        config_path=args.config,
        bom_path=args.bom,
        output_json_path=args.output_json,
        output_md_path=args.output_md,
        port=args.port,
        pcb_only=args.pcb_only,
        smt_only=args.smt_only,
        strict=args.strict
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
