#!/usr/bin/env python3
"""
score.py - Évaluateur Indépendant de Score de Placement PCB & CEM (Agnostique)
==============================================================================
Conforme à la Règle 0 (AGENTS.md) :
- Aucune référence en dur à des composants, broches ou valeurs spécifiques du projet.
- Manipulation d'abstractions (composants, courtyards, pastilles, nets, contraintes).
- Totalement découplé des algorithmes d'optimisation (solveurs).
- Unité interne normalisée : millimètre (mm).

Rôles :
1. Calcul des contraintes dures (Hard Constraints) :
   - Hors-carte (avec edge_clearance)
   - Chevauchements physiques de courtyards (NoOverlap2D)
   - Intrusions en zones interdites (Keepouts, avec gestion des exemptions)
   - Collisions avec les têtes de vis de fixation (Mounting Holes)
   - Respect strict des ancres mécaniques verrouillées
   - Contraintes CEM de proximité marquées "hard: true"
2. Calcul des objectifs mous normalisés (Soft Objectives) :
   - f_wire : Longueur totale estimée du chevelu (HPWL) normalisée par le demi-périmètre de carte
   - f_prox : Proximité CEM pad-à-pad (découplage HF, protection TVS/ESD)
   - f_loop : Compacité des boucles à fort di/dt (Buck hot loop)
   - f_net  : Compacité des nœuds rayonnants haute fréquence (PH_BUCK)
   - f_sep  : Isolation spatiale agresseurs (Buck) vs victimes (Antenne RF, bus différentiels)
   - f_edge : Accessibilité bord de carte (connecteurs, boutons, cavaliers)
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from export_geometry import BoardGeometrySnapshot, extract_board_geometry

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("PCBScorer")


@dataclass
class RectBox:
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    @property
    def width(self) -> float:
        return max(0.0, self.x_max - self.x_min)

    @property
    def height(self) -> float:
        return max(0.0, self.y_max - self.y_min)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x_min + self.x_max) / 2.0, (self.y_min + self.y_max) / 2.0)

    def intersects(self, other: RectBox) -> bool:
        return not (
            self.x_max <= other.x_min or
            self.x_min >= other.x_max or
            self.y_max <= other.y_min or
            self.y_min >= other.y_max
        )

    def intersection_area(self, other: RectBox) -> float:
        dx = max(0.0, min(self.x_max, other.x_max) - max(self.x_min, other.x_min))
        dy = max(0.0, min(self.y_max, other.y_max) - max(self.y_min, other.y_min))
        return dx * dy


@dataclass
class HardViolation:
    violation_type: str  # "out_of_board", "overlap", "keepout", "mounting_hole", "anchor", "proximity"
    subject: str
    target: Optional[str] = None
    details: str = ""
    amount: float = 0.0  # surface en mm² ou distance en mm


@dataclass
class ScoreMetrics:
    # Contraintes Dures
    hard_violations_count: int = 0
    total_overlap_area_mm2: float = 0.0
    overlapping_pairs: List[Tuple[str, str, float]] = field(default_factory=list)

    # Objectifs Mous Normalisés
    f_wire_hpwl: float = 0.0
    total_hpwl_mm: float = 0.0
    
    f_proximity_cem: float = 0.0
    f_loops_compactness: float = 0.0
    f_switching_nets: float = 0.0
    f_separation_emc: float = 0.0
    f_edge_access: float = 0.0

    # Score Global Normalisé
    weighted_total_score: float = 0.0

    # Bilan détaillé des contraintes
    constraint_details: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class PlacementEvaluation:
    is_valid: bool
    score: ScoreMetrics
    hard_violations: List[HardViolation]
    components_count: int
    evaluated_at: str


def rotate_offset(dx0: float, dy0: float, angle_deg: float) -> Tuple[float, float]:
    """Applique une rotation anti-horaire au vecteur (dx0, dy0)."""
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    return (dx0 * cos_a - dy0 * sin_a, dx0 * sin_a + dy0 * cos_a)


def get_component_courtyard_box(
    x_mm: float,
    y_mm: float,
    rot_deg: float,
    pkg_info: Dict[str, Any]
) -> RectBox:
    """Calcule la boîte englobante du courtyard IPC d'un composant orienté."""
    w0 = pkg_info.get("width_mm", 1.0)
    l0 = pkg_info.get("length_mm", 1.0)
    margin = pkg_info.get("courtyard_margin_mm", 0.25)

    w_court = w0 + 2.0 * margin
    h_court = l0 + 2.0 * margin

    # À 90° et 270°, la largeur et la hauteur sont permutées
    norm_rot = int(round(rot_deg)) % 360
    if norm_rot in (90, 270):
        w_court, h_court = h_court, w_court

    half_w = w_court / 2.0
    half_h = h_court / 2.0

    return RectBox(
        x_min=x_mm - half_w,
        x_max=x_mm + half_w,
        y_min=y_mm - half_h,
        y_max=y_mm + half_h
    )


