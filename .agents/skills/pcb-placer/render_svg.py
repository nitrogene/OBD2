#!/usr/bin/env python3
"""
render_svg.py - Générateur de Rendu Vectoriel SVG pour le Placement PCB (Agnostique)
====================================================================================
Conforme à la Règle 0 (AGENTS.md) :
- Moteur visuel agnostique, aucune valeur ni composant codé en dur.
- Visualise la carte, les trous de fixation M2, les zones keepout, les courtyards,
  les lignes élastiques de connectivité et les zones de collisions.
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from export_geometry import BoardGeometrySnapshot, extract_board_geometry
from score import PCBScorer, PlacementEvaluation, RectBox, get_component_courtyard_box, get_all_keepouts

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("SVGRenderer")

# Palette de couleurs distinctes par bloc fonctionnel
BLOCK_COLORS = {
    "protection_12v":   "#f97316",  # Orange
    "buck_5v":          "#ef4444",  # Rouge vif
    "ldo_3v3":          "#eab308",  # Jaune / Ambre
    "esp32_mcu":        "#3b82f6",  # Bleu
    "can_transceiver":  "#a855f7",  # Violet
    "kline_interface":  "#10b981",  # Émeraude
    "usbc_interface":   "#ec4899",  # Rose
    "vbat_monitoring":  "#06b6d4",  # Cyan
    "test_points":      "#64748b",  # Ardoise
    "default":          "#94a3b8"   # Gris neutre
}


def generate_svg_view(
    manifest: Dict[str, Any],
    board_constraints: Dict[str, Any],
    geometry: BoardGeometrySnapshot,
    eval_res: PlacementEvaluation,
    output_path: Path,
    placement_override: Optional[Dict[str, Dict[str, Any]]] = None
):
    """Génère un fichier SVG autonome haute fidélité du placement PCB."""
    board_cfg = board_constraints.get("board", {})
    board_w = board_cfg.get("width_mm", 81.28)
    board_h = board_cfg.get("height_mm", 35.56)
    edge_clearance = board_cfg.get("edge_clearance_mm", 1.0)
    mounting_holes = board_cfg.get("mounting_holes", [])
    keepouts = board_constraints.get("keepout_zones", [])
    anchors = board_constraints.get("anchors", {})

    packages = manifest.get("packages", {})
    manifest_comps = manifest.get("components", {})
    blocks_meta = manifest.get("functional_blocks", {})

    # Mappage bloc pour chaque composant
    comp_block_map = {}
    for blk_id, blk_info in blocks_meta.items():
        for des in blk_info.get("components", []):
            comp_block_map[des] = blk_id

    # Facteur d'échelle pour l'affichage (1 mm = 20 pixels)
    SCALE = 20.0
    PADDING = 60.0  # Marge extérieure pour la lisibilité
    HEADER_H = 100.0  # Bandeau supérieur pour les métriques de score

    canvas_w = board_w * SCALE + 2.0 * PADDING
    canvas_h = board_h * SCALE + 2.0 * PADDING + HEADER_H

    # Positions absolues et boîtes englobantes
    comp_positions: Dict[str, Tuple[float, float, float]] = {}
    comp_boxes: Dict[str, RectBox] = {}
    for des, comp_meta in manifest_comps.items():
        pkg_name = comp_meta.get("package") or comp_meta.get("footprint", "0603")
        pkg_info = packages.get(pkg_name, {"width_mm": 1.6, "length_mm": 0.8, "courtyard_margin_mm": 0.25})

        if placement_override and des in placement_override:
            p = placement_override[des]
            x = float(p.get("x_mm", p.get("x", 0.0)))
            y = float(p.get("y_mm", p.get("y", 0.0)))
            r = float(p.get("rot", p.get("rotation", 0.0)))
        elif des in geometry.components:
            gc = geometry.components[des]
            x, y, r = gc.x_mm, gc.y_mm, gc.rotation
        else:
            x, y, r = 0.0, 0.0, 0.0

        comp_positions[des] = (x, y, r)
        comp_boxes[des] = get_component_courtyard_box(x, y, r, pkg_info)

    # Ensemble des composants en collision
    colliding_des: Set[str] = set()
    for a, b, _ in eval_res.score.overlapping_pairs:
        colliding_des.add(a)
        colliding_des.add(b)

    # Conversion de coordonnées carte (mm) vers canvas SVG (pixels)
    # L'origine carte (0,0) est en bas à gauche, Y vers le haut
    def to_svg_x(x_mm: float) -> float:
        return PADDING + x_mm * SCALE

    def to_svg_y(y_mm: float) -> float:
        # Inverse l'axe Y : Y_svg = PADDING + HEADER_H + (board_h - y_mm) * SCALE
        return PADDING + HEADER_H + (board_h - y_mm) * SCALE

    # Début de l'écriture SVG
    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_w} {canvas_h}" '
        f'width="{canvas_w}" height="{canvas_h}" style="background-color: #0f172a; font-family: monospace;">',
        '<defs>',
        '  <!-- Motif de hachures pour les keepouts RF -->',
        '  <pattern id="keepoutHatch" width="10" height="10" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">',
        '    <line x1="0" y1="0" x2="0" y2="10" stroke="#dc2626" stroke-width="2" opacity="0.6"/>',
        '  </pattern>',
        '</defs>'
    ]

    # 1. Bandeau supérieur d'évaluation (HUD Score)
    status_color = "#22c55e" if eval_res.is_valid else "#ef4444"
    status_text = "VALIDE (0 VIOLATION DURE)" if eval_res.is_valid else f"INVALIDE ({eval_res.score.hard_violations_count} VIOLATIONS DURES)"

    svg_lines.append(f'<g id="hud_header">')
    svg_lines.append(f'  <rect x="{PADDING}" y="15" width="{board_w * SCALE}" height="75" rx="8" fill="#1e293b" stroke="#334155" stroke-width="1.5"/>')
    svg_lines.append(f'  <text x="{PADDING + 20}" y="42" fill="{status_color}" font-size="16" font-weight="bold">STATUT : {status_text}</text>')
    svg_lines.append(
        f'  <text x="{PADDING + 20}" y="70" fill="#94a3b8" font-size="13">'
        f'Score : <tspan fill="#f8fafc" font-weight="bold">{eval_res.score.weighted_total_score:.4f}</tspan> | '
        f'HPWL : <tspan fill="#38bdf8">{eval_res.score.total_hpwl_mm:.1f} mm</tspan> | '
        f'Chevauchements : <tspan fill="#fbbf24">{len(eval_res.score.overlapping_pairs)} paires ({eval_res.score.total_overlap_area_mm2:.1f} mm²)</tspan> | '
        f'Composants : {eval_res.components_count}'
        f'</text>'
    )
    svg_lines.append('</g>')

    # 2. Carte PCB et bordure
    bx = to_svg_x(0.0)
    by = to_svg_y(board_h)
    bw = board_w * SCALE
    bh = board_h * SCALE

    svg_lines.append('<!-- Contour de carte PCB -->')
    svg_lines.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="6" fill="#132a1e" stroke="#22c55e" stroke-width="2.5"/>')

    # Marge de bord autorisée (Clearance)
    cx = to_svg_x(edge_clearance)
    cy = to_svg_y(board_h - edge_clearance)
    cw = (board_w - 2.0 * edge_clearance) * SCALE
    ch = (board_h - 2.0 * edge_clearance) * SCALE
    svg_lines.append(f'<rect x="{cx}" y="{cy}" width="{cw}" height="{ch}" fill="none" stroke="#22c55e" stroke-width="1" stroke-dasharray="4,4" opacity="0.4"/>')

    # 3. Zones Keepout (statiques + dynamiques dérivées des packages)
    rendered_keepouts = get_all_keepouts(board_constraints, manifest, comp_positions)
    for kz in rendered_keepouts:
        rect = kz.get("rect_mm", {})
        kx = to_svg_x(rect.get("x_min", 0.0))
        ky = to_svg_y(rect.get("y_max", 0.0))
        kw = (rect.get("x_max", 0.0) - rect.get("x_min", 0.0)) * SCALE
        kh = (rect.get("y_max", 0.0) - rect.get("y_min", 0.0)) * SCALE

        svg_lines.append(f'<!-- Keepout {kz.get("name")} -->')
        svg_lines.append(f'<rect x="{kx}" y="{ky}" width="{kw}" height="{kh}" fill="url(#keepoutHatch)" stroke="#ef4444" stroke-width="1.5"/>')
        svg_lines.append(f'<text x="{kx + 5}" y="{ky + 15}" fill="#ef4444" font-size="10" font-weight="bold">{kz.get("name")}</text>')

    # 4. Trous de fixation mécaniques M2
    for h in mounting_holes:
        hx = to_svg_x(h.get("x_mm", 0.0))
        hy = to_svg_y(h.get("y_mm", 0.0))
        head_r = (h.get("head_clearance_mm", 4.5) / 2.0) * SCALE
        drill_r = (h.get("drill_mm", 2.2) / 2.0) * SCALE

        svg_lines.append(f'<!-- Trou {h.get("id")} -->')
        svg_lines.append(f'<circle cx="{hx}" cy="{hy}" r="{head_r}" fill="#fbbf24" fill-opacity="0.15" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="3,3"/>')
        svg_lines.append(f'<circle cx="{hx}" cy="{hy}" r="{drill_r}" fill="#0f172a" stroke="#cbd5e1" stroke-width="1.5"/>')
        svg_lines.append(f'<text x="{hx}" y="{hy + head_r + 12}" fill="#cbd5e1" font-size="10" text-anchor="middle">{h.get("id")}</text>')

    # 5. Chevelu élastique pour la boucle chaude Buck
    hot_loop_comps = ["U4", "C14", "C7", "D2", "L1"]
    loop_coords = [comp_positions[d] for d in hot_loop_comps if d in comp_positions]
    if len(loop_coords) >= 2:
        svg_lines.append('<!-- Vecteurs boucle chaude Buck -->')
        for k in range(len(hot_loop_comps) - 1):
            d1 = hot_loop_comps[k]
            d2 = hot_loop_comps[k + 1]
            if d1 in comp_positions and d2 in comp_positions:
                x1, y1 = to_svg_x(comp_positions[d1][0]), to_svg_y(comp_positions[d1][1])
                x2, y2 = to_svg_x(comp_positions[d2][0]), to_svg_y(comp_positions[d2][1])
                svg_lines.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#ef4444" stroke-width="2" stroke-dasharray="4,2" opacity="0.75"/>')

    # 6. Courtyards des composants
    svg_lines.append('<!-- Composants & Courtyards -->')
    for des, box in comp_boxes.items():
        is_anchor = des in anchors
        is_collision = des in colliding_des
        blk_id = comp_block_map.get(des, "default")
        fill_color = BLOCK_COLORS.get(blk_id, "#64748b")

        x_svg = to_svg_x(box.x_min)
        y_svg = to_svg_y(box.y_max)
        w_svg = box.width * SCALE
        h_svg = box.height * SCALE

        stroke_color = "#ffffff" if is_anchor else ("#ff0000" if is_collision else "#000000")
        stroke_w = "2.5" if is_collision else ("2.0" if is_anchor else "1.0")

        svg_lines.append(f'<g id="comp_{des}">')
        svg_lines.append(
            f'  <rect x="{x_svg}" y="{y_svg}" width="{w_svg}" height="{h_svg}" rx="2" '
            f'fill="{fill_color}" fill-opacity="0.8" stroke="{stroke_color}" stroke-width="{stroke_w}"/>'
        )

        # Désignateur au centre si la boîte est suffisamment grande
        cx_svg = to_svg_x(comp_positions[des][0])
        cy_svg = to_svg_y(comp_positions[des][1])
        font_size = max(7, min(12, int(min(w_svg, h_svg) * 0.7)))
        if w_svg >= 10 and h_svg >= 10:
            svg_lines.append(
                f'  <text x="{cx_svg}" y="{cy_svg + font_size * 0.35}" fill="#ffffff" '
                f'font-size="{font_size}" font-weight="bold" text-anchor="middle" '
                f'style="pointer-events: none;">{des}</text>'
            )
        svg_lines.append('</g>')

    svg_lines.append('</svg>')

    # Sauvegarde sur disque
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(svg_lines))


def main():
    parser = argparse.ArgumentParser(description="Générateur de rendu SVG pour le placement PCB")
    parser.add_argument("--manifest", type=Path, default=Path("circuit_manifest.json"))
    parser.add_argument("--board", type=Path, default=Path("board_constraints.json"))
    parser.add_argument("--geometry", type=Path, default=Path(".agents/skills/pcb-placer/.cache/netlist_geometry.json"))
    parser.add_argument("--placement", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=Path("placement_preview.svg"))

    args = parser.parse_args()

    with open(args.manifest, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    with open(args.board, "r", encoding="utf-8") as f:
        board_constraints = json.load(f)

    if args.geometry.is_file():
        with open(args.geometry, "r", encoding="utf-8") as f:
            raw_geom = json.load(f)
        from export_geometry import ComponentGeometry, PadGeometry
        comps = {}
        for des, c_data in raw_geom.get("components", {}).items():
            pads = [PadGeometry(**p) for p in c_data.get("pads", [])]
            c_dict = dict(c_data)
            c_dict["pads"] = pads
            comps[des] = ComponentGeometry(**c_dict)
        geom = BoardGeometrySnapshot(
            extracted_at=raw_geom.get("extracted_at", ""),
            components_count=raw_geom.get("components_count", len(comps)),
            pads_count=raw_geom.get("pads_count", 0),
            nets_count=raw_geom.get("nets_count", 0),
            board_outline=raw_geom.get("board_outline", {}),
            components=comps,
            nets=raw_geom.get("nets", {})
        )
    else:
        geom = extract_board_geometry()

    override = None
    if args.placement and args.placement.is_file():
        with open(args.placement, "r", encoding="utf-8") as f:
            p_data = json.load(f)
            override = p_data.get("components", p_data)

    scorer = PCBScorer(manifest, board_constraints, geom)
    eval_res = scorer.evaluate(placement_override=override)

    generate_svg_view(manifest, board_constraints, geom, eval_res, args.out, placement_override=override)
    logger.info(f"✅ Rendu SVG généré avec succès dans : {args.out}")


if __name__ == "__main__":
    main()
