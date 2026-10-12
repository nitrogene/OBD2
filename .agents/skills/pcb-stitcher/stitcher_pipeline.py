#!/usr/bin/env python3
"""
Pipeline Maître d'Automatisation de Continuité des Plans de Cuivre
==================================================================
Skill: pcb-stitcher
Règle 0: Moteur agnostique, zéro composant codé en dur, exécution uv run.
Orchestre la chaîne complète : Fanout d'échappement -> Recalcul de plans ->
Audit DRC -> Pontage A* d'îlots résiduels -> DRC = 0.
"""

import sys
import json
import logging
import argparse
import urllib.request
from typing import Dict, Any

from fanout_stitcher import run_fanout_stitcher
from island_bridger import run_island_bridger

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logger = logging.getLogger("pcb_stitcher.pipeline")


def rebuild_pours_and_check_drc(port: int = 49620, target_net: str = "GND") -> Dict[str, Any]:
    """Reconstruit toutes les zones de cuivre et audite le DRC."""
    js_code = """
    const pours = await eda.pcb_PrimitivePour.getAll();
    for (const p of pours) {
        await p.rebuildCopperRegion();
    }
    const groups = await eda.pcb_Drc.check(true, false, true);
    let totalErrors = 0;
    let connErrors = 0;
    let clearErrors = 0;
    const summary = [];

    if (Array.isArray(groups)) {
        for (const g of groups) {
            const count = g.count || (g.list ? g.list.length : 0);
            totalErrors += count;
            if (g.name === 'Connection Error') connErrors += count;
            if (g.name === 'Clearance Error') clearErrors += count;
            summary.push({ name: g.name, count: count });
        }
    }
    return {
        totalErrors,
        connErrors,
        clearErrors,
        summary
    };
    """
    req = urllib.request.Request(
        f"http://localhost:{port}/execute",
        data=json.dumps({"code": js_code}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=60.0) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    if not res.get("success"):
        raise RuntimeError(f"Échec EasyEDA DRC/Rebuild : {res.get('error')}")
    return res["result"]


def run_pipeline(
    target_net: str = "GND",
    clearance_mm: float = 0.23,
    track_width_mm: float = 0.30,
    via_drill_mm: float = 0.30,
    via_diameter_mm: float = 0.60,
    grid_step_mil: float = 5.0,
    port: int = 49620,
    only_disconnected: bool = True,
    apply: bool = False
) -> Dict[str, Any]:
    """Exécute les étapes du pipeline de stitching."""
    logger.info("==================================================")
    logger.info(f"Démarrage du Pipeline PCB Stitcher pour le net '{target_net}'")
    logger.info(f"Paramètres : clearance={clearance_mm}mm, track={track_width_mm}mm, via={via_drill_mm}/{via_diameter_mm}mm, only_disconnected={only_disconnected}, apply={apply}")
    logger.info("==================================================")

    # Étape 1 : Fanout d'échappement pour les pastilles sans via
    logger.info("\n--- Étape 1 : Fanout des pastilles CMS ---")
    fanout_res = run_fanout_stitcher(
        target_net=target_net,
        clearance_mm=clearance_mm,
        track_width_mm=track_width_mm,
        via_drill_mm=via_drill_mm,
        via_diameter_mm=via_diameter_mm,
        port=port,
        only_disconnected=only_disconnected,
        apply=apply
    )
    logger.info(f"Pastilles analysées : {fanout_res['unescaped_count']} sans via, {fanout_res['solved_count']} résolues.")

    # Étape 2 : Recalcul des plans de cuivre et audit DRC intermédiaire
    logger.info("\n--- Étape 2 : Recalcul des plans & Audit DRC ---")
    drc_inter = rebuild_pours_and_check_drc(port=port, target_net=target_net)
    logger.info(f"DRC intermédiaire : {drc_inter['totalErrors']} erreurs (Connexion: {drc_inter['connErrors']}, Dégagement: {drc_inter['clearErrors']})")

    # Étape 3 : Routage A* des îlots résiduels
    bridger_res = None
    if drc_inter["connErrors"] > 0:
        logger.info("\n--- Étape 3 : Routage A* multi-couches des îlots isolés ---")
        bridger_res = run_island_bridger(
            target_net=target_net,
            clearance_mm=clearance_mm,
            track_width_mm=track_width_mm,
            via_drill_mm=via_drill_mm,
            via_diameter_mm=via_diameter_mm,
            grid_step_mil=grid_step_mil,
            port=port,
            apply=apply
        )
        logger.info(f"Passerelles trouvées : {bridger_res['routes_found']} ({bridger_res['vias_count']} vias, {bridger_res['lines_count']} segments)")

    # Étape 4 : Audit DRC final
    logger.info("\n--- Étape 4 : Validation DRC Finale ---")
    drc_final = rebuild_pours_and_check_drc(port=port, target_net=target_net)
    logger.info("==================================================")
    logger.info(f"Bilan DRC Final : {drc_final['totalErrors']} erreurs au total")
    for s in drc_final["summary"]:
        logger.info(f"  - {s['name']} : {s['count']}")
    logger.info("==================================================")

    return {
        "fanout": fanout_res,
        "bridger": bridger_res,
        "drc_final": drc_final,
        "success": (drc_final["totalErrors"] == 0)
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[pcb_stitcher] %(message)s")
    parser = argparse.ArgumentParser(description="Pipeline Maître PCB Stitcher")
    parser.add_argument("--net", type=str, default="GND", help="Net cible (défaut: GND)")
    parser.add_argument("--clearance-mm", type=float, default=0.23, help="Isolement minimal (mm)")
    parser.add_argument("--track-width-mm", type=float, default=0.30, help="Largeur de piste (mm)")
    parser.add_argument("--via-drill-mm", type=float, default=0.30, help="Perçage de via (mm)")
    parser.add_argument("--via-diameter-mm", type=float, default=0.60, help="Diamètre de via (mm)")
    parser.add_argument("--grid-step-mil", type=float, default=5.0, help="Pas de grille A* (mil)")
    parser.add_argument("--port", type=int, default=49620, help="Port EasyEDA Pro")
    parser.add_argument("--all-smd", action="store_true", help="Génère un via pour TOUTES les pastilles CMS (pas seulement celles déconnectées)")
    parser.add_argument("--apply", action="store_true", help="Applique les modifications dans le PCB")
    args = parser.parse_args()

    res = run_pipeline(
        target_net=args.net,
        clearance_mm=args.clearance_mm,
        track_width_mm=args.track_width_mm,
        via_drill_mm=args.via_drill_mm,
        via_diameter_mm=args.via_diameter_mm,
        grid_step_mil=args.grid_step_mil,
        port=args.port,
        only_disconnected=(not args.all_smd),
        apply=args.apply
    )
    sys.exit(0 if res["success"] else 1)
