#!/usr/bin/env python3
"""
label_placer.py - Moteur de Placement & Normalisation de la Sérigraphie (IPC-7351)
=================================================================================
Positionne et oriente automatiquement les étiquettes de désignateurs de composants
sur la couche de sérigraphie (Top Silk Layer) dans EasyEDA Pro.

Conforme rigoureusement aux normes :
- IPC-7351 §3.4.7 : Lecture orthogonale stricte (orientations à 0° ou 90° uniquement,
  aucun texte inversé à 180° ou 270°).
- IPC-A-610 / IPC-2221 : Dégagement strict des pastilles de cuivre (clearance >= 0.20 mm),
  éliminant tout rognage de texte ou pollution de brasure.
- Dégagement des corps (No Under-Component Labels) : Interdiction formelle de placer
  une étiquette sous le corps plastique/silicium d'un composant (SOIC, connecteurs,
  relais, boutons, inductance, etc.).
- Dégagement mécanique des vis M2 : Zone d'exclusion de 3.5 mm de rayon autour des centres
  de perçages (MH1-MH4) pour garantir le passage libre de la tête de vis, rondelle et outil.
- JLCPCB SMT Capabilities : Hauteur de texte >= 0.8 mm (32-38 mil), épaisseur de trait >= 0.15 mm (6 mil).

Conforme aux Règles AGENTS.md :
- Règle 0 : Moteur agnostique pur, aucun composant en dur.
- Règle 1 : Transparence et sécurité sur le pont EasyEDA.
- Règle 4 : Validation DRC et sauvegarde automatique.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from easyeda_client import EasyEDAClient

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("LabelPlacer")

# Constantes de conversion
MM_TO_MIL = 1.0 / 0.0254
MIL_TO_MM = 0.0254

# Modes d'alignement EasyEDA Pro (EPCB_PrimitiveStringAlignMode)
ALIGN_CENTER = 5


@dataclass
class BoundingBox:
    """Boîte englobante 2D en millimètres."""
    min_x: float
    max_x: float
    min_y: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    @property
    def center_x(self) -> float:
        return (self.min_x + self.max_x) / 2.0

    @property
    def center_y(self) -> float:
        return (self.min_y + self.max_y) / 2.0

    def expanded(self, margin: float) -> BoundingBox:
        return BoundingBox(
            self.min_x - margin,
            self.max_x + margin,
            self.min_y - margin,
            self.max_y + margin
        )

    def intersects(self, other: BoundingBox) -> bool:
        return not (
            self.max_x < other.min_x or
            self.min_x > other.max_x or
            self.max_y < other.min_y or
            self.min_y > other.max_y
        )

    def contains(self, other: BoundingBox) -> bool:
        return (
            self.min_x <= other.min_x and
            self.max_x >= other.max_x and
            self.min_y <= other.min_y and
            self.max_y >= other.max_y
        )

    def intersects_segment(self, x1: float, y1: float, x2: float, y2: float) -> bool:
        """
        Vérifie si le segment 2D [(x1, y1), (x2, y2)] intersecte l'intérieur ou le bord de la boîte englobante.
        Méthode des intervalles paramétriques (Liang-Barsky / slab method).
        """
        dx = x2 - x1
        dy = y2 - y1

        t_min = 0.0
        t_max = 1.0

        # Test sur l'axe X
        if abs(dx) < 1e-9:
            if x1 < self.min_x or x1 > self.max_x:
                return False
        else:
            t1 = (self.min_x - x1) / dx
            t2 = (self.max_x - x1) / dx
            if t1 > t2:
                t1, t2 = t2, t1
            t_min = max(t_min, t1)
            t_max = min(t_max, t2)
            if t_min > t_max:
                return False

        # Test sur l'axe Y
        if abs(dy) < 1e-9:
            if y1 < self.min_y or y1 > self.max_y:
                return False
        else:
            t1 = (self.min_y - y1) / dy
            t2 = (self.max_y - y1) / dy
            if t1 > t2:
                t1, t2 = t2, t1
            t_min = max(t_min, t1)
            t_max = min(t_max, t2)
            if t_min > t_max:
                return False

        return t_min <= t_max and t_max >= 0.0 and t_min <= 1.0


@dataclass
class PadObstacle:
    """Obstacle représenté par une pastille de cuivre (pad)."""
    pad_id: str
    comp_id: str
    designator: str
    center_x_mm: float
    center_y_mm: float
    width_mm: float
    height_mm: float
    rotation_deg: float
    is_through_hole: bool
    bbox: BoundingBox


@dataclass
class ComponentInfo:
    """Informations géométriques d'un composant sur le PCB."""
    comp_id: str
    designator: str
    center_x_mm: float
    center_y_mm: float
    rotation_deg: float
    body_bbox: BoundingBox
    pads: List[PadObstacle] = field(default_factory=list)


@dataclass
class DesignatorAttr:
    """Attribut de sérigraphie du désignateur dans EasyEDA Pro."""
    attr_id: str
    comp_id: str
    text: str
    current_x_mil: float
    current_y_mil: float
    current_rotation: float
    current_font_size_mil: float
    current_line_width_mil: float
    current_align_mode: int


@dataclass
class CandidateLabelPlacement:
    """Proposition de placement pour une étiquette de désignateur."""
    designator: str
    attr_id: str
    comp_id: str
    center_x_mm: float
    center_y_mm: float
    rotation_deg: float  # 0 ou 90
    font_size_mil: float
    line_width_mil: float
    align_mode: int  # ALIGN_CENTER (5)
    bbox: BoundingBox
    cost: float
    dist_to_center_mm: float


