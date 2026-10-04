#!/usr/bin/env python3
"""
export_geometry.py - Extracteur Géométrique Live depuis EasyEDA Pro (Agnostique)
================================================================================
Conforme à la Règle 0 (AGENTS.md) :
- Aucune référence en dur à des composants ou des coordonnées spécifiques du projet.
- Manipulation d'abstractions (composants, pastilles, nets, contour de carte).
- Unité interne normalisée : millimètre (mm).
- Fonctionne en CLI ou en module Python importable (en mémoire).
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from easyeda_client import EasyEDAClient

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("GeometryExporter")

MIL_TO_MM = 0.0254


@dataclass
class PadGeometry:
    number: str
    net: str
    x_mm: float
    y_mm: float
    dx_0_mm: float  # Décalage relatif au centre à rotation 0°
    dy_0_mm: float
    width_mm: float = 0.0
    height_mm: float = 0.0
    shape: str = "RECT"
    drill_mm: float = 0.0


@dataclass
class ComponentGeometry:
    designator: str
    primitive_id: str
    footprint: str
    x_mm: float
    y_mm: float
    rotation: float
    layer: int
    locked: bool
    pads: List[PadGeometry] = field(default_factory=list)


@dataclass
class BoardGeometrySnapshot:
    extracted_at: str
    components_count: int
    pads_count: int
    nets_count: int
    board_outline: Dict[str, Any]
    components: Dict[str, ComponentGeometry]
    nets: Dict[str, List[Tuple[str, str]]]  # net_name -> list of (designator, pin_number)


def rotate_vector(dx: float, dy: float, angle_deg: float) -> Tuple[float, float]:
    """Applique une rotation 2D d'angle angle_deg (degrés anti-horaires)."""
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    return (dx * cos_a - dy * sin_a, dx * sin_a + dy * cos_a)


def compute_relative_pad_at_zero(
    comp_x: float,
    comp_y: float,
    comp_rot: float,
    pad_x: float,
    pad_y: float
) -> Tuple[float, float]:
    """
    Calcule le décalage (dx_0, dy_0) de la pastille par rapport au centre
    du composant à rotation 0°.
    Inversion de rotation par -comp_rot.
    """
    dx = pad_x - comp_x
    dy = pad_y - comp_y
    # Applique la rotation inverse (-comp_rot)
    return rotate_vector(dx, dy, -comp_rot)


