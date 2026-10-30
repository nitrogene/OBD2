#!/usr/bin/env python3
"""
emc_physics.py - Moteur de Calcul Physique CEM pour PCB (Agnostique)
====================================================================
Fournit les primitives mathématiques et physiques pour l'optimisation CEM v2 :
- Aire réelle de boucle polygonale fermée (formule de Shoelace / Lacet de Gauss)
- Estimation physique de l'inductance de boucle (Rosa / Grover / Paul)
- Décroissance spatiale des champs électromagnétiques proches :
    * Champ magnétique dipolaire H (di/dt) : décroissance en 1/r³
    * Champ électrique capacitif E (dv/dt) : décroissance en 1/r²
- Facteur d'atténuation angulaire par orthogonalité de couplage mutuel
- Évaluation de l'inductance parasite équivalente de découplage
"""

from __future__ import annotations

import math
from typing import List, Sequence, Tuple

# Constantes physiques
MU_0 = 4.0 * math.pi * 1e-7  # Perméabilité du vide en H/m (H/m = N/A²)
MU_0_NH_PER_MM = MU_0 * 1e6   # μ0 converti en nH/mm ≈ 1.2566 nH/mm


def polygon_area_shoelace(points: Sequence[Tuple[float, float]]) -> float:
    """
    Calcule l'aire géométrique réelle d'un polygone fermé 2D par la formule du lacet de Gauss (Shoelace).
    points : séquence ordonnée des sommets (x, y) en millimètres.
    Retourne l'aire en mm².
    """
    n = len(points)
    if n < 3:
        return 0.0

    area2 = 0.0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        area2 += (x1 * y2 - x2 * y1)

    return abs(area2) / 2.0


def loop_perimeter(points: Sequence[Tuple[float, float]]) -> float:
    """Calcule le périmètre total d'un polygone fermé en mm."""
    n = len(points)
    if n < 2:
        return 0.0

    perim = 0.0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        perim += math.hypot(x2 - x1, y2 - y1)

    return perim


def estimate_loop_inductance_nh(
    points: Sequence[Tuple[float, float]],
    trace_width_mm: float = 0.3,
    reference_plane_height_mm: float = 0.2
) -> float:
    """
    Estime l'inductance partielle d'une boucle fermée en nH.
    Modèle physique mixte :
    - Si un plan de référence de masse (GND) est présent à distance h (microstrip) :
      L_loop ≈ (μ0 / w) * h * perimeter / 2 + inductance d'aire de fuite.
    - Pour une boucle fermée coplanaire (sans plan ou aller-retour discret) :
      L_loop ≈ (μ0 / π) * perimeter * [ ln(perimeter / sqrt(area + ε)) - 0.5 ].
    """
    if len(points) < 3:
        return 0.0

    area_mm2 = polygon_area_shoelace(points)
    perim_mm = loop_perimeter(points)

    if perim_mm <= 0.0:
        return 0.0

    w = max(0.1, trace_width_mm)
    h = reference_plane_height_mm

    if h > 0.0:
        # Modèle microstrip fermé sur plan de référence GND (IPC-2141 / Wadell) :
        # 1. Inductance linéique de piste au-dessus du plan de masse
        ratio_hw = (5.98 * h) / (0.8 * w + 0.035)
        l_per_mm = (MU_0_NH_PER_MM / (2.0 * math.pi)) * max(0.3, math.log(max(1.1, ratio_hw)))
        trace_inductance = l_per_mm * (perim_mm / 2.0)

        # 2. Inductance d'ouverture rayonnante (flux non confiné sous le ruban)
        aperture_inductance = (MU_0_NH_PER_MM * area_mm2) / (perim_mm + 4.0 * h)
        l_nh = trace_inductance + aperture_inductance
    else:
        # Modèle de Grover pour boucle coplanaire sans plan de masse immédiat
        r0 = max(0.05, 0.25 * w)
        ratio = max(1e-4, area_mm2 / (perim_mm ** 2))
        geometry_factor = min(1.0, 4.0 * math.pi * ratio)
        base_l = (MU_0_NH_PER_MM / math.pi) * perim_mm * max(0.5, math.log(max(2.0, 2.0 * perim_mm / r0)) - 1.5)
        l_nh = base_l * math.sqrt(geometry_factor)

    return round(max(0.1, l_nh), 3)


