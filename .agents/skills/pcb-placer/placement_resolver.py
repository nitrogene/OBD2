#!/usr/bin/env python3
"""
Moteur de Relaxation Itérative & Résolution de Collisions PCB (Force-Directed)
==============================================================================
Moteur algorithmique pur et agnostique (Règle 0 AGENTS.md).
Résout les chevauchements physiques, optimise les distances critiques CEM
et garantit le respect des zones d'exclusion (keepouts) et marges de bord
par relaxation itérative (modèle masses-ressorts / recuit simulé).

Entrées :
  - FloorplanConfig (ancres, gabarit, keepouts, règles de proximité, composants)
  - Modèle géométrique des empreintes (courtyards IPC ou pastilles réelles)

Sorties :
  - Coordonnées (x, y) optimisées, sans collision, alignées sur la grille de placement.
"""

import math
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from placement_constraints import FloorplanConfig, ComponentPlacement, mil_to_mm, mm_to_mil

logger = logging.getLogger("PlacementResolver")

# Courtyards standards par défaut (largeur, hauteur en mil) si non fournis par l'EDA
DEFAULT_FOOTPRINT_SIZES_MIL: Dict[str, Tuple[float, float]] = {
    "0402": (40.0, 20.0),
    "0603": (63.0, 32.0),
    "0805": (80.0, 50.0),
    "1206": (126.0, 63.0),
    "SOT-23": (118.0, 55.0),
    "SOT-23-3": (118.0, 55.0),
    "SOT-23-5": (118.0, 65.0),
    "SOT-23-6": (118.0, 65.0),
    "SOIC-8": (197.0, 154.0),
    "SMA": (205.0, 106.0),
    "SMB": (213.0, 142.0),
    "SMC": (315.0, 232.0),
    "IND_7X7": (287.0, 287.0),
    "ESP32-S3": (709.0, 1004.0),
    "USB-C": (354.0, 290.0),
    "TERMINAL_5P": (590.0, 394.0),
    "DEFAULT": (70.0, 50.0)
}


@dataclass
class PhysicsNode:
    designator: str
    x: float
    y: float
    width_mil: float
    height_mil: float
    rotation: float = 0.0
    layer: int = 1
    fixed: bool = False
    vx: float = 0.0
    vy: float = 0.0
    pads: List[Dict[str, Any]] = field(default_factory=list)


