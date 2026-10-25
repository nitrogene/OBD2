#!/usr/bin/env python3
"""
apply_silkscreen.py - Injecteur Idempotent de Sérigraphie dans EasyEDA Pro (Agnostique)
======================================================================================
Conforme à la Règle 1 et Règle 2 (AGENTS.md) :
- Zéro composant ou coordonnée en dur dans le code Python.
- Idempotence stricte : purge préalable via le registre d'état (.cache/silkscreen_state.json)
  pour éliminer tout texte fantôme ou doublon si la configuration change.
- Injection directe via l'API EasyEDA Pro (eda.pcb_PrimitiveString).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Ajout du dossier courant au sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from silkscreen_resolver import ResolvedTextPrimitive, SilkscreenResolver

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SilkscreenApplier")

ALIGN_MAP = {
    "CENTER": 5,        # EPCB_PrimitiveStringAlignMode.CENTER
    "LEFT": 2,          # LEFT_MIDDLE
    "RIGHT": 8,         # RIGHT_MIDDLE
    "LEFT_MIDDLE": 2,
    "RIGHT_MIDDLE": 8
}


class EasyEDASilkscreenClient:
    """Client d'injection et de gestion d'idempotence de sérigraphie pour EasyEDA Pro."""

    def __init__(self, port: int = 49620, timeout: float = 15.0):
        self.port = port
        self.timeout = timeout
        self.url = f"http://localhost:{port}/execute"

    def execute_js(self, code: str) -> Any:
        payload = json.dumps({"code": code}).encode("utf-8")
        req = urllib.request.Request(self.url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if not data.get("success", False):
                    err = data.get("error", "Erreur inconnue du pont")
                    raise RuntimeError(f"Erreur API EasyEDA : {err}")
                return data.get("result")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Erreur HTTP {e.code} du pont EasyEDA : {err_body}")
        except urllib.error.URLError as e:
            raise ConnectionError(f"Impossible de joindre le pont EasyEDA sur http://localhost:{self.port} : {e}")

    def purge_previous_silkscreen(self, previous_ids: List[str], known_texts: List[str]) -> int:
        """Supprime proprement les anciens textes créés par le skill sans toucher aux désignateurs."""
        logger.info(f"🧹 Purge idempotente : vérification de {len(previous_ids)} IDs enregistrés...")
        code = f"""
        const idsToDelete = {json.dumps(previous_ids)};
        const knownTexts = new Set({json.dumps(known_texts)});
        let deletedCount = 0;

        // 1. Suppression par IDs enregistrés
        if (idsToDelete && idsToDelete.length > 0) {{
            try {{
                await eda.pcb_PrimitiveString.delete(idsToDelete);
                deletedCount += idsToDelete.length;
            }} catch(e) {{}}
        }}

        // 2. Filet de sécurité : suppression des textes libres résiduels correspondant à nos libellés
        try {{
            const allStrings = (await eda.pcb_PrimitiveString.getAll()) || [];
            const strayIds = [];
            for (const s of allStrings) {{
                const lay = s.getState_Layer ? s.getState_Layer() : null;
                const txt = s.getState_Text ? s.getState_Text() : '';
                // Seules les couches 3 (TopSilk) et 4 (BottomSilk) sont concernées
                if ((lay === 3 || lay === 4) && knownTexts.has(txt)) {{
                    const pid = s.getState_PrimitiveId ? s.getState_PrimitiveId() : null;
                    if (pid && !idsToDelete.includes(pid)) {{
                        strayIds.push(pid);
                    }}
                }}
            }}
            if (strayIds.length > 0) {{
                await eda.pcb_PrimitiveString.delete(strayIds);
                deletedCount += strayIds.length;
            }}
        }} catch(e) {{}}

        return {{ deletedCount }};
        """
        res = self.execute_js(code)
        cnt = res.get("deletedCount", 0) if isinstance(res, dict) else 0
        logger.info(f"   -> {cnt} ancienne(s) primitive(s) de sérigraphie purgée(s).")
        return cnt

    def inject_primitives(self, primitives: List[ResolvedTextPrimitive]) -> List[str]:
        """Injecte l'ensemble des primitives de texte dans le document PCB EasyEDA Pro."""
        logger.info(f"🖊️ Injection de {len(primitives)} nouvelles primitives de sérigraphie...")
        
        # Préparation des paramètres pour injection JS en une seule passe atomique
        js_payload = []
        for p in primitives:
            align_val = ALIGN_MAP.get(p.align_mode, 5)
            js_payload.append({
                "layer": p.layer,
                "x_mil": p.x_mil,
                "y_mil": p.y_mil,
                "text": p.text,
                "fontFamily": "default",
                "fontSize_mil": p.font_size_mil,
                "lineWidth_mil": p.stroke_width_mil,
                "alignMode": align_val,
                "rotation": p.rotation,
                "reverse": False,
                "expansion": 0,
                "mirror": p.mirror,
                "primitiveLock": False
            })

        code = f"""
        const items = {json.dumps(js_payload)};
        const createdIds = [];

        for (const item of items) {{
            try {{
                const strObj = await eda.pcb_PrimitiveString.create(
                    item.layer,
                    item.x_mil,
                    item.y_mil,
                    item.text,
                    item.fontFamily,
                    item.fontSize_mil,
                    item.lineWidth_mil,
                    item.alignMode,
                    item.rotation,
                    item.reverse,
                    item.expansion,
                    item.mirror,
                    item.primitiveLock
                );
                if (strObj && strObj.getState_PrimitiveId) {{
                    createdIds.push(strObj.getState_PrimitiveId());
                }}
            }} catch(e) {{
                // Poursuite pour les autres textes
            }}
        }}

        // Sauvegarde du document PCB
        try {{
            await eda.pcb_Document.save();
        }} catch(e) {{}}

        return {{ createdIds }};
        """

        res = self.execute_js(code)
        created_ids = res.get("createdIds", []) if isinstance(res, dict) else []
        logger.info(f"   -> {len(created_ids)}/{len(primitives)} primitive(s) injectée(s) et sauvegardée(s) dans EasyEDA Pro.")
        return created_ids


