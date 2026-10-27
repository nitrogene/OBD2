#!/usr/bin/env python3
"""
Interface avec le Pont Local EasyEDA Pro pour l'Extraction DFM
=============================================================
Skill: pcb-dfm
Règle 1: Moteur agnostique, zéro composant codé en dur, exécution uv run.
Extrait les primitives (pastilles, vias, pistes, sérigraphie, composants, DRC)
et normalise toutes les dimensions en millimètres (1 mil = 0.0254 mm).
"""

import sys
import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logger = logging.getLogger("pcb_dfm.bridge")
MIL_TO_MM = 0.0254


class EasyEdaBridgeClient:
    """Client d'extraction des données géométriques du PCB actif dans EasyEDA Pro."""

    def __init__(self, host: str = "127.0.0.1", port: int = 49620, timeout: float = 30.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{self.host}:{self.port}"

    def check_health(self) -> bool:
        """Vérifie la santé du pont et la connexion à un client EasyEDA actif."""
        try:
            req = urllib.request.Request(f"{self.base_url}/health")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("status") == "ok" and data.get("edaConnected", False)
        except Exception as e:
            logger.debug(f"Pont non joignable: {e}")
            return False

    def execute_js(self, js_code: str) -> Any:
        """Exécute du code JavaScript dans le client EasyEDA Pro via le pont HTTP."""
        req = urllib.request.Request(
            f"{self.base_url}/execute",
            data=json.dumps({"code": js_code}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                if not result.get("success"):
                    raise RuntimeError(f"Erreur d'exécution EasyEDA: {result.get('error')}")
                return result.get("result")
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise RuntimeError(f"Erreur HTTP {e.code}: {error_body}")

    def extract_full_pcb_primitives(self) -> Dict[str, Any]:
        """Extrait l'ensemble des primitives PCB nécessaires aux audits DFM et SMT."""
        js_code = """
        const pads = typeof eda.pcb_PrimitivePad !== 'undefined' ? await eda.pcb_PrimitivePad.getAll() : [];
        const vias = typeof eda.pcb_PrimitiveVia !== 'undefined' ? await eda.pcb_PrimitiveVia.getAll() : [];
        const tracks = typeof eda.pcb_PrimitiveTrack !== 'undefined' ? await eda.pcb_PrimitiveTrack.getAll() : [];
        const comps = typeof eda.pcb_PrimitiveComponent !== 'undefined' ? await eda.pcb_PrimitiveComponent.getAll() : [];
        const strings = typeof eda.pcb_PrimitiveString !== 'undefined' ? await eda.pcb_PrimitiveString.getAll() : [];
        const lines = typeof eda.pcb_PrimitiveLine !== 'undefined' ? await eda.pcb_PrimitiveLine.getAll() : [];
        const polylines = typeof eda.pcb_PrimitivePolyline !== 'undefined' ? await eda.pcb_PrimitivePolyline.getAll() : [];
        
        let drcResult = [];
        try {
            if (typeof eda.pcb_Drc !== 'undefined') {
                drcResult = await eda.pcb_Drc.check(true, false, true);
            }
        } catch(e) {
            drcResult = [{ error: e.toString() }];
        }

        // Sérialisation des pastilles
        const serializedPads = pads.map(p => {
            const padGeom = p.pad || [];
            const holeGeom = p.hole || [];
            const shape = padGeom[0] || 'UNKNOWN';
            let width = 0;
            let height = 0;

            if (shape === 'POLYGON' && Array.isArray(padGeom[1])) {
                const pts = padGeom[1].filter(v => typeof v === 'number');
                let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
                for (let i = 0; i < pts.length; i += 2) {
                    const x = pts[i];
                    const y = pts[i + 1];
                    if (x < minX) minX = x;
                    if (x > maxX) maxX = x;
                    if (y < minY) minY = y;
                    if (y > maxY) maxY = y;
                }
                width = isFinite(maxX - minX) ? (maxX - minX) : 0;
                height = isFinite(maxY - minY) ? (maxY - minY) : 0;
            } else {
                width = typeof padGeom[1] === 'number' ? padGeom[1] : 0;
                height = typeof padGeom[2] === 'number' ? padGeom[2] : width;
            }

            let holeShape = 'NONE';
            let holeDia = 0;
            if (Array.isArray(holeGeom) && holeGeom.length > 0) {
                holeShape = holeGeom[0] || 'NONE';
                holeDia = typeof holeGeom[1] === 'number' ? holeGeom[1] : 0;
            }

            return {
                id: p.primitiveId,
                net: p.net || '',
                layer: p.layer,
                padNumber: p.padNumber || '',
                x: p.x || 0,
                y: p.y || 0,
                rotation: p.rotation || 0,
                shape: shape,
                width: width,
                height: height,
                holeShape: holeShape,
                holeDiameter: holeDia,
                metallization: !!p.metallization,
                expansion: p.solderMaskAndPasteMaskExpansion || { topSolderMask: 0, bottomSolderMask: 0 }
            };
        });

        // Sérialisation des vias
        const serializedVias = vias.map(v => ({
            id: v.primitiveId,
            net: v.net || '',
            x: v.x || 0,
            y: v.y || 0,
            diameter: v.diameter || 0,
            holeDiameter: v.holeDiameter || 0,
            solderMaskExpansion: v.solderMaskExpansion
        }));

        // Sérialisation des composants
        const serializedComps = comps.map(c => {
            const des = c.designator ? (typeof c.designator === 'object' ? c.designator.text : c.designator) : '';
            return {
                id: c.primitiveId,
                designator: des || '',
                footprint: c.footprint ? (c.footprint.name || c.footprint.uuid || '') : '',
                x: c.x || 0,
                y: c.y || 0,
                rotation: c.rotation || 0,
                layer: c.layer || 1
            };
        });

        // Sérialisation des textes de sérigraphie
        const serializedStrings = strings.map(s => ({
            id: s.primitiveId,
            text: s.text || '',
            x: s.x || 0,
            y: s.y || 0,
            rotation: s.rotation || 0,
            layer: s.layer || 3,
            height: s.height || 0,
            strokeWidth: s.lineWidth || s.strokeWidth || 0
        }));

        // Extraction du contour de carte (Board Outline = layer 11)
        let boardBounds = null;
        for (const pl of polylines) {
            if (pl.layer === 11 && pl.polygon && Array.isArray(pl.polygon.polygon)) {
                const geom = pl.polygon.polygon;
                if (geom[0] === 'R' && geom.length >= 7) {
                    boardBounds = {
                        minX: Math.min(geom[1], geom[1] + geom[3]),
                        maxX: Math.max(geom[1], geom[1] + geom[3]),
                        minY: Math.min(geom[2] - geom[4], geom[2]),
                        maxY: Math.max(geom[2] - geom[4], geom[2])
                    };
                }
            }
        }

        return {
            pads: serializedPads,
            vias: serializedVias,
            components: serializedComps,
            strings: serializedStrings,
            boardBounds: boardBounds,
            drc: drcResult
        };
        """
        raw_data = self.execute_js(js_code)
        return self._normalize_to_mm(raw_data)

    def _normalize_to_mm(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Convertit toutes les coordonnées et dimensions géométriques de mils en millimètres."""
        normalized_pads = []
        for p in raw.get("pads", []):
            top_exp = (p.get("expansion", {}).get("topSolderMask", 0) or 0) * MIL_TO_MM
            bot_exp = (p.get("expansion", {}).get("bottomSolderMask", 0) or 0) * MIL_TO_MM
            normalized_pads.append({
                "id": p["id"],
                "net": p["net"],
                "layer": p["layer"],
                "padNumber": str(p["padNumber"]),
                "x_mm": round(p["x"] * MIL_TO_MM, 4),
                "y_mm": round(p["y"] * MIL_TO_MM, 4),
                "rotation": p["rotation"],
                "shape": p["shape"],
                "width_mm": round(p["width"] * MIL_TO_MM, 4),
                "height_mm": round(p["height"] * MIL_TO_MM, 4),
                "holeShape": p["holeShape"],
                "holeDiameter_mm": round(p["holeDiameter"] * MIL_TO_MM, 4),
                "metallization": p["metallization"],
                "topExpansion_mm": round(top_exp, 4),
                "bottomExpansion_mm": round(bot_exp, 4)
            })

        normalized_vias = []
        for v in raw.get("vias", []):
            normalized_vias.append({
                "id": v["id"],
                "net": v["net"],
                "x_mm": round(v["x"] * MIL_TO_MM, 4),
                "y_mm": round(v["y"] * MIL_TO_MM, 4),
                "diameter_mm": round(v["diameter"] * MIL_TO_MM, 4),
                "holeDiameter_mm": round(v["holeDiameter"] * MIL_TO_MM, 4),
                "annularRing_mm": round((v["diameter"] - v["holeDiameter"]) / 2.0 * MIL_TO_MM, 4)
            })

        normalized_comps = []
        for c in raw.get("components", []):
            normalized_comps.append({
                "id": c["id"],
                "designator": c["designator"],
                "footprint": c["footprint"],
                "x_mm": round(c["x"] * MIL_TO_MM, 4),
                "y_mm": round(c["y"] * MIL_TO_MM, 4),
                "rotation": c["rotation"],
                "layer": c["layer"]
            })

        normalized_strings = []
        for s in raw.get("strings", []):
            normalized_strings.append({
                "id": s["id"],
                "text": s["text"],
                "x_mm": round(s["x"] * MIL_TO_MM, 4),
                "y_mm": round(s["y"] * MIL_TO_MM, 4),
                "rotation": s["rotation"],
                "layer": s["layer"],
                "height_mm": round(s["height"] * MIL_TO_MM, 4),
                "strokeWidth_mm": round(s["strokeWidth"] * MIL_TO_MM, 4)
            })

        normalized_bounds = None
        raw_bounds = raw.get("boardBounds")
        if raw_bounds:
            normalized_bounds = {
                "minX_mm": round(raw_bounds["minX"] * MIL_TO_MM, 4),
                "maxX_mm": round(raw_bounds["maxX"] * MIL_TO_MM, 4),
                "minY_mm": round(raw_bounds["minY"] * MIL_TO_MM, 4),
                "maxY_mm": round(raw_bounds["maxY"] * MIL_TO_MM, 4),
                "width_mm": round((raw_bounds["maxX"] - raw_bounds["minX"]) * MIL_TO_MM, 4),
                "height_mm": round((raw_bounds["maxY"] - raw_bounds["minY"]) * MIL_TO_MM, 4)
            }

        return {
            "pads": normalized_pads,
            "vias": normalized_vias,
            "components": normalized_comps,
            "strings": normalized_strings,
            "boardBounds": normalized_bounds,
            "drc": raw.get("drc", [])
        }