def get_all_keepouts(
    board_constraints: Dict[str, Any],
    manifest: Dict[str, Any],
    comp_positions: Dict[str, Tuple[float, float, float]]
) -> List[Dict[str, Any]]:
    """
    Rassemble les keepouts statiques de carte et les zones d'antennes dérivées
    dynamiquement des boîtiers de composants (ex: module ESP32).
    """
    all_keepouts: List[Dict[str, Any]] = list(board_constraints.get("keepout_zones", []))

    board_w = board_constraints.get("board", {}).get("width_mm", 81.28)
    board_h = board_constraints.get("board", {}).get("height_mm", 35.56)
    packages = manifest.get("packages", {})
    manifest_comps = manifest.get("components", {})

    for des, pos in comp_positions.items():
        meta = manifest_comps.get(des, {})
        pkg_name = meta.get("package") or meta.get("footprint")
        pkg_info = packages.get(pkg_name, {})

        ak = pkg_info.get("antenna_keepout")
        if not ak:
            continue

        cx, cy, rot_deg = pos
        dx_min = float(ak.get("dx_min_mm", -9.0))
        dx_max = float(ak.get("dx_max_mm", 9.0))
        dy_min = float(ak.get("dy_min_mm", 6.45))
        dy_max = float(ak.get("dy_max_mm", 12.75))

        corners = [
            (dx_min, dy_min),
            (dx_max, dy_min),
            (dx_max, dy_max),
            (dx_min, dy_max)
        ]

        rot_corners = []
        for dx, dy in corners:
            rx, ry = rotate_offset(dx, dy, rot_deg)
            rot_corners.append((cx + rx, cy + ry))

        x_min = min(c[0] for c in rot_corners)
        x_max = max(c[0] for c in rot_corners)
        y_min = min(c[1] for c in rot_corners)
        y_max = max(c[1] for c in rot_corners)

        if ak.get("extend_to_board_edge", True):
            dir_x, dir_y = rotate_offset(0.0, 1.0, rot_deg)
            if dir_x > 0.5:
                x_max = board_w
            elif dir_x < -0.5:
                x_min = 0.0
            elif dir_y > 0.5:
                y_max = board_h
            elif dir_y < -0.5:
                y_min = 0.0

        all_keepouts.append({
            "name": ak.get("name", f"KEEPOUT_{des}"),
            "rect_mm": {
                "x_min": round(x_min, 3),
                "x_max": round(x_max, 3),
                "y_min": round(y_min, 3),
                "y_max": round(y_max, 3)
            },
            "exempt_refs": [des],
            "description": ak.get("description", f"Zone d'exclusion d'antenne pour {des}")
        })

    return all_keepouts


