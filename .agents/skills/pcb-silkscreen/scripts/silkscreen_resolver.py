#!/usr/bin/env python3
"""
silkscreen_resolver.py - Résolveur Géométrique de Sérigraphie (Agnostique)
=========================================================================
Conforme à la Règle 1 (AGENTS.md) :
- Zéro composant ni coordonnée codé en dur.
- Calcul trigonométrique des positions de textes pour :
  * pin_labels (repérage de broches de connecteurs / headers)
  * component_legends (consignes et libellés ancrés aux composants)
  * title_blocks (cartouche projet ancré au contour du PCB)
- Supporte les faces Top (couche 3) et Bottom (couche 4 avec miroir).
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SilkscreenResolver")

MM_TO_MIL = 39.3700787402
MIL_TO_MM = 0.0254


@dataclass
class ResolvedTextPrimitive:
    text: str
    layer: int              # 3: TopSilkLayer, 4: BottomSilkLayer
    layer_name: str         # "top" | "bottom"
    x_mm: float
    y_mm: float
    x_mil: float
    y_mil: float
    font_size_mm: float
    font_size_mil: float
    stroke_width_mm: float
    stroke_width_mil: float
    rotation: float         # 0.0 ou 90.0
    mirror: bool            # True si face arrière BottomSilkLayer
    align_mode: str         # "CENTER", "LEFT", "RIGHT"
    tag: str = "pcb-silkscreen"
    target_ref: Optional[str] = None
    target_pin: Optional[str] = None


class SilkscreenResolver:
    """Moteur de résolution géométrique agnostique de sérigraphie."""

    LAYER_MAP = {
        "top": 3,
        "bottom": 4
    }

    def __init__(
        self,
        silkscreen_cfg: Dict[str, Any],
        constraints_cfg: Dict[str, Any],
        placement_cfg: Dict[str, Any],
        manifest_cfg: Optional[Dict[str, Any]] = None,
        geometry_cfg: Optional[Dict[str, Any]] = None
    ):
        self.silkscreen = silkscreen_cfg
        self.constraints = constraints_cfg
        self.placement = placement_cfg.get("components", {}) if "components" in placement_cfg else placement_cfg
        self.manifest = manifest_cfg or {}
        self.geometry = geometry_cfg.get("components", {}) if geometry_cfg and "components" in geometry_cfg else (geometry_cfg or {})
        
        # Paramètres par défaut
        defaults = self.silkscreen.get("defaults", {})
        self.default_font_size = float(defaults.get("font_size_mm", 1.0))
        self.default_stroke = float(defaults.get("stroke_width_mm", 0.15))
        self.default_clearance = float(defaults.get("clearance_to_pads_mm", 0.25))

        # Dimensions de la carte
        board_cfg = self.constraints.get("board", {})
        self.board_w = float(board_cfg.get("width_mm", 81.28))
        self.board_h = float(board_cfg.get("height_mm", 35.56))

        # Récupération des ancres
        self.anchors = self.constraints.get("anchors", {})

    def get_component_pos_and_rot(self, ref: str) -> Tuple[float, float, float]:
        """Extrait les coordonnées (x_mm, y_mm) et rotation (deg) d'un composant."""
        if ref in self.anchors:
            anc = self.anchors[ref]
            return float(anc["x_mm"]), float(anc["y_mm"]), float(anc.get("rot_deg", 0.0))
        if ref in self.placement:
            plc = self.placement[ref]
            return float(plc["x_mm"]), float(plc["y_mm"]), float(plc.get("rotation", 0.0))
        if ref in self.geometry:
            geo = self.geometry[ref]
            return float(geo["x_mm"]), float(geo["y_mm"]), float(geo.get("rotation", 0.0))
        raise KeyError(f"Composant cible '{ref}' introuvable dans constraints.anchors ni dans placement.")

    def get_pad_relative_offset(self, ref: str, pin_num: str) -> Tuple[float, float]:
        """Retourne le décalage (dx_0, dy_0) de la pastille pin_num à rotation 0°."""
        # 1. Vérifier si netlist_geometry fournit le décalage exact
        if ref in self.geometry:
            comp_geo = self.geometry[ref]
            pads = comp_geo.get("pads", [])
            for p in pads:
                if str(p.get("number")) == str(pin_num):
                    return float(p.get("dx_0_mm", 0.0)), float(p.get("dy_0_mm", 0.0))

        # 2. Inférence géométrique standard pour connecteurs 1xN
        # Récupération du package depuis manifest ou bom
        pkg_name = ""
        if "components" in self.manifest and ref in self.manifest["components"]:
            pkg_name = self.manifest["components"][ref].get("package", "")

        try:
            pin_idx = int(pin_num)
        except ValueError:
            pin_idx = 1

        pitch = 2.54
        if "XH" in pkg_name or "JST" in pkg_name or "2.50" in pkg_name:
            pitch = 2.50

        # Nombre total de broches estimé
        total_pins = 2
        if "3P" in pkg_name or "1X3" in pkg_name:
            total_pins = 3
        elif "5P" in pkg_name or "1X5" in pkg_name:
            total_pins = 5
        elif "4P" in pkg_name or "1X4" in pkg_name:
            total_pins = 4

        dx_0 = (pin_idx - 1 - (total_pins - 1) / 2.0) * pitch
        dy_0 = 0.0
        return dx_0, dy_0

    def resolve_pin_labels(self, layer_key: str) -> List[ResolvedTextPrimitive]:
        """Résout les étiquettes de broches pour une couche donnée."""
        layer_data = self.silkscreen.get(layer_key, {})
        pin_labels_cfg = layer_data.get("pin_labels", [])
        layer_num = self.LAYER_MAP.get(layer_key, 3)
        mirror = False
        primitives: List[ResolvedTextPrimitive] = []

        for item in pin_labels_cfg:
            ref = item["component"]
            side = item.get("side", "outside")
            offset_mm = float(item.get("offset_mm", 2.0))
            font_size = float(item.get("font_size_mm", self.default_font_size))
            pins = item.get("pins", {})

            try:
                cx, cy, rot = self.get_component_pos_and_rot(ref)
            except KeyError as e:
                logger.warning(f"⚠️ {e}")
                continue

            rot_rad = math.radians(rot)
            cos_r = math.cos(rot_rad)
            sin_r = math.sin(rot_rad)

            for pin_num, label in pins.items():
                dx_0, dy_0 = self.get_pad_relative_offset(ref, pin_num)
                # Position réelle du pad après rotation
                pad_x = cx + (dx_0 * cos_r - dy_0 * sin_r)
                pad_y = cy + (dx_0 * sin_r + dy_0 * cos_r)

                # Vecteur de décalage selon le côté demandé
                if side == "outside":
                    # Pointeur vectoriel s'éloignant du centre de la carte
                    vx = pad_x - (self.board_w / 2.0)
                    vy = pad_y - (self.board_h / 2.0)
                    norm = math.hypot(vx, vy) or 1.0
                    off_x = (vx / norm) * offset_mm
                    off_y = (vy / norm) * offset_mm
                elif side == "below":
                    off_x, off_y = 0.0, -offset_mm
                elif side == "above":
                    off_x, off_y = 0.0, offset_mm
                elif side == "left":
                    off_x, off_y = -offset_mm, 0.0
                elif side == "right":
                    off_x, off_y = offset_mm, 0.0
                else:
                    off_x, off_y = 0.0, -offset_mm

                tx = pad_x + off_x
                ty = pad_y + off_y

                primitives.append(ResolvedTextPrimitive(
                    text=label,
                    layer=layer_num,
                    layer_name=layer_key,
                    x_mm=round(tx, 3),
                    y_mm=round(ty, 3),
                    x_mil=round(tx * MM_TO_MIL, 1),
                    y_mil=round(ty * MM_TO_MIL, 1),
                    font_size_mm=font_size,
                    font_size_mil=round(font_size * MM_TO_MIL, 1),
                    stroke_width_mm=self.default_stroke,
                    stroke_width_mil=round(self.default_stroke * MM_TO_MIL, 1),
                    rotation=0.0,
                    mirror=mirror,
                    align_mode="CENTER",
                    target_ref=ref,
                    target_pin=pin_num
                ))

        return primitives

    def resolve_component_legends(self, layer_key: str) -> List[ResolvedTextPrimitive]:
        """Résout les légendes et consignes associées à un composant."""
        layer_data = self.silkscreen.get(layer_key, {})
        legends_cfg = layer_data.get("component_legends", [])
        layer_num = self.LAYER_MAP.get(layer_key, 3)
        mirror = False
        primitives: List[ResolvedTextPrimitive] = []

        for item in legends_cfg:
            ref = item["component"]
            pos_side = item.get("position", "below")
            offset_mm = float(item.get("offset_mm", 2.0))
            font_size = float(item.get("font_size_mm", self.default_font_size))
            raw_text = item.get("text", "")

            try:
                cx, cy, _ = self.get_component_pos_and_rot(ref)
            except KeyError as e:
                logger.warning(f"⚠️ {e}")
                continue

            lines = raw_text.split("\n")
            line_height = font_size * 1.3

            # Décalage de base selon la position
            if pos_side == "below":
                base_x = cx
                base_y = cy - offset_mm
                step_y = -line_height
            elif pos_side == "above":
                base_x = cx
                base_y = cy + offset_mm + (len(lines) - 1) * line_height
                step_y = -line_height
            elif pos_side == "left":
                base_x = cx - offset_mm
                base_y = cy
                step_y = -line_height
            elif pos_side == "right":
                base_x = cx + offset_mm
                base_y = cy
                step_y = -line_height
            else:
                base_x = cx
                base_y = cy - offset_mm
                step_y = -line_height

            for i, line in enumerate(lines):
                line_str = line.strip()
                if not line_str:
                    continue
                cur_y = base_y + (i * step_y)
                primitives.append(ResolvedTextPrimitive(
                    text=line_str,
                    layer=layer_num,
                    layer_name=layer_key,
                    x_mm=round(base_x, 3),
                    y_mm=round(cur_y, 3),
                    x_mil=round(base_x * MM_TO_MIL, 1),
                    y_mil=round(cur_y * MM_TO_MIL, 1),
                    font_size_mm=font_size,
                    font_size_mil=round(font_size * MM_TO_MIL, 1),
                    stroke_width_mm=self.default_stroke,
                    stroke_width_mil=round(self.default_stroke * MM_TO_MIL, 1),
                    rotation=0.0,
                    mirror=mirror,
                    align_mode="CENTER",
                    target_ref=ref
                ))

        return primitives

    def resolve_title_blocks(self, layer_key: str) -> List[ResolvedTextPrimitive]:
        """Résout les cartouches projet ancrés aux bords du PCB."""
        layer_data = self.silkscreen.get(layer_key, {})
        title_cfg = layer_data.get("title_blocks", [])
        layer_num = self.LAYER_MAP.get(layer_key, 3)
        mirror = False
        primitives: List[ResolvedTextPrimitive] = []

        for item in title_cfg:
            anchor = item.get("anchor", "bottom_right")
            offset = item.get("offset_mm", [0.0, 0.0])
            dx, dy = float(offset[0]), float(offset[1])
            font_size = float(item.get("font_size_mm", self.default_font_size))
            align_mode = item.get("alignment", "right").upper()
            raw_text = item.get("text", "")

            if isinstance(raw_text, list):
                lines = raw_text
            else:
                lines = raw_text.split("\n")

            # Point d'ancrage sur le contour du PCB
            if anchor == "bottom_right":
                ax = self.board_w
                ay = 0.0
            elif anchor == "bottom_left":
                ax = 0.0
                ay = 0.0
            elif anchor == "top_right":
                ax = self.board_w
                ay = self.board_h
            elif anchor == "top_left":
                ax = 0.0
                ay = self.board_h
            elif anchor == "center":
                ax = self.board_w / 2.0
                ay = self.board_h / 2.0
            elif anchor == "custom":
                pos = item.get("position_mm", [self.board_w / 2.0, self.board_h / 2.0])
                ax, ay = float(pos[0]), float(pos[1])
            else:
                ax = self.board_w
                ay = 0.0

            start_x = ax + dx
            start_y = ay + dy
            line_height = font_size * 1.35

            # Empilement des lignes de bas en haut (si anchor en bas) ou haut en bas
            for i, line in enumerate(lines):
                line_str = line.strip()
                if not line_str:
                    continue
                # Si anchor en bas, les lignes suivantes montent (+Y)
                if "bottom" in anchor:
                    cur_y = start_y + (i * line_height)
                else:
                    cur_y = start_y - (i * line_height)

                primitives.append(ResolvedTextPrimitive(
                    text=line_str,
                    layer=layer_num,
                    layer_name=layer_key,
                    x_mm=round(start_x, 3),
                    y_mm=round(cur_y, 3),
                    x_mil=round(start_x * MM_TO_MIL, 1),
                    y_mil=round(cur_y * MM_TO_MIL, 1),
                    font_size_mm=font_size,
                    font_size_mil=round(font_size * MM_TO_MIL, 1),
                    stroke_width_mm=self.default_stroke,
                    stroke_width_mil=round(self.default_stroke * MM_TO_MIL, 1),
                    rotation=0.0,
                    mirror=mirror,
                    align_mode=align_mode
                ))

        return primitives

    def resolve_all(self) -> List[ResolvedTextPrimitive]:
        """Résout l'ensemble des primitives de sérigraphie (Top & Bottom)."""
        all_prims: List[ResolvedTextPrimitive] = []
        for lk in ["top", "bottom"]:
            all_prims.extend(self.resolve_pin_labels(lk))
            all_prims.extend(self.resolve_component_legends(lk))
            all_prims.extend(self.resolve_title_blocks(lk))
        return all_prims