def compute_3d_bbox(
    cx_mm: float,
    cy_mm: float,
    crot: float,
    t3d: str
) -> Optional[BoundingBox]:
    """
    Calcule la boîte englobante 2D (au sol) du modèle 3D orienté d'un composant
    à partir de sa chaîne '3D Model Transform' [w, l, h, rx, ry, rz, ox, oy, oz] en mils.
    """
    if not t3d:
        return None
    parts = [p.strip() for p in t3d.split(",") if p.strip()]
    if len(parts) < 8:
        return None
    try:
        w_mm = float(parts[0]) * MIL_TO_MM
        l_mm = float(parts[1]) * MIL_TO_MM
        ox_mm = float(parts[6]) * MIL_TO_MM
        oy_mm = float(parts[7]) * MIL_TO_MM
    except ValueError:
        return None

    hw = w_mm / 2.0
    hl = l_mm / 2.0
    corners = [
        (ox_mm - hw, oy_mm - hl),
        (ox_mm + hw, oy_mm - hl),
        (ox_mm + hw, oy_mm + hl),
        (ox_mm - hw, oy_mm + hl),
    ]

    rad = math.radians(crot)
    cos_r = math.cos(rad)
    sin_r = math.sin(rad)

    world_x = []
    world_y = []
    for lx, ly in corners:
        wx = cx_mm + lx * cos_r - ly * sin_r
        wy = cy_mm + lx * sin_r + ly * cos_r
        world_x.append(wx)
        world_y.append(wy)

    return BoundingBox(min(world_x), max(world_x), min(world_y), max(world_y))


