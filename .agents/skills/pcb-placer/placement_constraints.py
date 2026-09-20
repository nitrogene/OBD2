#!/usr/bin/env python3
"""
Modélisation formelle et chargement des contraintes de placement PCB
====================================================================
Ce module fournit le schéma générique (agnostique) des contraintes physiques,
CEM et géométriques, ainsi que le parseur/chargeur de configuration (ex: floorplan.json).
Il ne contient aucune référence en dur à des composants ou coordonnées d'un projet donné.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("PlacementConstraints")

# =============================================================================
# Constantes de Conversion d'Unités
# =============================================================================

MM_TO_MIL = 39.37007874
MIL_TO_MM = 0.0254

def mm_to_mil(mm: float) -> float:
    return mm * MM_TO_MIL

def mil_to_mm(mil: float) -> float:
    return mil * MIL_TO_MM


# =============================================================================
# Structures de Données Génériques (Agnostiques)
# =============================================================================

@dataclass
class BoardDimensions:
    width_mm: float
    height_mm: float
    width_mil: float
    height_mil: float
    edge_clearance_mm: float = 1.0
    edge_clearance_mil: float = 39.37
    grid_step_mil: float = 25.0


@dataclass
class AnchorConstraint:
    """Composant dont la position mécanique ou fonctionnelle est imposée."""
    designator: str
    target_x_mil: float
    target_y_mil: float
    target_rotation: float
    fixed: bool = True
    description: str = ""


@dataclass
class KeepoutZone:
    """Zone d'exclusion stricte multicouche (NO_WIRES, NO_POURS, NO_COMPONENTS)."""
    name: str
    x_min_mil: float
    x_max_mil: float
    y_min_mil: float
    y_max_mil: float
    description: str = ""


@dataclass
class ProximityRule:
    """Règle de distance maximale entre deux composants ou broches."""
    component: str
    reference_component: str
    max_distance_mm: float
    target_net: str
    description: str = ""


@dataclass
class ComponentPlacement:
    """Spécification de position cible pour un composant."""
    designator: str
    x_mil: float
    y_mil: float
    rotation: float
    layer: int = 1
    description: str = ""


@dataclass
class FloorplanConfig:
    """Configuration complète du floorplan et des contraintes d'une carte."""
    project_name: str
    board: BoardDimensions
    thresholds: Dict[str, float]
    anchors: Dict[str, AnchorConstraint]
    keepout_zones: List[KeepoutZone]
    functional_clusters: Dict[str, List[str]]
    proximity_rules: List[ProximityRule]
    components: Dict[str, ComponentPlacement]


def load_floorplan(config_path: str) -> FloorplanConfig:
    """
    Charge et valide un fichier JSON de configuration de floorplan.
    Lève FileNotFoundError ou ValueError en cas d'erreur de chemin ou de format.
    """
    p = Path(config_path)
    if not p.exists():
        raise FileNotFoundError(f"Le fichier de configuration spécifié est introuvable : {config_path}")

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    meta = data.get("meta", {})
    board_raw = data.get("board", {})
    board = BoardDimensions(
        width_mm=board_raw.get("width_mm", mil_to_mm(board_raw.get("width_mil", 0))),
        height_mm=board_raw.get("height_mm", mil_to_mm(board_raw.get("height_mil", 0))),
        width_mil=board_raw.get("width_mil", mm_to_mil(board_raw.get("width_mm", 0))),
        height_mil=board_raw.get("height_mil", mm_to_mil(board_raw.get("height_mm", 0))),
        edge_clearance_mm=board_raw.get("edge_clearance_mm", 1.0),
        edge_clearance_mil=board_raw.get("edge_clearance_mil", mm_to_mil(board_raw.get("edge_clearance_mm", 1.0))),
        grid_step_mil=board_raw.get("grid_step_mil", 25.0)
    )

    thresholds = data.get("thresholds", {
        "max_decoupling_distance_mm": 2.0,
        "max_reset_rc_distance_mm": 2.0,
        "max_esd_distance_mm": 5.0
    })

    anchors = {}
    for des, a in data.get("anchors", {}).items():
        anchors[des] = AnchorConstraint(
            designator=des,
            target_x_mil=float(a["x"]),
            target_y_mil=float(a["y"]),
            target_rotation=float(a.get("rot", 0.0)),
            fixed=bool(a.get("fixed", True)),
            description=a.get("description", "")
        )

    keepout_zones = []
    for k in data.get("keepout_zones", []):
        keepout_zones.append(KeepoutZone(
            name=k.get("name", "KEEPOUT"),
            x_min_mil=float(k["x_min_mil"]),
            x_max_mil=float(k["x_max_mil"]),
            y_min_mil=float(k["y_min_mil"]),
            y_max_mil=float(k["y_max_mil"]),
            description=k.get("description", "")
        ))

    functional_clusters = data.get("functional_clusters", {})

    proximity_rules = []
    for r in data.get("proximity_rules", []):
        proximity_rules.append(ProximityRule(
            component=r["component"],
            reference_component=r["reference_component"],
            max_distance_mm=float(r["max_distance_mm"]),
            target_net=r.get("target_net", ""),
            description=r.get("description", "")
        ))

    components = {}
    for des, c in data.get("components", {}).items():
        components[des] = ComponentPlacement(
            designator=des,
            x_mil=float(c["x"]),
            y_mil=float(c["y"]),
            rotation=float(c.get("rot", 0.0)),
            layer=int(c.get("layer", 1)),
            description=c.get("desc", "")
        )

    return FloorplanConfig(
        project_name=meta.get("project", "PCB Design"),
        board=board,
        thresholds=thresholds,
        anchors=anchors,
        keepout_zones=keepout_zones,
        functional_clusters=functional_clusters,
        proximity_rules=proximity_rules,
        components=components
    )