def extract_board_geometry(client: Optional[EasyEDAClient] = None) -> BoardGeometrySnapshot:
    """Extrait l'ensemble des données géométriques réelles depuis le PCB EasyEDA Pro actif."""
    c = client or EasyEDAClient()

    if not c.is_pcb_active():
        raise RuntimeError("Aucun document PCB actif détecté dans EasyEDA Pro.")

    # 1. Extraction JS en bloc de tous les composants et leurs broches (1 seule requête réseau)
    js_code = """
    try {
        const comps = await eda.pcb_PrimitiveComponent.getAll();
        if (!comps || !comps.length) return [];
        const out = [];
        for (const comp of comps) {
            const pins = (await comp.getAllPins?.()) || [];
            const pads = [];
            for (const p of pins) {
                pads.push({
                    id: p.getState_PrimitiveId(),
                    number: p.getState_PadNumber ? String(p.getState_PadNumber()) : "",
                    x: p.getState_X(),
                    y: p.getState_Y(),
                    rotation: p.getState_Rotation ? p.getState_Rotation() : 0,
                    net: p.getState_Net ? p.getState_Net() : "",
                    padInfo: p.getState_Pad ? p.getState_Pad() : null,
                    holeInfo: p.getState_Hole ? p.getState_Hole() : null
                });
            }
            const fp = comp.getState_Footprint ? comp.getState_Footprint() : null;
            out.push({
                id: comp.getState_PrimitiveId(),
                designator: comp.getState_Designator(),
                x: comp.getState_X(),
                y: comp.getState_Y(),
                rotation: comp.getState_Rotation(),
                layer: comp.getState_Layer(),
                locked: comp.getState_PrimitiveLock ? comp.getState_PrimitiveLock() : false,
                footprint: fp && fp.name ? fp.name : "UNKNOWN",
                pads: pads
            });
        }
        return out;
    } catch(e) {
        return { error: e.message };
    }
    """

    raw_comps = c.execute_js(js_code)
    if isinstance(raw_comps, dict) and "error" in raw_comps:
        raise RuntimeError(f"Erreur API EasyEDA lors de l'extraction des composants : {raw_comps['error']}")

    # 2. Récupération du contour de carte
    outline_data = c.get_board_outline()

    components: Dict[str, ComponentGeometry] = {}
    nets: Dict[str, List[Tuple[str, str]]] = {}
    total_pads = 0

    for item in raw_comps:
        des = item.get("designator")
        if not des:
            continue

        cx_mm = item.get("x", 0.0) * MIL_TO_MM
        cy_mm = item.get("y", 0.0) * MIL_TO_MM
        rot = item.get("rotation", 0.0)
        layer = item.get("layer", 1)
        locked = bool(item.get("locked", False))
        footprint = item.get("footprint", "UNKNOWN")

        pads_list: List[PadGeometry] = []
        for p in item.get("pads", []):
            px_mm = p.get("x", 0.0) * MIL_TO_MM
            py_mm = p.get("y", 0.0) * MIL_TO_MM
            num = p.get("number", "")
            net = p.get("net", "")

            dx_0, dy_0 = compute_relative_pad_at_zero(cx_mm, cy_mm, rot, px_mm, py_mm)

            pad_w = 0.0
            pad_h = 0.0
            shape = "RECT"
            p_info = p.get("padInfo")
            if isinstance(p_info, (list, tuple)) and len(p_info) >= 3:
                shape = str(p_info[0])
                pad_w = float(p_info[1]) * MIL_TO_MM
                pad_h = float(p_info[2]) * MIL_TO_MM

            drill_mm = 0.0
            h_info = p.get("holeInfo")
            if isinstance(h_info, (list, tuple)) and len(h_info) >= 2:
                drill_mm = float(h_info[1]) * MIL_TO_MM

            pad_obj = PadGeometry(
                number=num,
                net=net,
                x_mm=round(px_mm, 4),
                y_mm=round(py_mm, 4),
                dx_0_mm=round(dx_0, 4),
                dy_0_mm=round(dy_0, 4),
                width_mm=round(pad_w, 4),
                height_mm=round(pad_h, 4),
                shape=shape,
                drill_mm=round(drill_mm, 4)
            )
            pads_list.append(pad_obj)
            total_pads += 1

            # Graphe de la netlist
            if net:
                if net not in nets:
                    nets[net] = []
                nets[net].append((des, num))

        components[des] = ComponentGeometry(
            designator=des,
            primitive_id=item.get("id", ""),
            footprint=footprint,
            x_mm=round(cx_mm, 4),
            y_mm=round(cy_mm, 4),
            rotation=rot,
            layer=layer,
            locked=locked,
            pads=pads_list
        )

    # Horodatage ISO
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    return BoardGeometrySnapshot(
        extracted_at=ts,
        components_count=len(components),
        pads_count=total_pads,
        nets_count=len(nets),
        board_outline=outline_data,
        components=components,
        nets=nets
    )


def save_snapshot_to_json(snapshot: BoardGeometrySnapshot, output_path: Path):
    """Sauvegarde le snapshot en JSON sérialisé."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Conversion dataclass vers dictionnaire standard
    data = {
        "extracted_at": snapshot.extracted_at,
        "components_count": snapshot.components_count,
        "pads_count": snapshot.pads_count,
        "nets_count": snapshot.nets_count,
        "board_outline": snapshot.board_outline,
        "components": {
            des: asdict(comp) for des, comp in snapshot.components.items()
        },
        "nets": snapshot.nets
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Extraction géométrique live des composants, pastilles et nets depuis EasyEDA Pro"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".agents/skills/pcb-placer/.cache/netlist_geometry.json"),
        help="Chemin du fichier de sortie JSON (défaut : cache interne non versionné)"
    )

    args = parser.parse_args()

    logger.info("Extraction de la géométrie du PCB actif depuis EasyEDA Pro...")
    t0 = time.time()
    try:
        snapshot = extract_board_geometry()
        save_snapshot_to_json(snapshot, args.output)
        elapsed = time.time() - t0

        logger.info("================================================================================")
        logger.info("                   EXTRACTION GÉOMÉTRIQUE RÉUSSIE                              ")
        logger.info("================================================================================")
        logger.info(f"Fichier généré : {args.output}")
        logger.info(f"Temps de capture: {elapsed:.2f} s")
        logger.info(f"Composants      : {snapshot.components_count}")
        logger.info(f"Pastilles (Pads): {snapshot.pads_count}")
        logger.info(f"Nets connectés  : {snapshot.nets_count}")
        logger.info("================================================================================\n")
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'extraction : {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