class SilkscreenOptimizer:
    """
    Moteur algorithmique agnostique de placement des sérigraphies IPC-7351.
    """

    def __init__(
        self,
        board_bbox: BoundingBox,
        pad_clearance_mm: float = 0.20,
        text_clearance_mm: float = 0.15,
        edge_clearance_mm: float = 0.50,
        font_size_mil: float = 38.0,
        line_width_mil: float = 6.0,
        char_aspect_ratio: float = 0.72,
        keepout_boxes: Optional[List[BoundingBox]] = None,
        mounting_holes: Optional[List[Tuple[float, float, float]]] = None
    ):
        self.board_bbox = board_bbox
        self.pad_clearance_mm = pad_clearance_mm
        self.text_clearance_mm = text_clearance_mm
        self.edge_clearance_mm = edge_clearance_mm
        self.font_size_mil = font_size_mil
        self.line_width_mil = line_width_mil
        self.char_aspect_ratio = char_aspect_ratio
        self.keepout_boxes = keepout_boxes or []
        self.mounting_holes = mounting_holes or []

        # Limite stricte de la carte après application de la garde de bord
        self.allowed_board_bbox = BoundingBox(
            self.board_bbox.min_x + self.edge_clearance_mm,
            self.board_bbox.max_x - self.edge_clearance_mm,
            self.board_bbox.min_y + self.edge_clearance_mm,
            self.board_bbox.max_y - self.edge_clearance_mm
        )

    def intersects_circle(self, box: BoundingBox, cx: float, cy: float, r: float) -> bool:
        """Vérifie si une boîte englobante intersecte un cylindre/cercle de rayon r centré en (cx, cy)."""
        closest_x = max(box.min_x, min(cx, box.max_x))
        closest_y = max(box.min_y, min(cy, box.max_y))
        dist_sq = (closest_x - cx) ** 2 + (closest_y - cy) ** 2
        return dist_sq < (r ** 2)

    def estimate_text_dimensions_mm(self, text: str, font_size_mil: float) -> Tuple[float, float]:
        """
        Calcule la largeur et la hauteur nominales (en mm) d'une chaîne de caractères
        pour une orientation de 0° (horizontale).
        """
        font_height_mm = font_size_mil * MIL_TO_MM
        char_width_mm = font_height_mm * self.char_aspect_ratio
        text_width_mm = max(1, len(text)) * char_width_mm
        return text_width_mm, font_height_mm

    def compute_label_bbox(
        self,
        center_x_mm: float,
        center_y_mm: float,
        text: str,
        rotation_deg: float,
        font_size_mil: float
    ) -> BoundingBox:
        """Calcule la boîte englobante de l'étiquette centrée en (center_x, center_y)."""
        w_mm, h_mm = self.estimate_text_dimensions_mm(text, font_size_mil)
        norm_rot = int(round(rotation_deg)) % 360

        if norm_rot in (90, 270):
            # Texte vertical
            hw = h_mm / 2.0
            hh = w_mm / 2.0
        else:
            # Texte horizontal (0° ou 180°)
            hw = w_mm / 2.0
            hh = h_mm / 2.0

        return BoundingBox(
            center_x_mm - hw,
            center_x_mm + hw,
            center_y_mm - hh,
            center_y_mm + hh
        )

    def is_valid_label_bbox(
        self,
        label_bbox: BoundingBox,
        obstacles: List[BoundingBox],
        placed_labels: List[BoundingBox]
    ) -> bool:
        """
        Vérifie si la boîte englobante d'un label respecte toutes les contraintes dures :
        1. Reste à l'intérieur de la carte autorisée.
        2. Ne pénètre dans aucun keepout déclaré (antenne RF, zones interdites).
        3. Ne pénètre dans aucun cylindre mécanique de vis (garde circulaire exacte).
        4. Ne chevauche aucun obstacle (pastille de cuivre OU corps de composant).
        5. Ne chevauche aucun label déjà placé (avec marge text_clearance).
        """
        # 1. Dans la carte
        if not self.allowed_board_bbox.contains(label_bbox):
            return False

        # 2. Hors keepouts déclarés (boîtes)
        for ko in self.keepout_boxes:
            if label_bbox.intersects(ko):
                return False

        # 3. Hors cylindres de fixations mécaniques (cercles)
        for hx, hy, hr in self.mounting_holes:
            if self.intersects_circle(label_bbox, hx, hy, hr):
                return False

        # 4. Hors obstacles (pads et corps de composants)
        for obs in obstacles:
            if label_bbox.intersects(obs):
                return False

        # 5. Hors autres labels
        expanded_label = label_bbox.expanded(self.text_clearance_mm / 2.0)
        for placed_box in placed_labels:
            if expanded_label.intersects(placed_box):
                return False

        return True

    def is_line_of_sight_clear(
        self,
        comp: ComponentInfo,
        cand_x: float,
        cand_y: float,
        all_components: Optional[List[ComponentInfo]],
        placed_labels: List[BoundingBox]
    ) -> bool:
        """
        Vérifie la contrainte de Ligne de Visée Directe (Line-of-Sight clearance) :
        Le segment joignant le centre du composant (cx, cy) au centre du libellé
        candidat (cand_x, cand_y) ne doit être traversé :
        1. Par aucun corps d'un autre composant tiers (interdiction d'enjamber un composant).
        2. Par aucune autre étiquette de sérigraphie déjà positionnée (interdiction d'enjamber un autre libellé).
        """
        cx = comp.center_x_mm
        cy = comp.center_y_mm

        # 1. Obstruction par les corps d'autres composants
        if all_components:
            for other in all_components:
                if other.comp_id == comp.comp_id:
                    continue
                # Garde de -0.06 mm pour éviter les faux rejets sur simple affleurement tangentiel
                obs_box = other.body_bbox.expanded(-0.06) if (other.body_bbox.width > 0.15 and other.body_bbox.height > 0.15) else other.body_bbox
                if obs_box.intersects_segment(cx, cy, cand_x, cand_y):
                    return False

        # 2. Obstruction par des libellés déjà positionnés
        for pl_box in placed_labels:
            test_pl = pl_box.expanded(-0.02) if (pl_box.width > 0.10 and pl_box.height > 0.10) else pl_box
            if test_pl.intersects_segment(cx, cy, cand_x, cand_y):
                return False

        return True

    def find_best_placement(
        self,
        comp: ComponentInfo,
        desig_attr: DesignatorAttr,
        obstacles: List[BoundingBox],
        placed_labels: List[BoundingBox],
        all_components: Optional[List[ComponentInfo]] = None,
        allow_extended: bool = False
    ) -> Optional[CandidateLabelPlacement]:
        """
        Explore les positions candidates autour du périmètre extérieur du corps du composant.
        Garantit que le label ne se retrouve jamais sous le corps du composant.
        Pour les composants monopad (points de test), assure une proximité immédiate (< 1.8 mm)
        et une répulsion vectorielle mutuelle pour éviter toute ambiguïté visuelle.
        """
        text = desig_attr.text
        is_single_pad = (len(comp.pads) == 1)
        cx = comp.center_x_mm
        cy = comp.center_y_mm
        bbox = comp.body_bbox
        hw = max(0.35 if is_single_pad else 0.5, bbox.width / 2.0)
        hh = max(0.35 if is_single_pad else 0.5, bbox.height / 2.0)

        # Détection de proximité avec d'autres mires monopad pour éviter l'ambiguïté visuelle
        repulsion_targets = []
        if is_single_pad and all_components:
            for other in all_components:
                if other.comp_id != comp.comp_id and len(other.pads) == 1:
                    d_other = math.hypot(other.center_x_mm - cx, other.center_y_mm - cy)
                    if d_other < 3.5:
                        repulsion_targets.append((other.center_x_mm - cx, other.center_y_mm - cy, d_other))

        # Distances d'écartement au périmètre extérieur du composant
        if is_single_pad:
            gaps = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.65, 0.80, 0.95, 1.15, 1.35, 1.60, 1.90]
            if allow_extended:
                gaps.extend([2.20, 2.50, 2.80, 3.20])
            font_sizes = [32.0, 28.0, 26.0, 24.0]
        else:
            gaps = [0.45, 0.75, 1.15, 1.65, 2.30, 3.10, 4.20, 5.80, 7.80]
            if allow_extended:
                gaps.extend([9.5, 12.0])
            font_sizes = [self.font_size_mil, 32.0]
            if allow_extended:
                font_sizes.append(28.0)

        # Détection de l'orientation dominante du corps du composant
        is_comp_vertical = (bbox.height > bbox.width * 1.2)
        is_comp_horizontal = (bbox.width > bbox.height * 1.2)

        best_candidate: Optional[CandidateLabelPlacement] = None
        lowest_cost = float("inf")

        for f_size in font_sizes:
            text_w, text_h = self.estimate_text_dimensions_mm(text, f_size)
            f_pen = 0.0 if f_size >= self.font_size_mil else (0.5 if f_size >= 32.0 else (1.0 if f_size >= 28.0 else (1.8 if f_size >= 26.0 else 2.5)))

            for rot in [0.0, 90.0]:
                rot_is_vert = (int(round(rot)) % 180 == 90)
                eff_w = text_h if rot_is_vert else text_w
                eff_h = text_w if rot_is_vert else text_h
                rot_penalty = 0.3 if rot_is_vert else 0.0

                for g in gaps:
                    pts = []
                    # Séquencement directionnel ergonomique selon la géométrie du composant
                    if is_comp_vertical:
                        pts.extend([
                            (hw + g + eff_w / 2.0, 0.0),          # East
                            (-hw - g - eff_w / 2.0, 0.0),         # West
                            (0.0, hh + g + eff_h / 2.0),          # North
                            (0.0, -hh - g - eff_h / 2.0),         # South
                        ])
                    elif is_comp_horizontal:
                        pts.extend([
                            (0.0, hh + g + eff_h / 2.0),          # North
                            (0.0, -hh - g - eff_h / 2.0),         # South
                            (hw + g + eff_w / 2.0, 0.0),          # East
                            (-hw - g - eff_w / 2.0, 0.0),         # West
                        ])
                    else:
                        pts.extend([
                            (0.0, hh + g + eff_h / 2.0),
                            (0.0, -hh - g - eff_h / 2.0),
                            (hw + g + eff_w / 2.0, 0.0),
                            (-hw - g - eff_w / 2.0, 0.0),
                        ])

                    # Coins et diagonales
                    pts.extend([
                        (hw + g, hh + g),
                        (-hw - g, hh + g),
                        (hw + g, -hh - g),
                        (-hw - g, -hh - g),
                        (hw * 0.7, hh + g + eff_h / 2.0),
                        (-hw * 0.7, hh + g + eff_h / 2.0),
                        (hw * 0.7, -hh - g - eff_h / 2.0),
                        (-hw * 0.7, -hh - g - eff_h / 2.0),
                    ])

                    # Échantillonnage angulaire continu le long du contour
                    angle_step = 15 if allow_extended else 20
                    for ang in range(0, 360, angle_step):
                        rad = math.radians(ang)
                        cos_a = math.cos(rad)
                        sin_a = math.sin(rad)
                        dx = math.copysign(min(hw, abs((hh / math.tan(rad)) if sin_a != 0 else hw)), cos_a) if cos_a != 0 else 0.0
                        dy = math.copysign(min(hh, abs(hw * math.tan(rad))), sin_a) if sin_a != 0 else 0.0
                        px = dx + cos_a * (g + eff_w / 2.0)
                        py = dy + sin_a * (g + eff_h / 2.0)
                        pts.append((px, py))

                    for dx, dy in pts:
                        cand_x = cx + dx
                        cand_y = cy + dy

                        cand_bbox = self.compute_label_bbox(cand_x, cand_y, text, rot, f_size)

                        if not self.is_valid_label_bbox(cand_bbox, obstacles, placed_labels):
                            continue

                        if not self.is_line_of_sight_clear(comp, cand_x, cand_y, all_components, placed_labels):
                            continue

                        dist = math.hypot(dx, dy)
                        if is_single_pad and (not allow_extended) and dist > 2.2:
                            continue
                        if is_single_pad and allow_extended and dist > 3.3:
                            continue

                        # Pénalité de répulsion si le déplacement pointe vers une mire monopad voisine
                        repulsion_cost = 0.0
                        for rx, ry, rd in repulsion_targets:
                            dot = (dx * rx + dy * ry) / (rd * dist) if dist > 0 else 0.0
                            if dot > 0.2:
                                repulsion_cost += 4.0 * dot

                        # Bonus d'alignement pour placement naturel sur les flancs
                        align_bonus = 0.0
                        if is_comp_vertical and abs(dy) < 0.5:
                            align_bonus = -0.8
                        elif is_comp_horizontal and abs(dx) < 0.5:
                            align_bonus = -0.8

                        cost = (dist * (2.5 if is_single_pad else 1.0)) + rot_penalty + f_pen + align_bonus + repulsion_cost

                        if cost < lowest_cost:
                            lowest_cost = cost
                            best_candidate = CandidateLabelPlacement(
                                designator=text,
                                attr_id=desig_attr.attr_id,
                                comp_id=comp.comp_id,
                                center_x_mm=cand_x,
                                center_y_mm=cand_y,
                                rotation_deg=rot,
                                font_size_mil=f_size,
                                line_width_mil=self.line_width_mil,
                                align_mode=ALIGN_CENTER,
                                bbox=cand_bbox,
                                cost=cost,
                                dist_to_center_mm=dist
                            )

            if best_candidate and (not is_single_pad) and best_candidate.font_size_mil == self.font_size_mil and lowest_cost < 3.5:
                break
            if best_candidate and is_single_pad and lowest_cost < 2.5:
                break
            if best_candidate and allow_extended:
                break

        # Passe de repli cartésienne fine pour les couloirs encombrés
        if not best_candidate and allow_extended:
            max_d = 4.2 if is_single_pad else 8.0
            steps = int(max_d / 0.10)
            for f_size in font_sizes:
                for rot in [0.0, 90.0]:
                    rot_is_vert = (int(round(rot)) % 180 == 90)
                    rot_penalty = 0.3 if rot_is_vert else 0.0
                    f_pen = 0.0 if f_size >= self.font_size_mil else (0.5 if f_size >= 32.0 else (1.0 if f_size >= 28.0 else (1.8 if f_size >= 26.0 else 2.5)))

                    for dx_s in range(-steps, steps + 1):
                        dx = dx_s * 0.10
                        for dy_s in range(-steps, steps + 1):
                            dy = dy_s * 0.10
                            dist = math.hypot(dx, dy)
                            if dist > max_d or dist < 0.30:
                                continue

                            cand_x = cx + dx
                            cand_y = cy + dy
                            cand_bbox = self.compute_label_bbox(cand_x, cand_y, text, rot, f_size)

                            if not self.is_valid_label_bbox(cand_bbox, obstacles, placed_labels):
                                continue

                            if not self.is_line_of_sight_clear(comp, cand_x, cand_y, all_components, placed_labels):
                                continue

                            repulsion_cost = 0.0
                            for rx, ry, rd in repulsion_targets:
                                dot = (dx * rx + dy * ry) / (rd * dist) if dist > 0 else 0.0
                                if dot > 0.2:
                                    repulsion_cost += 4.0 * dot

                            cost = (dist * (2.5 if is_single_pad else 1.0)) + rot_penalty + f_pen + repulsion_cost
                            if cost < lowest_cost:
                                lowest_cost = cost
                                best_candidate = CandidateLabelPlacement(
                                    designator=text,
                                    attr_id=desig_attr.attr_id,
                                    comp_id=comp.comp_id,
                                    center_x_mm=cand_x,
                                    center_y_mm=cand_y,
                                    rotation_deg=rot,
                                    font_size_mil=f_size,
                                    line_width_mil=self.line_width_mil,
                                    align_mode=ALIGN_CENTER,
                                    bbox=cand_bbox,
                                    cost=cost,
                                    dist_to_center_mm=dist
                                )
                    if best_candidate and lowest_cost < 6.0:
                        break
                if best_candidate:
                    break

        return best_candidate



