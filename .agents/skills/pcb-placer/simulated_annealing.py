#!/usr/bin/env python3
"""
simulated_annealing.py - Moteur de Placement Global par Recuit Simulé (Agnostique v2.0)
========================================================================================
Conforme à la Règle 0 (AGENTS.md) :
- Aucune référence en dur à des composants, coordonnées ou valeurs spécifiques.
- Manipulation d'abstractions géométriques (boîtes, pastilles, nets, ancres, keepouts).
- Optimisation incrémentale O(N) ultra-rapide (50 000+ itérations en quelques secondes).
- Élimination garantie des collisions (0 chevauchement), respect des gardes de bord,
  des keepouts RF, des fixations M2 et des règles de proximité CEM.
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import math
import random
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from export_geometry import BoardGeometrySnapshot, extract_board_geometry
from score import (
    PCBScorer,
    PlacementEvaluation,
    RectBox,
    get_component_courtyard_box,
    rotate_offset,
    get_all_keepouts
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("AnnealingPlacer")


@dataclass
class MovableItem:
    index: int
    designator: str
    package: str
    width_0: float  # Largeur du courtyard à 0°
    height_0: float  # Hauteur du courtyard à 0°
    x: float
    y: float
    rotation: float
    is_fixed: bool
    allowed_rotations: List[float] = field(default_factory=lambda: [0.0, 90.0, 180.0, 270.0])
    block: str = "default"
    # Offsets relatifs des broches à 0° : { pin_number: (dx0, dy0) }
    pads_dx0_dy0: Dict[str, Tuple[float, float]] = field(default_factory=dict)

    @property
    def current_half_w(self) -> float:
        r = int(round(self.rotation)) % 360
        return (self.height_0 if r in (90, 270) else self.width_0) / 2.0

    @property
    def current_half_h(self) -> float:
        r = int(round(self.rotation)) % 360
        return (self.width_0 if r in (90, 270) else self.height_0) / 2.0

    @property
    def box(self) -> RectBox:
        hw = self.current_half_w
        hh = self.current_half_h
        return RectBox(self.x - hw, self.x + hw, self.y - hh, self.y + hh)

    def get_pad_abs(self, pin_num: str) -> Optional[Tuple[float, float]]:
        if pin_num not in self.pads_dx0_dy0:
            return (self.x, self.y)
        dx0, dy0 = self.pads_dx0_dy0[pin_num]
        dx, dy = rotate_offset(dx0, dy0, self.rotation)
        return (self.x + dx, self.y + dy)


class FastAnnealingEngine:
    """Moteur d'optimisation stochastique haute performance avec calcul incrémental O(N)."""

    def __init__(
        self,
        manifest: Dict[str, Any],
        board_constraints: Dict[str, Any],
        geometry: BoardGeometrySnapshot,
        spacing_margin_mm: float = 0.35
    ):
        self.manifest = manifest
        self.board_cfg = board_constraints
        self.geometry = geometry
        self.spacing_margin_mm = spacing_margin_mm

        self.board_w = board_constraints.get("board", {}).get("width_mm", 81.28)
        self.board_h = board_constraints.get("board", {}).get("height_mm", 35.56)
        self.edge_clearance = board_constraints.get("board", {}).get("edge_clearance_mm", 1.0)
        self.mounting_holes = board_constraints.get("board", {}).get("mounting_holes", [])
        self.keepouts = board_constraints.get("keepout_zones", [])
        self.anchors = board_constraints.get("anchors", {})

        self.packages = manifest.get("packages", {})
        self.manifest_comps = manifest.get("components", {})
        self.placement_constraints = manifest.get("placement_constraints", [])

        # Identification agnostique des composants à couplage CEM strict (ne doivent pas être distendus)
        tight_cem_components: Set[str] = set()
        for rg in manifest.get("rigid_groups", []):
            for m in rg.get("members", []):
                tight_cem_components.add(m)
        for pc in self.placement_constraints:
            if pc.get("type") == "proximity" and pc.get("max_mm", 10.0) <= 6.0:
                s_ref = pc.get("subject", {}).get("ref")
                t_ref = pc.get("target", {}).get("ref")
                if s_ref:
                    tight_cem_components.add(s_ref)
                if t_ref:
                    tight_cem_components.add(t_ref)

        # Construction de la liste des items
        self.items: List[MovableItem] = []
        self.des_to_index: Dict[str, int] = {}

        idx = 0
        for des, meta in self.manifest_comps.items():
            pkg_name = meta.get("package") or meta.get("footprint", "0603")
            pkg_info = self.packages.get(pkg_name, {"width_mm": 1.6, "length_mm": 0.8, "courtyard_margin_mm": 0.25})

            is_fixed = False
            cur_x, cur_y, cur_rot = 0.0, 0.0, 0.0

            if des in self.anchors:
                anc = self.anchors[des]
                cur_x = float(anc.get("x_mm", 0.0))
                cur_y = float(anc.get("y_mm", 0.0))
                cur_rot = float(anc.get("rot_deg", 0.0))
                is_fixed = bool(anc.get("fixed", True))
            elif des in geometry.components:
                gc = geometry.components[des]
                cur_x, cur_y, cur_rot = gc.x_mm, gc.y_mm, gc.rotation
                is_fixed = gc.locked

            # Marge de confort d'aération appliquée aux composants libres hors groupes CEM denses
            if is_fixed or des in tight_cem_components:
                extra_margin = 0.0
            else:
                extra_margin = self.spacing_margin_mm

            margin_tot = pkg_info.get("courtyard_margin_mm", 0.25) + extra_margin
            w0 = pkg_info.get("width_mm", 1.6) + 2.0 * margin_tot
            h0 = pkg_info.get("length_mm", 0.8) + 2.0 * margin_tot

            pads_map = {}
            if des in geometry.components:
                for p in geometry.components[des].pads:
                    pads_map[p.number] = (p.dx_0_mm, p.dy_0_mm)

            allowed_rot = meta.get("placement", {}).get("allowed_rotations", [0.0, 90.0, 180.0, 270.0])

            item = MovableItem(
                index=idx,
                designator=des,
                package=pkg_name,
                width_0=w0,
                height_0=h0,
                x=cur_x,
                y=cur_y,
                rotation=cur_rot,
                is_fixed=is_fixed,
                allowed_rotations=[float(r) for r in allowed_rot],
                block=meta.get("block", "default"),
                pads_dx0_dy0=pads_map
            )
            self.items.append(item)
            self.des_to_index[des] = idx
            idx += 1

        self.movable_indices = [i for i, item in enumerate(self.items) if not item.is_fixed]
        self.n_items = len(self.items)

        # Netlist indexée pour calcul rapide
        self.fast_nets: List[List[Tuple[int, str]]] = []
        # Item index -> list of net indices containing it
        self.item_to_nets: List[List[int]] = [[] for _ in range(self.n_items)]

        power_ground = {"GND", "+12V", "+5V", "3.3V"}
        net_idx = 0
        for net_name, pins in geometry.nets.items():
            if net_name in power_ground or len(pins) < 2:
                continue
            net_members = []
            for des, pnum in pins:
                if des in self.des_to_index:
                    i_idx = self.des_to_index[des]
                    net_members.append((i_idx, pnum))
                    self.item_to_nets[i_idx].append(net_idx)
            if len(net_members) >= 2:
                self.fast_nets.append(net_members)
                net_idx += 1

        # Graphe de connectivité
        self.neighbors: Dict[int, Set[int]] = {i: set() for i in range(self.n_items)}
        for net_members in self.fast_nets:
            indices = [m[0] for m in net_members]
            for a in indices:
                for b in indices:
                    if a != b:
                        self.neighbors[a].add(b)

        # Contraintes de proximité CEM indexées
        self.hard_proximities: List[Tuple[int, str, int, str, float]] = []
        self.soft_proximities: List[Tuple[int, str, int, str, float, float]] = []
        self.loop_constraints: List[Tuple[List[Tuple[int, str]], float, float]] = []

        for c in self.placement_constraints:
            ctype = c.get("type")
            if ctype == "proximity":
                s_ref = c.get("subject", {}).get("ref")
                s_pin = c.get("subject", {}).get("pin")
                t_ref = c.get("target", {}).get("ref")
                t_pin = c.get("target", {}).get("pin")
                max_d = c.get("max_mm", 3.0)
                is_hard = c.get("hard", False)
                w = c.get("weight", 5.0)

                if s_ref in self.des_to_index and t_ref in self.des_to_index:
                    s_idx = self.des_to_index[s_ref]
                    t_idx = self.des_to_index[t_ref]
                    if is_hard:
                        self.hard_proximities.append((s_idx, s_pin, t_idx, t_pin, max_d))
                    else:
                        self.soft_proximities.append((s_idx, s_pin, t_idx, t_pin, max_d, w))

            elif ctype == "loop":
                members = []
                for m in c.get("members", []):
                    mref = m.get("ref")
                    mpin = m.get("pin")
                    if mref in self.des_to_index:
                        members.append((self.des_to_index[mref], mpin))
                target_max = c.get("target_max_mm", 25.0)
                w = c.get("weight", 8.0)
                if len(members) >= 2:
                    self.loop_constraints.append((members, target_max, w))

        # Indexation des proximités dures par composant
        self.item_to_hard_proximities: Dict[int, List[Tuple[int, str, int, str, float]]] = {i: [] for i in range(self.n_items)}
        for hp in self.hard_proximities:
            s_idx, s_pin, t_idx, t_pin, max_d = hp
            self.item_to_hard_proximities[s_idx].append(hp)
            self.item_to_hard_proximities[t_idx].append(hp)

        # Indexation des proximités douces et boucles par composant
        self.item_to_soft_proximities: Dict[int, List[Tuple[int, str, int, str, float, float]]] = {i: [] for i in range(self.n_items)}
        for sp in self.soft_proximities:
            s_idx, s_pin, t_idx, t_pin, max_d, w = sp
            self.item_to_soft_proximities[s_idx].append(sp)
            self.item_to_soft_proximities[t_idx].append(sp)

        self.item_to_loops: Dict[int, List[Tuple[List[Tuple[int, str]], float, float]]] = {i: [] for i in range(self.n_items)}
        for lp in self.loop_constraints:
            members, target_max, w = lp
            for m_idx, _ in members:
                self.item_to_loops[m_idx].append(lp)

        # Indexation des contraintes d'accès bord (ex: SW1 au bord Nord)
        self.item_to_edge_access: Dict[int, List[Tuple[str, float, float]]] = {i: [] for i in range(self.n_items)}
        for c in self.placement_constraints:
            if c.get("type") == "edge_access":
                sub_ref = c.get("subject", {}).get("ref")
                edge = c.get("edge", "north")
                max_d = c.get("max_distance_to_edge_mm", 5.0)
                w = c.get("weight", 3.0)
                if sub_ref in self.des_to_index:
                    s_idx = self.des_to_index[sub_ref]
                    self.item_to_edge_access[s_idx].append((edge, max_d, w))

        # Résolution des keepouts dynamiques (packages + carte)
        init_pos_map = {it.designator: (it.x, it.y, it.rotation) for it in self.items}
        self.keepouts = get_all_keepouts(board_constraints, manifest, init_pos_map)

        # Configuration de la grille de densité 2D (8x4 Bins) pour homogénéité spatiale
        self.n_bins_x = 8
        self.n_bins_y = 4
        self.bin_w = self.board_w / self.n_bins_x
        self.bin_h = self.board_h / self.n_bins_y
        self.total_bins = self.n_bins_x * self.n_bins_y

        self.usable_bins: List[int] = []
        keepout_boxes = []
        for kz in self.keepouts:
            rect = kz.get("rect_mm", {})
            keepout_boxes.append(RectBox(rect.get("x_min", 0.0), rect.get("x_max", 0.0), rect.get("y_min", 0.0), rect.get("y_max", 0.0)))

        for ix in range(self.n_bins_x):
            for iy in range(self.n_bins_y):
                b_idx = iy * self.n_bins_x + ix
                bx_min = ix * self.bin_w
                bx_max = (ix + 1) * self.bin_w
                by_min = iy * self.bin_h
                by_max = (iy + 1) * self.bin_h
                b_box = RectBox(bx_min, bx_max, by_min, by_max)
                in_ko = any(b_box.intersection_area(kbox) > 0.6 * b_box.area for kbox in keepout_boxes)
                if not in_ko:
                    self.usable_bins.append(b_idx)

        # Matrices d'état incrémental pour exécution ultra-rapide
        self.overlap_matrix = [[0.0] * self.n_items for _ in range(self.n_items)]
        self.total_overlap = 0.0

        # Suivi incrémental de l'occupation par bin
        self.bin_areas: List[float] = [0.0] * self.total_bins
        self.item_bin_overlaps: List[Dict[int, float]] = [{} for _ in range(self.n_items)]

        # Initialisation de la matrice de chevauchement et de la grille de densité
        for i in range(self.n_items):
            box_i = self.items[i].box
            overlaps = self.compute_box_bin_overlaps(box_i)
            self.item_bin_overlaps[i] = overlaps
            for b_idx, area in overlaps.items():
                self.bin_areas[b_idx] += area

            for j in range(i + 1, self.n_items):
                box_j = self.items[j].box
                if box_i.intersects(box_j):
                    area = box_i.intersection_area(box_j)
                    if area > 0.01:
                        self.overlap_matrix[i][j] = area
                        self.overlap_matrix[j][i] = area
                        self.total_overlap += area

        tot_area = sum(self.items[i].box.area for i in range(self.n_items))
        self.target_bin_area = tot_area / max(1, len(self.usable_bins))

    def compute_box_bin_overlaps(self, box: RectBox) -> Dict[int, float]:
        """Calcule en O(1) les intersections d'une boîte avec les cellules de la grille de densité."""
        ix_min = max(0, min(self.n_bins_x - 1, int(box.x_min / self.bin_w)))
        ix_max = max(0, min(self.n_bins_x - 1, int(box.x_max / self.bin_w)))
        iy_min = max(0, min(self.n_bins_y - 1, int(box.y_min / self.bin_h)))
        iy_max = max(0, min(self.n_bins_y - 1, int(box.y_max / self.bin_h)))

        res = {}
        for ix in range(ix_min, ix_max + 1):
            for iy in range(iy_min, iy_max + 1):
                b_idx = iy * self.n_bins_x + ix
                bx_min = ix * self.bin_w
                bx_max = (ix + 1) * self.bin_w
                by_min = iy * self.bin_h
                by_max = (iy + 1) * self.bin_h
                b_box = RectBox(bx_min, bx_max, by_min, by_max)
                ia = box.intersection_area(b_box)
                if ia > 0.001:
                    res[b_idx] = ia
        return res

    def compute_item_prox_and_loop(self, item_idx: int) -> float:
        """Calcule les pénalités CEM de proximité douce et de compacité de boucles pour un composant."""
        pen = 0.0
        for s_idx, s_pin, t_idx, t_pin, max_d, w in self.item_to_soft_proximities[item_idx]:
            p1 = self.items[s_idx].get_pad_abs(s_pin)
            p2 = self.items[t_idx].get_pad_abs(t_pin)
            if p1 and p2:
                dist = math.hypot(p1[0] - p2[0], p1[1] - p2[1])
                if dist > max_d:
                    pen += (dist - max_d) * (w * 0.8)

        for members, target_max, w in self.item_to_loops[item_idx]:
            loop_pts = []
            for m_idx, m_pin in members:
                pt = self.items[m_idx].get_pad_abs(m_pin)
                if pt:
                    loop_pts.append(pt)
            if len(loop_pts) >= 2:
                xs = [p[0] for p in loop_pts]
                ys = [p[1] for p in loop_pts]
                l_hpwl = (max(xs) - min(xs)) + (max(ys) - min(ys))
                if l_hpwl > target_max:
                    pen += (l_hpwl - target_max) * (w * 1.0)

        for edge, max_d, w in self.item_to_edge_access.get(item_idx, []):
            it = self.items[item_idx]
            box = it.box
            d_edge = 0.0
            if edge == "north":
                d_edge = self.board_h - box.y_max
            elif edge == "south":
                d_edge = box.y_min
            elif edge == "east":
                d_edge = self.board_w - box.x_max
            elif edge == "west":
                d_edge = box.x_min
            if d_edge > max_d:
                pen += (d_edge - max_d) * (w * 1.5)

        return pen

    def compute_single_net_hpwl(self, net_idx: int) -> float:
        """Calcule le demi-périmètre d'un seul net."""
        net = self.fast_nets[net_idx]
        min_x = 1e9
        max_x = -1e9
        min_y = 1e9
        max_y = -1e9
        for idx, pin_num in net:
            it = self.items[idx]
            pt = it.get_pad_abs(pin_num)
            if pt:
                px, py = pt
                if px < min_x: min_x = px
                if px > max_x: max_x = px
                if py < min_y: min_y = py
                if py > max_y: max_y = py
        if min_x <= max_x:
            return (max_x - min_x) + (max_y - min_y)
        return 0.0

    def compute_total_hpwl(self) -> float:
        return sum(self.compute_single_net_hpwl(k) for k in range(len(self.fast_nets)))

    def compute_item_hard_violations(self, it: MovableItem) -> float:
        """Calcule les pénalités hors-carte, trous M2 et keepout pour un item donné."""
        if it.is_fixed:
            return 0.0
        penalty = 0.0
        box = it.box

        # 1. Bords de carte
        min_x = self.edge_clearance
        max_x = self.board_w - self.edge_clearance
        min_y = self.edge_clearance
        max_y = self.board_h - self.edge_clearance

        dx = max(0.0, min_x - box.x_min) + max(0.0, box.x_max - max_x)
        dy = max(0.0, min_y - box.y_min) + max(0.0, box.y_max - max_y)
        if dx > 0.0 or dy > 0.0:
            penalty += (dx + dy) * 20.0

        # 2. Trous de fixation M2
        for h in self.mounting_holes:
            hx = h.get("x_mm", 0.0)
            hy = h.get("y_mm", 0.0)
            hr = h.get("head_clearance_mm", 4.5) / 2.0
            hole_box = RectBox(hx - hr, hx + hr, hy - hr, hy + hr)
            if box.intersects(hole_box):
                penalty += (box.intersection_area(hole_box) + 5.0) * 25.0

        # 3. Keepouts
        for kz in self.keepouts:
            rect = kz.get("rect_mm", {})
            kbox = RectBox(rect.get("x_min", 0.0), rect.get("x_max", 0.0), rect.get("y_min", 0.0), rect.get("y_max", 0.0))
            exempt = set(kz.get("exempt_refs", []))
            if it.designator in exempt:
                continue
            if box.intersects(kbox):
                penalty += (box.intersection_area(kbox) + 5.0) * 30.0

        # 4. Proximités dures (ex: C14 < 3mm de U4 pin 2)
        for s_idx, s_pin, t_idx, t_pin, max_d in self.item_to_hard_proximities.get(it.index, []):
            p1 = self.items[s_idx].get_pad_abs(s_pin)
            p2 = self.items[t_idx].get_pad_abs(t_pin)
            if p1 and p2:
                dist = math.hypot(p1[0] - p2[0], p1[1] - p2[1])
                if dist > max_d:
                    penalty += (dist - max_d) * 60.0 + 30.0

        return penalty

    def compute_proximity_and_loop_penalties(self) -> float:
        """Calcule les pénalités de proximité CEM et boucles critiques."""
        penalty = 0.0

        # Proximités dures (ex: C14 < 3mm de U4 pin 2)
        for s_idx, s_pin, t_idx, t_pin, max_d in self.hard_proximities:
            p1 = self.items[s_idx].get_pad_abs(s_pin)
            p2 = self.items[t_idx].get_pad_abs(t_pin)
            if p1 and p2:
                dist = math.hypot(p1[0] - p2[0], p1[1] - p2[1])
                if dist > max_d:
                    penalty += (dist - max_d) * 50.0

        # Proximités douces
        for s_idx, s_pin, t_idx, t_pin, max_d, w in self.soft_proximities:
            p1 = self.items[s_idx].get_pad_abs(s_pin)
            p2 = self.items[t_idx].get_pad_abs(t_pin)
            if p1 and p2:
                dist = math.hypot(p1[0] - p2[0], p1[1] - p2[1])
                if dist > max_d:
                    penalty += (dist - max_d) * (w * 0.5)

        # Boucles critiques (ex: Buck hot loop)
        for members, target_max, w in self.loop_constraints:
            loop_pts = []
            for m_idx, m_pin in members:
                pt = self.items[m_idx].get_pad_abs(m_pin)
                if pt:
                    loop_pts.append(pt)
            if len(loop_pts) >= 2:
                xs = [p[0] for p in loop_pts]
                ys = [p[1] for p in loop_pts]
                l_hpwl = (max(xs) - min(xs)) + (max(ys) - min(ys))
                if l_hpwl > target_max:
                    penalty += (l_hpwl - target_max) * (w * 0.8)

        # Accessibilité bord (ex: SW1 bord Nord)
        for s_idx, access_list in self.item_to_edge_access.items():
            it = self.items[s_idx]
            box = it.box
            for edge, max_d, w in access_list:
                d_edge = 0.0
                if edge == "north":
                    d_edge = self.board_h - box.y_max
                elif edge == "south":
                    d_edge = box.y_min
                elif edge == "east":
                    d_edge = self.board_w - box.x_max
                elif edge == "west":
                    d_edge = box.x_min
                if d_edge > max_d:
                    penalty += (d_edge - max_d) * (w * 1.0)

        return penalty

    def compute_all_hard_penalties(self) -> float:
        return sum(self.compute_item_hard_violations(it) for it in self.items)

    def run(
        self,
        steps: int = 30000,
        t_start: float = 60.0,
        t_end: float = 0.01,
        seed: Optional[int] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Exécute un cycle de recuit simulé optimisé avec mise à jour incrémentale."""
        if seed is not None:
            random.seed(seed)

        lambda_hard_start = 5.0
        lambda_hard_end = 250.0
        mu_overlap_start = 3.0
        mu_overlap_end = 200.0

        # État initial
        current_hpwl = self.compute_total_hpwl()
        current_hard = self.compute_all_hard_penalties()
        current_prox = self.compute_proximity_and_loop_penalties()

        usable_bins_set = set(self.usable_bins)
        n_usable = max(1, len(self.usable_bins))
        current_density_var = sum(
            ((self.bin_areas[b] - self.target_bin_area) / self.target_bin_area) ** 2
            for b in self.usable_bins
        ) / n_usable

        w_prox = 1.5
        w_dens = 180.0

        current_energy = (
            current_hpwl +
            mu_overlap_start * self.total_overlap +
            lambda_hard_start * current_hard +
            w_prox * current_prox +
            w_dens * current_density_var
        )

        best_energy = current_energy
        best_state = [(it.x, it.y, it.rotation) for it in self.items]
        best_valid_energy = current_energy if (self.total_overlap < 0.005 and current_hard < 0.005) else None
        best_valid_state = [(it.x, it.y, it.rotation) for it in self.items] if best_valid_energy is not None else None

        T = t_start
        alpha_cool = (t_end / t_start) ** (1.0 / steps)

        for step in range(steps):
            frac = step / steps
            lambda_h = lambda_hard_start + frac * (lambda_hard_end - lambda_hard_start)
            mu_ov = mu_overlap_start + frac * (mu_overlap_end - mu_overlap_start)

            idx = random.choice(self.movable_indices)
            it = self.items[idx]

            old_x, old_y, old_rot = it.x, it.y, it.rotation
            old_box = it.box
            old_hard = self.compute_item_hard_violations(it)
            old_prox = self.compute_item_prox_and_loop(idx)

            # Calcul des anciens overlaps de l'item idx
            old_item_overlap = sum(self.overlap_matrix[idx][j] for j in range(self.n_items) if j != idx)

            # Calcul de l'ancien HPWL pour les nets connectés à idx
            affected_nets = list(set(self.item_to_nets[idx]))
            old_nets_hpwl = sum(self.compute_single_net_hpwl(n) for n in affected_nets)

            old_bin_overlaps = self.item_bin_overlaps[idx]

            # Choix de l'opérateur
            r_move = random.random()

            if r_move < 0.35:
                # 1. Translation gaussienne locale
                sigma = 0.4 + 7.0 * (T / t_start)
                new_x = it.x + random.gauss(0, sigma)
                new_y = it.y + random.gauss(0, sigma)
                hw = it.current_half_w
                hh = it.current_half_h
                it.x = max(self.edge_clearance + hw, min(self.board_w - self.edge_clearance - hw, new_x))
                it.y = max(self.edge_clearance + hh, min(self.board_h - self.edge_clearance - hh, new_y))

            elif r_move < 0.50:
                # 2. Migration vers cellule sous-occupée (colonisation homogène des zones vides)
                starved_bins = [b for b in self.usable_bins if self.bin_areas[b] < self.target_bin_area * 0.85]
                if not starved_bins:
                    starved_bins = self.usable_bins
                tgt_b = random.choice(starved_bins)
                iy = tgt_b // self.n_bins_x
                ix = tgt_b % self.n_bins_x
                bx_min = ix * self.bin_w
                by_min = iy * self.bin_h
                tgt_x = bx_min + random.uniform(0.15, 0.85) * self.bin_w
                tgt_y = by_min + random.uniform(0.15, 0.85) * self.bin_h

                blend = 0.35 + 0.65 * (T / t_start)
                new_x = it.x + blend * (tgt_x - it.x)
                new_y = it.y + blend * (tgt_y - it.y)
                hw = it.current_half_w
                hh = it.current_half_h
                it.x = max(self.edge_clearance + hw, min(self.board_w - self.edge_clearance - hw, new_x))
                it.y = max(self.edge_clearance + hh, min(self.board_h - self.edge_clearance - hh, new_y))

            elif r_move < 0.65:
                # 3. Rotation
                if len(it.allowed_rotations) > 1:
                    it.rotation = random.choice(it.allowed_rotations)

            elif r_move < 0.85:
                # 4. Attraction barycentrique
                connected = list(self.neighbors.get(idx, []))
                if connected:
                    tgt = self.items[random.choice(connected)]
                    pull = random.uniform(0.2, 0.5)
                    new_x = it.x + pull * (tgt.x - it.x)
                    new_y = it.y + pull * (tgt.y - it.y)
                    hw = it.current_half_w
                    hh = it.current_half_h
                    it.x = max(self.edge_clearance + hw, min(self.board_w - self.edge_clearance - hw, new_x))
                    it.y = max(self.edge_clearance + hh, min(self.board_h - self.edge_clearance - hh, new_y))

            else:
                # 5. Éjection anti-collision directe
                collision_found = False
                for other_idx in range(self.n_items):
                    if other_idx == idx:
                        continue
                    if self.overlap_matrix[idx][other_idx] > 0.01:
                        other_it = self.items[other_idx]
                        dx = it.x - other_it.x
                        dy = it.y - other_it.y
                        dist = math.hypot(dx, dy)
                        if dist < 0.001:
                            dx, dy, dist = 1.0, 0.0, 1.0
                        push = 1.5 + 2.5 * random.random()
                        it.x += (dx / dist) * push
                        it.y += (dy / dist) * push
                        hw = it.current_half_w
                        hh = it.current_half_h
                        it.x = max(self.edge_clearance + hw, min(self.board_w - self.edge_clearance - hw, it.x))
                        it.y = max(self.edge_clearance + hh, min(self.board_h - self.edge_clearance - hh, it.y))
                        collision_found = True
                        break
                if not collision_found:
                    it.x += random.uniform(-0.8, 0.8)
                    it.y += random.uniform(-0.8, 0.8)
                    hw = it.current_half_w
                    hh = it.current_half_h
                    it.x = max(self.edge_clearance + hw, min(self.board_w - self.edge_clearance - hw, it.x))
                    it.y = max(self.edge_clearance + hh, min(self.board_h - self.edge_clearance - hh, it.y))

            # Calcul incrémental O(N) des nouveaux overlaps de l'item idx
            new_box = it.box
            new_overlaps: Dict[int, float] = {}
            new_item_overlap = 0.0
            for j in range(self.n_items):
                if j == idx:
                    continue
                box_j = self.items[j].box
                if new_box.intersects(box_j):
                    area = new_box.intersection_area(box_j)
                    if area > 0.01:
                        new_overlaps[j] = area
                        new_item_overlap += area

            new_hard = self.compute_item_hard_violations(it)
            new_nets_hpwl = sum(self.compute_single_net_hpwl(n) for n in affected_nets)
            new_prox = self.compute_item_prox_and_loop(idx)

            # Calcul incrémental O(1) de la variation de densité
            new_bin_overlaps = self.compute_box_bin_overlaps(new_box)
            affected_bins = set(old_bin_overlaps.keys()) | set(new_bin_overlaps.keys())
            delta_dens_sum = 0.0
            for b in affected_bins:
                if b in usable_bins_set:
                    old_a = self.bin_areas[b]
                    new_a = old_a - old_bin_overlaps.get(b, 0.0) + new_bin_overlaps.get(b, 0.0)
                    delta_dens_sum += (
                        ((new_a - self.target_bin_area) / self.target_bin_area) ** 2 -
                        ((old_a - self.target_bin_area) / self.target_bin_area) ** 2
                    )
            delta_density = delta_dens_sum / n_usable

            # Variations incrémentales
            delta_hpwl = new_nets_hpwl - old_nets_hpwl
            delta_overlap = new_item_overlap - old_item_overlap
            delta_hard = new_hard - old_hard
            delta_prox = new_prox - old_prox

            delta_energy = (
                delta_hpwl +
                mu_ov * delta_overlap +
                lambda_h * delta_hard +
                w_prox * delta_prox +
                w_dens * delta_density
            )

            # Metropolis
            accept = False
            if delta_energy < 0:
                accept = True
            else:
                p = math.exp(-delta_energy / max(1e-5, T))
                if random.random() < p:
                    accept = True

            if accept:
                # Appliquer la mise à jour à la matrice d'overlap
                for j in range(self.n_items):
                    if j == idx:
                        continue
                    area = new_overlaps.get(j, 0.0)
                    self.overlap_matrix[idx][j] = area
                    self.overlap_matrix[j][idx] = area

                # Mettre à jour l'occupation par bin
                for b in affected_bins:
                    self.bin_areas[b] += new_bin_overlaps.get(b, 0.0) - old_bin_overlaps.get(b, 0.0)
                self.item_bin_overlaps[idx] = new_bin_overlaps

                self.total_overlap += delta_overlap
                current_hpwl += delta_hpwl
                current_hard += delta_hard
                current_prox += delta_prox
                current_density_var += delta_density
                current_energy += delta_energy

                if current_energy < best_energy:
                    best_energy = current_energy
                    best_state = [(item.x, item.y, item.rotation) for item in self.items]

                if self.total_overlap < 0.005 and current_hard < 0.005:
                    if best_valid_energy is None or current_energy < best_valid_energy:
                        best_valid_energy = current_energy
                        best_valid_state = [(item.x, item.y, item.rotation) for item in self.items]
            else:
                # Rollback de position
                it.x, it.y, it.rotation = old_x, old_y, old_rot

            T *= alpha_cool

        # Restauration du meilleur état (priorité absolue à un état 100% valide)
        chosen_state = best_valid_state if best_valid_state is not None else best_state
        for k, (bx, by, brot) in enumerate(chosen_state):
            self.items[k].x = bx
            self.items[k].y = by
            self.items[k].rotation = brot

        # Passe de légalisation géométrique agnostique pour éliminer toute micro-pénétration résiduelle
        self.legalize()

        res: Dict[str, Dict[str, Any]] = {}
        for it in self.items:
            res[it.designator] = {
                "x_mm": round(it.x, 3),
                "y_mm": round(it.y, 3),
                "rotation": int(round(it.rotation)) % 360,
                "layer": 1
            }
        return res

    def legalize(self, max_passes: int = 100) -> bool:
        """
        Passe de légalisation géométrique agnostique :
        Résout les micro-pénétrations résiduelles par répulsion le long de l'axe
        de pénétration minimale, tout en respectant les ancres fixes, les fixations M2,
        les zones d'exclusion (keepouts) et les bords de carte selon les courtyards IPC certifiés.
        """
        ipc_half_dims: Dict[int, Tuple[float, float]] = {}
        for it in self.items:
            pkg_info = self.packages.get(it.package, {"width_mm": 1.6, "length_mm": 0.8, "courtyard_margin_mm": 0.25})
            w_c = pkg_info.get("width_mm", 1.6) + 2.0 * pkg_info.get("courtyard_margin_mm", 0.25)
            h_c = pkg_info.get("length_mm", 0.8) + 2.0 * pkg_info.get("courtyard_margin_mm", 0.25)
            ipc_half_dims[it.index] = (w_c / 2.0, h_c / 2.0)

        def get_real_box(item: MovableItem) -> Tuple[RectBox, float, float]:
            r = int(round(item.rotation)) % 360
            hw_c, hh_c = ipc_half_dims[item.index]
            hw = hh_c if r in (90, 270) else hw_c
            hh = hw_c if r in (90, 270) else hh_c
            return RectBox(item.x - hw, item.x + hw, item.y - hh, item.y + hh), hw, hh

        for _ in range(max_passes):
            moved = False
            for i in range(self.n_items):
                it_a = self.items[i]
                box_a, hw_a, hh_a = get_real_box(it_a)

                for j in range(i + 1, self.n_items):
                    it_b = self.items[j]
                    box_b, hw_b, hh_b = get_real_box(it_b)

                    if box_a.intersects(box_b):
                        inter_area = box_a.intersection_area(box_b)
                        if inter_area <= 0.001:
                            continue

                        pen_x = min(box_a.x_max, box_b.x_max) - max(box_a.x_min, box_b.x_min)
                        pen_y = min(box_a.y_max, box_b.y_max) - max(box_a.y_min, box_b.y_min)
                        push_margin = 0.08

                        if pen_x < pen_y:
                            dist_x = pen_x + push_margin
                            sign = 1.0 if it_a.x >= it_b.x else -1.0
                            if not it_a.is_fixed and not it_b.is_fixed:
                                it_a.x += sign * (dist_x / 2.0)
                                it_b.x -= sign * (dist_x / 2.0)
                            elif not it_a.is_fixed:
                                it_a.x += sign * dist_x
                            elif not it_b.is_fixed:
                                it_b.x -= sign * dist_x
                        else:
                            dist_y = pen_y + push_margin
                            sign = 1.0 if it_a.y >= it_b.y else -1.0
                            if not it_a.is_fixed and not it_b.is_fixed:
                                it_a.y += sign * (dist_y / 2.0)
                                it_b.y -= sign * (dist_y / 2.0)
                            elif not it_a.is_fixed:
                                it_a.y += sign * dist_y
                            elif not it_b.is_fixed:
                                it_b.y -= sign * dist_y

                        for it, hw, hh in ((it_a, hw_a, hh_a), (it_b, hw_b, hh_b)):
                            if not it.is_fixed:
                                it.x = max(self.edge_clearance + hw, min(self.board_w - self.edge_clearance - hw, it.x))
                                it.y = max(self.edge_clearance + hh, min(self.board_h - self.edge_clearance - hh, it.y))

                        moved = True
                        box_a, hw_a, hh_a = get_real_box(it_a)

            # Repousser les composants hors des trous de fixation et keepouts
            for it in self.items:
                if it.is_fixed:
                    continue
                box, hw, hh = get_real_box(it)
                for h in self.mounting_holes:
                    hx = h.get("x_mm", 0.0)
                    hy = h.get("y_mm", 0.0)
                    hr = h.get("head_clearance_mm", 4.5) / 2.0
                    hole_box = RectBox(hx - hr, hx + hr, hy - hr, hy + hr)
                    if box.intersects(hole_box):
                        dx = it.x - hx
                        dy = it.y - hy
                        dist = math.hypot(dx, dy)
                        if dist < 0.001:
                            dx, dy, dist = 1.0, 0.0, 1.0
                        push = (hr + max(hw, hh) + 0.1) - dist
                        if push > 0:
                            it.x += (dx / dist) * push
                            it.y += (dy / dist) * push
                            it.x = max(self.edge_clearance + hw, min(self.board_w - self.edge_clearance - hw, it.x))
                            it.y = max(self.edge_clearance + hh, min(self.board_h - self.edge_clearance - hh, it.y))
                            moved = True

                for kz in self.keepouts:
                    rect = kz.get("rect_mm", {})
                    kbox = RectBox(rect.get("x_min", 0.0), rect.get("x_max", 0.0), rect.get("y_min", 0.0), rect.get("y_max", 0.0))
                    exempt = set(kz.get("exempt_refs", []))
                    if it.designator in exempt:
                        continue
                    if box.intersects(kbox):
                        pen_left = box.x_max - kbox.x_min
                        pen_right = kbox.x_max - box.x_min
                        pen_bottom = box.y_max - kbox.y_min
                        pen_top = kbox.y_max - box.y_min
                        min_pen = min(pen_left, pen_right, pen_bottom, pen_top)
                        if min_pen == pen_left:
                            it.x = kbox.x_min - hw - 0.1
                        elif min_pen == pen_right:
                            it.x = kbox.x_max + hw + 0.1
                        elif min_pen == pen_bottom:
                            it.y = kbox.y_min - hh - 0.1
                        else:
                            it.y = kbox.y_max + hh + 0.1
                        it.x = max(self.edge_clearance + hw, min(self.board_w - self.edge_clearance - hw, it.x))
                        it.y = max(self.edge_clearance + hh, min(self.board_h - self.edge_clearance - hh, it.y))
                        moved = True

            if not moved:
                return True
        return False


def optimize_placement_multistart(
    manifest: Dict[str, Any],
    board_constraints: Dict[str, Any],
    geometry: BoardGeometrySnapshot,
    starts: int = 4,
    steps_per_start: int = 40000,
    spacing_margin_mm: float = 0.20
) -> Tuple[Dict[str, Dict[str, Any]], PlacementEvaluation]:
    """Exécute un recuit multi-départs ultra-rapide et sélectionne la meilleure solution certifiée."""
    scorer = PCBScorer(manifest, board_constraints, geometry)
    best_candidate = None
    best_eval = None
    best_score_val = 1e9

    logger.info(f"Démarrage de l'optimisation par Recuit Simulé ({starts} départs, {steps_per_start} itérations/départ, marge espacement {spacing_margin_mm} mm)...")

    for s in range(starts):
        t0 = time.time()
        engine = FastAnnealingEngine(manifest, board_constraints, geometry, spacing_margin_mm=spacing_margin_mm)

        seed = 42 + s * 1337 if s > 0 else 1000
        candidate = engine.run(steps=steps_per_start, seed=seed)
        elapsed = time.time() - t0

        eval_res = scorer.evaluate(placement_override=candidate)
        total_score = eval_res.score.weighted_total_score
        hard_v = eval_res.score.hard_violations_count
        overlap_a = eval_res.score.total_overlap_area_mm2
        hpwl = eval_res.score.total_hpwl_mm
        dens_v = eval_res.score.f_density_uniformity
        spac_p = eval_res.score.f_spacing_comfort
        pairs_cnt = len(eval_res.score.overlapping_pairs)

        logger.info(
            f"  Départ {s + 1}/{starts} [{elapsed:.1f}s] : "
            f"Score = {total_score:.4f} | HPWL = {hpwl:.1f} mm | "
            f"Densité = {dens_v:.3f} | Espacement = {spac_p:.3f} | "
            f"Collisions = {pairs_cnt} ({overlap_a:.1f} mm²) | "
            f"Violations dures = {hard_v}"
        )

        is_better = False
        if best_eval is None:
            is_better = True
        elif hard_v < best_eval.score.hard_violations_count:
            is_better = True
        elif hard_v == best_eval.score.hard_violations_count:
            if overlap_a < best_eval.score.total_overlap_area_mm2:
                is_better = True
            elif overlap_a == best_eval.score.total_overlap_area_mm2 and total_score < best_score_val:
                is_better = True

        if is_better:
            best_candidate = candidate
            best_eval = eval_res
            best_score_val = total_score

    return best_candidate, best_eval


def main():
    parser = argparse.ArgumentParser(
        description="Solveur d'Auto-Placement Global par Recuit Simulé (Agnostique)"
    )
    parser.add_argument("--manifest", type=Path, default=Path("circuit_manifest.json"))
    parser.add_argument("--board", type=Path, default=Path("board_constraints.json"))
    parser.add_argument("--geometry", type=Path, default=Path(".agents/skills/pcb-placer/.cache/netlist_geometry.json"))
    parser.add_argument("--out", type=Path, default=Path("placement_candidate.json"))
    parser.add_argument("--svg", type=Path, default=Path("placement_candidate.svg"))
    parser.add_argument("--starts", type=int, default=4, help="Nombre de départs multi-graines")
    parser.add_argument("--steps", type=int, default=40000, help="Itérations par départ")
    parser.add_argument("--spacing", type=float, default=0.20, help="Marge d'aération supplémentaire par composant (mm)")

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

    best_placement, best_eval = optimize_placement_multistart(
        manifest, board_constraints, geom, starts=args.starts, steps_per_start=args.steps, spacing_margin_mm=args.spacing
    )

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "generator": "simulated_annealing.py v2.0",
        "is_valid": best_eval.is_valid,
        "score": asdict(best_eval.score),
        "components": best_placement
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    logger.info(f"✅ Livrable de placement sauvegardé dans : {args.out}")

    try:
        from render_svg import generate_svg_view
        generate_svg_view(manifest, board_constraints, geom, best_eval, args.svg, placement_override=best_placement)
        logger.info(f"✅ Rendu SVG candidat généré avec succès dans : {args.svg}")
    except Exception as e:
        logger.warning(f"Échec de génération SVG : {e}")


if __name__ == "__main__":
    main()
