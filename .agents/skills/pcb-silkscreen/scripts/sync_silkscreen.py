#!/usr/bin/env python3
"""
sync_silkscreen.py - Synchronisation Bidirectionnelle et Revue Interactive de Sérigraphie
==========================================================================================
Conforme à la Règle 1 (AGENTS.md) :
- Zéro composant ou coordonnée en dur. Moteur agnostique.
- Mode PULL : Extrait les positions réelles des textes depuis EasyEDA Pro, calcule les
  vecteurs relatifs (ΔX, ΔY) par rapport aux composants ou pastilles, et met à jour
  documents/pcb/silkscreen.json.
- Mode PUSH : Injecte fidèlement silkscreen.json dans EasyEDA Pro via apply_silkscreen.py.
- Mode INTERACTIVE : Point de contrôle de fin de pipeline permettant la revue manuelle
  visuelle avec capture immédiate dans le JSON et re-certification DFM.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path.cwd() if (Path.cwd() / "documents").exists() else SCRIPT_DIR.parents[3]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sync_silkscreen")

MIL_TO_MM = 0.0254


class EasyEDASilkscreenBridge:
    """Client d'extraction métrologique depuis EasyEDA Pro."""

    def __init__(self, port: int = 49620, timeout: float = 15.0):
        self.port = port
        self.url = f"http://127.0.0.1:{port}/execute"
        self.timeout = timeout

    def execute_js(self, code: str) -> Any:
        payload = json.dumps({"code": code}).encode("utf-8")
        req = urllib.request.Request(self.url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if not data.get("success", False):
                    err = data.get("error", "Erreur inconnue du pont EasyEDA")
                    raise RuntimeError(f"Erreur API EasyEDA : {err}")
                return data.get("result")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Erreur HTTP {e.code} du pont EasyEDA : {err_body}")
        except urllib.error.URLError as e:
            raise ConnectionError(f"Impossible de joindre le pont EasyEDA sur http://127.0.0.1:{self.port} : {e}")

    def fetch_scene_primitives(self) -> Dict[str, Any]:
        """Extrait l'ensemble des textes, composants, pastilles et contours PCB."""
        code = """
        // 1. S'assurer que le document PCB principal est bien l'onglet actif
        try {
            const tree = await eda.dmt_EditorControl.getSplitScreenTree();
            const pcbTab = tree.tabs && tree.tabs.find(t => t.data && t.data.doctype === 3);
            if (pcbTab) {
                await eda.dmt_EditorControl.activateDocument(pcbTab.tabId);
                await new Promise(r => setTimeout(r, 150));
            }
        } catch(e_tab) {}

        const strings = (await eda.pcb_PrimitiveString.getAll()) || [];
        const comps = (await eda.pcb_PrimitiveComponent.getAll()) || [];
        const pads = (await eda.pcb_PrimitivePad.getAll()) || [];

        const strList = strings.map(s => {
            const rawX = s.getState_X ? s.getState_X() : (s.x || 0);
            const rawY = s.getState_Y ? s.getState_Y() : (s.y || 0);
            const txt = s.getState_Text ? s.getState_Text() : (s.text || '');
            const lay = s.getState_Layer ? s.getState_Layer() : (s.layer || 0);
            const rot = s.getState_Rotation ? s.getState_Rotation() : (s.rotation || 0);
            const fs = s.getState_FontSize ? s.getState_FontSize() : (s.fontSize || s.height || 39.37);
            const lw = s.getState_LineWidth ? s.getState_LineWidth() : (s.lineWidth || 5.9);
            const pid = s.getState_PrimitiveId ? s.getState_PrimitiveId() : (s.primitiveId || s.id || '');
            return {
                id: pid,
                text: txt,
                layer: lay,
                x_mm: Number((rawX * 0.0254).toFixed(4)),
                y_mm: Number((rawY * 0.0254).toFixed(4)),
                rotation: Number(rot),
                fontSize_mm: Number((fs * 0.0254).toFixed(3)),
                lineWidth_mm: Number((lw * 0.0254).toFixed(3))
            };
        });

        const compList = comps.map(c => {
            const rawX = c.getState_X ? c.getState_X() : (c.x || 0);
            const rawY = c.getState_Y ? c.getState_Y() : (c.y || 0);
            const des = c.getState_Designator ? c.getState_Designator() : (c.designator || '');
            const lay = c.getState_Layer ? c.getState_Layer() : (c.layer || 1);
            const rot = c.getState_Rotation ? c.getState_Rotation() : (c.rotation || 0);
            const pid = c.getState_PrimitiveId ? c.getState_PrimitiveId() : (c.primitiveId || c.id || '');
            return {
                id: pid,
                des: des,
                layer: lay,
                x_mm: Number((rawX * 0.0254).toFixed(4)),
                y_mm: Number((rawY * 0.0254).toFixed(4)),
                rotation: Number(rot)
            };
        });

        const padList = pads.map(p => {
            const rawX = p.getState_X ? p.getState_X() : (p.x || 0);
            const rawY = p.getState_Y ? p.getState_Y() : (p.y || 0);
            const des = p.getState_ComponentDesignator ? p.getState_ComponentDesignator() : (p.componentDesignator || '');
            const num = p.getState_Number ? p.getState_Number() : (p.padNumber || p.number || '');
            const lay = p.getState_Layer ? p.getState_Layer() : (p.layer || 0);
            const pid = p.getState_PrimitiveId ? p.getState_PrimitiveId() : (p.primitiveId || p.id || '');
            return {
                id: pid,
                des: des,
                num: num,
                layer: lay,
                x_mm: Number((rawX * 0.0254).toFixed(4)),
                y_mm: Number((rawY * 0.0254).toFixed(4))
            };
        });

        return { strings: strList, components: compList, pads: padList };
        """
        return self.execute_js(code)


def pull_silkscreen(
    silkscreen_path: Path,
    constraints_path: Path,
    port: int = 49620
) -> bool:
    """Capture les modifications manuelles de sérigraphie depuis EasyEDA Pro et met à jour silkscreen.json."""
    logger.info("==================================================")
    logger.info("📥 RÉTRO-SYNCHRONISATION SÉRIGRAPHIE (EASYEDA -> JSON)")
    logger.info("==================================================")

    if not silkscreen_path.exists():
        logger.error(f"Fichier de configuration introuvable : {silkscreen_path}")
        return False

    with open(silkscreen_path, "r", encoding="utf-8") as f:
        silk_data = json.load(f)

    with open(constraints_path, "r", encoding="utf-8") as f:
        constraints_data = json.load(f)

    board_cfg = constraints_data.get("board", {})
    board_w = float(board_cfg.get("width_mm", 81.28))
    board_h = float(board_cfg.get("height_mm", 35.56))

    bridge = EasyEDASilkscreenBridge(port=port)
    try:
        scene = bridge.fetch_scene_primitives()
    except Exception as e:
        logger.error(f"Échec de connexion au pont EasyEDA : {e}")
        return False

    strings: List[Dict[str, Any]] = scene.get("strings", [])
    components: List[Dict[str, Any]] = scene.get("components", [])
    pads: List[Dict[str, Any]] = scene.get("pads", [])

    comps_map = {c["des"]: c for c in components if c.get("des")}
    pads_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for p in pads:
        des = p.get("des", "")
        num = str(p.get("num", ""))
        if des and num:
            pads_map[(des, num)] = p

    layer_to_id = {"top": 3, "bottom": 4}
    modified_count = 0

    for layer_key, layer_id in layer_to_id.items():
        layer_cfg = silk_data.get(layer_key, {})
        layer_strings = [s for s in strings if s.get("layer") == layer_id]

        # 1. Mise à jour des component_legends (Ancrage relatif aux composants)
        legends = layer_cfg.get("component_legends", [])
        for leg in legends:
            ref = leg.get("component")
            raw_text = leg.get("text", "")
            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
            if not lines or ref not in comps_map:
                continue

            first_line = lines[0]
            # Recherche de la chaîne correspondante dans la scène EasyEDA
            matched_str = next((s for s in layer_strings if s.get("text", "").strip() == first_line), None)
            if matched_str:
                comp = comps_map[ref]
                dx = round(matched_str["x_mm"] - comp["x_mm"], 3)
                dy = round(matched_str["y_mm"] - comp["y_mm"], 3)
                rot = round(matched_str.get("rotation", 0.0), 1)

                leg["relative_offset_mm"] = [dx, dy]
                if abs(rot) > 0.01:
                    leg["rotation"] = rot
                elif "rotation" in leg:
                    del leg["rotation"]

                # Retrait de la position 1D rigide devenue obsolète
                if "position" in leg:
                    del leg["position"]
                if "offset_mm" in leg:
                    del leg["offset_mm"]

                logger.info(f"   [Legend {ref}] Décalage relatif capturé : ΔX = {dx:+.2f} mm, ΔY = {dy:+.2f} mm (rot: {rot}°)")
                modified_count += 1

        # 2. Mise à jour des pin_labels (Ancrage relatif aux broches/pastilles)
        pin_labels_list = layer_cfg.get("pin_labels", [])
        for pl in pin_labels_list:
            ref = pl.get("component")
            pins_dict = pl.get("pins", {})
            offsets_dict = pl.setdefault("offsets_mm", {})

            for pin_num, pin_label in pins_dict.items():
                pad_key = (ref, str(pin_num))
                if pad_key not in pads_map:
                    continue
                pad = pads_map[pad_key]
                matched_str = next((s for s in layer_strings if s.get("text", "").strip() == pin_label.strip()), None)
                if matched_str:
                    dx = round(matched_str["x_mm"] - pad["x_mm"], 3)
                    dy = round(matched_str["y_mm"] - pad["y_mm"], 3)
                    offsets_dict[str(pin_num)] = [dx, dy]
                    logger.info(f"   [Pin {ref}.{pin_num} - '{pin_label}'] Décalage capturé : ΔX = {dx:+.2f} mm, ΔY = {dy:+.2f} mm")
                    modified_count += 1

        # 3. Mise à jour des title_blocks (Ancrage relatif aux coins du PCB)
        title_blocks = layer_cfg.get("title_blocks", [])
        for tb in title_blocks:
            anchor = tb.get("anchor", "bottom_left")
            raw_text = tb.get("text", "")
            lines = raw_text if isinstance(raw_text, list) else raw_text.split("\n")
            lines = [l.strip() for l in lines if l.strip()]
            if not lines:
                continue

            first_line = lines[0]
            matched_str = next((s for s in layer_strings if s.get("text", "").strip() == first_line), None)
            if matched_str:
                # Calcul de l'ancre de référence
                if anchor == "bottom_left":
                    ax, ay = 0.0, 0.0
                elif anchor == "bottom_right":
                    ax, ay = board_w, 0.0
                elif anchor == "top_left":
                    ax, ay = 0.0, board_h
                elif anchor == "top_right":
                    ax, ay = board_w, board_h
                else:
                    ax, ay = 0.0, 0.0

                dx = round(matched_str["x_mm"] - ax, 3)
                dy = round(matched_str["y_mm"] - ay, 3)
                tb["offset_mm"] = [dx, dy]
                logger.info(f"   [TitleBlock {anchor}] Décalage capturé : [{dx:.2f}, {dy:.2f}] mm")
                modified_count += 1

    # Sauvegarde formelle dans silkscreen.json
    with open(silkscreen_path, "w", encoding="utf-8") as f:
        json.dump(silk_data, f, indent=2, ensure_ascii=False)

    logger.info(f"💾 Fichier '{silkscreen_path}' synchronisé avec succès ({modified_count} éléments capturés).")
    return True


def push_silkscreen(
    silkscreen_path: Path,
    constraints_path: Path,
    port: int = 49620
) -> bool:
    """Injecte le contenu de silkscreen.json dans EasyEDA Pro via apply_silkscreen.py."""
    logger.info("==================================================")
    logger.info("📤 INJECTION SÉRIGRAPHIE (JSON -> EASYEDA)")
    logger.info("==================================================")
    apply_script = SCRIPT_DIR / "apply_silkscreen.py"
    cmd = [
        "uv", "run", "python", str(apply_script),
        "--silkscreen", str(silkscreen_path),
        "--constraints", str(constraints_path),
        "--port", str(port)
    ]
    res = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return res.returncode == 0


def run_interactive_review(
    silkscreen_path: Path,
    constraints_path: Path,
    port: int = 49620
) -> bool:
    """Exécute l'étape interactive de revue manuelle et de capture finale."""
    print("\n" + "=" * 80)
    print("🔍 ÉTAPE INTERACTIVE : REVUE MANUELLE DE SÉRIGRAPHIE (EASYEDA PRO)")
    print("=" * 80)
    print("1. Ouvrez EasyEDA Pro et activez la couche BottomSilk (face arrière) ou TopSilk.")
    print("2. Déplacez, orientez ou alignez vos textes librement selon votre confort visuel.")
    print("3. Une fois vos ajustements terminés dans EasyEDA Pro :")
    print("   -> Appuyez sur [Entrée] pour capturer automatiquement les positions relatives.")
    print("   -> Ou tapez 'q' pour ignorer et conserver le JSON intact.\n")

    try:
        user_input = input("Action ([Entrée] = Valider et Capturer / 'q' = Ignorer) : ").strip()
    except EOFError:
        user_input = ""

    if user_input.lower() == "q":
        logger.info("Revue manuelle ignorée par l'utilisateur. Aucune modification apportée au JSON.")
        return True

    # Capture des positions manuelles
    success = pull_silkscreen(silkscreen_path, constraints_path, port=port)
    if not success:
        logger.error("❌ Échec de la capture de sérigraphie.")
        return False

    # Audit DFM immédiat pour certifier l'absence de chevauchement
    logger.info("🔍 Lancement de la certification DFM post-ajustement...")
    dfm_script = PROJECT_ROOT / ".agents" / "skills" / "pcb-dfm" / "scripts" / "dfm_pipeline.py"
    dfm_cmd = [
        "uv", "run", "python", str(dfm_script),
        "--config", str(PROJECT_ROOT / ".agents" / "skills" / "pcb-dfm" / "config" / "rules_jlcpcb.json"),
        "--bom", str(PROJECT_ROOT / "documents" / "schema" / "bom.json"),
        "--port", str(port)
    ]
    res = subprocess.run(dfm_cmd, cwd=str(PROJECT_ROOT))
    if res.returncode != 0:
        logger.warning("⚠️ L'audit DFM a relevé des anomalies après déplacement. Vérifiez le rapport documents/pcb/dfm_report.md.")

    return True


def main():
    parser = argparse.ArgumentParser(description="Synchronisation bidirectionnelle de sérigraphie EasyEDA Pro")
    parser.add_argument("action", choices=["pull", "push", "interactive"], help="Action à exécuter : pull, push ou interactive")
    parser.add_argument("--silkscreen", default="documents/pcb/silkscreen.json", help="Chemin vers silkscreen.json")
    parser.add_argument("--constraints", default="documents/pcb/constraints.json", help="Chemin vers constraints.json")
    parser.add_argument("--port", type=int, default=49620, help="Port du pont EasyEDA Pro")
    args = parser.parse_args()

    silkscreen_p = PROJECT_ROOT / args.silkscreen
    constraints_p = PROJECT_ROOT / args.constraints

    if args.action == "pull":
        ok = pull_silkscreen(silkscreen_p, constraints_p, port=args.port)
    elif args.action == "push":
        ok = push_silkscreen(silkscreen_p, constraints_p, port=args.port)
    elif args.action == "interactive":
        ok = run_interactive_review(silkscreen_p, constraints_p, port=args.port)
    else:
        parser.print_help()
        ok = False

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