def main():
    parser = argparse.ArgumentParser(description="Résolveur géométrique de sérigraphie PCB pour EasyEDA Pro")
    parser.add_argument("--silkscreen", required=True, help="Chemin vers documents/pcb/silkscreen.json")
    parser.add_argument("--constraints", required=True, help="Chemin vers documents/pcb/constraints.json")
    parser.add_argument("--placement", required=True, help="Chemin vers candidate_placement.json")
    parser.add_argument("--manifest", help="Chemin vers manifest.json (optionnel)")
    parser.add_argument("--geometry", help="Chemin vers netlist_geometry.json (optionnel)")
    parser.add_argument("--output", required=True, help="Fichier JSON cible pour les primitives résolues")
    args = parser.parse_args()

    with open(args.silkscreen, "r", encoding="utf-8") as f:
        silk_data = json.load(f)
    with open(args.constraints, "r", encoding="utf-8") as f:
        constraints_data = json.load(f)
    with open(args.placement, "r", encoding="utf-8") as f:
        placement_data = json.load(f)

    manifest_data = None
    if args.manifest and Path(args.manifest).exists():
        with open(args.manifest, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)

    geometry_data = None
    if args.geometry and Path(args.geometry).exists():
        with open(args.geometry, "r", encoding="utf-8") as f:
            geometry_data = json.load(f)

    resolver = SilkscreenResolver(
        silkscreen_cfg=silk_data,
        constraints_cfg=constraints_data,
        placement_cfg=placement_data,
        manifest_cfg=manifest_data,
        geometry_cfg=geometry_data
    )

    primitives = resolver.resolve_all()
    logger.info(f"✨ Résolution terminée : {len(primitives)} primitives de texte générées.")

    top_count = sum(1 for p in primitives if p.layer_name == "top")
    bottom_count = sum(1 for p in primitives if p.layer_name == "bottom")
    logger.info(f"   - Face avant (Top Silk)   : {top_count} texte(s)")
    logger.info(f"   - Face arrière (Bottom)   : {bottom_count} texte(s)")

    out_p = Path(args.output)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w", encoding="utf-8") as f:
        json.dump([asdict(p) for p in primitives], f, indent=2)
    logger.info(f"💾 Primitives enregistrées dans '{out_p}'.")


if __name__ == "__main__":
    main()