def magnetic_field_coupling(
    dist_mm: float,
    orientation_deg_1: float = 0.0,
    orientation_deg_2: float = 0.0,
    min_dist_mm: float = 1.0
) -> float:
    """
    Calcule le couplage magnétique dipolaire H (di/dt) entre deux blocs ou composants.
    Décroissance dipolaire en 1/r³ normalisée à min_dist_mm.
    Orientation angulaire : couplage maximal si parallèles (0° ou 180°), minimal si orthogonaux (90° ou 270°).
    """
    effective_dist = max(0.5, dist_mm)
    # Facteur de décroissance spatiale en 1/r³
    spatial_factor = (min_dist_mm / effective_dist) ** 3

    # Atténuation angulaire : |cos(theta1 - theta2)|
    # Les inductances à 90° minimisent la mutuelle induction (M ≈ 0)
    angle_diff_rad = math.radians(orientation_deg_1 - orientation_deg_2)
    angular_factor = 0.2 + 0.8 * abs(math.cos(angle_diff_rad))

    return spatial_factor * angular_factor


def electric_field_coupling(
    dist_mm: float,
    min_dist_mm: float = 1.0
) -> float:
    """
    Calcule le couplage capacitif / champ électrique E (dv/dt).
    Décroissance monopolaire/capacitive en 1/r² normalisée à min_dist_mm.
    """
    effective_dist = max(0.5, dist_mm)
    return (min_dist_mm / effective_dist) ** 2


def decoupling_effective_inductance_nh(
    dist_mm: float,
    via_count: int = 2,
    via_inductance_nh: float = 0.8,
    trace_inductance_nh_per_mm: float = 0.8
) -> float:
    """
    Estime l'inductance parasite équivalente de raccordement d'un condensateur de découplage :
    L_eff = L_trace + (L_via / via_count).
    L_trace ≈ 0.8 nH/mm * distance.
    """
    l_trace = trace_inductance_nh_per_mm * max(0.0, dist_mm)
    l_vias = (via_inductance_nh / max(1, via_count)) * 2.0  # aller + retour
    return round(l_trace + l_vias, 3)


def in_line_path_metrics(
    source_pt: Tuple[float, float],
    protection_pt: Tuple[float, float],
    target_pt: Tuple[float, float]
) -> Tuple[bool, float, float]:
    """
    Évalue la topologie CEM « En-Ligne » (In-Line Path : Source -> Protection -> Cible)
    pour prévenir les embranchements inductifs (stubs) sur les protections TVS/ESD/Fusibles.
    Retourne :
      - is_ordered (bool) : True si dist(Source, Protection) <= dist(Source, Cible)
      - detour_mm (float) : Sur-longueur de détour (d(S,P) + d(P,T) - d(S,T)) en mm
      - order_violation_mm (float) : Dépassement d'ordre max(0, d(S,P) - d(S,T)) en mm
    """
    d_sp = math.hypot(protection_pt[0] - source_pt[0], protection_pt[1] - source_pt[1])
    d_pt = math.hypot(target_pt[0] - protection_pt[0], target_pt[1] - protection_pt[1])
    d_st = math.hypot(target_pt[0] - source_pt[0], target_pt[1] - source_pt[1])

    detour_mm = max(0.0, (d_sp + d_pt) - d_st)
    order_violation_mm = max(0.0, d_sp - d_st)
    is_ordered = (d_sp <= d_st + 0.5)
    return is_ordered, round(detour_mm, 3), round(order_violation_mm, 3)
