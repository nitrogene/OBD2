#!/usr/bin/env python3
"""
Solveur de Fanout et Vias d'Échappement Automatique pour EasyEDA Pro
===================================================================
Skill: pcb-stitcher
Règle 0: Ce script est purement agnostique.
Il scanne les pastilles CMS d'un net cible (ex: GND), calcule les spots de vias
d'échappement optimaux sans collision et injecte les primitives via l'API EasyEDA Pro.
"""

import sys
import json
import math
import logging
import argparse
import urllib.request
from typing import Dict, List, Any, Optional

from geometry import (
    ObstacleEnvironment,
    dist_point_to_segment,
    MM_TO_MIL,
    MIL_TO_MM,
)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logger = logging.getLogger("pcb_stitcher.fanout")


def fetch_pcb_layout(port: int = 49620) -> Dict[str, Any]:
    """Extrait les primitives physiques nécessaires depuis le document PCB actif."""
    js_code = """
    const lines = await eda.pcb_PrimitiveLine.getAll();
    const vias = await eda.pcb_PrimitiveVia.getAll();
    const pads = await eda.pcb_PrimitivePad.getAll();

    return {
        lines: lines.map(l => ({
            id: l.getState_PrimitiveId(),
            net: l.getState_Net(),
            layer: l.getState_Layer(),
            x1: l.getState_StartX(),
            y1: l.getState_StartY(),
            x2: l.getState_EndX(),
            y2: l.getState_EndY(),
            width: l.getState_LineWidth()
        })),
        vias: vias.map(v => ({
            id: v.getState_PrimitiveId(),
            net: v.getState_Net(),
            x: v.getState_X(),
            y: v.getState_Y(),
            diameter: v.getState_Diameter ? v.getState_Diameter() : 24
        })),
        pads: pads.map(p => {
            const padShape = p.getState_Pad ? p.getState_Pad() : null;
            const holeShape = p.getState_Hole ? p.getState_Hole() : null;
            const rot = p.getState_Rotation ? (p.getState_Rotation() || 0) : 0;
            let w = 40, h = 40;
            if (Array.isArray(padShape)) {
                if (typeof padShape[1] === 'number') {
                    w = padShape[1];
                    h = (typeof padShape[2] === 'number' && padShape[0] !== 'REGULAR_POLYGON') ? padShape[2] : w;
                } else if (Array.isArray(padShape[1])) {
                    const pts = padShape[1].flat(2).filter(v => typeof v === 'number');
                    if (pts.length >= 4) {
                        let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
                        for (let i = 0; i + 1 < pts.length; i += 2) {
                            if (pts[i] < minX) minX = pts[i];
                            if (pts[i] > maxX) maxX = pts[i];
                            if (pts[i+1] < minY) minY = pts[i+1];
                            if (pts[i+1] > maxY) maxY = pts[i+1];
                        }
                        if (isFinite(minX) && maxX > minX) w = maxX - minX;
                        if (isFinite(minY) && maxY > minY) h = maxY - minY;
                    }
                }
            }
            let drill = 0;
            if (Array.isArray(holeShape) && typeof holeShape[1] === 'number') {
                drill = holeShape[1];
                w = Math.max(w, holeShape[1] + 12);
                h = Math.max(h, (typeof holeShape[2] === 'number' ? holeShape[2] : holeShape[1]) + 12);
            }
            const rNorm = ((rot % 180) + 180) % 180;
            if (rNorm >= 45 && rNorm <= 135) {
                const tmp = w; w = h; h = tmp;
            }
            return {
                id: p.getState_PrimitiveId(),
                net: p.getState_Net(),
                layer: p.getState_Layer(),
                x: p.getState_X(),
                y: p.getState_Y(),
                width: w,
                height: h,
                drill: drill
            };
        })
    };
    """
    req = urllib.request.Request(
        f"http://localhost:{port}/execute",
        data=json.dumps({"code": js_code}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30.0) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    if not res.get("success"):
        raise RuntimeError(f"Échec d'extraction EasyEDA : {res.get('error')}")
    return res["result"]


def solve_pad_fanout(
    pad: Dict[str, Any],
    env: ObstacleEnvironment,
    target_net: str,
    track_width_mil: float,
    clearance_mil: float,
    via_radius_mil: float,
    escape_dist_mil: float = 22.0
) -> Optional[Dict[str, Any]]:
    """Recherche la position angulaire optimale pour un via d'échappement autour d'une pastille."""
    px = pad["x"]
    py = pad["y"]
    play = pad.get("layer", 1)
    if play not in (1, 2):
        play = 1

    best_cand = None
    best_score = -1e9

    # Échantillonnage radial (24 angles pour exploration fine)
    angles = [i * (2.0 * math.pi / 24.0) for i in range(24)]
    # Essayer un éventail progressif de distances d'échappement (de 0.6 mm à 2.1 mm)
    distances = [25.0, 35.0, 45.0, 55.0, 70.0, 85.0]

    for dist in distances:
        for angle in angles:
            vx = px + dist * math.cos(angle)
            vy = py + dist * math.sin(angle)

            # 1. Vérification dégagement du via
            if not env.is_via_clear(vx, vy, via_radius_mil, clearance_mil, target_net=target_net):
                continue

            # 2. Vérification dégagement de la micro-piste
            if not env.is_segment_clear(px, py, vx, vy, play, track_width_mil, clearance_mil, target_net=target_net):
                continue

            # Score basé sur la marge d'isolement minimale
            min_margin = 1e9
            for l in env.lines:
                if l.get("net") == target_net:
                    continue
                d = dist_point_to_segment(vx, vy, l["x1"], l["y1"], l["x2"], l["y2"])
                min_margin = min(min_margin, d - (via_radius_mil + l.get("width", 10.0)/2.0))

            if min_margin > best_score:
                best_score = min_margin
                best_cand = {
                    "pad_id": pad["id"],
                    "pad_pos": (px, py),
                    "pad_layer": play,
                    "via_pos": (vx, vy),
                    "distance_mil": dist,
                    "margin_score_mil": min_margin
                }

        if best_cand:
            break

    return best_cand


def run_fanout_stitcher(
    target_net: str,
    clearance_mm: float = 0.23,
    track_width_mm: float = 0.30,
    via_drill_mm: float = 0.30,
    via_diameter_mm: float = 0.60,
    port: int = 49620,
    only_disconnected: bool = False,
    apply: bool = False
) -> Dict[str, Any]:
    """Exécute l'analyse et la génération du fanout de vias."""
    clearance_mil = clearance_mm * MM_TO_MIL
    track_width_mil = track_width_mm * MM_TO_MIL
    via_drill_mil = via_drill_mm * MM_TO_MIL
    via_dia_mil = via_diameter_mm * MM_TO_MIL
    via_radius_mil = via_dia_mil / 2.0

    logger.info(f"Extraction des primitives pour le net '{target_net}'...")
    data = fetch_pcb_layout(port=port)
    lines = data["lines"]
    vias = data["vias"]
    pads = data["pads"]

    env = ObstacleEnvironment(lines=lines, vias=vias, pads=pads)

    target_pads = [p for p in pads if p.get("net") == target_net and p.get("layer") in (1, 2)]
    target_vias = [v for v in vias if v.get("net") == target_net]

    logger.info(f"Trouvé {len(target_pads)} pastilles et {len(target_vias)} vias pour le net '{target_net}'.")

    # Si only_disconnected est actif, purger d'abord tout via/piste de target_net en conflit DRC
    # puis récupérer les IDs des pastilles en erreur de connexion DRC
    drc_pad_ids = set()
    if only_disconnected:
        js_drc = f"""
        const groups = await eda.pcb_Drc.check(true, false, true) || [];
        const allVias = await eda.pcb_PrimitiveVia.getAll() || [];
        const allLines = await eda.pcb_PrimitiveLine.getAll() || [];
        const viaMap = new Map(allVias.map(v => [v.getState_PrimitiveId(), v]));
        const lineMap = new Map(allLines.map(l => [l.getState_PrimitiveId(), l]));
        const badViaIds = new Set();
        const badLineIds = new Set();

        for (const cat of groups) {{
            if (cat.name === 'Clearance Error') {{
                for (const sub of (cat.list || [])) {{
                    for (const item of (sub.list || [])) {{
                        const objs = item.objs || [item.explanation?.errData?.obj1, item.explanation?.errData?.obj2].filter(Boolean);
                        for (const oid of objs) {{
                            const v = viaMap.get(oid);
                            if (v && v.getState_Net() === '{target_net}') badViaIds.add(oid);
                            const l = lineMap.get(oid);
                            if (l && l.getState_Net() === '{target_net}') badLineIds.add(oid);
                        }}
                    }}
                }}
            }}
        }}

        if (badViaIds.size > 0 || badLineIds.size > 0) {{
            for (const vid of badViaIds) {{
                const v = viaMap.get(vid);
                const vx = v.getState_X(), vy = v.getState_Y();
                for (const l of allLines) {{
                    if (l.getState_Net() === '{target_net}') {{
                        const d1 = Math.hypot(l.getState_StartX() - vx, l.getState_StartY() - vy);
                        const d2 = Math.hypot(l.getState_EndX() - vx, l.getState_EndY() - vy);
                        if (d1 < 3.0 || d2 < 3.0) badLineIds.add(l.getState_PrimitiveId());
                    }}
                }}
            }}
            for (const lid of Array.from(badLineIds)) {{
                const l = lineMap.get(lid);
                if (!l) continue;
                for (const v of allVias) {{
                    if (v.getState_Net() === '{target_net}') {{
                        const d1 = Math.hypot(l.getState_StartX() - v.getState_X(), l.getState_StartY() - v.getState_Y());
                        const d2 = Math.hypot(l.getState_EndX() - v.getState_X(), l.getState_EndY() - v.getState_Y());
                        if (d1 < 3.0 || d2 < 3.0) badViaIds.add(v.getState_PrimitiveId());
                    }}
                }}
            }}
            if (badViaIds.size > 0) await eda.pcb_PrimitiveVia.delete(Array.from(badViaIds));
            if (badLineIds.size > 0) await eda.pcb_PrimitiveLine.delete(Array.from(badLineIds));
            const pours = await eda.pcb_PrimitivePour.getAll() || [];
            for (const p of pours) {{
                if (p.rebuildCopperRegion) await p.rebuildCopperRegion();
            }}
        }}

        const groupsAfter = (badViaIds.size > 0 || badLineIds.size > 0) ? (await eda.pcb_Drc.check(true, false, true) || []) : groups;
        const ids = [];
        for (const cat of groupsAfter) {{
            if (cat.name === 'Connection Error') {{
                for (const netGroup of (cat.list || [])) {{
                    if (netGroup.name === '{target_net}') {{
                        for (const item of (netGroup.list || [])) {{
                            const objs = item.objs || [item.explanation?.errData?.obj1, item.explanation?.errData?.obj2].filter(Boolean);
                            for (const primId of objs) {{
                                if (primId) ids.push(primId);
                            }}
                        }}
                    }}
                }}
            }}
        }}
        return {{ ids, deletedBadVias: badViaIds.size + badLineIds.size }};
        """
        req_drc = urllib.request.Request(
            f"http://localhost:{port}/execute",
            data=json.dumps({"code": js_drc}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req_drc, timeout=45.0) as resp:
                res_drc_obj = json.loads(resp.read().decode("utf-8")).get("result", {})
                if isinstance(res_drc_obj, dict):
                    drc_pad_ids = set(res_drc_obj.get("ids", []))
                    if res_drc_obj.get("deletedBadVias", 0) > 0:
                        logger.info(f"Auto-correction DRC : {res_drc_obj['deletedBadVias']} primitive(s) en violation Clearance supprimée(s) et recalculée(s).")
                        data = fetch_pcb_layout(port=port)
                        lines = data["lines"]
                        vias = data["vias"]
                        pads = data["pads"]
                        env = ObstacleEnvironment(lines=lines, vias=vias, pads=pads)
                        target_pads = [p for p in pads if p.get("net") == target_net and p.get("layer") in (1, 2)]
                        target_vias = [v for v in vias if v.get("net") == target_net]
                else:
                    drc_pad_ids = set(res_drc_obj)
        except Exception as e:
            logger.warning(f"Impossible de récupérer le DRC pour le filtre : {e}")

    # Détecter les pastilles qui ont déjà un via superposé (< 5 mil) ou une ligne connectée
    unescaped = []
    for p in target_pads:
        if only_disconnected and p["id"] not in drc_pad_ids:
            continue
        px, py = p["x"], p["y"]
        # Une pastille CMS n'est connectée à la masse que si un via est directement sous elle ou relié par une piste
        has_via = any(math.hypot(v["x"] - px, v["y"] - py) < 5.0 for v in target_vias)
        has_line = any(
            (math.hypot(l["x1"] - px, l["y1"] - py) < 2.0 or math.hypot(l["x2"] - px, l["y2"] - py) < 2.0)
            and l.get("net") == target_net for l in lines
        )
        if not has_via and not has_line:
            unescaped.append(p)

    logger.info(f"Pastilles nécessitant un via d'échappement : {len(unescaped)}")

    solutions = []
    for p in unescaped:
        px, py = p["x"], p["y"]
        play = p.get("layer", 1)
        if play not in (1, 2):
            play = 1

        # Détection d'un via (< 40 mil) ou d'une pastille traversante THT layer 12 (< 65 mil) du même net pour mutualisation sans via doublon
        v_candidates = [
            v for v in env.vias if v.get("net") == target_net and math.hypot(v["x"] - px, v["y"] - py) < 40.0
        ] + [
            tp for tp in env.pads if tp.get("net") == target_net and tp.get("layer") == 12 and tp.get("id") != p["id"] and math.hypot(tp["x"] - px, tp["y"] - py) < 65.0
        ]
        v_candidates.sort(key=lambda v: math.hypot(v["x"] - px, v["y"] - py))
        shared_found = False
        for v_cand in v_candidates:
            if env.is_segment_clear(px, py, v_cand["x"], v_cand["y"], play, track_width_mil, clearance_mil, target_net=target_net):
                logger.info(f"  -> Pad {p['id']} mutualisé avec ancrage THT/via à ({v_cand['x']:.1f}, {v_cand['y']:.1f}) mil (micro-piste directe sans via doublon).")
                solutions.append({
                    "pad_id": p["id"],
                    "pad_pos": (px, py),
                    "pad_layer": play,
                    "via_pos": (v_cand["x"], v_cand["y"]),
                    "shared_via": True,
                    "distance_mil": math.hypot(v_cand["x"] - px, v_cand["y"] - py),
                    "margin_score_mil": 10.0
                })
                shared_found = True
                break

        if shared_found:
            continue

        sol = solve_pad_fanout(
            p, env,
            target_net=target_net,
            track_width_mil=track_width_mil,
            clearance_mil=clearance_mil,
            via_radius_mil=via_radius_mil
        )
        if sol:
            sol["shared_via"] = False
            solutions.append(sol)
            # Mise à jour incrémentale immédiate de l'environnement pour éviter tout doublon trou-à-trou
            env.vias.append({
                "x": sol["via_pos"][0],
                "y": sol["via_pos"][1],
                "diameter": via_radius_mil * 2.0,
                "net": target_net
            })
            env.lines.append({
                "x1": px, "y1": py,
                "x2": sol["via_pos"][0], "y2": sol["via_pos"][1],
                "layer": play,
                "width": track_width_mil,
                "net": target_net
            })
            logger.info(f"  -> Solution trouvée pour pad {sol['pad_id']} à ({sol['via_pos'][0]:.1f}, {sol['via_pos'][1]:.1f}) mil (marge: {sol['margin_score_mil']:.1f} mil)")
        else:
            # Fallback : liaison directe vers un via ou une pastille traversante (layer 12) du même net à proximité (< 75 mil)
            tht_or_vias = [
                v for v in env.vias if v.get("net") == target_net and math.hypot(v["x"] - px, v["y"] - py) < 75.0
            ] + [
                tp for tp in env.pads if tp.get("net") == target_net and tp.get("layer") == 12 and tp.get("id") != p["id"] and math.hypot(tp["x"] - px, tp["y"] - py) < 75.0
            ]
            tht_or_vias.sort(key=lambda item: math.hypot(item["x"] - px, item["y"] - py))
            fallback_connected = False
            for anchor in tht_or_vias:
                if env.is_segment_clear(px, py, anchor["x"], anchor["y"], play, track_width_mil, clearance_mil, target_net=target_net):
                    logger.info(f"  -> Pad {p['id']} raccordé par micro-piste directe à l'ancrage THT/via ({anchor['x']:.1f}, {anchor['y']:.1f}) mil.")
                    solutions.append({
                        "pad_id": p["id"],
                        "pad_pos": (px, py),
                        "pad_layer": play,
                        "via_pos": (anchor["x"], anchor["y"]),
                        "shared_via": True,
                        "distance_mil": math.hypot(anchor["x"] - px, anchor["y"] - py),
                        "margin_score_mil": 8.0
                    })
                    env.lines.append({
                        "x1": px, "y1": py,
                        "x2": anchor["x"], "y2": anchor["y"],
                        "layer": play,
                        "width": track_width_mil,
                        "net": target_net
                    })
                    fallback_connected = True
                    break
            if not fallback_connected:
                logger.warning(f"  -> Aucun spot de via valide pour pad {p['id']} à ({p['x']:.1f}, {p['y']:.1f}) mil.")

    if apply and solutions:
        logger.info(f"Injection de {len(solutions)} vias et pistes d'échappement dans EasyEDA Pro...")
        js_apply = """
        const sols = %s;
        const net = %s;
        const drill = %s;
        const dia = %s;
        const width = %s;

        for (const s of sols) {
            const vx = s.via_pos[0];
            const vy = s.via_pos[1];
            const px = s.pad_pos[0];
            const py = s.pad_pos[1];
            const lay = (s.pad_layer === 1 || s.pad_layer === 2) ? s.pad_layer : 1;

            if (!s.shared_via) {
                await eda.pcb_PrimitiveVia.create(net, vx, vy, drill, dia);
            }
            await eda.pcb_PrimitiveLine.create(net, lay, px, py, vx, vy, width);
        }

        const pours = await eda.pcb_PrimitivePour.getAll();
        for (const p of pours) {
            await p.rebuildCopperRegion();
        }

        return { injected: sols.length };
        """ % (
            json.dumps(solutions),
            json.dumps(target_net),
            via_drill_mil,
            via_dia_mil,
            track_width_mil
        )
        req = urllib.request.Request(
            f"http://localhost:{port}/execute",
            data=json.dumps({"code": js_apply}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=60.0) as resp:
            apply_res = json.loads(resp.read().decode("utf-8"))
        logger.info(f"Résultat injection : {apply_res.get('result')}")

    return {
        "total_target_pads": len(target_pads),
        "unescaped_count": len(unescaped),
        "solved_count": len(solutions),
        "solutions": solutions
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[fanout_stitcher] %(message)s")
    parser = argparse.ArgumentParser(description="Solveur Fanout & Vias d'échappement EasyEDA Pro")
    parser.add_argument("--net", type=str, required=True, help="Nom du réseau cible à échapper (ex: GND, 0V)")
    parser.add_argument("--clearance-mm", type=float, default=0.23, help="Isolement minimal en mm (défaut: 0.23 mm / 9.0 mil)")
    parser.add_argument("--track-width-mm", type=float, default=0.30, help="Largeur de piste en mm (défaut: 0.30 mm / 12 mil)")
    parser.add_argument("--via-drill-mm", type=float, default=0.30, help="Perçage de via en mm (défaut: 0.30 mm / 12 mil)")
    parser.add_argument("--via-diameter-mm", type=float, default=0.60, help="Diamètre de via en mm (défaut: 0.60 mm / 24 mil)")
    parser.add_argument("--port", type=int, default=49620, help="Port du pont EasyEDA Pro")
    parser.add_argument("--only-disconnected", action="store_true", help="Ne traite que les pastilles avec erreur de connexion DRC")
    parser.add_argument("--apply", action="store_true", help="Applique les modifications dans EasyEDA Pro")
    args = parser.parse_args()

    res = run_fanout_stitcher(
        target_net=args.net,
        clearance_mm=args.clearance_mm,
        track_width_mm=args.track_width_mm,
        via_drill_mm=args.via_drill_mm,
        via_diameter_mm=args.via_diameter_mm,
        port=args.port,
        only_disconnected=args.only_disconnected,
        apply=args.apply
    )
    sys.exit(0 if res["solved_count"] == res["unescaped_count"] else 1)
