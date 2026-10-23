#!/usr/bin/env python3
"""
Moteur géométrique agnostique de détection de collision et de calcul de dégagement
==================================================================================
Skill: pcb-stitcher
Règle 0: Aucune référence en dur à un composant, net ou géométrie de projet.
Fournit des primitives de calcul 2D/3D (distances continues segment-obstacle,
dégagements circulaires/rectangulaires, keepouts et limites du circuit).
"""

import math
from typing import Dict, List, Tuple, Any, Optional

# Facteurs de conversion
MIL_TO_MM = 0.0254
MM_TO_MIL = 39.37007874


def dist_point_to_segment(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    """Distance euclidienne minimale entre un point (px, py) et un segment fini [(x1,y1), (x2,y2)]."""
    dx = x2 - x1
    dy = y2 - y1
    l2 = dx * dx + dy * dy
    if l2 == 0.0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def dist_segment_to_segment(
    p1x: float, p1y: float, p2x: float, p2y: float,
    q1x: float, q1y: float, q2x: float, q2y: float
) -> float:
    """Distance minimale exacte entre deux segments 2D finis."""
    def ccw(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> bool:
        return (cy - ay) * (bx - ax) > (by - ay) * (cx - ax)

    # Intersection test
    intersect = (ccw(p1x, p1y, q1x, q1y, q2x, q2y) != ccw(p2x, p2y, q1x, q1y, q2x, q2y)) and \
                (ccw(p1x, p1y, p2x, p2y, q1x, q1y) != ccw(p1x, p1y, p2x, p2y, q2x, q2y))
    if intersect:
        return 0.0

    return min(
        dist_point_to_segment(p1x, p1y, q1x, q1y, q2x, q2y),
        dist_point_to_segment(p2x, p2y, q1x, q1y, q2x, q2y),
        dist_point_to_segment(q1x, q1y, p1x, p1y, p2x, p2y),
        dist_point_to_segment(q2x, q2y, p1x, p1y, p2x, p2y),
    )


class ObstacleEnvironment:
    """Environnement d'obstacles extrait du layout PCB pour les calculs de collision."""

    def __init__(
        self,
        lines: List[Dict[str, Any]],
        vias: List[Dict[str, Any]],
        pads: List[Dict[str, Any]],
        keepouts: Optional[List[Dict[str, Any]]] = None,
        board_bounds: Optional[Tuple[float, float, float, float]] = None,
        boundary_margin_mil: float = 45.0,
    ):
        self.lines = lines
        self.vias = vias
        self.pads = pads
        self.keepouts = keepouts or []
        if board_bounds is not None:
            self.board_bounds = board_bounds
        elif pads or vias:
            all_x = [p.get("x", 0.0) for p in pads] + [v.get("x", 0.0) for v in vias]
            all_y = [p.get("y", 0.0) for p in pads] + [v.get("y", 0.0) for v in vias]
            self.board_bounds = (min(all_x), max(all_x), min(all_y), max(all_y))
        else:
            self.board_bounds = (0.0, 0.0, 0.0, 0.0)
        self.boundary_margin_mil = boundary_margin_mil

    def is_in_bounds(self, px: float, py: float) -> bool:
        min_x, max_x, min_y, max_y = self.board_bounds
        m = self.boundary_margin_mil
        if px < min_x + m or px > max_x - m or py < min_y + m or py > max_y - m:
            return False
        for k in self.keepouts:
            kx1, kx2, ky1, ky2 = k["x1"], k["x2"], k["y1"], k["y2"]
            if kx1 <= px <= kx2 and ky1 <= py <= ky2:
                return False
        return True

    def is_segment_clear(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        layer: int,
        track_width: float,
        clearance_margin: float,
        target_net: str,
    ) -> bool:
        """Vérifie le dégagement continu d'un segment de piste face à tous les obstacles."""
        if not self.is_in_bounds(x1, y1) or not self.is_in_bounds(x2, y2):
            return False

        half_w = track_width / 2.0
        seg_min_x = min(x1, x2)
        seg_max_x = max(x1, x2)
        seg_min_y = min(y1, y2)
        seg_max_y = max(y1, y2)

        # 1. Pistes de couches identiques appartenant à d'autres nets
        for l in self.lines:
            if l.get("net") == target_net or l.get("layer") != layer:
                continue
            req = half_w + l.get("width", 10.0) / 2.0 + clearance_margin
            l_min_x = min(l["x1"], l["x2"]) - req
            l_max_x = max(l["x1"], l["x2"]) + req
            if l_max_x < seg_min_x or l_min_x > seg_max_x:
                continue
            l_min_y = min(l["y1"], l["y2"]) - req
            l_max_y = max(l["y1"], l["y2"]) + req
            if l_max_y < seg_min_y or l_min_y > seg_max_y:
                continue
            d = dist_segment_to_segment(x1, y1, x2, y2, l["x1"], l["y1"], l["x2"], l["y2"])
            if d < req:
                return False

        # 2. Vias (traversants multi-couches)
        for v in self.vias:
            if v.get("net") == target_net:
                continue
            req = half_w + v.get("diameter", 24.0) / 2.0 + clearance_margin
            if v["x"] + req < seg_min_x or v["x"] - req > seg_max_x:
                continue
            if v["y"] + req < seg_min_y or v["y"] - req > seg_max_y:
                continue
            d = dist_point_to_segment(v["x"], v["y"], x1, y1, x2, y2)
            if d < req:
                return False

        # 3. Pastilles (Pads)
        for p in self.pads:
            if p.get("net") == target_net:
                continue
            p_lay = p.get("layer", 1)
            if p_lay != 12 and p_lay != layer:
                continue
            pad_r = math.hypot(p.get("width", 40.0) / 2.0, p.get("height", 40.0) / 2.0)
            req = half_w + pad_r + clearance_margin
            if p["x"] + req < seg_min_x or p["x"] - req > seg_max_x:
                continue
            if p["y"] + req < seg_min_y or p["y"] - req > seg_max_y:
                continue
            d = dist_point_to_segment(p["x"], p["y"], x1, y1, x2, y2)
            if d < req:
                return False

        return True

    def is_via_clear(
        self,
        px: float,
        py: float,
        via_radius: float,
        clearance_margin: float,
        target_net: str,
    ) -> bool:
        """Vérifie le dégagement d'un via traversant sur toutes les couches conductrices."""
        if not self.is_in_bounds(px, py):
            return False

        # Pistes sur n'importe quelle couche conductrice
        for l in self.lines:
            if l.get("net") == target_net:
                continue
            req = via_radius + l.get("width", 10.0) / 2.0 + clearance_margin
            if min(l["x1"], l["x2"]) - req > px or max(l["x1"], l["x2"]) + req < px:
                continue
            if min(l["y1"], l["y2"]) - req > py or max(l["y1"], l["y2"]) + req < py:
                continue
            d = dist_point_to_segment(px, py, l["x1"], l["y1"], l["x2"], l["y2"])
            if d < req:
                return False

        # Vias existants
        for v in self.vias:
            d = math.hypot(px - v["x"], py - v["y"])
            if v.get("net") == target_net:
                # Règle trou-à-trou (Hole-to-Hole) minimale même sur le même réseau : >= 0.50 mm (20 mil)
                if d < 20.0:
                    return False
                continue
            req = via_radius + v.get("diameter", 24.0) / 2.0 + clearance_margin
            if abs(px - v["x"]) > req or abs(py - v["y"]) > req:
                continue
            if d < req:
                return False

        # Pastilles
        for p in self.pads:
            if p.get("net") == target_net:
                continue
            pad_r = math.hypot(p.get("width", 40.0) / 2.0, p.get("height", 40.0) / 2.0)
            req = via_radius + pad_r + clearance_margin + 4.0  # Marge de garde stricte pour DRC = 0
            if abs(px - p["x"]) > req or abs(py - p["y"]) > req:
                continue
            d = math.hypot(px - p["x"], py - p["y"])
            if d < req:
                return False

        return True
