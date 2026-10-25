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

if str(SYNTHESIZER_DIR) not in sys.path:
    sys.path.insert(0, str(SYNTHESIZER_DIR))
if str(PLACER_DIR) not in sys.path:
    sys.path.insert(0, str(PLACER_DIR))

from dsn_metrics import DsnMetrologyAnalyzer, PostRoutingReport, print_report

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
        apply_easyeda: bool = True
    ):
        self.manifest_path = manifest_path.resolve()
        self.board_path = board_path.resolve()
        self.max_cycles = max_cycles
        self.passes = passes
        self.spacing = spacing
        self.dry_run = dry_run
        self.apply_easyeda = apply_easyeda

        # Cache de synthèse
        self.cache_dir = SYNTHESIZER_DIR / ".cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.candidate_placement = self.cache_dir / "candidate_placement.json"
        self.adapted_manifest_path = self.cache_dir / "adapted_manifest.json"

    def execute_closed_loop(self) -> bool:
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

        synthesis_success = False

        for cycle in range(1, self.max_cycles + 1):
            logger.info(f"\n>>>>>>>> CYCLE DE SYNTHÈSE {cycle} / {self.max_cycles} <<<<<<<<")

            # -----------------------------------------------------------------
            # Étape 1 : Placement Global Stochastique & Recuit Simulé CEM v2
            # -----------------------------------------------------------------
            logger.info(f"[Cycle {cycle} - Étape 1/5] Placement Global & Recuit Simulé CEM v2...")
            with open(self.adapted_manifest_path, "w", encoding="utf-8") as f:
                json.dump(current_manifest, f, indent=2)

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

            if not self.dry_run and self.apply_easyeda:
                # -------------------------------------------------------------
                # Étape 2 : Nettoyage et Injection du placement dans EasyEDA Pro
                # -------------------------------------------------------------
                logger.info(f"[Cycle {cycle} - Étape 2/5] Préparation du PCB dans EasyEDA Pro...")
                try:
                    from easyeda_client import EasyEDAClient
                    client = EasyEDAClient()
                    if client.health().get("edaConnected"):
                        logger.info("🧹 Tabula Rasa : Effacement des pistes, vias et plans de masse cuivre pour carte 100% nue...")
                        clr_res = client.clear_unlocked_routing()
                        logger.info(
                            f"   Nettoyage : {clr_res.get('deletedLines', 0)} pistes, "
                            f"{clr_res.get('deletedArcs', 0)} arcs, {clr_res.get('deletedVias', 0)} vias, "
                            f"{clr_res.get('deletedPours', 0)} plans de masse, {clr_res.get('deletedFills', 0)} fills supprimés."
                        )
                except Exception as e_clean:
                    logger.warning(f"⚠️ Avertissement lors du nettoyage préalable : {e_clean}")

                logger.info(f"[Cycle {cycle} - Étape 2/5] Repositionnement des composants...")
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

                # Étape 2b : Fanout d'échappement préalable des pastilles CMS vers les plans internes
                logger.info(f"[Cycle {cycle} - Étape 2b/5] Fanout d'échappement préalable vers les plans internes (PCB Stitcher)...")
                default_rules = board_cfg.get("net_classes", {}).get("DEFAULT", {})
                st_clearance = str(max(0.23, float(default_rules.get("clearance_mm", 0.20))))
                st_track = str(default_rules.get("track_width_mm", 0.254))
                st_drill = str(default_rules.get("via_drill_mm", 0.30))
                st_diameter = str(default_rules.get("via_diameter_mm", 0.60))
                plane_nets = board_cfg.get("plane_nets", [])
                for p_net in plane_nets:
                    fanout_cmd = [
                        "uv", "run", "python",
                        str(STITCHER_DIR / "fanout_stitcher.py"),
                        "--net", str(p_net),
                        "--clearance-mm", st_clearance,
                        "--track-width-mm", st_track,
                        "--via-drill-mm", st_drill,
                        "--via-diameter-mm", st_diameter,
                        "--apply"
                    ]
                    rc_fo, out_fo, err_fo = run_cmd(fanout_cmd, PROJECT_ROOT)
                    logger.info(out_fo)

            # -----------------------------------------------------------------
            # Étape 3 : Routage Automatique Headless (FreeRouting)
            # -----------------------------------------------------------------
            logger.info(f"[Cycle {cycle} - Étape 3/5] Routage Automatique FreeRouting...")
            ses_output = FREEROUTING_DIR / ".cache" / "board_routed.ses"

            cpu_threads = min(4, max(1, os.cpu_count() or 4))
            fr_cmd = [
                "uv", "run", "python",
                str(FREEROUTING_DIR / "freerouting_pipeline.py"),
                "--config", str(self.board_path),
                "--passes", str(self.passes),
                "--threads", str(cpu_threads)
            ]
            if self.dry_run or not self.apply_easyeda:
                fr_cmd.append("--no-import")

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
            logger.info(f"[Cycle {cycle} - Étape 4/5] Métrologie Physique Post-Routage...")
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

            if report.unrouted_count == 0 and report.violation_count == 0:
                logger.info(f"✅ [Cycle {cycle}] Routage 100% complet (0 non-routé, 0 violation) !")
                synthesis_success = True
                break
            else:
                logger.warning(f"⚠️ [Cycle {cycle}] Écarts métrologiques ou routage incomplet détectés.")
                if cycle < self.max_cycles:
                    logger.info("⚙️ Rétroaction adaptative : resserrement automatique des contraintes locales...")
                    failed_loop_ids = {l.constraint_id for l in report.loops if not l.ok}
                    for c in current_manifest.get("placement_constraints", []):
                        if c.get("type") == "loop" and c.get("id") in failed_loop_ids:
                            old_a = c.get("target_max_area_mm2", 25.0)
                            c["target_max_area_mm2"] = round(old_a * 0.85, 2)
                            c["weight"] = c.get("weight", 8) + 2
                            logger.info(f"  • Boucle {c.get('id')} : réduction cible aire {old_a} -> {c['target_max_area_mm2']} mm²")
                        elif c.get("type") == "proximity" and report.unrouted_count > 0:
                            old_m = c.get("max_mm", 3.0)
                            c["max_mm"] = round(old_m * 0.95, 2)
                            c["weight"] = c.get("weight", 5) + 1
                else:
                    logger.warning("Nombre maximal de cycles atteint.")

        # ---------------------------------------------------------------------
        # Étape 5 : Couture de Masse & Certification DRC Finale
        # ---------------------------------------------------------------------
        if not self.dry_run and self.apply_easyeda:
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


def main():
    parser = argparse.ArgumentParser(description="Orchestrateur de Synthèse PCB en Boucle Fermée")
    parser.add_argument("--manifest", type=Path, default=Path("documents/pcb/manifest.json"))
    parser.add_argument("--board", type=Path, default=Path("documents/pcb/constraints.json"))
    parser.add_argument("--max-cycles", type=int, default=3)
    parser.add_argument("--passes", type=int, default=15)
    parser.add_argument("--spacing", type=float, default=0.20)
    parser.add_argument("--dry-run", action="store_true", help="Mode simulation sans altération d'EasyEDA")
    parser.add_argument("--apply", action="store_true", help="Applique l'injection réelle dans EasyEDA Pro")
    args = parser.parse_args()

    synthesizer = PcbSynthesizer(
        manifest_path=args.manifest,
        board_path=args.board,
        max_cycles=args.max_cycles,
        passes=args.passes,
        spacing=args.spacing,
        dry_run=args.dry_run,
        apply_easyeda=args.apply
    )
    ok = synthesizer.execute_closed_loop()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
