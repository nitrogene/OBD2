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
    mounting_holes: List[Dict[str, Any]] = field(default_factory=list)


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
    mh_raw = board_raw.get("mounting_holes", {})
    mh_list = mh_raw.get("holes", []) if isinstance(mh_raw, dict) else (mh_raw if isinstance(mh_raw, list) else [])

    board = BoardDimensions(
        width_mm=board_raw.get("width_mm", mil_to_mm(board_raw.get("width_mil", 0))),
        height_mm=board_raw.get("height_mm", mil_to_mm(board_raw.get("height_mil", 0))),
        width_mil=board_raw.get("width_mil", mm_to_mil(board_raw.get("width_mm", 0))),
        height_mil=board_raw.get("height_mil", mm_to_mil(board_raw.get("height_mm", 0))),
        edge_clearance_mm=board_raw.get("edge_clearance_mm", 1.0),
        edge_clearance_mil=board_raw.get("edge_clearance_mil", mm_to_mil(board_raw.get("edge_clearance_mm", 1.0))),
        grid_step_mil=board_raw.get("grid_step_mil", 25.0),
        mounting_holes=mh_list
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

    # Détection automatique du circuit_manifest pour enrichir les règles CEM et clusters
    manifest_path = None
    possible_manifests = [
        p.parent / "circuit_manifest.json",
        p.parent / "circuit_semantics.json",
        Path("circuit_manifest.json"),
        Path("circuit_semantics.json")
    ]
    for pm in possible_manifests:
        if pm.exists():
            manifest_path = pm
            break

    manifest_data = {}
    if manifest_path:
        try:
            with open(manifest_path, "r", encoding="utf-8") as mf:
                manifest_data = json.load(mf)
            logger.info(f"Manifeste de circuit détecté et chargé : {manifest_path}")
        except Exception as e:
            logger.warning(f"Impossible de lire le manifeste {manifest_path} : {e}")

    # Si functional_clusters n'est pas dans le board_constraints, extraire depuis le circuit_manifest
    if not functional_clusters and manifest_data.get("functional_blocks"):
        for fb_id, fb in manifest_data["functional_blocks"].items():
            comps = [des for des, c in manifest_data.get("components", {}).items() if c.get("block") == fb_id]
            functional_clusters[fb_id.upper()] = comps

    # Extraction des règles de proximité : priorité à la déduction automatique depuis circuit_manifest
    proximity_rules = []
    if manifest_data.get("components"):
        for des, comp in manifest_data["components"].items():
            cem = comp.get("cem_target")
            if cem:
                ref = cem.get("component") or cem.get("connector")
                target_net = cem.get("rail") or cem.get("signal") or ""
                max_dist = float(cem.get("max_distance_mm", 5.0))
                reason = cem.get("reason", comp.get("description", ""))
                proximity_rules.append(ProximityRule(
                    component=des,
                    reference_component=ref,
                    max_distance_mm=max_dist,
                    target_net=target_net,
                    description=f"{comp.get('role', '')} {des} -> {ref} ({reason})"
                ))

    # Si aucune règle CEM n'a été déduite du manifeste, utiliser celles du fichier config s'il en a
    if not proximity_rules and data.get("proximity_rules"):
        for r in data["proximity_rules"]:
            proximity_rules.append(ProximityRule(
                component=r["component"],
                reference_component=r["reference_component"],
                max_distance_mm=float(r["max_distance_mm"]),
                target_net=r.get("target_net", ""),
                description=r.get("description", "")
            ))

    components = {}
    # 1. Composants explicites dans le fichier de config (ex: floorplan.json existant)
    for des, c in data.get("components", {}).items():
        components[des] = ComponentPlacement(
            designator=des,
            x_mil=float(c["x"]),
            y_mil=float(c["y"]),
            rotation=float(c.get("rot", 0.0)),
            layer=int(c.get("layer", 1)),
            description=c.get("desc", "")
        )

    # 2. Si le fichier de config est un board_constraints sans section components,
    # peupler avec la liste des composants de circuit_manifest
    if not components and manifest_data.get("components"):
        for des, comp in manifest_data["components"].items():
            # Si c'est une ancre mécanique fixe définie dans board_constraints, initialiser avec ses coordonnées
            anc = anchors.get(des)
            components[des] = ComponentPlacement(
                designator=des,
                x_mil=anc.target_x_mil if anc else 0.0,
                y_mil=anc.target_y_mil if anc else 0.0,
                rotation=anc.target_rotation if anc else 0.0,
                layer=1,
                description=comp.get("description", "")
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
