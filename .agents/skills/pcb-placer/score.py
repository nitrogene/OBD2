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
from placement_constraints import get_power_nets
from emc_physics import (
    polygon_area_shoelace,
    estimate_loop_inductance_nh,
    magnetic_field_coupling,
    electric_field_coupling,
    decoupling_effective_inductance_nh,
)

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

    def distance_to_box(self, other: RectBox) -> float:
        """Calcule la distance euclidienne minimale entre deux boîtes alignées avec les axes (0.0 si contact ou chevauchement)."""
        dx = max(0.0, max(self.x_min - other.x_max, other.x_min - self.x_max))
        dy = max(0.0, max(self.y_min - other.y_max, other.y_min - self.y_max))
        return math.hypot(dx, dy)

    def distance_to_point(self, px: float, py: float) -> float:
        """Calcule la distance euclidienne minimale entre un point et la boîte."""
        dx = max(0.0, self.x_min - px, px - self.x_max)
        dy = max(0.0, self.y_min - py, py - self.y_max)
        return math.hypot(dx, dy)


@dataclass
class HardViolation:
    violation_type: str  # "out_of_board", "overlap", "keepout", "mounting_hole", "anchor", "proximity", "loop", "separation", "return_path"
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
    loop_area_mm2: float = 0.0
    loop_inductance_nh: float = 0.0
    f_switching_nets: float = 0.0
    f_return_path: float = 0.0
    f_separation_emc: float = 0.0
    f_edge_access: float = 0.0
    f_density_uniformity: float = 0.0
    f_spacing_comfort: float = 0.0
    f_cluster_cohesion: float = 0.0

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

    board_info = board_constraints.get("board", {})
    if "width_mm" not in board_info or "height_mm" not in board_info:
        raise KeyError("La section 'board' des contraintes doit définir 'width_mm' et 'height_mm'.")
    board_w = float(board_info["width_mm"])
    board_h = float(board_info["height_mm"])
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
        self.board_constraints = board_constraints
        self.geom = geometry

        # Résolution de la sémantique liée si functional_blocks est absent
        sem_ref = manifest.get("schema_semantics")
        if sem_ref and "functional_blocks" not in self.manifest:
            candidate_paths = [
                Path("documents/schema/semantics.json"),
                Path("documents/pcb") / sem_ref,
                Path(sem_ref)
            ]
            for cp in candidate_paths:
                if cp.exists():
                    try:
                        with open(cp, "r", encoding="utf-8") as sf:
                            sdata = json.load(sf)
                            if "functional_blocks" in sdata:
                                self.manifest["functional_blocks"] = sdata["functional_blocks"]
                            break
                    except Exception:
                        pass

        self.packages = manifest.get("packages", {})
        self.manifest_comps = manifest.get("components", {})
        self.rigid_groups = manifest.get("rigid_groups", [])
        self.placement_constraints = manifest.get("placement_constraints", [])
        self.functional_blocks = self.manifest.get("functional_blocks", {})
        self.net_classes = board_constraints.get("net_classes", {})

        board_info = board_constraints.get("board", {})
        if "width_mm" not in board_info or "height_mm" not in board_info:
            raise KeyError("La configuration 'board' doit définir 'width_mm' et 'height_mm'.")
        self.board_width = float(board_info["width_mm"])
        self.board_height = float(board_info["height_mm"])
        self.edge_clearance = board_constraints.get("board", {}).get("edge_clearance_mm", 1.0)
        self.mounting_holes = board_constraints.get("board", {}).get("mounting_holes", [])
        self.anchors = board_constraints.get("anchors", {})
        self.keepouts = board_constraints.get("keepout_zones", [])
        self.separation_rules = board_constraints.get("separation_rules", [])

        # Échelle de référence pour normaliser le câblage : demi-périmètre de carte
        self.half_perimeter = self.board_width + self.board_height
        self.power_ground_nets = get_power_nets(self.manifest, self.board)

    def _get_components_by_emc_class(self, emc_class: str) -> Set[str]:
        """Identifie agnostiquement les composants rattachés à une classe CEM."""
        result = set()
        # 1. Vérification métadonnées directes
        for des, meta in self.manifest_comps.items():
            if meta.get("emc_class") == emc_class:
                result.add(des)
        # 2. Vérification par classes de nets
        target_nets = set()
        for nc_info in self.net_classes.values():
            if nc_info.get("emc_class") == emc_class:
                for n in nc_info.get("nets", []):
                    target_nets.add(n)
        for net_name in target_nets:
            if net_name in self.geom.nets:
                for des, _ in self.geom.nets[net_name]:
                    result.add(des)
        return result

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
        power_ground_nets = self.power_ground_nets

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
                    l_eff_nh = decoupling_effective_inductance_nh(dist)
                    if dist > max_d:
                        penalty = (dist - max_d) / max_d
                        # Sur-pénalité si l'inductance parasite excède le budget acceptable
                        l_target_nh = decoupling_effective_inductance_nh(max_d)
                        if l_eff_nh > l_target_nh:
                            penalty += ((l_eff_nh - l_target_nh) / max(0.1, l_target_nh)) ** 1.5
                        prox_penalty_sum += weight * penalty
                        if is_hard:
                            hard_violations.append(HardViolation(
                                violation_type="proximity",
                                subject=sub_ref,
                                target=tgt_ref,
                                details=f"Règle dure {cid} violée : distance {dist:.2f} mm > max {max_d:.2f} mm (L_eff={l_eff_nh:.1f} nH)",
                                amount=dist - max_d
                            ))
                    metrics.constraint_details.append({
                        "id": cid,
                        "type": "proximity",
                        "dist_mm": round(dist, 2),
                        "max_mm": max_d,
                        "effective_inductance_nh": round(l_eff_nh, 2),
                        "ok": dist <= max_d
                    })
                prox_weights_sum += weight

            elif ctype == "loop":
                # Compacité physique de boucle di/dt fermée (Shoelace + Inductance de boucle)
                members = c.get("members", [])
                return_members = c.get("return_members", [])
                target_max_area = c.get("target_max_area_mm2", c.get("target_max_mm", 25.0))
                target_max_ind = c.get("target_max_inductance_nH", 8.0)

                ordered_members = list(members) + list(return_members)
                loop_points: List[Tuple[float, float]] = []

                for m in ordered_members:
                    mref = m.get("ref")
                    mpin = m.get("pin")
                    pt = None
                    if mref in comp_pads_abs and mpin in comp_pads_abs[mref]:
                        pt = comp_pads_abs[mref][mpin]
                    elif mref in comp_positions:
                        pt = (comp_positions[mref][0], comp_positions[mref][1])
                    if pt:
                        if not loop_points or (abs(loop_points[-1][0] - pt[0]) > 1e-4 or abs(loop_points[-1][1] - pt[1]) > 1e-4):
                            loop_points.append(pt)

                if len(loop_points) >= 3:
                    area = polygon_area_shoelace(loop_points)
                    inductance = estimate_loop_inductance_nh(loop_points, trace_width_mm=0.8, reference_plane_height_mm=0.2)
                    metrics.loop_area_mm2 = round(area, 2)
                    metrics.loop_inductance_nh = round(inductance, 2)

                    pen_area = max(0.0, (area - target_max_area) / max(1.0, target_max_area))
                    pen_ind = max(0.0, (inductance - target_max_ind) / max(1.0, target_max_ind))

                    loop_norm = (area / max(1.0, target_max_area)) + (inductance / max(1.0, target_max_ind)) + 3.0 * (pen_area ** 2 + pen_ind ** 2)
                    metrics.f_loops_compactness = round(loop_norm, 4)

                    is_ok = (area <= target_max_area) and (inductance <= target_max_ind)
                    if is_hard and not is_ok:
                        hard_violations.append(HardViolation(
                            violation_type="loop",
                            subject=cid,
                            details=f"Boucle di/dt {cid} non conforme : S={area:.1f} mm² (max {target_max_area}), L={inductance:.1f} nH (max {target_max_ind})",
                            amount=max(area - target_max_area, inductance - target_max_ind)
                        ))

                    metrics.constraint_details.append({
                        "id": cid,
                        "type": "loop",
                        "area_mm2": round(area, 2),
                        "target_max_area_mm2": target_max_area,
                        "inductance_nh": round(inductance, 2),
                        "target_max_inductance_nH": target_max_ind,
                        "ok": is_ok
                    })
                elif loop_points:
                    l_xs = [pt[0] for pt in loop_points]
                    l_ys = [pt[1] for pt in loop_points]
                    loop_hpwl = (max(l_xs) - min(l_xs)) + (max(l_ys) - min(l_ys))
                    metrics.f_loops_compactness = round(loop_hpwl / target_max_area, 4)

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

            elif ctype == "return_path_proximity":
                # Proximité du chemin de retour vers le plan ou broches de masse GND
                sig_net = c.get("signal_net")
                plane_nets = self.board_constraints.get("plane_nets", [])
                ref_net = c.get("reference_net") or (plane_nets[0] if plane_nets else None)
                if not ref_net:
                    raise KeyError(f"Contrainte '{cid}' ({ctype}) : aucun 'reference_net' spécifié et aucun réseau déclaré dans 'plane_nets'.")
                max_ret_d = c.get("max_distance_to_reference_mm", 3.0)

                sig_pins = self.geom.nets.get(sig_net, []) if sig_net else []
                ref_pins = self.geom.nets.get(ref_net, []) if ref_net else []

                sig_pts = []
                for d, p in sig_pins:
                    if d in comp_pads_abs and p in comp_pads_abs[d]:
                        sig_pts.append(comp_pads_abs[d][p])
                    elif d in comp_positions:
                        sig_pts.append((comp_positions[d][0], comp_positions[d][1]))

                ref_pts = []
                for d, p in ref_pins:
                    if d in comp_pads_abs and p in comp_pads_abs[d]:
                        ref_pts.append(comp_pads_abs[d][p])
                    elif d in comp_positions:
                        ref_pts.append((comp_positions[d][0], comp_positions[d][1]))

                if sig_pts and ref_pts:
                    max_nearest_dist = 0.0
                    for sp in sig_pts:
                        d_nearest = min(math.hypot(sp[0] - rp[0], sp[1] - rp[1]) for rp in ref_pts)
                        if d_nearest > max_nearest_dist:
                            max_nearest_dist = d_nearest

                    pen_ret = max(0.0, (max_nearest_dist - max_ret_d) / max(0.1, max_ret_d))
                    metrics.f_return_path = round(pen_ret, 4)

                    if is_hard and max_nearest_dist > max_ret_d:
                        hard_violations.append(HardViolation(
                            violation_type="return_path",
                            subject=cid,
                            details=f"Chemin de retour {cid} trop éloigné du plan {ref_net} : {max_nearest_dist:.2f} mm > {max_ret_d:.2f} mm",
                            amount=max_nearest_dist - max_ret_d
                        ))

                    metrics.constraint_details.append({
                        "id": cid,
                        "type": "return_path_proximity",
                        "signal_net": sig_net,
                        "reference_net": ref_net,
                        "dist_mm": round(max_nearest_dist, 2),
                        "max_mm": max_ret_d,
                        "ok": max_nearest_dist <= max_ret_d
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

        # C. Règles de séparation CEM isotropes 2D avec lois physiques de couplage
        sep_penalty_sum = 0.0
        for rule in self.separation_rules:
            rid = rule.get("id", "SEP")
            req_d = rule.get("min_distance_mm", 10.0)
            coupling_type = rule.get("coupling", "H_field")
            weight = rule.get("weight", 5)
            is_hard = rule.get("hard", False)

            # Résolution de group_a
            group_a_cfg = rule.get("group_a", {})
            comps_a: Set[str] = set()
            if "cluster" in group_a_cfg:
                c_name = group_a_cfg["cluster"]
                comps_a.update(self.functional_blocks.get(c_name, {}).get("components", []))
            if "emc_class" in group_a_cfg:
                cls_name = group_a_cfg["emc_class"]
                comps_a.update(self._get_components_by_emc_class(cls_name))

            # Résolution de group_b (soit zone de keepout, soit cluster, soit emc_class)
            group_b_cfg = rule.get("group_b", {})
            target_zone_box: Optional[RectBox] = None
            comps_b: Set[str] = set()

            if "zone" in group_b_cfg:
                z_name = group_b_cfg["zone"]
                for kz in all_keepouts:
                    if kz.get("id") == z_name or kz.get("name") == z_name:
                        r = kz.get("rect_mm", {})
                        target_zone_box = RectBox(r.get("x_min", 0.0), r.get("x_max", 0.0), r.get("y_min", 0.0), r.get("y_max", 0.0))
                        break
            if "cluster" in group_b_cfg:
                c_name = group_b_cfg["cluster"]
                comps_b.update(self.functional_blocks.get(c_name, {}).get("components", []))
            if "emc_class" in group_b_cfg:
                cls_name = group_b_cfg["emc_class"]
                comps_b.update(self._get_components_by_emc_class(cls_name))

            # Calcul de la distance 2D euclidienne minimale
            min_dist_2d = float("inf")
            valid_comps_a = [c for c in comps_a if c in comp_boxes]

            if valid_comps_a and target_zone_box:
                for ca in valid_comps_a:
                    d = comp_boxes[ca].distance_to_box(target_zone_box)
                    if d < min_dist_2d:
                        min_dist_2d = d
            elif valid_comps_a and comps_b:
                valid_comps_b = [c for c in comps_b if c in comp_boxes and c not in comps_a]
                for ca in valid_comps_a:
                    for cb in valid_comps_b:
                        d = comp_boxes[ca].distance_to_box(comp_boxes[cb])
                        if d < min_dist_2d:
                            min_dist_2d = d

            if min_dist_2d < float("inf"):
                rule_penalty = 0.0
                if min_dist_2d < req_d:
                    if coupling_type == "H_field":
                        # Décroissance dipolaire magnétique en 1/r³
                        coupling_factor = (req_d / max(0.5, min_dist_2d)) ** 3 - 1.0
                    elif coupling_type == "E_field":
                        # Décroissance capacitive électrique en 1/r²
                        coupling_factor = (req_d / max(0.5, min_dist_2d)) ** 2 - 1.0
                    else:
                        coupling_factor = (req_d - min_dist_2d) / req_d

                    rule_penalty = weight * max(0.0, coupling_factor)
                    sep_penalty_sum += rule_penalty

                    if is_hard:
                        hard_violations.append(HardViolation(
                            violation_type="separation",
                            subject=rid,
                            details=f"Violation règle CEM {rid} : distance {min_dist_2d:.2f} mm < min requis {req_d:.2f} mm",
                            amount=req_d - min_dist_2d
                        ))

                metrics.constraint_details.append({
                    "id": rid,
                    "type": "separation",
                    "coupling": coupling_type,
                    "dist_mm": round(min_dist_2d, 2),
                    "req_mm": req_d,
                    "penalty": round(rule_penalty, 4),
                    "ok": min_dist_2d >= req_d
                })

        metrics.f_separation_emc = round(sep_penalty_sum, 4)

        # D. Cohésion des Blocs Fonctionnels (f_cluster_cohesion)
        # Règle agnostique : chaque bloc technique doit maintenir ses passifs groupés
        # autour de son circuit intégré (IC) ou barycentre pour éviter l'éparpillement.
        cluster_penalty_sum = 0.0
        clusters_checked = 0
        functional_blocks = self.manifest.get("functional_blocks", {})

        # Identifier les exemptions (composants astreints à une ancre externe, ex: TVS sur J1)
        external_anchored = set()
        for c in self.placement_constraints:
            if c.get("type") == "proximity":
                s_ref = c.get("subject", {}).get("ref")
                t_ref = c.get("target", {}).get("ref")
                if t_ref in self.anchors:
                    external_anchored.add(s_ref)

        max_cluster_radius_mm = 10.0  # Rayon maximal admissible pour un bloc technique de passifs

        for fb_id, fb_info in functional_blocks.items():
            members = fb_info.get("components", [])
            valid_members = [m for m in members if m in comp_positions and m not in self.anchors]
            if len(valid_members) <= 1:
                continue

            # Trouver le composant maître du bloc (priorité IC 'U*', sinon composant avec silicon_ic)
            anchor_candidates = [m for m in valid_members if m.startswith("U") or self.manifest_comps.get(m, {}).get("constraints", {}).get("silicon_ic")]
            anchor_comp = anchor_candidates[0] if anchor_candidates else None

            if anchor_comp:
                anc_pos = comp_positions[anchor_comp]
                anc_x, anc_y = anc_pos[0], anc_pos[1]
            else:
                anc_x = sum(comp_positions[m][0] for m in valid_members) / len(valid_members)
                anc_y = sum(comp_positions[m][1] for m in valid_members) / len(valid_members)

            block_pen = 0.0
            for m in valid_members:
                if m == anchor_comp or m in external_anchored:
                    continue
                mx, my = comp_positions[m][0], comp_positions[m][1]
                dist_to_anc = math.hypot(mx - anc_x, my - anc_y)
                if dist_to_anc > max_cluster_radius_mm:
                    pen = (dist_to_anc - max_cluster_radius_mm) / max_cluster_radius_mm
                    block_pen += pen ** 2
                    metrics.constraint_details.append({
                        "id": f"CLUSTER_{fb_id}_{m}",
                        "type": "cluster_cohesion",
                        "block": fb_id,
                        "component": m,
                        "anchor": anchor_comp or "center",
                        "dist_mm": round(dist_to_anc, 2),
                        "max_mm": max_cluster_radius_mm,
                        "ok": False
                    })
                else:
                    metrics.constraint_details.append({
                        "id": f"CLUSTER_{fb_id}_{m}",
                        "type": "cluster_cohesion",
                        "block": fb_id,
                        "component": m,
                        "anchor": anchor_comp or "center",
                        "dist_mm": round(dist_to_anc, 2),
                        "max_mm": max_cluster_radius_mm,
                        "ok": True
                    })

            cluster_penalty_sum += block_pen
            clusters_checked += 1

        metrics.f_cluster_cohesion = round(cluster_penalty_sum / max(1, clusters_checked), 4)

        # D. Densité Uniforme par Grille (8x4 Bins)
        n_bins_x, n_bins_y = 8, 4
        bin_w = self.board_width / n_bins_x
        bin_h = self.board_height / n_bins_y
        bin_areas = [0.0] * (n_bins_x * n_bins_y)
        usable_bins = []

        keepout_boxes = []
        for kz in all_keepouts:
            rect = kz.get("rect_mm", {})
            keepout_boxes.append(RectBox(rect.get("x_min", 0.0), rect.get("x_max", 0.0), rect.get("y_min", 0.0), rect.get("y_max", 0.0)))

        for ix in range(n_bins_x):
            for iy in range(n_bins_y):
                b_idx = iy * n_bins_x + ix
                bx_min = ix * bin_w
                bx_max = (ix + 1) * bin_w
                by_min = iy * bin_h
                by_max = (iy + 1) * bin_h
                b_box = RectBox(bx_min, bx_max, by_min, by_max)

                # Si la cellule est dominée par un keepout (ex: antenne RF 2.4 GHz), on l'exclut de la cible
                in_ko = any(b_box.intersection_area(kbox) > 0.6 * b_box.area for kbox in keepout_boxes)
                if not in_ko:
                    usable_bins.append(b_idx)

                for des, box in comp_boxes.items():
                    if box.intersects(b_box):
                        bin_areas[b_idx] += box.intersection_area(b_box)

        total_comp_area = sum(box.area for box in comp_boxes.values())
        target_area_per_bin = total_comp_area / max(1, len(usable_bins))

        density_var = 0.0
        if usable_bins and target_area_per_bin > 0:
            density_var = sum(((bin_areas[b] - target_area_per_bin) / target_area_per_bin) ** 2 for b in usable_bins) / len(usable_bins)

        metrics.f_density_uniformity = round(density_var, 4)

        # E. Confort d'espacement (Aération minimale >= 0.80 mm entre courtyards)
        min_comfort_gap = 0.80
        spacing_penalty = 0.0
        comp_keys = list(comp_boxes.keys())
        for i in range(len(comp_keys)):
            box_i = comp_boxes[comp_keys[i]]
            for j in range(i + 1, len(comp_keys)):
                box_j = comp_boxes[comp_keys[j]]
                gap_x = max(0.0, max(box_i.x_min - box_j.x_max, box_j.x_min - box_i.x_max))
                gap_y = max(0.0, max(box_i.y_min - box_j.y_max, box_j.y_min - box_i.y_max))
                box_dist = max(gap_x, gap_y)
                if box_dist < min_comfort_gap:
                    spacing_penalty += ((min_comfort_gap - box_dist) / min_comfort_gap) ** 2

        metrics.f_spacing_comfort = round(spacing_penalty / max(1, len(comp_keys)), 4)

        # Calcul du score global pondéré
        # Score = w1 * f_wire + w2 * f_prox + w3 * f_loop + w4 * f_net + w5 * f_ret + w6 * f_sep + w7 * f_edge + w8 * f_density + w9 * f_spacing
        metrics.hard_violations_count = len(hard_violations)
        total_score = (
            1.0 * metrics.f_wire_hpwl +
            2.5 * metrics.f_proximity_cem +
            3.0 * metrics.f_loops_compactness +
            2.0 * metrics.f_switching_nets +
            2.0 * metrics.f_return_path +
            2.0 * metrics.f_separation_emc +
            2.0 * metrics.f_cluster_cohesion +
            0.5 * metrics.f_edge_access +
            2.0 * metrics.f_density_uniformity +
            1.5 * metrics.f_spacing_comfort
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
    logger.info(f"  • Boucle Buck di/dt        : {score.loop_area_mm2:.2f} mm² / {score.loop_inductance_nh:.2f} nH (f_loop: {score.f_loops_compactness:.4f})")
    logger.info(f"  • Compacité nœud rayonnant : {score.f_switching_nets:.4f}")
    logger.info(f"  • Chemin de retour GND     : {score.f_return_path:.4f}")
    logger.info(f"  • Pénalité séparation CEM  : {score.f_separation_emc:.4f}")
    logger.info(f"  • Cohésion des clusters    : {score.f_cluster_cohesion:.4f}")
    logger.info(f"  • Accessibilité bords      : {score.f_edge_access:.4f}")
    logger.info(f"  • Densité uniforme (8x4)   : {score.f_density_uniformity:.4f}")
    logger.info(f"  • Aération / Confort       : {score.f_spacing_comfort:.4f}")
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
    default_manifest = Path("documents/pcb/manifest.json") if Path("documents/pcb/manifest.json").exists() else Path("circuit_manifest.json")
    default_board = Path("documents/pcb/constraints.json") if Path("documents/pcb/constraints.json").exists() else Path("board_constraints.json")
    parser.add_argument("--manifest", type=Path, default=default_manifest)
    parser.add_argument("--board", type=Path, default=default_board)
    parser.add_argument("--geometry", type=Path, default=Path(".agents/skills/pcb-placer/.cache/netlist_geometry.json"))
    parser.add_argument("--placement", type=Path, default=None, help="Optionnel: fichier placement.json à évaluer")
    parser.add_argument("--svg", type=Path, default=None, help="Optionnel: générer le rendu SVG vectoriel")

    args = parser.parse_args()

    # Chargement du manifeste et des contraintes mécaniques
    manifest_path = args.manifest
    if not manifest_path.exists() and Path("documents/pcb/manifest.json").exists():
        manifest_path = Path("documents/pcb/manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    # Résolution de la sémantique liée pour éliminer toute redondance
    sem_ref = manifest.get("schema_semantics")
    if sem_ref:
        sem_path = (manifest_path.parent / sem_ref).resolve()
        if sem_path.exists():
            with open(sem_path, "r", encoding="utf-8") as sf:
                sem_data = json.load(sf)
            if "functional_blocks" not in manifest and "functional_blocks" in sem_data:
                manifest["functional_blocks"] = sem_data["functional_blocks"]
            for des, s_comp in sem_data.get("components", {}).items():
                if des in manifest.get("components", {}):
                    for k, v in s_comp.items():
                        if k not in manifest["components"][des]:
                            manifest["components"][des][k] = v
    board_path = args.board
    if not board_path.exists() and Path("documents/pcb/constraints.json").exists():
        board_path = Path("documents/pcb/constraints.json")
    with open(board_path, "r", encoding="utf-8") as f:
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