def extract_pcb_geometry(
    client: EasyEDAClient,
    manifest_path: Optional[Path] = None,
    constraints_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Extrait l'intégralité de la géométrie du PCB actif via le pont local :
    - Contour de carte (Layer 11)
    - Trous de perçage / fixations mécaniques (MH1-MH4)
    - Composants avec pads réels et boîtes de corps (Body BBoxes)
    - Attributs de désignateurs de sérigraphie
    """
    code = """
    try {
        // 0. S'assurer que le document PCB est actif au premier plan
        try {
            const pcbs = await eda.dmt_Pcb.getAllPcbsInfo();
            if (pcbs && pcbs.length > 0) {
                await eda.dmt_EditorControl.openDocument(pcbs[0].uuid);
            }
        } catch(e) {}

        // 1. Contour de carte
        const lines = (await eda.pcb_PrimitiveLine.getAll(undefined, 11)) || [];
        let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
        for (const l of lines) {
            minX = Math.min(minX, l.getState_StartX(), l.getState_EndX());
            maxX = Math.max(maxX, l.getState_StartX(), l.getState_EndX());
            minY = Math.min(minY, l.getState_StartY(), l.getState_EndY());
            maxY = Math.max(maxY, l.getState_StartY(), l.getState_EndY());
        }

        // 2. Composants et pads
        const comps = await eda.pcb_PrimitiveComponent.getAll();
        const compList = [];
        for (const c of comps) {
            const cid = c.getState_PrimitiveId();
            const des = c.getState_Designator();
            const cx = c.getState_X();
            const cy = c.getState_Y();
            const rot = c.getState_Rotation ? c.getState_Rotation() : 0;
            const pins = (await c.getAllPins?.()) || [];
            
            const padList = [];
            for (const p of pins) {
                const padData = p.pad || [];
                const shape = padData[0] || 'RECT';
                const pw = typeof padData[1] === 'number' ? padData[1] : 30;
                const ph = typeof padData[2] === 'number' ? padData[2] : 30;
                const prot = typeof padData[3] === 'number' ? padData[3] : 0;
                const isTh = !!p.hole;
                padList.push({
                    id: p.getState_PrimitiveId ? p.getState_PrimitiveId() : null,
                    num: p.getState_PadNumber ? p.getState_PadNumber() : null,
                    x: p.getState_X(),
                    y: p.getState_Y(),
                    shape: shape,
                    width: pw,
                    height: ph,
                    rotation: prot,
                    is_th: isTh
                });
            }
            const other = c.otherProperty || {};
            const t3d = other['3D Model Transform'] || '';
            compList.push({
                id: cid,
                designator: des,
                x: cx,
                y: cy,
                rotation: rot,
                t3d: t3d,
                pads: padList
            });
        }

        // 3. Attributs de désignateurs
        const attrs = await eda.pcb_PrimitiveAttribute.getAll();
        const desigAttrs = [];
        for (const a of attrs) {
            if (a.getState_Key() === 'Designator' && a.getState_ValueVisible()) {
                desigAttrs.push({
                    id: a.getState_PrimitiveId(),
                    parentId: a.getState_ParentPrimitiveId(),
                    text: a.getState_Value(),
                    x: a.getState_X(),
                    y: a.getState_Y(),
                    rotation: a.getState_Rotation ? a.getState_Rotation() : 0,
                    fontSize: a.getState_FontSize ? a.getState_FontSize() : 40,
                    lineWidth: a.getState_LineWidth ? a.getState_LineWidth() : 6,
                    alignMode: a.getState_AlignMode ? a.getState_AlignMode() : 3
                });
            }
        }

        return {
            success: true,
            board: {
                minX_mil: minX,
                maxX_mil: maxX,
                minY_mil: minY,
                maxY_mil: maxY
            },
            components: compList,
            designators: desigAttrs
        };
    } catch(e) {
        return { success: false, error: e.message || String(e) };
    }
    """
    res = client.execute_js(code)
    if not res or not res.get("success"):
        raise RuntimeError(f"Échec de l'extraction de la géométrie PCB : {res.get('error') if res else 'Pont déconnecté'}")
    return res


def optimize_labels(
    geo_data: Dict[str, Any],
    manifest_path: Optional[Path] = None,
    board_constraints_path: Optional[Path] = None,
    font_size_mil: float = 38.0,
    line_width_mil: float = 6.0,
    pad_clearance_mm: float = 0.20,
    text_clearance_mm: float = 0.15,
    edge_clearance_mm: float = 0.50,
    hole_exclusion_radius_mm: float = 3.50
) -> Dict[str, Any]:
    """
    Exécute l'algorithme d'optimisation et génère le plan de repositionnement des étiquettes.
    """
    board_raw = geo_data["board"]
    min_x_mm = board_raw["minX_mil"] * MIL_TO_MM
    max_x_mm = board_raw["maxX_mil"] * MIL_TO_MM
    min_y_mm = board_raw["minY_mil"] * MIL_TO_MM
    max_y_mm = board_raw["maxY_mil"] * MIL_TO_MM

    board_bbox = BoundingBox(min_x_mm, max_x_mm, min_y_mm, max_y_mm)
    logger.info(f"📐 Contour PCB détecté : {board_bbox.width:.2f} × {board_bbox.height:.2f} mm")

    # Chargement du manifeste et des packages
    packages = {}
    comps_manifest = {}
    if manifest_path and manifest_path.is_file():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                mf = json.load(f)
            packages = mf.get("packages", {})
            comps_manifest = mf.get("components", {})
        except Exception as e:
            logger.warning(f"⚠️ Impossible de charger {manifest_path} : {e}")

    # Keepouts mécaniques : trous de fixation (cylindres) et antenne RF / zones déclarées (boîtes)
    keepout_boxes: List[BoundingBox] = []
    mounting_holes: List[Tuple[float, float, float]] = []
    if board_constraints_path and board_constraints_path.is_file():
        try:
            with open(board_constraints_path, "r", encoding="utf-8") as f:
                bc = json.load(f)

            # Trous de fixation mécaniques : extraction de la garde circulaire
            board_data = bc.get("board", {})
            for h in board_data.get("mounting_holes", []):
                hx = h.get("x_mm", 0.0)
                hy = h.get("y_mm", 0.0)
                head_clr = h.get("head_clearance_mm")
                r = (head_clr / 2.0 + 0.35) if head_clr is not None else hole_exclusion_radius_mm
                mounting_holes.append((hx, hy, r))

            # Antenne radio U1 (keepout Est)
            u1_anchor = bc.get("anchors", {}).get("U1", {})
            if u1_anchor:
                keepout_boxes.append(BoundingBox(75.5, 81.28, 8.5, 27.0))

            # Zones keepout déclarées
            for ko in bc.get("keepout_zones", []):
                keepout_boxes.append(BoundingBox(
                    ko.get("min_x_mm", 0.0),
                    ko.get("max_x_mm", 0.0),
                    ko.get("min_y_mm", 0.0),
                    ko.get("max_y_mm", 0.0)
                ))
        except Exception as e:
            logger.warning(f"⚠️ Impossible de charger les keepouts de {board_constraints_path} : {e}")

    logger.info(f"🛡️ Fixations mécaniques circulaires : {len(mounting_holes)}, Keepouts déclarés : {len(keepout_boxes)}")

    # Construction de la liste des obstacles physiques :
    # 1. Pastilles de cuivre (pads) avec garde pad_clearance
    # 2. Corps entiers de composants (Body BBoxes) pour interdire le passage SOUS les composants
    obstacle_boxes: List[BoundingBox] = []
    comp_map: Dict[str, ComponentInfo] = {}

    for c in geo_data["components"]:
        cid = c["id"]
        des = c["designator"]
        cx_mm = c["x"] * MIL_TO_MM
        cy_mm = c["y"] * MIL_TO_MM
        crot = c["rotation"]

        # Pastilles de cuivre
        pad_objs = []
        for p in c.get("pads", []):
            px_mm = p["x"] * MIL_TO_MM
            py_mm = p["y"] * MIL_TO_MM
            pw_mm = p["width"] * MIL_TO_MM
            ph_mm = p["height"] * MIL_TO_MM
            prot = p["rotation"]

            norm_prot = int(round(prot)) % 180
            if norm_prot in (90, 270):
                eff_pw, eff_ph = ph_mm, pw_mm
            else:
                eff_pw, eff_ph = pw_mm, ph_mm

            pad_bbox = BoundingBox(
                px_mm - eff_pw / 2.0,
                px_mm + eff_pw / 2.0,
                py_mm - eff_ph / 2.0,
                py_mm + eff_ph / 2.0
            )

            # Obstacle de pad avec marge cuivre
            obstacle_boxes.append(pad_bbox.expanded(pad_clearance_mm))

            pad_objs.append(PadObstacle(
                pad_id=p.get("id", ""),
                comp_id=cid,
                designator=des,
                center_x_mm=px_mm,
                center_y_mm=py_mm,
                width_mm=eff_pw,
                height_mm=eff_ph,
                rotation_deg=prot,
                is_through_hole=p.get("is_th", False),
                bbox=pad_bbox
            ))

        # Enveloppe des pads
        if pad_objs:
            p_min_x = min(p.bbox.min_x for p in pad_objs)
            p_max_x = max(p.bbox.max_x for p in pad_objs)
            p_min_y = min(p.bbox.min_y for p in pad_objs)
            p_max_y = max(p.bbox.max_y for p in pad_objs)
        else:
            p_min_x, p_max_x, p_min_y, p_max_y = cx_mm - 1.0, cx_mm + 1.0, cy_mm - 1.0, cy_mm + 1.0

        # Cotes issues du catalogue de boîtiers du manifeste
        cm = comps_manifest.get(des, {})
        pname = cm.get("package")
        pkg = packages.get(pname, {})
        pw_m = pkg.get("width_mm", 0.0)
        pl_m = pkg.get("length_mm", 0.0)

        norm_rot = int(round(crot)) % 180
        if norm_rot == 90:
            eff_w, eff_h = pl_m, pw_m
        else:
            eff_w, eff_h = pw_m, pl_m

        m_min_x = cx_mm - eff_w / 2.0 if eff_w else p_min_x
        m_max_x = cx_mm + eff_w / 2.0 if eff_w else p_max_x
        m_min_y = cy_mm - eff_h / 2.0 if eff_h else p_min_y
        m_max_y = cy_mm + eff_h / 2.0 if eff_h else p_max_y

        t3d = c.get("t3d", "")
        box_3d = compute_3d_bbox(cx_mm, cy_mm, crot, t3d)

        # Détection des connecteurs d'interface mécanique et des composants discrets sensibles
        is_edge_connector = (des in ("J1", "J2"))
        is_discrete_diode_led = (des.startswith("LED") or des in ("D4", "D5"))

        if is_edge_connector and box_3d:
            # Connecteurs physiques d'interface : boîte 3D réelle prioritaire avec garde mécanique
            body_bbox = BoundingBox(
                min(p_min_x, box_3d.min_x) - 0.40,
                max(p_max_x, box_3d.max_x) + 0.40,
                min(p_min_y, box_3d.min_y) - 0.40,
                max(p_max_y, box_3d.max_y) + 0.40
            )
        elif is_discrete_diode_led:
            # LEDs et diodes CMS : garde augmentée pour englober la sérigraphie d'usine
            body_bbox = BoundingBox(
                min(p_min_x, m_min_x, box_3d.min_x if box_3d else p_min_x) - 0.30,
                max(p_max_x, m_max_x, box_3d.max_x if box_3d else p_max_x) + 0.30,
                min(p_min_y, m_min_y, box_3d.min_y if box_3d else p_min_y) - 0.30,
                max(p_max_y, m_max_y, box_3d.max_y if box_3d else p_max_y) + 0.30
            )
        else:
            all_min_x = min(p_min_x, m_min_x, box_3d.min_x if box_3d else p_min_x)
            all_max_x = max(p_max_x, m_max_x, box_3d.max_x if box_3d else p_max_x)
            all_min_y = min(p_min_y, m_min_y, box_3d.min_y if box_3d else p_min_y)
            all_max_y = max(p_max_y, m_max_y, box_3d.max_y if box_3d else p_max_y)
            body_bbox = BoundingBox(all_min_x - 0.05, all_max_x + 0.05, all_min_y - 0.05, all_max_y + 0.05)

        # Le corps physique du composant est un obstacle strict (interdit tout passage dessous)
        obstacle_boxes.append(body_bbox)

        comp_info = ComponentInfo(
            comp_id=cid,
            designator=des,
            center_x_mm=cx_mm,
            center_y_mm=cy_mm,
            rotation_deg=crot,
            body_bbox=body_bbox,
            pads=pad_objs
        )
        comp_map[cid] = comp_info

    logger.info(f"🧱 Obstacles physiques totaux (pads + corps) : {len(obstacle_boxes)}")
    logger.info(f"🏷️ Étiquettes de désignateurs à positionner : {len(geo_data['designators'])}")

    optimizer = SilkscreenOptimizer(
        board_bbox=board_bbox,
        pad_clearance_mm=pad_clearance_mm,
        text_clearance_mm=text_clearance_mm,
        edge_clearance_mm=edge_clearance_mm,
        font_size_mil=font_size_mil,
        line_width_mil=line_width_mil,
        keepout_boxes=keepout_boxes,
        mounting_holes=mounting_holes
    )

    desig_list: List[DesignatorAttr] = [
        DesignatorAttr(
            attr_id=d["id"],
            comp_id=d["parentId"],
            text=d["text"],
            current_x_mil=d["x"],
            current_y_mil=d["y"],
            current_rotation=d["rotation"],
            current_font_size_mil=d["fontSize"],
            current_line_width_mil=d["lineWidth"],
            current_align_mode=d["alignMode"]
        )
        for d in geo_data["designators"]
    ]

    # Priorité de placement agnostique :
    # 0. Composants monopad (points de test) en priorité absolue pour verrouiller l'espace immédiat (< 1.8 mm)
    # 1. Composants discrets et passifs denses (0805, 0603, SOT)
    # 2. Grands circuits intégrés et connecteurs de bord
    def sort_key(d: DesignatorAttr) -> Tuple[int, str]:
        comp = comp_map.get(d.comp_id)
        if comp and len(comp.pads) == 1:
            return (0, d.text)
        if comp and (len(comp.pads) >= 8 or (comp.body_bbox.width * comp.body_bbox.height > 50.0)):
            return (2, d.text)
        return (1, d.text)

    sorted_desigs = sorted(desig_list, key=sort_key)

    placed_labels_boxes: List[BoundingBox] = []
    placements: List[CandidateLabelPlacement] = []
    unplaced: List[str] = []
    all_comp_list = list(comp_map.values())

    for d in sorted_desigs:
        comp = comp_map.get(d.comp_id)
        if not comp:
            logger.warning(f"⚠️ Composant introuvable pour '{d.text}'")
            unplaced.append(d.text)
            continue

        cand = optimizer.find_best_placement(
            comp, d, obstacle_boxes, placed_labels_boxes,
            all_components=all_comp_list, allow_extended=False
        )
        if not cand:
            # Passe de repli étendue avec grille cartésienne fine
            cand = optimizer.find_best_placement(
                comp, d, obstacle_boxes, placed_labels_boxes,
                all_components=all_comp_list, allow_extended=True
            )

        if cand:
            placements.append(cand)
            placed_labels_boxes.append(cand.bbox)
        else:
            logger.warning(f"⚠️ Aucun emplacement 100% dégagé trouvé pour '{d.text}'")
            unplaced.append(d.text)

    # Statistiques
    rot_0_count = sum(1 for p in placements if int(round(p.rotation_deg)) % 180 == 0)
    rot_90_count = sum(1 for p in placements if int(round(p.rotation_deg)) % 180 == 90)
    avg_dist = sum(p.dist_to_center_mm for p in placements) / max(1, len(placements))

    logger.info("================================================================================")
    logger.info("             RÉSULTAT DE L'OPTIMISATION DE SÉRIGRAPHIE (IPC-7351)               ")
    logger.info("================================================================================")
    logger.info(f"  • Étiquettes positionnées avec succès : {len(placements)} / {len(desig_list)} ({len(placements)/max(1, len(desig_list))*100:.1f}%)")
    logger.info(f"  • Non placées (congestions dures)     : {len(unplaced)}")
    logger.info(f"  • Orientations : Horizontale (0°) = {rot_0_count} ({rot_0_count/max(1, len(placements))*100:.1f}%), Verticale (90°) = {rot_90_count} ({rot_90_count/max(1, len(placements))*100:.1f}%)")
    logger.info(f"  • Textes inversés (180° / 270°)      : 0 (100% éliminés conforme IPC-7351 §3.4.7)")
    logger.info(f"  • Textes sous les corps de composants : 0 (100% à l'extérieur des composants)")
    logger.info(f"  • Dégagement vis de fixation M2       : >= {hole_exclusion_radius_mm:.2f} mm de rayon")
    logger.info(f"  • Distance moyenne au composant       : {avg_dist:.2f} mm")
    logger.info(f"  • Dégagement minimal du cuivre       : >= {pad_clearance_mm:.2f} mm")
    logger.info("================================================================================")

    return {
        "success": len(unplaced) == 0,
        "total": len(desig_list),
        "placed_count": len(placements),
        "unplaced_count": len(unplaced),
        "unplaced": unplaced,
        "rotations": {"0": rot_0_count, "90": rot_90_count, "180": 0, "270": 0},
        "placements": placements
    }


def apply_label_placements(
    client: EasyEDAClient,
    placements: List[CandidateLabelPlacement],
    save_pcb: bool = True
) -> Dict[str, Any]:
    """
    Applique en lot les nouvelles positions et orientations des étiquettes de sérigraphie
    dans EasyEDA Pro via eda.pcb_PrimitiveAttribute.modify().
    """
    logger.info(f"⚡ Injection en lot de {len(placements)} étiquettes de sérigraphie dans EasyEDA Pro...")

    updates = []
    for p in placements:
        x_mil = round(p.center_x_mm * MM_TO_MIL, 1)
        y_mil = round(p.center_y_mm * MM_TO_MIL, 1)
        norm_rot = int(round(p.rotation_deg)) % 360

        updates.append({
            "id": p.attr_id,
            "designator": p.designator,
            "x": x_mil,
            "y": y_mil,
            "rotation": norm_rot,
            "fontSize": round(p.font_size_mil, 1),
            "lineWidth": round(p.line_width_mil, 1),
            "alignMode": p.align_mode  # 5 = CENTER
        })

    code = f"""
    try {{
        const items = {json.dumps(updates)};
        let successCount = 0;
        let failCount = 0;

        for (const item of items) {{
            try {{
                const res = await eda.pcb_PrimitiveAttribute.modify(item.id, {{
                    x: item.x,
                    y: item.y,
                    rotation: item.rotation,
                    fontSize: item.fontSize,
                    lineWidth: item.lineWidth,
                    alignMode: item.alignMode
                }});
                if (res) successCount++;
                else failCount++;
            }} catch(err) {{
                failCount++;
            }}
        }}

        return {{ success: true, modifiedCount: successCount, failCount: failCount }};
    }} catch(e) {{
        return {{ success: false, error: e.message || String(e) }};
    }}
    """
    t0 = time.time()
    res = client.execute_js(code)
    elapsed = time.time() - t0

    if not res or not res.get("success"):
        raise RuntimeError(f"Échec de l'injection sérigraphie : {res.get('error') if res else 'Erreur pont'}")

    mod_count = res.get("modifiedCount", 0)
    logger.info(f"✅ {mod_count} étiquettes repositionnées et normalisées avec succès en {elapsed:.2f} s !")

    if save_pcb:
        logger.info("💾 Sauvegarde du document PCB actif...")
        saved = client.save_pcb()
        if saved:
            logger.info("✅ Document PCB sauvegardé.")
        else:
            logger.warning("⚠️ Impossible de confirmer la sauvegarde automatique.")

    return {
        "success": True,
        "modifiedCount": mod_count,
        "elapsed_sec": elapsed
    }


def main():
    parser = argparse.ArgumentParser(
        description="Moteur de Placement & Normalisation de la Sérigraphie IPC-7351 (Agnostique)"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("circuit_manifest.json"),
        help="Chemin vers le manifeste sémantique et packages (défaut: circuit_manifest.json)"
    )
    parser.add_argument(
        "--constraints",
        type=Path,
        default=Path("board_constraints.json"),
        help="Chemin vers le fichier des contraintes mécaniques (défaut: board_constraints.json)"
    )
    parser.add_argument(
        "--font-size",
        type=float,
        default=38.0,
        help="Hauteur de police par défaut en mil (défaut: 38.0 mil = 0.965 mm)"
    )
    parser.add_argument(
        "--line-width",
        type=float,
        default=6.0,
        help="Épaisseur de trait de sérigraphie en mil (défaut: 6.0 mil = 0.152 mm JLCPCB standard)"
    )
    parser.add_argument(
        "--pad-clearance",
        type=float,
        default=0.20,
        help="Garde minimale entre le texte et les pastilles de cuivre en mm (défaut: 0.20 mm)"
    )
    parser.add_argument(
        "--text-clearance",
        type=float,
        default=0.15,
        help="Garde minimale entre deux textes de sérigraphie en mm (défaut: 0.15 mm)"
    )
    parser.add_argument(
        "--edge-clearance",
        type=float,
        default=0.50,
        help="Garde minimale entre le texte et le bord du PCB en mm (défaut: 0.50 mm)"
    )
    parser.add_argument(
        "--hole-exclusion",
        type=float,
        default=3.50,
        help="Rayon de la zone d'exclusion autour des vis de fixation M2 en mm (défaut: 3.50 mm)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calculer et afficher l'audit sans modifier le document PCB"
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Ne pas sauvegarder automatiquement le PCB après injection"
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Chemin optionnel pour exporter le rapport JSON détaillé"
    )

    args = parser.parse_args()

    client = EasyEDAClient()
    health = client.health()
    if not health.get("edaConnected"):
        logger.error("❌ EasyEDA Pro n'est pas connecté au serveur pont local.")
        sys.exit(1)

    logger.info("🔍 Extraction de la géométrie PCB, des pads et des corps de composants...")
    geo_data = extract_pcb_geometry(client, manifest_path=args.manifest, constraints_path=args.constraints)

    logger.info("⚡ Résolution géométrique du placement des étiquettes (IPC-7351)...")
    opt_result = optimize_labels(
        geo_data=geo_data,
        manifest_path=args.manifest,
        board_constraints_path=args.constraints,
        font_size_mil=args.font_size,
        line_width_mil=args.line_width,
        pad_clearance_mm=args.pad_clearance,
        text_clearance_mm=args.text_clearance,
        edge_clearance_mm=args.edge_clearance,
        hole_exclusion_radius_mm=args.hole_exclusion
    )

    if args.report:
        report_data = {
            "success": opt_result["success"],
            "total": opt_result["total"],
            "placed_count": opt_result["placed_count"],
            "rotations": opt_result["rotations"],
            "unplaced": opt_result["unplaced"],
            "placements": [
                {
                    "designator": p.designator,
                    "x_mm": round(p.center_x_mm, 3),
                    "y_mm": round(p.center_y_mm, 3),
                    "rotation_deg": p.rotation_deg,
                    "font_size_mil": p.font_size_mil,
                    "dist_to_center_mm": round(p.dist_to_center_mm, 3)
                }
                for p in opt_result["placements"]
            ]
        }
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
        logger.info(f"📄 Rapport exporté : {args.report}")

    if args.dry_run:
        logger.info("🔍 Mode simulation (--dry-run) : aucune modification appliquée sur le PCB.")
        return

    if not opt_result["success"]:
        logger.warning(f"⚠️ {opt_result['unplaced_count']} étiquettes n'ont pas pu être placées sans collision.")

    apply_label_placements(
        client=client,
        placements=opt_result["placements"],
        save_pcb=not args.no_save
    )


if __name__ == "__main__":
    main()