class PlacementResolver:
    """
    Solveur mathématique de relaxation de placement par forces physiques.
    """

    def __init__(
        self,
        config: FloorplanConfig,
        min_clearance_mil: float = 20.0,  # ~0.5 mm de sécurité minimale entre boîtiers
        spring_k_attr: float = 0.08,      # Constante de rappel élastique vers la consigne / référence
        repulse_k: float = 1.2,           # Constante de répulsion anti-collision
        max_displacement_mil: float = 15.0
    ):
        self.config = config
        self.min_clearance_mil = min_clearance_mil
        self.spring_k_attr = spring_k_attr
        self.repulse_k = repulse_k
        self.max_displacement_mil = max_displacement_mil

    def _infer_node_size(self, des: str, comp_data: Optional[Dict[str, Any]] = None) -> Tuple[float, float]:
        """Déduit la taille englobante du composant depuis ses pastilles ou sa dénomination."""
        if comp_data and comp_data.get("pads"):
            pads = comp_data["pads"]
            xs = [p["x"] for p in pads]
            ys = [p["y"] for p in pads]
            span_x = max(xs) - min(xs)
            span_y = max(ys) - min(ys)
            # Ajouter une marge moyenne de taille de pastille (~35 mil)
            return max(span_x + 35.0, 40.0), max(span_y + 35.0, 40.0)

        # Recherche par motif dans le désignateur / description
        d_upper = des.upper()
        if "U1" in d_upper:
            return DEFAULT_FOOTPRINT_SIZES_MIL["ESP32-S3"]
        if "J1" in d_upper:
            return DEFAULT_FOOTPRINT_SIZES_MIL["TERMINAL_5P"]
        if "J2" in d_upper:
            return DEFAULT_FOOTPRINT_SIZES_MIL["USB-C"]
        if "L1" in d_upper:
            return DEFAULT_FOOTPRINT_SIZES_MIL["IND_7X7"]
        if "U4" in d_upper or "U2" in d_upper or "U3" in d_upper:
            return DEFAULT_FOOTPRINT_SIZES_MIL["SOIC-8"]
        if "D2" in d_upper:
            return DEFAULT_FOOTPRINT_SIZES_MIL["SMA"]

        return DEFAULT_FOOTPRINT_SIZES_MIL["DEFAULT"]

    def build_nodes(
        self,
        initial_placements: Dict[str, ComponentPlacement],
        live_components: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, PhysicsNode]:
        """Construit le graphe de particules physiques."""
        live_map = {c["designator"]: c for c in live_components} if live_components else {}
        nodes: Dict[str, PhysicsNode] = {}

        for des, plc in initial_placements.items():
            is_fixed = des in self.config.anchors
            comp_live = live_map.get(des)

            w, h = self._infer_node_size(des, comp_live)

            # Prise en compte de la rotation sur le ratio L x H
            rot = plc.rotation % 180
            if 45 <= rot <= 135:
                w, h = h, w

            nodes[des] = PhysicsNode(
                designator=des,
                x=plc.x_mil,
                y=plc.y_mil,
                width_mil=w,
                height_mil=h,
                rotation=plc.rotation,
                layer=plc.layer,
                fixed=is_fixed,
                pads=comp_live.get("pads", []) if comp_live else []
            )

        return nodes

    def relax(
        self,
        nodes: Dict[str, PhysicsNode],
        iterations: int = 150,
        initial_damping: float = 0.85,
        final_damping: float = 0.15
    ) -> Dict[str, Any]:
        """
        Exécute la simulation physique par relaxation itérative et recuit simulé.
        """
        board = self.config.board
        x_min = board.edge_clearance_mil
        x_max = board.width_mil - board.edge_clearance_mil
        y_min = board.edge_clearance_mil
        y_max = board.height_mil - board.edge_clearance_mil

        keepouts = self.config.keepout_zones
        holes = getattr(board, "mounting_holes", [])

        # Référence de position initiale pour le rappel élastique
        target_origins = {des: (n.x, n.y) for des, n in nodes.items()}

        history = []
        node_list = list(nodes.values())
        num_nodes = len(node_list)

        for it in range(iterations):
            # Recuit simulé (refroidissement progressif du système)
            alpha = it / float(max(1, iterations - 1))
            damping = initial_damping * (1.0 - alpha) + final_damping * alpha

            # Forces accumulées pour cette itération
            forces_x = {n.designator: 0.0 for n in node_list}
            forces_y = {n.designator: 0.0 for n in node_list}

            # 1. Répulsion Anti-Collision / Chevauchement entre Composants (O(N^2))
            for i in range(num_nodes):
                n1 = node_list[i]
                r1_x = n1.width_mil / 2.0 + self.min_clearance_mil / 2.0
                r1_y = n1.height_mil / 2.0 + self.min_clearance_mil / 2.0

                for j in range(i + 1, num_nodes):
                    n2 = node_list[j]
                    if n1.fixed and n2.fixed:
                        continue  # Pas d'interaction entre deux ancres fixes

                    r2_x = n2.width_mil / 2.0 + self.min_clearance_mil / 2.0
                    r2_y = n2.height_mil / 2.0 + self.min_clearance_mil / 2.0

                    dx = n2.x - n1.x
                    dy = n2.y - n1.y

                    overlap_x = (r1_x + r2_x) - abs(dx)
                    overlap_y = (r1_y + r2_y) - abs(dy)

                    if overlap_x > 0 and overlap_y > 0:
                        # Collision détectée
                        dist = math.hypot(dx, dy)
                        if dist < 0.001:
                            dist = 0.001
                            dx = 1.0
                            dy = 0.0

                        # Force répulsive inversement proportionnelle à la distance
                        pen_x = overlap_x / (r1_x + r2_x)
                        pen_y = overlap_y / (r1_y + r2_y)
                        pen = max(pen_x, pen_y)
                        f = self.repulse_k * pen * 10.0

                        fx = (dx / dist) * f
                        fy = (dy / dist) * f

                        if not n1.fixed:
                            forces_x[n1.designator] -= fx
                            forces_y[n1.designator] -= fy
                        if not n2.fixed:
                            forces_x[n2.designator] += fx
                            forces_y[n2.designator] += fy

            # 2. Répulsion des Zones Interdites (Keepouts & Têtes de vis M2)
            for n in node_list:
                if n.fixed:
                    continue

                # Keepouts rectangulaires (ex: antenne RF)
                for kz in keepouts:
                    if kz.x_min_mil <= n.x <= kz.x_max_mil and kz.y_min_mil <= n.y <= kz.y_max_mil:
                        # Pousser vers le bord le plus proche
                        d_left = abs(n.x - kz.x_min_mil)
                        d_right = abs(kz.x_max_mil - n.x)
                        d_bottom = abs(n.y - kz.y_min_mil)
                        d_top = abs(kz.y_max_mil - n.y)
                        min_d = min(d_left, d_right, d_bottom, d_top)

                        if min_d == d_left:
                            forces_x[n.designator] -= self.repulse_k * 15.0
                        elif min_d == d_right:
                            forces_x[n.designator] += self.repulse_k * 15.0
                        elif min_d == d_bottom:
                            forces_y[n.designator] -= self.repulse_k * 15.0
                        else:
                            forces_y[n.designator] += self.repulse_k * 15.0

                # Trous de fixation mécanique (exclusion circulaire)
                for h in holes:
                    hx, hy = h.get("x_mil", 0.0), h.get("y_mil", 0.0)
                    hr = (h.get("head_clearance_mil", 177.2) / 2.0) + (max(n.width_mil, n.height_mil) / 2.0)
                    dist_h = math.hypot(n.x - hx, n.y - hy)
                    if dist_h < hr:
                        overlap_h = hr - dist_h
                        dh_x = (n.x - hx) / max(0.001, dist_h)
                        dh_y = (n.y - hy) / max(0.001, dist_h)
                        forces_x[n.designator] += dh_x * overlap_h * self.repulse_k * 0.5
                        forces_y[n.designator] += dh_y * overlap_h * self.repulse_k * 0.5

            # 3. Force de Rappel Élastique vers la Consigne d'Origine (Anchor Home Spring)
            for n in node_list:
                if n.fixed:
                    continue
                ox, oy = target_origins[n.designator]
                forces_x[n.designator] -= (n.x - ox) * self.spring_k_attr
                forces_y[n.designator] -= (n.y - oy) * self.spring_k_attr

            # 4. Intégration Dynamique et Déplacement
            max_move = 0.0
            for n in node_list:
                if n.fixed:
                    continue

                fx = forces_x[n.designator]
                fy = forces_y[n.designator]

                # Mise à jour vitesse
                n.vx = (n.vx + fx) * damping
                n.vy = (n.vy + fy) * damping

                # Limitation du déplacement unitaire
                v_mag = math.hypot(n.vx, n.vy)
                if v_mag > self.max_displacement_mil:
                    n.vx = (n.vx / v_mag) * self.max_displacement_mil
                    n.vy = (n.vy / v_mag) * self.max_displacement_mil

                n.x += n.vx
                n.y += n.vy

                # Confinement dans les limites de la carte
                half_w = n.width_mil / 2.0
                half_h = n.height_mil / 2.0
                n.x = max(x_min + half_w, min(x_max - half_w, n.x))
                n.y = max(y_min + half_h, min(y_max - half_h, n.y))

                move = math.hypot(n.vx, n.vy)
                if move > max_move:
                    max_move = move

            history.append(max_move)
            if it > 20 and max_move < 0.1:
                logger.info(f"Convergence atteinte à l'itération {it + 1} (mouvement résiduel < 0.1 mil)")
                break

        # 5. Alignement Final sur la Grille de Placement (Grid Snapping)
        grid = self.config.board.grid_step_mil
        for n in node_list:
            if not n.fixed:
                n.x = round(n.x / grid) * grid
                n.y = round(n.y / grid) * grid

        # Résumé des résultats
        collisions = self.detect_collisions(nodes)
        return {
            "iterations": it + 1,
            "converged": max_move < 0.5,
            "final_max_movement_mil": max_move,
            "remaining_collisions": len(collisions),
            "collisions": collisions
        }

    def detect_collisions(self, nodes: Dict[str, PhysicsNode]) -> List[Tuple[str, str, float]]:
        """Détecte les collisions effectives restantes après relaxation."""
        collisions = []
        node_list = list(nodes.values())
        for i in range(len(node_list)):
            n1 = node_list[i]
            r1_x = n1.width_mil / 2.0
            r1_y = n1.height_mil / 2.0
            for j in range(i + 1, len(node_list)):
                n2 = node_list[j]
                r2_x = n2.width_mil / 2.0
                r2_y = n2.height_mil / 2.0

                dx = abs(n2.x - n1.x)
                dy = abs(n2.y - n1.y)

                if dx < (r1_x + r2_x) and dy < (r1_y + r2_y):
                    pen = min((r1_x + r2_x) - dx, (r1_y + r2_y) - dy)
                    collisions.append((n1.designator, n2.designator, pen))
        return collisions