class PCBScorer:
    """Évaluateur agnostique de placement PCB."""

    def __init__(
        self,
        manifest: Dict[str, Any],
        board_constraints: Dict[str, Any],
        geometry: BoardGeometrySnapshot
    ):
        self.manifest = manifest
        self.board = board_constraints
        self.geom = geometry

        self.packages = manifest.get("packages", {})
        self.manifest_comps = manifest.get("components", {})
        self.rigid_groups = manifest.get("rigid_groups", [])
        self.placement_constraints = manifest.get("placement_constraints", [])

        self.board_width = board_constraints.get("board", {}).get("width_mm", 81.28)
        self.board_height = board_constraints.get("board", {}).get("height_mm", 35.56)
        self.edge_clearance = board_constraints.get("board", {}).get("edge_clearance_mm", 1.0)
        self.mounting_holes = board_constraints.get("board", {}).get("mounting_holes", [])
        self.anchors = board_constraints.get("anchors", {})
        self.keepouts = board_constraints.get("keepout_zones", [])
        self.separation_rules = board_constraints.get("separation_rules", [])

        # Échelle de référence pour normaliser le câblage : demi-périmètre de carte
        self.half_perimeter = self.board_width + self.board_height

    def evaluate(
        self,
        placement_override: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> PlacementEvaluation:
        """
        Évalue un placement physique (soit celui actuellement dans geometry, soit un override).
        Format de placement_override : { des: {"x_mm": ..., "y_mm": ..., "rot": ..., "side": ...} }
        """
        hard_violations: List[HardViolation] = []
        metrics = ScoreMetrics()

        # 1. Résolution des positions et boîtes d'encombrement de tous les composants
        comp_positions: Dict[str, Tuple[float, float, float]] = {}  # des -> (x_mm, y_mm, rot)
        comp_boxes: Dict[str, RectBox] = {}
        comp_pads_abs: Dict[str, Dict[str, Tuple[float, float]]] = {}  # des -> { pin_num: (px, py) }

        for des, comp_meta in self.manifest_comps.items():
            pkg_name = comp_meta.get("package") or comp_meta.get("footprint", "0603")
            pkg_info = self.packages.get(pkg_name, {"width_mm": 1.6, "length_mm": 0.8, "courtyard_margin_mm": 0.25})

            # Récupération de la position (override ou geometry)
            if placement_override and des in placement_override:
                pos = placement_override[des]
                x_mm = float(pos.get("x_mm", pos.get("x", 0.0)))
                y_mm = float(pos.get("y_mm", pos.get("y", 0.0)))
                rot = float(pos.get("rot", pos.get("rotation", 0.0)))
            elif des in self.geom.components:
                g_comp = self.geom.components[des]
                x_mm = g_comp.x_mm
                y_mm = g_comp.y_mm
                rot = g_comp.rotation
            else:
                x_mm, y_mm, rot = 0.0, 0.0, 0.0

            comp_positions[des] = (x_mm, y_mm, rot)
            box = get_component_courtyard_box(x_mm, y_mm, rot, pkg_info)
            comp_boxes[des] = box

            # Calcul des positions absolues des broches
            pads_map: Dict[str, Tuple[float, float]] = {}
            if des in self.geom.components:
                for p in self.geom.components[des].pads:
                    dx, dy = rotate_offset(p.dx_0_mm, p.dy_0_mm, rot)
                    pads_map[p.number] = (round(x_mm + dx, 4), round(y_mm + dy, 4))
            comp_pads_abs[des] = pads_map

        # =====================================================================
        # 2. Vérification des Contraintes Dures (Hard Constraints)
        # =====================================================================

        # A. Limites de carte (Hors-carte)
        min_x = self.edge_clearance
        max_x = self.board_width - self.edge_clearance
        min_y = self.edge_clearance
        max_y = self.board_height - self.edge_clearance

        for des, box in comp_boxes.items():
            # Tolérance d'ancres affleurantes
            is_anchor = des in self.anchors
            if is_anchor:
                # Les ancres ont le droit d'affleurer jusqu'au bord 0.0 (avec tolérance pour connecteurs de bord flush)
                anc_info = self.anchors.get(des, {})
                flush = anc_info.get("edge_flush")
                limit_x_min = -1.0 if flush == "west" else -0.1
                limit_x_max = self.board_width + 1.0 if flush == "east" else self.board_width + 0.1
                limit_y_min = -1.0 if flush == "south" else -0.1
                limit_y_max = self.board_height + 1.0 if flush == "north" else self.board_height + 0.1
                if box.x_min < limit_x_min or box.x_max > limit_x_max or box.y_min < limit_y_min or box.y_max > limit_y_max:
                    hard_violations.append(HardViolation(
                        violation_type="out_of_board",
                        subject=des,
                        details=f"Ancre {des} dépasse totalement de la carte",
                        amount=1.0
                    ))
            else:
                if box.x_min < min_x or box.x_max > max_x or box.y_min < min_y or box.y_max > max_y:
                    overflow = max(0.0, min_x - box.x_min, box.x_max - max_x, min_y - box.y_min, box.y_max - max_y)
                    hard_violations.append(HardViolation(
                        violation_type="out_of_board",
                        subject=des,
                        details=f"Composant {des} hors zone autorisée (dépassement {overflow:.2f} mm)",
                        amount=overflow
                    ))

        # B. Chevauchement physique des courtyards (NoOverlap2D)
        comp_keys = list(comp_boxes.keys())
        total_overlap_area = 0.0
        overlapping_pairs = []

        for i in range(len(comp_keys)):
            des_a = comp_keys[i]
            box_a = comp_boxes[des_a]
            for j in range(i + 1, len(comp_keys)):
                des_b = comp_keys[j]
                box_b = comp_boxes[des_b]

                if box_a.intersects(box_b):
                    area = box_a.intersection_area(box_b)
                    if area > 0.01:  # Ignorer les simples contacts de frontière (< 0.01 mm²)
                        total_overlap_area += area
                        overlapping_pairs.append((des_a, des_b, round(area, 3)))
                        hard_violations.append(HardViolation(
                            violation_type="overlap",
                            subject=des_a,
                            target=des_b,
                            details=f"Collision entre {des_a} et {des_b} (aire: {area:.2f} mm²)",
                            amount=area
                        ))

        metrics.total_overlap_area_mm2 = round(total_overlap_area, 3)
        metrics.overlapping_pairs = overlapping_pairs

        # C. Intrusions Keepouts (statiques + dynamiques dérivées des packages)
        all_keepouts = get_all_keepouts(self.board, self.manifest, comp_positions)
        for kz in all_keepouts:
            kname = kz.get("name", "KEEPOUT")
            rect = kz.get("rect_mm", {})
            kbox = RectBox(
                x_min=rect.get("x_min", 0.0),
                x_max=rect.get("x_max", 0.0),
                y_min=rect.get("y_min", 0.0),
                y_max=rect.get("y_max", 0.0)
            )
            exempt = set(kz.get("exempt_refs", []))

            for des, box in comp_boxes.items():
                if des in exempt:
                    continue
                if box.intersects(kbox):
                    area = box.intersection_area(kbox)
                    if area > 0.01:
                        hard_violations.append(HardViolation(
                            violation_type="keepout",
                            subject=des,
                            target=kname,
                            details=f"{des} empiète sur la zone keepout {kname} ({area:.2f} mm²)",
                            amount=area
                        ))

        # D. Trous de fixation mécaniques M2
        for h in self.mounting_holes:
            hid = h.get("id", "MH")
            hx = h.get("x_mm", 0.0)
            hy = h.get("y_mm", 0.0)
            head_radius = h.get("head_clearance_mm", 4.5) / 2.0

            for des, box in comp_boxes.items():
                # Distance du centre du trou au rectangle de courtyard
                cx, cy = comp_positions[des][0], comp_positions[des][1]
                dist_center = math.hypot(cx - hx, cy - hy)
                # Bounding box du trou
                hole_box = RectBox(hx - head_radius, hx + head_radius, hy - head_radius, hy + head_radius)
                if box.intersects(hole_box):
                    hard_violations.append(HardViolation(
                        violation_type="mounting_hole",
                        subject=des,
                        target=hid,
                        details=f"{des} interfère avec la tête de vis {hid} (distance centre: {dist_center:.2f} mm)",
                        amount=dist_center
                    ))

        # E. Ancres verrouillées
        for anchor_des, anchor_cfg in self.anchors.items():
            if not anchor_cfg.get("fixed", True):
                continue
            target_x = anchor_cfg.get("x_mm", 0.0)
            target_y = anchor_cfg.get("y_mm", 0.0)
            target_rot = anchor_cfg.get("rot_deg", 0.0)

            if anchor_des in comp_positions:
                cur_x, cur_y, cur_rot = comp_positions[anchor_des]
                dist = math.hypot(cur_x - target_x, cur_y - target_y)
                rot_diff = abs(cur_rot - target_rot) % 360
                if dist > 0.1 or (rot_diff > 1.0 and rot_diff < 359.0):
                    hard_violations.append(HardViolation(
                        violation_type="anchor",
                        subject=anchor_des,
                        details=f"Ancre {anchor_des} déplacée : ({cur_x:.2f}, {cur_y:.2f}) vs cible ({target_x:.2f}, {target_y:.2f}) mm",
                        amount=dist
                    ))

        # =====================================================================
        # 3. Calcul des Objectifs Mous Normalisés (Soft Objectives)
        # =====================================================================

        # A. Longueur totale de câblage HPWL (hors gros plans GND/Power)
        total_hpwl = 0.0
        power_ground_nets = {"GND", "+12V", "+5V", "3.3V"}

        for net_name, pins in self.geom.nets.items():
            if net_name in power_ground_nets or len(pins) < 2:
                continue

            pin_coords: List[Tuple[float, float]] = []
            for des, pin_num in pins:
                if des in comp_pads_abs and pin_num in comp_pads_abs[des]:
                    pin_coords.append(comp_pads_abs[des][pin_num])
                elif des in comp_positions:
                    pin_coords.append((comp_positions[des][0], comp_positions[des][1]))

            if len(pin_coords) >= 2:
                xs = [p[0] for p in pin_coords]
                ys = [p[1] for p in pin_coords]
                hpwl = (max(xs) - min(xs)) + (max(ys) - min(ys))
                total_hpwl += hpwl

        metrics.total_hpwl_mm = round(total_hpwl, 2)
        metrics.f_wire_hpwl = round(total_hpwl / self.half_perimeter, 4)

        # B. Proximité CEM pad-à-pad (depuis placement_constraints et cem_target)
        prox_penalty_sum = 0.0
        prox_weights_sum = 0.0

        for c in self.placement_constraints:
            cid = c.get("id", "PROX")
            ctype = c.get("type")
            is_hard = c.get("hard", False)
            weight = c.get("weight", 5)

            if ctype == "proximity":
                sub_ref = c.get("subject", {}).get("ref")
                sub_pin = c.get("subject", {}).get("pin")
                tgt_ref = c.get("target", {}).get("ref")
                tgt_pin = c.get("target", {}).get("pin")
                max_d = c.get("max_mm", 3.0)

                p1 = None
                p2 = None
                if sub_ref in comp_pads_abs and sub_pin in comp_pads_abs[sub_ref]:
                    p1 = comp_pads_abs[sub_ref][sub_pin]
                elif sub_ref in comp_positions:
                    p1 = (comp_positions[sub_ref][0], comp_positions[sub_ref][1])

                if tgt_ref in comp_pads_abs and tgt_pin in comp_pads_abs[tgt_ref]:
                    p2 = comp_pads_abs[tgt_ref][tgt_pin]
                elif tgt_ref in comp_positions:
                    p2 = (comp_positions[tgt_ref][0], comp_positions[tgt_ref][1])

                if p1 and p2:
                    dist = math.hypot(p1[0] - p2[0], p1[1] - p2[1])
                    if dist > max_d:
                        penalty = (dist - max_d) / max_d
                        prox_penalty_sum += weight * penalty
                        if is_hard:
                            hard_violations.append(HardViolation(
                                violation_type="proximity",
                                subject=sub_ref,
                                target=tgt_ref,
                                details=f"Règle dure {cid} violée : distance {dist:.2f} mm > max {max_d:.2f} mm",
                                amount=dist - max_d
                            ))
                    metrics.constraint_details.append({
                        "id": cid,
                        "type": "proximity",
                        "dist_mm": round(dist, 2),
                        "max_mm": max_d,
                        "ok": dist <= max_d
                    })
                prox_weights_sum += weight

            elif ctype == "loop":
                # Compacité de boucle di/dt
                members = c.get("members", [])
                target_max = c.get("target_max_mm", 25.0)
                loop_points: List[Tuple[float, float]] = []

                for m in members:
                    mref = m.get("ref")
                    mpin = m.get("pin")
                    if mref in comp_pads_abs and mpin in comp_pads_abs[mref]:
                        loop_points.append(comp_pads_abs[mref][mpin])
                    elif mref in comp_positions:
                        loop_points.append((comp_positions[mref][0], comp_positions[mref][1]))

                if loop_points:
                    l_xs = [pt[0] for pt in loop_points]
                    l_ys = [pt[1] for pt in loop_points]
                    loop_hpwl = (max(l_xs) - min(l_xs)) + (max(l_ys) - min(l_ys))
                    metrics.f_loops_compactness = round(loop_hpwl / target_max, 4)
                    metrics.constraint_details.append({
                        "id": cid,
                        "type": "loop",
                        "loop_hpwl_mm": round(loop_hpwl, 2),
                        "target_max_mm": target_max,
                        "ok": loop_hpwl <= target_max
                    })

            elif ctype == "net_compact":
                # Compacité d'un nœud rayonnant (ex: PH_BUCK)
                net_name = c.get("net")
                target_max = c.get("target_max_mm", 12.0)
                if net_name in self.geom.nets:
                    pins = self.geom.nets[net_name]
                    n_pts = []
                    for d, p in pins:
                        if d in comp_pads_abs and p in comp_pads_abs[d]:
                            n_pts.append(comp_pads_abs[d][p])
                    if n_pts:
                        xs = [pt[0] for pt in n_pts]
                        ys = [pt[1] for pt in n_pts]
                        net_hpwl = (max(xs) - min(xs)) + (max(ys) - min(ys))
                        metrics.f_switching_nets = round(net_hpwl / target_max, 4)
                        metrics.constraint_details.append({
                            "id": cid,
                            "type": "net_compact",
                            "net": net_name,
                            "net_hpwl_mm": round(net_hpwl, 2),
                            "target_max_mm": target_max,
                            "ok": net_hpwl <= target_max
                        })

            elif ctype == "edge_access":
                # Accessibilité bord de carte
                sub_ref = c.get("subject", {}).get("ref")
                edge = c.get("edge", "north")
                max_d = c.get("max_distance_to_edge_mm", 5.0)

                if sub_ref in comp_boxes:
                    box = comp_boxes[sub_ref]
                    d_edge = 0.0
                    if edge == "north":
                        d_edge = self.board_height - box.y_max
                    elif edge == "south":
                        d_edge = box.y_min
                    elif edge == "east":
                        d_edge = self.board_width - box.x_max
                    elif edge == "west":
                        d_edge = box.x_min

                    metrics.f_edge_access += max(0.0, d_edge / max_d)
                    metrics.constraint_details.append({
                        "id": cid,
                        "type": "edge_access",
                        "component": sub_ref,
                        "edge": edge,
                        "dist_to_edge_mm": round(d_edge, 2),
                        "max_mm": max_d,
                        "ok": d_edge <= max_d
                    })

        metrics.f_proximity_cem = round(prox_penalty_sum / max(1.0, prox_weights_sum), 4)

        # C. Règles de séparation CEM (Agressor vs Victim / Antenne)
        sep_penalty_sum = 0.0
        for rule in self.separation_rules:
            rid = rule.get("id", "SEP")
            req_d = rule.get("min_distance_mm", 10.0)
            weight = rule.get("weight", 5)

            # Identification des composants du groupe A et B
            if rid == "SEP_BUCK_ANTENNA":
                # Buck cluster vs RF keepout
                buck_pts = [comp_positions[d] for d in ["U4", "L1", "D2", "C7", "C14"] if d in comp_positions]
                if buck_pts:
                    # Plus courte distance au keepout antenne (X_min = 73.66)
                    closest_x = max(p[0] for p in buck_pts)
                    dist_to_ant = 73.66 - closest_x
                    if dist_to_ant < req_d:
                        sep_penalty_sum += weight * ((req_d - dist_to_ant) / req_d)
                    metrics.constraint_details.append({
                        "id": rid,
                        "type": "separation",
                        "dist_mm": round(dist_to_ant, 2),
                        "req_mm": req_d,
                        "ok": dist_to_ant >= req_d
                    })

        metrics.f_separation_emc = round(sep_penalty_sum, 4)

        # Calcul du score global pondéré
        # Score = w1 * f_wire + w2 * f_prox + w3 * f_loop + w4 * f_net + w5 * f_sep + w6 * f_edge
        metrics.hard_violations_count = len(hard_violations)
        total_score = (
            1.0 * metrics.f_wire_hpwl +
            2.5 * metrics.f_proximity_cem +
            3.0 * metrics.f_loops_compactness +
            2.0 * metrics.f_switching_nets +
            1.5 * metrics.f_separation_emc +
            0.5 * metrics.f_edge_access
        )
        metrics.weighted_total_score = round(total_score, 4)

        is_valid = (metrics.hard_violations_count == 0)

        ts = ""
        try:
            import time
            ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        except Exception:
            pass

        return PlacementEvaluation(
            is_valid=is_valid,
            score=metrics,
            hard_violations=hard_violations,
            components_count=len(comp_positions),
            evaluated_at=ts
        )


def print_evaluation_report(eval_res: PlacementEvaluation):
    score = eval_res.score
    logger.info("================================================================================")
    logger.info("                   RAPPORT D'ÉVALUATION DE PLACEMENT (SCORE.PY)                 ")
    logger.info("================================================================================")
    logger.info(f"Composants évalués   : {eval_res.components_count}")
    logger.info(f"Statut de validité   : {'✅ VALIDE (0 violation dure)' if eval_res.is_valid else '❌ INVALIDE'}")
    logger.info(f"Violations dures     : {score.hard_violations_count}")
    logger.info("--------------------------------------------------------------------------------")
    logger.info(f"  • Score global pondéré     : {score.weighted_total_score:.4f}")
    logger.info(f"  • Chevelu total (HPWL)     : {score.total_hpwl_mm:.2f} mm  (f_wire: {score.f_wire_hpwl:.4f})")
    logger.info(f"  • Pénalité proximité CEM   : {score.f_proximity_cem:.4f}")
    logger.info(f"  • Compacité boucle Buck    : {score.f_loops_compactness:.4f}")
    logger.info(f"  • Compacité nœud rayonnant : {score.f_switching_nets:.4f}")
    logger.info(f"  • Pénalité séparation CEM  : {score.f_separation_emc:.4f}")
    logger.info(f"  • Accessibilité bords      : {score.f_edge_access:.4f}")
    logger.info("--------------------------------------------------------------------------------")

    if score.overlapping_pairs:
        logger.info(f"⚠️ Chevauchements détectés ({len(score.overlapping_pairs)} paires, aire totale: {score.total_overlap_area_mm2:.2f} mm²) :")
        for a, b, s in score.overlapping_pairs[:10]:
            logger.info(f"   - {a} <--> {b} : {s:.2f} mm²")
        if len(score.overlapping_pairs) > 10:
            logger.info(f"   ... et {len(score.overlapping_pairs) - 10} autres chevauchements.")

    if eval_res.hard_violations:
        logger.info(f"❌ Détail des violations bloquantes ({len(eval_res.hard_violations)}) :")
        for v in eval_res.hard_violations[:10]:
            logger.info(f"   - [{v.violation_type}] {v.details}")
        if len(eval_res.hard_violations) > 10:
            logger.info(f"   ... et {len(eval_res.hard_violations) - 10} autres violations.")
    logger.info("================================================================================\n")


def main():
    parser = argparse.ArgumentParser(
        description="Évaluateur indépendant de score et conformité physique du placement PCB"
    )
    parser.add_argument("--manifest", type=Path, default=Path("circuit_manifest.json"))
    parser.add_argument("--board", type=Path, default=Path("board_constraints.json"))
    parser.add_argument("--geometry", type=Path, default=Path(".agents/skills/pcb-placer/.cache/netlist_geometry.json"))
    parser.add_argument("--placement", type=Path, default=None, help="Optionnel: fichier placement.json à évaluer")
    parser.add_argument("--svg", type=Path, default=None, help="Optionnel: générer le rendu SVG vectoriel")

    args = parser.parse_args()

    # Chargement du manifeste et des contraintes mécaniques
    with open(args.manifest, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    with open(args.board, "r", encoding="utf-8") as f:
        board_constraints = json.load(f)

    # Chargement ou extraction de la géométrie
    if args.geometry.is_file():
        with open(args.geometry, "r", encoding="utf-8") as f:
            raw_geom = json.load(f)
        # Reconstitution simple du snapshot
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
        logger.info("Cache géométrique non trouvé, extraction live depuis EasyEDA Pro...")
        geom = extract_board_geometry()

    # Chargement optionnel d'un fichier placement
    override = None
    if args.placement and args.placement.is_file():
        with open(args.placement, "r", encoding="utf-8") as f:
            p_data = json.load(f)
            override = p_data.get("components", p_data)

    scorer = PCBScorer(manifest, board_constraints, geom)
    eval_res = scorer.evaluate(placement_override=override)
    print_evaluation_report(eval_res)

    # Si rendu SVG demandé
    if args.svg:
        try:
            from render_svg import generate_svg_view
            generate_svg_view(manifest, board_constraints, geom, eval_res, args.svg, placement_override=override)
            logger.info(f"Rendu vectoriel SVG généré avec succès : {args.svg}")
        except ImportError:
            logger.warning("Module render_svg non disponible.")

    # Sortie avec code d'erreur si invalide
    sys.exit(0 if eval_res.is_valid else 2)


if __name__ == "__main__":
    main()
