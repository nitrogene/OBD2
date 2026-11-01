#!/usr/bin/env python3
"""
synthesizer_pipeline.py - Orchestrateur de Synthèse PCB en Boucle Fermée (Agnostique)
====================================================================================
Skill: pcb-synthesizer
Règle 0 (AGENTS.md) :
- Zéro composant en dur : lit toutes les règles depuis --manifest et --board.
- Orchestre la chaîne complète :
    pcb-placer -> apply_placement -> freerouting -> dsn_metrics -> pcb-stitcher -> certification DRC = 0.
- Intègre une boucle de rétroaction itérative (max 3 cycles) avec resserrement adaptatif.
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Chemins des compétences sœurs
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SKILLS_DIR = PROJECT_ROOT / ".agents" / "skills"
PLACER_DIR = SKILLS_DIR / "pcb-placer"
FREEROUTING_DIR = SKILLS_DIR / "freerouting"
STITCHER_DIR = SKILLS_DIR / "pcb-stitcher"
SYNTHESIZER_DIR = SKILLS_DIR / "pcb-synthesizer"
DFM_DIR = SKILLS_DIR / "pcb-dfm"
ENCLOSURE_DIR = SKILLS_DIR / "pcb-enclosure"
SILKSCREEN_DIR = SKILLS_DIR / "pcb-silkscreen"

if str(SYNTHESIZER_DIR) not in sys.path:
    sys.path.insert(0, str(SYNTHESIZER_DIR))
if str(PLACER_DIR) not in sys.path:
    sys.path.insert(0, str(PLACER_DIR))
if str(FREEROUTING_DIR) not in sys.path:
    sys.path.insert(0, str(FREEROUTING_DIR))

from dsn_metrics import DsnMetrologyAnalyzer, PostRoutingReport, print_report
from dsn_updater import update_dsn_from_placement
from ses_importer import import_ses_into_easyeda

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SynthesizerPipeline")


def run_cmd(cmd: List[str], cwd: Path) -> Tuple[int, str, str]:
    """Exécute une commande sous uv dans le dossier spécifié."""
    logger.info(f"Exécution : {' '.join(cmd)}")
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore"
    )
    return proc.returncode, proc.stdout, proc.stderr


class PcbSynthesizer:
    """Moteur maître de synthèse en boucle fermée."""

    def __init__(
        self,
        manifest_path: Path,
        board_path: Path,
        max_cycles: int = 3,
        passes: int = 15,
        spacing: float = 0.20,
        dry_run: bool = False,
        apply_easyeda: bool = True,
        placement_override: Optional[Path] = None,
        bootstrap_only: bool = False,
        skip_bootstrap: bool = False,
        turnkey: bool = False,
        production_only: bool = False,
        review_silkscreen: bool = False
    ):
        self.manifest_path = manifest_path.resolve()
        self.board_path = board_path.resolve()
        self.max_cycles = max_cycles
        self.passes = passes
        self.spacing = spacing
        self.dry_run = dry_run
        self.apply_easyeda = apply_easyeda
        self.placement_override = placement_override.resolve() if placement_override else None
        self.bootstrap_only = bootstrap_only
        self.skip_bootstrap = skip_bootstrap
        self.turnkey = turnkey
        self.production_only = production_only
        self.review_silkscreen = review_silkscreen

        # Cache de synthèse
        self.cache_dir = SYNTHESIZER_DIR / ".cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.candidate_placement = self.cache_dir / "candidate_placement.json"
        self.adapted_manifest_path = self.cache_dir / "adapted_manifest.json"
        self.baseline_dsn = self.cache_dir / "board_baseline.dsn"
        self.geometry_cache = PLACER_DIR / ".cache" / "netlist_geometry.json"

    def bootstrap_raw_pcb(self, board_cfg: Dict[str, Any]) -> bool:
        """
        Étape 0 : Amorce Idempotente du PCB Nu (Upstream & Raw PCB Idempotent Bootstrap).
        1. Valide ERC = 0 via eda.sch_Drc.check et la conformité sémantique via sync_semantics.py.
        2. Synchronise le schéma vers le PCB via sync_schematic_to_pcb(auto_confirm=True).
        3. Configure l'empilement 4 couches de cuivre via eda.pcb_Layer.setTheNumberOfCopperLayers(4).
        4. Crée ou vérifie le contour de carte idempotent sur Layer 11 depuis outline_polygon_mm.
        5. Instancie ou valide les trous de fixation mécaniques MH1 à MH4 (M2 drill, net GND).
        """
        logger.info("\n================================================================================")
        logger.info("   [ÉTAPE 0] AMORCE IDEMPOTENTE DU PCB NU (UPSTREAM & RAW PCB BOOTSTRAP)        ")
        logger.info("================================================================================")

        # 1a. Vérification de conformité sémantique (sync_semantics.py check)
        logger.info("[Étape 0.1a] Vérification de conformité sémantique de schéma...")
        sync_cmd = ["uv", "run", "python", str(SKILLS_DIR / "stingy-schematics" / "scripts" / "sync_semantics.py"), "check"]
        rc_sync, stdout_sync, stderr_sync = run_cmd(sync_cmd, PROJECT_ROOT)
        if rc_sync != 0:
            logger.error(f"❌ Désynchronisation sémantique détectée :\n{stderr_sync or stdout_sync}")
            return False
        logger.info("   ✅ Sémantique et nomenclature 100% synchronisées.")

        if self.dry_run or not self.apply_easyeda:
            logger.info("ℹ️ Mode simulation (Dry-Run) ou sans EasyEDA : amorce PCB EasyEDA passée.")
            return True

        from easyeda_client import EasyEDAClient
        client = EasyEDAClient()
        if not client.health().get("edaConnected"):
            logger.error("❌ EasyEDA Pro n'est pas connecté au pont local.")
            return False

        # 1b. Validation ERC = 0 via eda.sch_Drc.check
        logger.info("[Étape 0.1b] Contrôle des règles électriques du schéma (ERC)...")
        erc_res = client.run_erc()
        if not erc_res.get("success"):
            err_cnt = erc_res.get("errorCount", -1)
            logger.error(f"❌ Violation(s) ERC détectée(s) ({err_cnt} erreur(s)) :\n{erc_res.get('errors')}")
            return False
        logger.info("   ✅ Contrôle ERC = 0 certifié sous EasyEDA Pro.")

        # 2. Synchronisation Schéma vers PCB
        logger.info("[Étape 0.2] Synchronisation Schéma -> PCB (importChanges)...")
        sync_res = client.sync_schematic_to_pcb(auto_confirm=True)
        logger.info(f"   Synchronisation PCB : {'✅ Réussie' if sync_res.get('success') else '⚠️ Avertissement'} (autoConfirmed={sync_res.get('autoConfirmed')})")

        # 3. Configuration de l'empilement 4 couches
        board_data = board_cfg.get("board", {})
        layers_count = int(board_data.get("layers", 4))
        logger.info(f"[Étape 0.3] Configuration de l'empilement {layers_count} couches de cuivre...")
        ok_lay = client.set_copper_layers(layers_count)
        if not ok_lay:
            logger.warning(f"   ⚠️ Avertissement lors de la configuration {layers_count} couches.")
        else:
            logger.info(f"   ✅ Empilement {layers_count} couches configuré.")

        # 4. Contour de carte idempotent sur Layer 11
        logger.info("[Étape 0.4] Vérification et injection du contour de carte Layer 11...")
        polygon_mm = board_data.get("outline_polygon_mm")
        w_mm = float(board_data.get("width_mm", 81.28))
        h_mm = float(board_data.get("height_mm", 35.56))
        ok_outline = client.ensure_board_outline(polygon_mm=polygon_mm, width_mm=w_mm, height_mm=h_mm)
        if not ok_outline:
            logger.error("❌ Échec de la vérification/création du contour de carte.")
            return False
        logger.info("   ✅ Contour de carte Layer 11 opérationnel.")

        # 5. Fixations mécaniques MH1 à MH4 (M2, net GND)
        logger.info("[Étape 0.5] Vérification et instanciation des fixations mécaniques MH1..MH4...")
        mounting_holes = board_data.get("mounting_holes", [])
        ok_mh = client.ensure_mounting_holes(mounting_holes)
        if not ok_mh:
            logger.warning("   ⚠️ Avertissement lors de l'instanciation des trous de fixation.")
        else:
            logger.info(f"   ✅ {len(mounting_holes)} trous de fixation mécaniques validés (net GND).")

        # 6. Capture de référence DSN et géométrie CAO pour synthèse hors-ligne
        logger.info("[Étape 0.6] Capture du DSN de référence et snapshot géométrique...")
        try:
            from dsn_exporter import export_dsn_from_easyeda
            from export_geometry import extract_board_geometry
            from dataclasses import asdict
            export_dsn_from_easyeda(self.baseline_dsn)
            geom_snap = extract_board_geometry(client)
            self.geometry_cache.parent.mkdir(parents=True, exist_ok=True)
            with open(self.geometry_cache, "w", encoding="utf-8") as f_g:
                json.dump(asdict(geom_snap), f_g, indent=2)
            logger.info("   ✅ DSN de référence et snapshot géométrique prêts pour synthèse hors-ligne.")
        except Exception as e_base:
            logger.warning(f"   ⚠️ Avertissement capture de référence : {e_base}")

        client.save_pcb()
        logger.info("✅ [ÉTAPE 0] Amorce du PCB nu achevée avec succès !\n")
        return True

    def execute_closed_loop(self) -> bool:
        if self.production_only:
            logger.info("Mode --production-only activé : exécution immédiate du Step 7 (Packaging & 3D)...")
            return self.run_turnkey_production_packaging()

        t_start = time.time()
        cycle_history: List[Dict[str, Any]] = []
        final_drc_summary: Dict[str, Any] = {"errorCount": -1, "warningCount": 0, "by_category": {}}
        logger.info("================================================================================")
        logger.info("            DÉMARRAGE DE LA SYNTHÈSE PCB EN BOUCLE FERMÉE (CO-DESIGN)           ")
        logger.info("================================================================================")
        logger.info(f"Manifeste source       : {self.manifest_path}")
        logger.info(f"Contraintes de carte   : {self.board_path}")
        logger.info(f"Nombre max de cycles   : {self.max_cycles}")
        logger.info(f"Passes autoroutage     : {self.passes}")
        logger.info(f"Mode d'application     : {'Simulation (Dry-Run)' if self.dry_run else 'Injection EasyEDA Pro'}")
        logger.info("--------------------------------------------------------------------------------\n")

        with open(self.manifest_path, "r", encoding="utf-8") as f:
            current_manifest = json.load(f)
        with open(self.board_path, "r", encoding="utf-8") as f:
            board_cfg = json.load(f)

        # ---------------------------------------------------------------------
        # Étape 0 : Amorce Idempotente du PCB Nu (Upstream & Raw PCB Bootstrap)
        # ---------------------------------------------------------------------
        if not self.skip_bootstrap:
            if not self.bootstrap_raw_pcb(board_cfg):
                logger.error("❌ Échec de l'étape 0 (Raw PCB Bootstrap). Arrêt de la synthèse.")
                return False

        if self.bootstrap_only:
            logger.info("🏁 Fin de l'exécution : --bootstrap-only demandé.")
            return True

        # S'assurer que le DSN de référence et la géométrie de base sont disponibles
        if not self.baseline_dsn.exists() or not self.geometry_cache.exists():
            logger.info("📦 Extraction préalable du DSN de référence et du modèle géométrique...")
            from dsn_exporter import export_dsn_from_easyeda
            from export_geometry import extract_board_geometry
            from dataclasses import asdict
            from easyeda_client import EasyEDAClient
            client = EasyEDAClient()
            if not self.baseline_dsn.exists():
                export_dsn_from_easyeda(self.baseline_dsn)
            if not self.geometry_cache.exists():
                geom_snap = extract_board_geometry(client)
                self.geometry_cache.parent.mkdir(parents=True, exist_ok=True)
                with open(self.geometry_cache, "w", encoding="utf-8") as f_g:
                    json.dump(asdict(geom_snap), f_g, indent=2)

        synthesis_success = False
        ses_output = self.cache_dir / "board_routed.ses"

        for cycle in range(1, self.max_cycles + 1):
            logger.info(f"\n>>>>>>>> CYCLE DE SYNTHÈSE {cycle} / {self.max_cycles} (HORS-LIGNE) <<<<<<<<")

            # -----------------------------------------------------------------
            # Étape 1 : Placement Global Stochastique & Recuit Simulé CEM v2
            # -----------------------------------------------------------------
            logger.info(f"[Cycle {cycle} - Étape 1/4] Placement Global & Recuit Simulé CEM v2...")
            with open(self.adapted_manifest_path, "w", encoding="utf-8") as f:
                json.dump(current_manifest, f, indent=2)

            if cycle == 1 and self.placement_override and self.placement_override.is_file():
                logger.info(f"📂 Utilisation directe du placement fourni : {self.placement_override}")
                import shutil
                shutil.copyfile(self.placement_override, self.candidate_placement)
            else:
                placer_cmd = [
                    "uv", "run", "python",
                    str(PLACER_DIR / "simulated_annealing.py"),
                    "--manifest", str(self.adapted_manifest_path),
                    "--board", str(self.board_path),
                    "--starts", "4",
                    "--steps", "40000",
                    "--spacing", str(self.spacing),
                    "--out", str(self.candidate_placement),
                    "--svg", str(PROJECT_ROOT / "documents" / "pcb" / "placement.svg")
                ]
                rc, stdout, stderr = run_cmd(placer_cmd, PROJECT_ROOT)
                if rc != 0:
                    logger.error(f"Échec de l'auto-placement :\n{stderr or stdout}")
                    return False

            # Évaluation du score de placement
            score_cmd = [
                "uv", "run", "python",
                str(PLACER_DIR / "score.py"),
                "--manifest", str(self.adapted_manifest_path),
                "--board", str(self.board_path),
                "--placement", str(self.candidate_placement)
            ]
            rc, stdout, stderr = run_cmd(score_cmd, PROJECT_ROOT)
            logger.info(stdout)
            if rc != 0:
                logger.warning("Le placement obtenu présente des réserves ou violations bloquantes.")

            # -----------------------------------------------------------------
            # Étape 2 : Synthèse DSN Hors-Ligne (Zéro appel HTTP)
            # -----------------------------------------------------------------
            logger.info(f"[Cycle {cycle} - Étape 2/4] Injection locale des coordonnées dans le Specctra DSN...")
            raw_dsn = self.cache_dir / "board_raw.dsn"
            update_dsn_from_placement(
                baseline_dsn_path=self.baseline_dsn,
                geometry_path=self.geometry_cache,
                placement_path=self.candidate_placement,
                output_dsn_path=raw_dsn
            )

            # -----------------------------------------------------------------
            # Étape 3 : Routage Automatique Headless Hors-Ligne (FreeRouting)
            # -----------------------------------------------------------------
            logger.info(f"[Cycle {cycle} - Étape 3/4] Routage Automatique FreeRouting (Hors-Ligne)...")
            cpu_threads = 1  # Mono-thread déterministe
            fr_cmd = [
                "uv", "run", "python",
                str(FREEROUTING_DIR / "freerouting_pipeline.py"),
                "--config", str(self.board_path),
                "--dsn", str(raw_dsn),
                "--passes", str(self.passes),
                "--threads", str(cpu_threads),
                "--no-import"
            ]

            rc, stdout, stderr = run_cmd(fr_cmd, PROJECT_ROOT)
            logger.info(stdout)

            unrouted_val = 0
            violations_val = 0
            m_unrouted = re.search(r'Non routés\s*:\s*(\d+)', stdout)
            if m_unrouted:
                unrouted_val = int(m_unrouted.group(1))
            m_viols = re.search(r'Violations\s*:\s*(\d+)', stdout)
            if m_viols:
                violations_val = int(m_viols.group(1))

            fr_ses = FREEROUTING_DIR / ".cache" / "board_routed.ses"
            if fr_ses.exists():
                import shutil
                shutil.copyfile(fr_ses, ses_output)

            if not ses_output.exists():
                logger.error(f"Échec critique du pipeline FreeRouting (aucun SES produit) :\n{stderr or stdout}")
                return False

            if rc != 0 or unrouted_val > 0 or violations_val > 0:
                logger.warning(
                    f"Routage partiel détecté ({unrouted_val} non routés, {violations_val} violations). "
                    "Poursuite vers l'audit métrologique pour rétroaction..."
                )

            # -----------------------------------------------------------------
            # Étape 4 : Métrologie Post-Routage & Audit en Boucle Fermée
            # -----------------------------------------------------------------
            logger.info(f"[Cycle {cycle} - Étape 4/4] Métrologie Physique Post-Routage...")
            analyzer = DsnMetrologyAnalyzer(ses_output, current_manifest, board_cfg)
            report = analyzer.analyze(unrouted_count=unrouted_val, violation_count=violations_val)
            print_report(report)

            loop_area_val = report.loops[0].area_mm2 if report.loops else 0.0
            max_skew_val = max((dp.skew_mm for dp in report.diff_pairs), default=0.0)
            cycle_history.append({
                "cycle": cycle,
                "unrouted": report.unrouted_count,
                "violations": report.violation_count,
                "wire_length_mm": report.total_wire_length_mm,
                "vias": report.total_vias_count,
                "loop_area_mm2": loop_area_val,
                "max_skew_mm": max_skew_val,
                "is_valid": report.is_valid
            })

            if report.is_valid:
                logger.info(f"✅ [Cycle {cycle}] Synthèse 100% certifiée (0 non-routé, 0 violation, métrologie CEM conforme) !")
                synthesis_success = True
                break
            else:
                logger.warning(f"⚠️ [Cycle {cycle}] Écarts métrologiques ou routage incomplet détectés.")
                if cycle < self.max_cycles:
                    logger.info("⚙️ Rétroaction adaptative : resserrement automatique des contraintes locales...")
                    failed_loop_ids = {l.constraint_id for l in report.loops if not l.ok}
                    failed_dp_classes = {dp.class_id for dp in report.diff_pairs if not dp.ok}
                    failed_crit_nets = {c.net_name for c in report.critical_nets if not c.ok}
                    for c in current_manifest.get("placement_constraints", []):
                        if c.get("type") == "loop" and c.get("id") in failed_loop_ids:
                            old_a = c.get("target_max_area_mm2", 25.0)
                            c["target_max_area_mm2"] = round(old_a * 0.85, 2)
                            c["weight"] = c.get("weight", 8) + 2
                            logger.info(f"  • Boucle {c.get('id')} : réduction cible aire {old_a} -> {c['target_max_area_mm2']} mm²")
                        elif c.get("type") == "proximity" and (report.unrouted_count > 0 or bool(failed_dp_classes) or bool(failed_crit_nets)):
                            old_m = c.get("max_mm", 3.0)
                            c["max_mm"] = round(old_m * 0.95, 2)
                            c["weight"] = c.get("weight", 5) + 1
                else:
                    logger.warning("Nombre maximal de cycles atteint.")

        # ---------------------------------------------------------------------
        # Condition d'arrêt bloquante CEM & Intégrité
        # ---------------------------------------------------------------------
        if not synthesis_success:
            logger.error(
                f"\n❌ [ARRÊT BLOQUANT] Non-convergence de la synthèse après {self.max_cycles} cycles.\n"
                "Les conditions métrologiques ou d'intégrité de routage ne sont pas satisfaites (is_valid == False).\n"
                "Le PCB dans EasyEDA Pro est préservé intact sans altération partielle."
            )
            report_file = PROJECT_ROOT / "documents" / "pcb" / "synthesis_report.json"
            report_data = {
                "date": datetime.now().isoformat(),
                "success": False,
                "cycles": cycle_history,
                "drc": {"errorCount": -1, "warningCount": -1, "groups": [], "items": []}
            }
            with open(report_file, "w", encoding="utf-8") as rf:
                json.dump(report_data, rf, indent=2)
            return False

        # ---------------------------------------------------------------------
        # Étape 5 : Matérialisation Unique dans EasyEDA Pro & Couture de Masse
        # ---------------------------------------------------------------------
        if not self.dry_run and self.apply_easyeda:
            logger.info("\n================================================================================")
            logger.info("   [MATÉRIALISATION UNIQUE] APPLICATION DU LAYOUT CONVERGÉ DANS EASYEDA PRO      ")
            logger.info("================================================================================")
            try:
                from easyeda_client import EasyEDAClient
                client = EasyEDAClient()
                if not client.health().get("edaConnected"):
                    logger.error("❌ EasyEDA Pro n'est pas connecté pour la matérialisation.")
                    return False

                # 1. Tabula Rasa
                logger.info("🧹 Tabula Rasa : Effacement des pistes, vias et plans de masse cuivre pour carte 100% nue...")
                clr_res = client.clear_unlocked_routing()
                logger.info(
                    f"   Nettoyage : {clr_res.get('deletedLines', 0)} pistes, "
                    f"{clr_res.get('deletedArcs', 0)} arcs, {clr_res.get('deletedVias', 0)} vias, "
                    f"{clr_res.get('deletedPours', 0)} plans de masse supprimés."
                )

                # 2. Injection du placement validé
                logger.info("📍 Repositionnement des composants...")
                apply_cmd = [
                    "uv", "run", "python",
                    str(PLACER_DIR / "apply_placement.py"),
                    "--placement", str(self.candidate_placement),
                    "--no-drc"
                ]
                rc, stdout, stderr = run_cmd(apply_cmd, PROJECT_ROOT)
                if rc != 0:
                    logger.error(f"Échec de l'application dans EasyEDA Pro :\n{stderr or stdout}")
                    return False

                # 3. Import du routage SES certifié
                logger.info("🔌 Importation du tracé des pistes (.ses) dans EasyEDA Pro...")
                import_ok = import_ses_into_easyeda(ses_output, save_after_import=False)
                if not import_ok:
                    logger.error("❌ Échec de l'importation du routage SES dans EasyEDA Pro.")
                    return False
                logger.info("   ✅ Tracés de signaux et paires différentielles importés avec succès.")
            except Exception as e_mat:
                logger.error(f"❌ Erreur critique lors de la matérialisation dans EasyEDA Pro : {e_mat}")
                return False

            logger.info("\n[Finalisation - Étape 5/5] Création des Plans de Masse & Couture (PCB Stitcher)...")
            try:
                from easyeda_client import EasyEDAClient
                client = EasyEDAClient()
                if client.health().get("edaConnected"):
                    # Extraction dynamique et agnostique des dimensions depuis la configuration du board
                    board_info = board_cfg["board"]
                    b_width_mm = float(board_info["width_mm"])
                    b_height_mm = float(board_info["height_mm"])
                    edge_clr_mm = float(board_info.get("edge_clearance_mm", 0.5))

                    x_min_mil = round(edge_clr_mm * 39.37007874, 2)
                    y_min_mil = round(edge_clr_mm * 39.37007874, 2)
                    x_max_mil = round((b_width_mm - edge_clr_mm) * 39.37007874, 2)
                    y_max_mil = round((b_height_mm - edge_clr_mm) * 39.37007874, 2)
                    pour_w_mil = round((b_width_mm - 2 * edge_clr_mm) * 39.37007874, 2)
                    pour_h_mil = round((b_height_mm - 2 * edge_clr_mm) * 39.37007874, 2)
                    # Extraction agnostique des couches et réseaux de plans depuis la configuration
                    pours_config = []
                    stackup_layers = board_cfg.get("board", {}).get("stackup", {}).get("layers") or board_cfg.get("stackup", {}).get("layers", [])
                    if stackup_layers:
                        for lay in stackup_layers:
                            net_name = lay.get("default_net")
                            lay_id = lay.get("id")
                            if net_name and lay_id is not None:
                                pours_config.append({
                                    "net": str(net_name),
                                    "layer": int(lay_id),
                                    "name": f"{net_name}_L{lay_id}"
                                })
                    else:
                        plane_nets_list = board_cfg.get("plane_nets", [])
                        for p_net in plane_nets_list:
                            pours_config.append({"net": str(p_net), "layer": 1, "name": f"{p_net}_TOP"})
                            pours_config.append({"net": str(p_net), "layer": 2, "name": f"{p_net}_BOTTOM"})

                    logger.info(
                        f"📐 Injection dynamique de {len(pours_config)} plans de cuivre : "
                        f"X=[{x_min_mil}..{x_max_mil}] mil, Y=[{y_min_mil}..{y_max_mil}] mil..."
                    )

                    js_pours = f"""
                    const oldPours = await eda.pcb_PrimitivePour.getAll();
                    if (oldPours && oldPours.length) {{
                        await eda.pcb_PrimitivePour.delete(oldPours.map(p => p.getState_PrimitiveId()));
                    }}
                    // Polygone universel recouvrant la surface utile du PCB (point haut-gauche: x_min, y_max)
                    const poly = eda.pcb_MathPolygon.createPolygon(['R', {x_min_mil}, {y_max_mil}, {pour_w_mil}, {pour_h_mil}, 0, 0]);
                    const configs = {json.dumps(pours_config)};
                    const createdPours = [];

                    for (const cfg of configs) {{
                        const p = await eda.pcb_PrimitivePour.create(cfg.net, cfg.layer, poly, 'solid', false, cfg.name, 1, 10, false);
                        createdPours.push(p);
                    }}

                    // Reconstitution native du cuivre via l'API EasyEDA Pro
                    for (const p of createdPours) {{
                        if (p && p.rebuildCopperRegion) await p.rebuildCopperRegion();
                    }}

                    await eda.pcb_Document.save();
                    return true;
                    """
                    client.execute_js(js_pours)
            except Exception as e_pours:
                logger.warning(f"⚠️ Avertissement injection plans de masse : {e_pours}")

            # Extraction agnostique des contraintes DRC de couture depuis la classe par défaut
            default_rules = board_cfg.get("net_classes", {}).get("DEFAULT", {})
            st_clearance = str(max(0.23, float(default_rules.get("clearance_mm", 0.20))))
            st_track = str(default_rules.get("track_width_mm", 0.254))
            st_drill = str(default_rules.get("via_drill_mm", 0.30))
            st_diameter = str(default_rules.get("via_diameter_mm", 0.60))
            plane_nets = board_cfg.get("plane_nets", [])
            if not plane_nets:
                raise KeyError("La configuration de carte doit définir 'plane_nets'.")
            st_net = str(plane_nets[0])

            # 6a. Fanout de rattrapage sur d'éventuelles pastilles restées déconnectées
            fanout_fix_cmd = [
                "uv", "run", "python",
                str(STITCHER_DIR / "fanout_stitcher.py"),
                "--net", st_net,
                "--clearance-mm", st_clearance,
                "--track-width-mm", st_track,
                "--via-drill-mm", st_drill,
                "--via-diameter-mm", st_diameter,
                "--only-disconnected",
                "--apply"
            ]
            rc_f, stdout_f, stderr_f = run_cmd(fanout_fix_cmd, PROJECT_ROOT)
            logger.info(stdout_f)

            # 6b. Résolution des îlots isolés via routage A* multi-couches
            stitcher_cmd = [
                "uv", "run", "python",
                str(STITCHER_DIR / "island_bridger.py"),
                "--net", st_net,
                "--clearance-mm", st_clearance,
                "--track-width-mm", st_track,
                "--via-drill-mm", st_drill,
                "--via-diameter-mm", st_diameter,
                "--apply"
            ]
            rc, stdout, stderr = run_cmd(stitcher_cmd, PROJECT_ROOT)
            logger.info(stdout)
            if rc != 0:
                logger.warning(f"Avertissement lors de la couture de masse (code {rc}). Poursuite de la finalisation...")

            # 6c. Reconstitution finale des plans de masse et déduplication des vias
            try:
                from easyeda_client import EasyEDAClient
                client = EasyEDAClient()
                if client.health().get("edaConnected"):
                    js_rebuild = """
                    const vias = await eda.pcb_PrimitiveVia.getAll() || [];
                    const seen = new Set();
                    const dups = [];
                    for (const v of vias) {
                        const key = Math.round(v.getState_X()) + '_' + Math.round(v.getState_Y());
                        if (seen.has(key)) dups.push(v.getState_PrimitiveId());
                        else seen.add(key);
                    }
                    if (dups.length) await eda.pcb_PrimitiveVia.delete(dups);

                    const pours = await eda.pcb_PrimitivePour.getAll() || [];
                    for (const p of pours) {
                        if (p.rebuildCopperRegion) await p.rebuildCopperRegion();
                    }
                    await eda.pcb_Document.save();
                    return { deletedDups: dups.length };
                    """
                    res_reb = client.execute_js(js_rebuild)
                    if res_reb and res_reb.get("deletedDups"):
                        logger.info(f"🧹 Déduplication EasyEDA Pro : {res_reb['deletedDups']} via(s) doublon(s) éliminé(s).")
            except Exception as e_reb:
                logger.warning(f"⚠️ Avertissement lors de la reconstruction finale du cuivre : {e_reb}")

            # Normalisation IPC-7351 de la sérigraphie (redressement des étiquettes à 0°/90° strict)
            logger.info("\n📐 Normalisation de la Sérigraphie (Label Placer - IPC-7351)...")
            label_cmd = [
                "uv", "run", "python",
                str(PLACER_DIR / "label_placer.py"),
                "--manifest", str(self.manifest_path),
                "--constraints", str(self.board_path)
            ]
            rc_lbl, stdout_lbl, stderr_lbl = run_cmd(label_cmd, PROJECT_ROOT)
            logger.info(stdout_lbl)

            # Injection déclarative de la sérigraphie additionnelle (pcb-silkscreen)
            silk_file = PROJECT_ROOT / "documents" / "pcb" / "silkscreen.json"
            if silk_file.exists():
                logger.info("\n🎨 Application de la Sérigraphie Additionnelle (pcb-silkscreen)...")
                silk_cmd = [
                    "uv", "run", "python",
                    str(SKILLS_DIR / "pcb-silkscreen" / "scripts" / "apply_silkscreen.py"),
                    "--silkscreen", str(silk_file),
                    "--constraints", str(self.board_path),
                    "--placement", str(self.candidate_placement)
                ]
                rc_silk, stdout_silk, stderr_silk = run_cmd(silk_cmd, PROJECT_ROOT)
                logger.info(stdout_silk)

            # Contrôle DRC natif final dans EasyEDA Pro
            try:
                from easyeda_client import EasyEDAClient
                client = EasyEDAClient()
                if client.health().get("edaConnected"):
                    logger.info("🔍 Exécution du contrôle DRC natif final EasyEDA Pro...")
                    drc_res = client.run_drc()
                    err_cnt = drc_res.get("errorCount", 0)
                    warn_cnt = drc_res.get("warningCount", 0)
                    items = drc_res.get("items", [])
                    groups = drc_res.get("groups", [])

                    cat_map: Dict[str, List[Dict[str, Any]]] = {}
                    for it in items:
                        cat_name = it.get("category", "Autres")
                        cat_map.setdefault(cat_name, []).append(it)

                    final_drc_summary = {
                        "errorCount": err_cnt,
                        "warningCount": warn_cnt,
                        "by_category": {k: len(v) for k, v in cat_map.items()}
                    }

                    logger.info(f"   Résultat DRC final : {err_cnt} erreur(s), {warn_cnt} avertissement(s)")

                    if err_cnt == 0:
                        logger.info("✅ DRC = 0 certifié avec succès !")
                        client.save_pcb()
                        if self.turnkey:
                            self.run_turnkey_production_packaging()
                    else:
                        logger.warning(f"⚠️ DRC présente encore {err_cnt} erreur(s) résiduelle(s) :")
                        for cat_name, cat_items in cat_map.items():
                            logger.info(f"\n  📋 [{cat_name}] ({len(cat_items)} occurrence(s)) :")
                            net_map: Dict[str, List[str]] = {}
                            for ci in cat_items:
                                n = ci.get("net") or "Sans net"
                                desc = f"{ci.get('obj1')}"
                                if ci.get("obj2"):
                                    desc += f" vs {ci.get('obj2')}"
                                if ci.get("minDistance") and ci.get("requiredDistance"):
                                    desc += f" ({ci.get('minDistance')} < {ci.get('requiredDistance')})"
                                net_map.setdefault(n, []).append(desc)

                            for net_n, descs in net_map.items():
                                logger.info(f"     • Réseau '{net_n}' ({len(descs)}) : {', '.join(descs[:8])}{'...' if len(descs) > 8 else ''}")

                    # Sauvegarde automatique du rapport complet de synthèse
                    report_file = PROJECT_ROOT / "documents" / "pcb" / "synthesis_report.json"
                    report_data = {
                        "date": datetime.now().isoformat(),
                        "success": (err_cnt == 0) and synthesis_success,
                        "cycles": cycle_history,
                        "drc": {
                            "errorCount": err_cnt,
                            "warningCount": warn_cnt,
                            "groups": groups,
                            "items": items
                        }
                    }
                    with open(report_file, "w", encoding="utf-8") as rf:
                        json.dump(report_data, rf, indent=2)
                    logger.info(f"\n📄 Rapport de synthèse exporté dans : {report_file}")
            except Exception as e_drc:
                logger.warning(f"Impossible de vérifier le DRC natif EasyEDA : {e_drc}")

        elapsed_s = round(time.time() - t_start, 1)
        logger.info("\n================================================================================")
        logger.info(f"         RÉSUMÉ EXÉCUTIF DU PIPELINE DE SYNTHÈSE PCB ({elapsed_s} s)            ")
        logger.info("================================================================================")
        for ch in cycle_history:
            logger.info(
                f"  • Cycle {ch['cycle']} : Non routés = {ch['unrouted']} | Violations FR = {ch['violations']} | "
                f"Longueur = {ch['wire_length_mm']:.1f} mm | Vias = {ch['vias']} | "
                f"Boucle Buck = {ch['loop_area_mm2']:.2f} mm² | Skew max = {ch['max_skew_mm']:.2f} mm"
            )
        if final_drc_summary["errorCount"] >= 0:
            logger.info("--------------------------------------------------------------------------------")
            logger.info(
                f"  • Bilan DRC EasyEDA Pro : {final_drc_summary['errorCount']} erreur(s), "
                f"{final_drc_summary['warningCount']} avertissement(s)"
            )
            for cname, ccnt in final_drc_summary["by_category"].items():
                logger.info(f"      - {cname:<22} : {ccnt}")
        logger.info("--------------------------------------------------------------------------------")
        logger.info(f"  • Statut final : {'✅ SUCCÈS (DRC = 0 & Routage 100%)' if (synthesis_success and final_drc_summary.get('errorCount', 0) == 0) else '⚠️ ACHEVÉ AVEC ALERTES'}")
        logger.info("================================================================================\n")
        return synthesis_success

    def run_turnkey_production_packaging(self) -> bool:
        """Exécute automatiquement la chaîne complète des livrables de production (Step 7)."""
        logger.info("\n" + "=" * 80)
        logger.info("📦 DÉMARRAGE DU PACKAGING DE PRODUCTION CLEF EN MAIN (STEP 7)")
        logger.info("=" * 80)

        prod_dir = PROJECT_ROOT / "documents" / "production"
        enclosure_dir = PROJECT_ROOT / "documents" / "enclosure"
        pcb_dir = PROJECT_ROOT / "documents" / "pcb"

        # 0. Revue interactive optionnelle de la sérigraphie (Point d'étape ultime)
        if self.review_silkscreen:
            logger.info("\n[0/3] Point de contrôle : Revue interactive de sérigraphie dans EasyEDA Pro...")
            sync_script = SILKSCREEN_DIR / "scripts" / "sync_silkscreen.py"
            subprocess.run([
                "uv", "run", "python", str(sync_script),
                "interactive",
                "--silkscreen", str(pcb_dir / "silkscreen.json"),
                "--constraints", str(self.board_path)
            ], cwd=str(PROJECT_ROOT))

        # 1. Export fabrication (Gerber, Drill, CPL, BOM)
        logger.info("\n[1/3] Exportation du dossier de fabrication industrielle...")
        fab_script = DFM_DIR / "scripts" / "export_fabrication.py"
        rc, out, err = run_cmd([
            "uv", "run", "python", str(fab_script),
            "--output-dir", str(prod_dir),
            "--prefix", "OBD2"
        ], cwd=PROJECT_ROOT)
        if rc != 0:
            logger.error(f"Échec de l'export de fabrication : {err}")
            return False

        # 2. Export des rendus visuels d'inspection (2D Top, 2D Bottom, 3D PCBA, PCB natif)
        logger.info("\n[2/3] Exportation des rendus d'inspection visuelle...")
        img_script = DFM_DIR / "scripts" / "export_pcb_images.py"
        rc, out, err = run_cmd([
            "uv", "run", "python", str(img_script),
            "--output-dir", str(pcb_dir)
        ], cwd=PROJECT_ROOT)
        if rc != 0:
            logger.warning(f"Avertissement lors de l'export des rendus : {err}")

        # 3. Contrôle d'interférence 3D & Assemblage Boîtier + PCBA réelle
        logger.info("\n[3/3] Contrôle d'interférence 3D & Assemblage Boîtier + PCBA réelle...")
        enclosure_script = ENCLOSURE_DIR / "scripts" / "enclosure_generator.py"
        pcba_step = prod_dir / "OBD2_PCBA.step"
        rc, out, err = run_cmd([
            "uv", "run", "--with", "build123d", "python", str(enclosure_script),
            "--constraints", str(self.board_path),
            "--enclosure", str(pcb_dir / "enclosure.json"),
            "--pcba-step", str(pcba_step),
            "--output-dir", str(enclosure_dir)
        ], cwd=PROJECT_ROOT)
        if rc != 0:
            logger.error(f"Échec de la modélisation et assemblage boîtier : {err}")
            return False

        logger.info("\n" + "=" * 80)
        logger.info("🎉 PACKAGING DE PRODUCTION ET ASSEMBLAGE 3D ACHEVÉS AVEC SUCCÈS")
        logger.info("=" * 80 + "\n")
        return True


def main():
    parser = argparse.ArgumentParser(description="Orchestrateur de Synthèse PCB en Boucle Fermée")
    parser.add_argument("--manifest", type=Path, default=Path("documents/pcb/manifest.json"))
    parser.add_argument("--board", type=Path, default=Path("documents/pcb/constraints.json"))
    parser.add_argument("--max-cycles", type=int, default=3)
    parser.add_argument("--passes", type=int, default=15)
    parser.add_argument("--spacing", type=float, default=0.20)
    parser.add_argument("--dry-run", action="store_true", help="Mode simulation sans altération d'EasyEDA")
    parser.add_argument("--apply", action="store_true", help="Applique l'injection réelle dans EasyEDA Pro")
    parser.add_argument("--placement", type=Path, default=None, help="Placement initial pré-calculé (saute l'étape 1 du cycle 1)")
    parser.add_argument("--bootstrap-only", action="store_true", help="Exécute uniquement l'étape 0 (Raw PCB Bootstrap) et s'arrête")
    parser.add_argument("--skip-bootstrap", action="store_true", help="Saute l'étape 0 d'amorce du PCB nu")
    parser.add_argument("--turnkey", action="store_true", help="Enchaîne automatiquement le packaging de production (Step 7) dès que DRC = 0")
    parser.add_argument("--production-only", action="store_true", help="Exécute uniquement le packaging de production (Step 7) sans relancer la synthèse")
    parser.add_argument("--review-silkscreen", action="store_true", help="Active la revue interactive de sérigraphie au début du Step 7")
    args = parser.parse_args()

    synthesizer = PcbSynthesizer(
        manifest_path=args.manifest,
        board_path=args.board,
        max_cycles=args.max_cycles,
        passes=args.passes,
        spacing=args.spacing,
        dry_run=args.dry_run,
        apply_easyeda=args.apply,
        placement_override=args.placement,
        bootstrap_only=args.bootstrap_only,
        skip_bootstrap=args.skip_bootstrap,
        turnkey=args.turnkey,
        production_only=args.production_only,
        review_silkscreen=args.review_silkscreen
    )
    ok = synthesizer.execute_closed_loop()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