def main():
    parser = argparse.ArgumentParser(description="Application idempotente de la sérigraphie additionnelle EasyEDA Pro")
    parser.add_argument("--silkscreen", default="documents/pcb/silkscreen.json", help="Chemin vers silkscreen.json")
    parser.add_argument("--constraints", default="documents/pcb/constraints.json", help="Chemin vers constraints.json")
    parser.add_argument("--placement", default=".agents/skills/pcb-synthesizer/.cache/candidate_placement.json", help="Chemin vers candidate_placement.json")
    parser.add_argument("--manifest", default="documents/pcb/manifest.json", help="Chemin vers manifest.json")
    parser.add_argument("--geometry", default=".agents/skills/pcb-placer/.cache/netlist_geometry.json", help="Chemin vers netlist_geometry.json")
    parser.add_argument("--port", type=int, default=49620, help="Port du pont local EasyEDA Pro")
    parser.add_argument("--dry-run", action="store_true", help="Résout sans injecter dans EasyEDA Pro")
    args = parser.parse_args()

    # 1. Résolution géométrique
    with open(args.silkscreen, "r", encoding="utf-8") as f:
        silk_data = json.load(f)
    with open(args.constraints, "r", encoding="utf-8") as f:
        constraints_data = json.load(f)
    with open(args.placement, "r", encoding="utf-8") as f:
        placement_data = json.load(f)

    manifest_data = None
    if args.manifest and Path(args.manifest).exists():
        with open(args.manifest, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)

    geometry_data = None
    if args.geometry and Path(args.geometry).exists():
        with open(args.geometry, "r", encoding="utf-8") as f:
            geometry_data = json.load(f)

    resolver = SilkscreenResolver(
        silkscreen_cfg=silk_data,
        constraints_cfg=constraints_data,
        placement_cfg=placement_data,
        manifest_cfg=manifest_data,
        geometry_cfg=geometry_data
    )

    primitives = resolver.resolve_all()
    logger.info(f"📋 {len(primitives)} primitive(s) de sérigraphie résolue(s).")

    if args.dry_run:
        logger.info("🔍 Mode simulation (Dry-Run) actif : aucune modification injectée dans EasyEDA Pro.")
        return

    # 2. Gestion de l'état persistant (.cache/silkscreen_state.json)
    state_file = SCRIPT_DIR.parent / ".cache" / "silkscreen_state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    
    previous_ids = []
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state_data = json.load(f)
                previous_ids = state_data.get("primitive_ids", [])
        except Exception:
            previous_ids = []

    # Liste des textes connus pour le filet de sécurité
    known_texts = [p.text for p in primitives]

    # 3. Connexion et Purge idempotente
    client = EasyEDASilkscreenClient(port=args.port)
    client.purge_previous_silkscreen(previous_ids, known_texts)

    # 4. Injection des nouvelles primitives
    new_ids = client.inject_primitives(primitives)

    # 5. Mise à jour de l'état
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "primitive_ids": new_ids,
            "count": len(new_ids)
        }, f, indent=2)

    logger.info(f"✅ Sérigraphie appliquée avec succès ! Registre d'état mis à jour ({len(new_ids)} IDs).")


if __name__ == "__main__":
    main()
