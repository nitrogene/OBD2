#!/usr/bin/env python3
"""
Routeur Labyrinthe A* Multi-Couches pour Pontage d'Îlots Isolés
==============================================================
Skill: pcb-stitcher
Règle 0: Ce script est purement agnostique.
Il identifie les îlots déconnectés d'un plan de référence (via DRC ou analyse de graphe),
calcule des trajectoires A* 3D (Layer 1, Layer 2, transitions de vias) garantissant
un dégagement continu strict face à tous les obstacles, et injecte les passerelles.
"""

import sys
import json
import math
import heapq
import logging
import argparse
import urllib.request
from typing import Dict, List, Tuple, Any, Optional

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

logger = logging.getLogger("pcb_stitcher.island_bridger")


def fetch_layout_and_drc(port: int = 49620, target_net: str = "GND") -> Dict[str, Any]:
    """Récupère les primitives du PCB et les éléments non connectés du net cible via DRC."""
    js_code = """
    const lines = await eda.pcb_PrimitiveLine.getAll();
    const vias = await eda.pcb_PrimitiveVia.getAll();
    const pads = await eda.pcb_PrimitivePad.getAll();

    const groups = await eda.pcb_Drc.check(true, false, true);
    const drcDisconnected = [];
    if (groups && groups[0] && groups[0].list && groups[0].list[0] && groups[0].list[0].list) {
        for (const item of groups[0].list[0].list) {
            const primId = (item.objs && item.objs[0]) || (item.explanation?.errData?.obj1);
            const net = item.explanation?.errData?.net || '';
            drcDisconnected.push({
                id: primId,
                net: net,
                suffix: item.obj1 ? item.obj1.suffix : '',
                type: item.errorObjType,
                x: item.pos ? (item.pos.x * 10) : 0,
                y: item.pos ? (item.pos.y * 10) : 0
            });
        }
    }

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
        pads: pads.map(p => ({
            id: p.getState_PrimitiveId(),
            net: p.getState_Net(),
            layer: p.getState_Layer(),
            x: p.getState_X(),
            y: p.getState_Y(),
            width: p.getState_Width ? p.getState_Width() : 40,
            height: p.getState_Height ? p.getState_Height() : 40
        })),
        drcDisconnected
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


def route_2layer_astar(
    start_pt: Tuple[float, float],
    goal_pt: Tuple[float, float],
    env: ObstacleEnvironment,
    start_lay: Optional[int] = 2,
    goal_lay: Optional[int] = 2,
    target_net: str = "GND",
    track_width_mil: float = 12.0,
    clearance_mil: float = 9.0,
    via_radius_mil: float = 12.0,
    grid_step_mil: float = 5.0,
    search_margin_mil: float = 100.0,
    max_iterations: int = 20000
) -> Optional[List[Tuple[float, float, int]]]:
    """Recherche un chemin A* sans collision en 2 couches avec transitions de vias."""
    sx, sy = start_pt
    gx, gy = goal_pt

    min_x = math.floor((min(sx, gx) - search_margin_mil) / grid_step_mil) * grid_step_mil
    max_x = math.ceil((max(sx, gx) + search_margin_mil) / grid_step_mil) * grid_step_mil
    min_y = math.floor((min(sy, gy) - search_margin_mil) / grid_step_mil) * grid_step_mil
    max_y = math.ceil((max(sy, gy) + search_margin_mil) / grid_step_mil) * grid_step_mil

    gx_grid = round(gx / grid_step_mil) * grid_step_mil
    gy_grid = round(gy / grid_step_mil) * grid_step_mil

    open_set = []
    came_from = {}
    g_score = {}

    start_layers = [start_lay] if start_lay is not None else [1, 2]
    for slay in start_layers:
        snode = (round(sx / grid_step_mil) * grid_step_mil, round(sy / grid_step_mil) * grid_step_mil, slay)
        g_score[snode] = 0.0
        h_init = math.hypot(snode[0] - gx_grid, snode[1] - gy_grid)
        heapq.heappush(open_set, (h_init, snode))

    moves_2d = [
        (grid_step_mil, 0, grid_step_mil),
        (-grid_step_mil, 0, grid_step_mil),
        (0, grid_step_mil, grid_step_mil),
        (0, -grid_step_mil, grid_step_mil),
        (grid_step_mil, grid_step_mil, grid_step_mil * 1.414),
        (grid_step_mil, -grid_step_mil, grid_step_mil * 1.414),
        (-grid_step_mil, grid_step_mil, grid_step_mil * 1.414),
        (-grid_step_mil, -grid_step_mil, grid_step_mil * 1.414)
    ]

    iterations = 0
    while open_set:
        iterations += 1
        if iterations > max_iterations:
            return None

        f, current = heapq.heappop(open_set)
        cx, cy, clay = current

        # But atteint si à proximité immédiate du nœud objectif
        if math.hypot(cx - gx_grid, cy - gy_grid) < grid_step_mil * 1.2 and (goal_lay is None or clay == goal_lay):
            path = [(goal_pt[0], goal_pt[1], clay)]
            node = current
            while node in came_from:
                path.append(node)
                node = came_from[node]
            first_lay = path[-1][2]
            path.append((start_pt[0], start_pt[1], first_lay))
            path.reverse()
            return path

        # 1. Déplacement sur la couche courante
        for dx, dy, cost in moves_2d:
            nx = round((cx + dx) * 10) / 10.0
            ny = round((cy + dy) * 10) / 10.0
            if nx < min_x or nx > max_x or ny < min_y or ny > max_y:
                continue

            # Contrôle de dégagement continu du segment
            if not env.is_segment_clear(
                cx, cy, nx, ny, clay,
                track_width=track_width_mil,
                clearance_margin=clearance_mil,
                target_net=target_net
            ):
                continue

            neighbor = (nx, ny, clay)
            tentative_g = g_score[current] + cost
            if tentative_g < g_score.get(neighbor, 1e9):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                h = math.hypot(nx - gx_grid, ny - gy_grid) + (0.0 if (goal_lay is None or clay == goal_lay) else 40.0)
                heapq.heappush(open_set, (tentative_g + h, neighbor))

        # 2. Transition de couche par via
        other_lay = 2 if clay == 1 else 1
        neighbor = (cx, cy, other_lay)
        via_cost = 45.0
        tentative_g = g_score[current] + via_cost
        if tentative_g < g_score.get(neighbor, 1e9):
            if env.is_via_clear(cx, cy, via_radius=via_radius_mil, clearance_margin=clearance_mil, target_net=target_net):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                h = math.hypot(cx - gx_grid, cy - gy_grid) + (0.0 if (goal_lay is None or other_lay == goal_lay) else 40.0)
                heapq.heappush(open_set, (tentative_g + h, neighbor))

    return None


def simplify_path(path: List[Tuple[float, float, int]]) -> Tuple[List[Tuple[float, float]], List[Dict[str, Any]]]:
    """Convertit un chemin de grille en vias de transition et segments de pistes colinéaires."""
    if not path or len(path) < 2:
        return [], []

    vias_to_create = []
    lines_to_create = []

    curr_line = [path[0]]
    for i in range(1, len(path)):
        prev = path[i-1]
        curr = path[i]
        if prev[2] != curr[2]:
            vias_to_create.append((curr[0], curr[1]))
            if len(curr_line) > 1:
                lines_to_create.append(curr_line)
            curr_line = [curr]
        else:
            curr_line.append(curr)
    if len(curr_line) > 1:
        lines_to_create.append(curr_line)

    simplified_lines = []
    for l_pts in lines_to_create:
        lay = l_pts[0][2]
        pts_2d = [(p[0], p[1]) for p in l_pts]
        sim = [pts_2d[0]]
        for j in range(1, len(pts_2d) - 1):
            p0 = sim[-1]
            p1 = pts_2d[j]
            p2 = pts_2d[j + 1]
            a1 = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
            a2 = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
            if abs(a1 - a2) > 0.05:
                sim.append(p1)
        sim.append(pts_2d[-1])
        for k in range(len(sim) - 1):
            simplified_lines.append({
                "layer": lay,
                "x1": sim[k][0], "y1": sim[k][1],
                "x2": sim[k + 1][0], "y2": sim[k + 1][1]
            })

    return vias_to_create, simplified_lines


def run_island_bridger(
    target_net: str = "GND",
    clearance_mm: float = 0.23,
    track_width_mm: float = 0.30,
    via_drill_mm: float = 0.30,
    via_diameter_mm: float = 0.60,
    grid_step_mil: float = 5.0,
    port: int = 49620,
    apply: bool = False
) -> Dict[str, Any]:
    """Identifie les îlots déconnectés du net cible et trace les passerelles multi-couches."""
    clearance_mil = clearance_mm * MM_TO_MIL
    track_width_mil = track_width_mm * MM_TO_MIL
    via_drill_mil = via_drill_mm * MM_TO_MIL
    via_dia_mil = via_diameter_mm * MM_TO_MIL
    via_radius_mil = via_dia_mil / 2.0

    logger.info(f"Audit DRC & topologie pour le net '{target_net}'...")
    data = fetch_layout_and_drc(port=port, target_net=target_net)
    lines = data["lines"]
    vias = data["vias"]
    pads = data["pads"]
    drc_items = [d for d in data["drcDisconnected"] if d.get("net") == target_net or target_net in d.get("suffix", "")]

    logger.info(f"Total violations DRC de connexion pour '{target_net}' : {len(drc_items)}")
    if not drc_items:
        logger.info(f"Aucun îlot isolé détecté pour le net '{target_net}'. Continuite parfaite !")
        return {"routes_found": 0, "status": "all_connected"}

    env = ObstacleEnvironment(lines=lines, vias=vias, pads=pads)

    env = ObstacleEnvironment(lines=lines, vias=vias, pads=pads)

    # 1. Construction du graphe de connexions pour le net cible
    drc_ids = {d["id"] for d in drc_items}
    nodes = {}
    for p in pads:
        if p.get("net") == target_net:
            nodes[p["id"]] = {"type": "pad", "x": p["x"], "y": p["y"], "lay": p.get("layer", 1), "is_drc": p["id"] in drc_ids}
    for v in vias:
        if v.get("net") == target_net:
            nodes[v["id"]] = {"type": "via", "x": v["x"], "y": v["y"], "lay": 12, "is_drc": v["id"] in drc_ids}

    adj = {nid: set() for nid in nodes}
    for l in lines:
        if l.get("net") != target_net:
            continue
        lx1, ly1, lx2, ly2 = l["x1"], l["y1"], l["x2"], l["y2"]
        m1 = [nid for nid, n in nodes.items() if math.hypot(n["x"] - lx1, n["y"] - ly1) < 3.0]
        m2 = [nid for nid, n in nodes.items() if math.hypot(n["x"] - lx2, n["y"] - ly2) < 3.0]
        for n1 in m1:
            for n2 in m2:
                if n1 != n2:
                    adj[n1].add(n2)
                    adj[n2].add(n1)

    # 2. Décomposition en composantes connexes
    visited = set()
    components = []
    for nid in nodes:
        if nid not in visited:
            comp = []
            q = [nid]
            visited.add(nid)
            while q:
                curr = q.pop(0)
                comp.append(curr)
                for neigh in adj[curr]:
                    if neigh not in visited:
                        visited.add(neigh)
                        q.append(neigh)
            components.append(comp)

    # 3. Séparation entre îlots isolés (avec DRC) et composantes saines (sans DRC)
    drc_islands = []
    clean_nodes = []
    for comp in components:
        if any(nodes[nid]["is_drc"] for nid in comp):
            drc_islands.append(comp)
        else:
            clean_nodes.extend([nid for nid in comp if nodes[nid]["type"] == "via"])

    # Trier les îlots par distance minimale croissante vers les vias sains (Principe de l'arbre couvrant minimal / Prim)
    drc_islands.sort(key=lambda isl: min(
        math.hypot(nodes[nid]["x"] - nodes[cid]["x"], nodes[nid]["y"] - nodes[cid]["y"])
        for nid in isl for cid in clean_nodes
    ))

    logger.info(f"Topologie du net '{target_net}' : {len(components)} composantes au total.")
    logger.info(f"  - Îlots isolés nécessitant raccordement : {len(drc_islands)}")
    logger.info(f"  - Vias de référence connectés (composantes saines) : {len(clean_nodes)}")

    if not clean_nodes:
        raise RuntimeError("Aucun via de référence sain identifié sur le PCB !")

    all_vias_to_inject = []
    all_lines_to_inject = []
    routes_computed = 0

    # 4. Raccordement de chaque îlot isolé vers la composante saine la plus proche
    for idx, island in enumerate(drc_islands):
        island_node_objs = [nodes[nid] for nid in island]
        logger.info(f"\n--- Traitement Îlot {idx+1}/{len(drc_islands)} ({len(island)} nœuds) ---")

        # Préférer les vias comme nœuds sources si l'îlot en possède
        vias_in_island = [n for n in island_node_objs if n["type"] == "via"]
        src_nodes = vias_in_island if vias_in_island else island_node_objs

        # Collecter toutes les paires triées par distance avec cibles distinctes
        raw_pairs = []
        for inod in src_nodes:
            for cid in clean_nodes:
                cnod = nodes[cid]
                dist = math.hypot(inod["x"] - cnod["x"], inod["y"] - cnod["y"])
                raw_pairs.append((dist, inod, cnod))
        raw_pairs.sort(key=lambda x: x[0])

        seen_dst = set()
        candidate_pairs = []
        for dist, src, dst in raw_pairs:
            dst_key = (dst["x"], dst["y"])
            if dst_key not in seen_dst:
                seen_dst.add(dst_key)
                candidate_pairs.append((dist, src, dst))
                if len(candidate_pairs) >= 8:
                    break

        route_found = False
        # Tester jusqu'aux 8 cibles distinctes les plus proches
        for dist, src, dst in candidate_pairs:
            logger.info(f"Routage A* : ({src['x']:.1f}, {src['y']:.1f}) [{src['type']}] -> ({dst['x']:.1f}, {dst['y']:.1f}) [via sain] (dist: {dist:.1f} mil)...")

            start_lay = src["lay"] if src["type"] != "via" else None
            goal_lay = dst["lay"] if dst["type"] != "via" else None

            path = route_2layer_astar(
                (src["x"], src["y"]), (dst["x"], dst["y"]),
                env=env,
                start_lay=start_lay,
                goal_lay=goal_lay,
                target_net=target_net,
                track_width_mil=track_width_mil,
                clearance_mil=clearance_mil,
                via_radius_mil=via_radius_mil,
                grid_step_mil=grid_step_mil,
                search_margin_mil=120.0,
                max_iterations=25000
            )

            if path:
                r_vias, r_lines = simplify_path(path)
                logger.info(f"  -> Passerelle validée ! ({len(r_vias)} vias, {len(r_lines)} segments)")
                all_vias_to_inject.extend(r_vias)
                all_lines_to_inject.extend(r_lines)
                routes_computed += 1
                route_found = True
                # L'îlot est désormais virtuellement connecté : ses vias deviennent des cibles valides
                for nid in island:
                    if nodes[nid]["type"] == "via":
                        clean_nodes.append(nid)
                break
            else:
                logger.info(f"  ... cible bloquée, essai de la cible suivante...")

        if not route_found:
            logger.warning(f"  -> Aucune passerelle trouvée pour l'îlot {idx+1} parmi les cibles testées !")

    if apply and (all_vias_to_inject or all_lines_to_inject):
        logger.info(f"Injection de {len(all_vias_to_inject)} vias et {len(all_lines_to_inject)} pistes dans EasyEDA Pro...")
        js_apply = """
        const vias = %s;
        const lines = %s;
        const net = %s;
        const drill = %s;
        const dia = %s;
        const width = %s;

        for (const v of vias) {
            await eda.pcb_PrimitiveVia.create(net, v[0], v[1], drill, dia);
        }

        for (const l of lines) {
            await eda.pcb_PrimitiveLine.create(net, l.layer, l.x1, l.y1, l.x2, l.y2, width);
        }

        const pours = await eda.pcb_PrimitivePour.getAll();
        for (const p of pours) {
            await p.rebuildCopperRegion();
        }

        const drc = await eda.pcb_Drc.check(true, false, true);
        return {
            viasAdded: vias.length,
            linesAdded: lines.length,
            drcResult: drc ? (drc[0]?.list?.length || 0) : 0
        };
        """ % (
            json.dumps(all_vias_to_inject),
            json.dumps(all_lines_to_inject),
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
        with urllib.request.urlopen(req, timeout=90.0) as resp:
            apply_res = json.loads(resp.read().decode("utf-8"))
        logger.info(f"Résultat injection passerelles : {apply_res.get('result')}")

    return {
        "routes_found": routes_computed,
        "vias_count": len(all_vias_to_inject),
        "lines_count": len(all_lines_to_inject),
        "vias": all_vias_to_inject,
        "lines": all_lines_to_inject
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[island_bridger] %(message)s")
    parser = argparse.ArgumentParser(description="Routeur de passerelles d'îlots isolés EasyEDA Pro")
    parser.add_argument("--net", type=str, default="GND", help="Nom du net cible (défaut: GND)")
    parser.add_argument("--clearance-mm", type=float, default=0.23, help="Isolement minimal en mm (défaut: 0.23 mm / 9.0 mil)")
    parser.add_argument("--track-width-mm", type=float, default=0.30, help="Largeur de piste en mm (défaut: 0.30 mm / 12 mil)")
    parser.add_argument("--via-drill-mm", type=float, default=0.30, help="Perçage de via en mm (défaut: 0.30 mm / 12 mil)")
    parser.add_argument("--via-diameter-mm", type=float, default=0.60, help="Diamètre de via en mm (défaut: 0.60 mm / 24 mil)")
    parser.add_argument("--grid-step-mil", type=float, default=5.0, help="Pas de la grille A* en mil (défaut: 5.0 mil)")
    parser.add_argument("--port", type=int, default=49620, help="Port du pont EasyEDA Pro")
    parser.add_argument("--apply", action="store_true", help="Applique les passerelles dans EasyEDA Pro")
    args = parser.parse_args()

    res = run_island_bridger(
        target_net=args.net,
        clearance_mm=args.clearance_mm,
        track_width_mm=args.track_width_mm,
        via_drill_mm=args.via_drill_mm,
        via_diameter_mm=args.via_diameter_mm,
        grid_step_mil=args.grid_step_mil,
        port=args.port,
        apply=args.apply
    )
    sys.exit(0 if res["routes_found"] > 0 or res.get("status") == "all_connected" else 1)
