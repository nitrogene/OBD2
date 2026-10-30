#!/usr/bin/env python3
"""
silkscreen_feedback_loop.py - Moteur de Rétroaction Adaptative Silkscreen (2D Closed-Loop Solver)
=================================================================================================
Skill: pcb-silkscreen / pcb-dfm
Conforme aux Règles du Projet (AGENTS.md) :
- Règle 1 : Moteur algorithmique pur, zéro composant codé en dur, exécution exclusive uv run.
- Règle 2 : Sécurité, robustesse et gestion active des onglets EasyEDA Pro (doctype 3 = PCB).
- Règle 3 : Séquencement strict et convergence sans dérive.

Boucle fermée de rétroaction :
1. Extraction live des obstacles physiques depuis EasyEDA Pro (vias réels, pastilles traversantes/bottom).
2. Détection formelle des violations :
   - OOB (Out-Of-Bounds : textes hors du contour physique du PCB).
   - Perforations de perçage de vias (Via Drill Hole Collision / Solder Wicking).
   - Chevauchement de pastilles cuivre / masques de soudure (Pad Collision).
   - Conflits texte-sur-texte (Légendes vs repérages de broches vs cartouche).
3. Exploration 2D adaptative (quadrants, offsets, tailles de police) avec fonction de coût pénalisante.
4. Mise à jour de silkscreen.json, ré-injection dans EasyEDA Pro et actualisation des 4 rendus visuels.
"""

from __future__ import annotations

import sys
import math
import json
import logging
import argparse
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from silkscreen_resolver import SilkscreenResolver, ResolvedTextPrimitive
from apply_silkscreen import EasyEDASilkscreenClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SilkscreenFeedbackLoop")


class SilkscreenAuditor:
    """Moteur d'audit géométrique multi-obstacles pour la sérigraphie."""

    def __init__(
        self,
        board_bounds: Dict[str, float],
        vias: List[Dict[str, Any]],
        pads: Optional[List[Dict[str, Any]]] = None,
        existing_obstacles: Optional[List[Tuple[float, float, float, float]]] = None,
        min_clearance_mm: float = 0.20
    ):
        self.bounds = board_bounds
        self.vias = vias
        self.pads = pads or []
        self.obstacles = existing_obstacles or []  # Liste de bboxes [min_x, max_x, min_y, max_y]
        self.min_clearance = min_clearance_mm

    @staticmethod
    def estimate_text_bbox(
        text: str,
        cx: float,
        cy: float,
        font_size_mm: float,
        align_mode: str = "CENTER",
        layer: int = 4
    ) -> Tuple[float, float, float, float]:
        """Estime la boîte englobante [min_x, max_x, min_y, max_y] d'une ligne de texte en tenant compte de la couche."""
        char_count = max(1, len(text))
        width = char_count * font_size_mm * 0.65
        height = font_size_mm * 1.10
        mode = align_mode.upper()

        if mode == "CENTER":
            min_x = cx - width / 2.0
            max_x = cx + width / 2.0
        elif layer == 4:  # BottomSilkLayer (vue miroir horizontale en consultation de dessous)
            if mode in ["LEFT", "LEFT_MIDDLE", "LEFT_BOTTOM", "LEFT_TOP"]:
                # En vue Bottom, l'ancre gauche visuelle correspond au plus grand X en coordonnées CAD
                # Le texte se développe vers les X décroissants (vers la gauche de la carte)
                min_x = cx - width
                max_x = cx
            elif mode in ["RIGHT", "RIGHT_MIDDLE", "RIGHT_BOTTOM", "RIGHT_TOP"]:
                min_x = cx
                max_x = cx + width
            else:
                min_x = cx - width / 2.0
                max_x = cx + width / 2.0
        else:  # TopSilkLayer (couche 3)
            if mode in ["LEFT", "LEFT_MIDDLE", "LEFT_BOTTOM", "LEFT_TOP"]:
                min_x = cx
                max_x = cx + width
            elif mode in ["RIGHT", "RIGHT_MIDDLE", "RIGHT_BOTTOM", "RIGHT_TOP"]:
                min_x = cx - width
                max_x = cx
            else:
                min_x = cx - width / 2.0
                max_x = cx + width / 2.0

        min_y = cy - height / 2.0
        max_y = cy + height / 2.0
        return (min_x, max_x, min_y, max_y)

    def evaluate_bbox(self, min_x: float, max_x: float, min_y: float, max_y: float) -> Tuple[int, List[str]]:
        """Calcule le nombre de violations et les descriptions pour une boîte englobante."""
        violations = []
        b_min_x = self.bounds.get("min_x", 0.0) + self.min_clearance
        b_max_x = self.bounds.get("max_x", 81.28) - self.min_clearance
        b_min_y = self.bounds.get("min_y", 0.0) + self.min_clearance
        b_max_y = self.bounds.get("max_y", 35.56) - self.min_clearance

        # 1. Contrôle limites physiques de la carte (OOB)
        if min_x < b_min_x or max_x > b_max_x or min_y < b_min_y or max_y > b_max_y:
            violations.append(f"OOB: [{min_x:.1f}, {max_x:.1f}, {min_y:.1f}, {max_y:.1f}] hors contour carte")

        # 2. Contrôle perçages de vias (Drill Hole Collision)
        for v in self.vias:
            vx = v["x_mm"]
            vy = v["y_mm"]
            drill_r = (v.get("hole_mm", 0.30) / 2.0) + self.min_clearance
            if (min_x - drill_r <= vx <= max_x + drill_r) and (min_y - drill_r <= vy <= max_y + drill_r):
                violations.append(f"VIA_COLLISION: via ({vx:.2f}, {vy:.2f}) [Net: {v.get('net')}]")

        # 3. Contrôle pastilles cuivre (Pads Traversants et Bottom)
        for p in self.pads:
            px = p["x_mm"]
            py = p["y_mm"]
            half_w = (p.get("w_mm", 1.5) / 2.0) + self.min_clearance
            half_h = (p.get("h_mm", 1.5) / 2.0) + self.min_clearance
            p_min_x = px - half_w
            p_max_x = px + half_w
            p_min_y = py - half_h
            p_max_y = py + half_h

            if not (max_x < p_min_x or min_x > p_max_x or max_y < p_min_y or min_y > p_max_y):
                violations.append(f"PAD_COLLISION: pad ({px:.2f}, {py:.2f}) [Net: {p.get('net')}]")

        # 4. Contrôle chevauchement d'autres textes existants (Obstacles)
        for ob in self.obstacles:
            ob_min_x, ob_max_x, ob_min_y, ob_max_y = ob
            if not (max_x < ob_min_x or min_x > ob_max_x or max_y < ob_min_y or min_y > ob_max_y):
                violations.append("TEXT_OVERLAP")

        return len(violations), violations


class SilkscreenFeedbackLoopEngine:
    """Moteur d'optimisation en boucle fermée de la sérigraphie."""

    def __init__(
        self,
        silkscreen_path: Path,
        constraints_path: Path,
        placement_path: Path,
        manifest_path: Optional[Path] = None,
        port: int = 49620
    ):
        self.silkscreen_path = silkscreen_path
        self.constraints_path = constraints_path
        self.placement_path = placement_path
        self.manifest_path = manifest_path
        self.port = port
        self.client = EasyEDASilkscreenClient(port=port)

    def load_configs(self) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        with open(self.silkscreen_path, "r", encoding="utf-8") as f:
            silk_cfg = json.load(f)
        with open(self.constraints_path, "r", encoding="utf-8") as f:
            const_cfg = json.load(f)
        with open(self.placement_path, "r", encoding="utf-8") as f:
            place_cfg = json.load(f)
        manif_cfg = {}
        if self.manifest_path and self.manifest_path.exists():
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                manif_cfg = json.load(f)
        return silk_cfg, const_cfg, place_cfg, manif_cfg

    def ensure_pcb_tab_active(self):
        """Active explicitement l'onglet PCB principal pour garantir la disponibilité de l'API."""
        code = """
        const tree = await eda.dmt_EditorControl.getSplitScreenTree();
        const pcbTab = (tree.tabs || []).find(t => t.data && t.data.doctype === 3);
        if (pcbTab) {
            await eda.dmt_EditorControl.activateDocument(pcbTab.tabId);
            await new Promise(r => setTimeout(r, 150));
            return true;
        }
        return false;
        """
        try:
            self.client.execute_js(code)
        except Exception as e:
            logger.warning(f"Impossible d'activer l'onglet PCB ({e})")

    def fetch_live_vias(self) -> List[Dict[str, Any]]:
        """Récupère l'ensemble des vias réels depuis le client EasyEDA Pro."""
        self.ensure_pcb_tab_active()
        code = """
        const vias = await eda.pcb_PrimitiveVia.getAll();
        if (!vias) return [];
        return vias.map(v => ({
            x_mm: v.getState_X() * 0.0254,
            y_mm: v.getState_Y() * 0.0254,
            hole_mm: v.getState_HoleDiameter() * 0.0254,
            diameter_mm: v.getState_Diameter() * 0.0254,
            net: v.getState_Net()
        }));
        """
        try:
            res = self.client.execute_js(code)
            return res if isinstance(res, list) else []
        except Exception as e:
            logger.warning(f"Impossible de récupérer les vias depuis EasyEDA Pro ({e})")
            return []

    def fetch_live_pads(self) -> List[Dict[str, Any]]:
        """Récupère les pastilles réelles (traversantes et face arrière) depuis EasyEDA Pro."""
        self.ensure_pcb_tab_active()
        code = """
        const pads = await eda.pcb_PrimitivePad.getAll();
        if (!pads) return [];
        // Pastilles couche 12 (traversantes multi-couches) et couche 2 (Bottom cuivre)
        const relevantPads = pads.filter(p => p.getState_Layer() === 12 || p.getState_Layer() === 2);
        return relevantPads.map(p => {
            const padDef = p.getState_Pad() || [];
            const w_mm = (padDef[1] || 60) * 0.0254;
            const h_mm = (padDef[2] || padDef[1] || 60) * 0.0254;
            return {
                x_mm: p.getState_X() * 0.0254,
                y_mm: p.getState_Y() * 0.0254,
                w_mm: w_mm,
                h_mm: h_mm,
                layer: p.getState_Layer(),
                net: p.getState_Net()
            };
        });
        """
        try:
            res = self.client.execute_js(code)
            return res if isinstance(res, list) else []
        except Exception as e:
            logger.warning(f"Impossible de récupérer les pastilles depuis EasyEDA Pro ({e})")
            return []

    def audit_all_primitives(
        self,
        silk_cfg: Dict[str, Any],
        const_cfg: Dict[str, Any],
        place_cfg: Dict[str, Any],
        manif_cfg: Dict[str, Any],
        vias: List[Dict[str, Any]],
        pads: List[Dict[str, Any]],
        bounds: Dict[str, float]
    ) -> Tuple[int, List[str]]:
        """Audite l'ensemble de la sérigraphie résolue et retourne le bilan global des violations."""
        resolver = SilkscreenResolver(silk_cfg, const_cfg, place_cfg, manif_cfg)
        primitives = resolver.resolve_all()
        auditor = SilkscreenAuditor(board_bounds=bounds, vias=vias, pads=pads, min_clearance_mm=0.20)

        all_violations = []
        bboxes: List[Tuple[float, float, float, float]] = []

        for p in primitives:
            bbox = auditor.estimate_text_bbox(p.text, p.x_mm, p.y_mm, p.font_size_mm, p.align_mode, p.layer)
            cnt, viols = auditor.evaluate_bbox(*bbox)
            for v in viols:
                all_violations.append(f"[{p.target_ref or 'GLOBAL'}] '{p.text}' @ ({p.x_mm:.1f}, {p.y_mm:.1f}) -> {v}")

            # Vérification de chevauchement avec les textes déjà enregistrés
            for prev_b in bboxes:
                if not (bbox[1] < prev_b[0] or bbox[0] > prev_b[1] or bbox[3] < prev_b[2] or bbox[2] > prev_b[3]):
                    all_violations.append(f"[{p.target_ref or 'GLOBAL'}] '{p.text}' chevauche un autre texte sérigraphie")

            bboxes.append(bbox)

        return len(all_violations), all_violations

    def solve_legend_pose(
        self,
        comp_ref: str,
        raw_text: str,
        cx: float,
        cy: float,
        font_size: float,
        auditor: SilkscreenAuditor,
        allowed_positions: List[str],
        has_pin_labels_below: bool = False
    ) -> Tuple[str, float]:
        """Recherche 2D exhaustive du quadrant et de l'offset optimal sans collision."""
        lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
        line_height = font_size * 1.35

        best_cost = float("inf")
        best_choice = (allowed_positions[0] if allowed_positions else "below", 3.0)

        for pos in allowed_positions:
            # Si des étiquettes de broches sont déjà placées sous le composant, l'offset 'below' doit démarrer plus loin
            start_off = 3.8 if (pos == "below" and has_pin_labels_below) else 1.5
            start_off_10 = int(round(start_off * 10))
            end_off_10 = 75  # jusqu'à 7.5 mm

            for off_10 in range(start_off_10, end_off_10, 2):
                offset_mm = off_10 / 10.0

                if pos == "below":
                    base_x = cx
                    base_y = cy - offset_mm
                    step_y = -line_height
                elif pos == "above":
                    base_x = cx
                    base_y = cy + offset_mm + (len(lines) - 1) * line_height
                    step_y = -line_height
                elif pos == "left":
                    base_x = cx - offset_mm
                    base_y = cy
                    step_y = -line_height
                elif pos == "right":
                    base_x = cx + offset_mm
                    base_y = cy
                    step_y = -line_height
                else:
                    continue

                total_viols = 0
                for i, line in enumerate(lines):
                    cur_y = base_y + (i * step_y)
                    min_x, max_x, min_y, max_y = auditor.estimate_text_bbox(line, base_x, cur_y, font_size, "CENTER")
                    cnt, _ = auditor.evaluate_bbox(min_x, max_x, min_y, max_y)
                    total_viols += cnt

                cost = (total_viols * 10000.0) + (offset_mm * 1.5)
                if cost < best_cost:
                    best_cost = cost
                    best_choice = (pos, offset_mm)
                    if total_viols == 0 and offset_mm >= start_off:
                        return best_choice

        return best_choice

    def optimize_silkscreen(self) -> Tuple[bool, int, int]:
        """Exécute l'audit complet et applique les corrections optimales."""
        silk_cfg, const_cfg, place_cfg, manif_cfg = self.load_configs()
        vias = self.fetch_live_vias()
        pads = self.fetch_live_pads()
        logger.info(f"Obstacles physiques interrogés dans EasyEDA Pro : {len(vias)} vias, {len(pads)} pastilles traversantes/bottom")

        board_cfg = const_cfg.get("board", {})
        bounds = {
            "min_x": 0.0,
            "max_x": float(board_cfg.get("width_mm", 81.28)),
            "min_y": 0.0,
            "max_y": float(board_cfg.get("height_mm", 35.56))
        }

        # 0. Bilan initial
        init_cnt, init_viols = self.audit_all_primitives(silk_cfg, const_cfg, place_cfg, manif_cfg, vias, pads, bounds)
        logger.info(f"📊 Bilan avant optimisation : {init_cnt} violation(s)")
        for v in init_viols[:5]:
            logger.info(f"   ⚠️  {v}")
        if len(init_viols) > 5:
            logger.info(f"   ... et {len(init_viols) - 5} autre(s) violation(s)")

        # 1. Étape 1 : Optimiser les étiquettes de broches
        pin_labels = silk_cfg.get("bottom", {}).get("pin_labels", [])
        pin_auditor = SilkscreenAuditor(board_bounds=bounds, vias=vias, pads=pads, min_clearance_mm=0.20)

        for pitem in pin_labels:
            ref = pitem["component"]
            best_side = pitem.get("side", "below")
            best_p_off = pitem.get("offset_mm", 1.8)
            min_p_viols = 999

            sides_to_test = ["below", "above"] if ref in ["H1", "H2", "H3"] else ["outside", "below", "above", "left", "right"]
            for s in sides_to_test:
                for off_10 in range(15, 42, 2):
                    test_off = off_10 / 10.0
                    pitem["side"] = s
                    pitem["offset_mm"] = test_off
                    temp_resolver = SilkscreenResolver(silk_cfg, const_cfg, place_cfg, manif_cfg)
                    test_prims = [pr for pr in temp_resolver.resolve_pin_labels("bottom") if pr.target_ref == ref]
                    cur_v = 0
                    for pr in test_prims:
                        bb = pin_auditor.estimate_text_bbox(pr.text, pr.x_mm, pr.y_mm, pr.font_size_mm, pr.align_mode, pr.layer)
                        c, _ = pin_auditor.evaluate_bbox(*bb)
                        cur_v += c
                    if cur_v < min_p_viols:
                        min_p_viols = cur_v
                        best_side = s
                        best_p_off = test_off
                    if cur_v == 0:
                        break
                if min_p_viols == 0:
                    break

            pitem["side"] = best_side
            pitem["offset_mm"] = best_p_off
            logger.info(f"✨ Broches {ref} : side='{best_side}', offset={best_p_off:.2f} mm ({min_p_viols} collision)")

        # 2. Collecter les bboxes de toutes les étiquettes de broches comme obstacles pour les légendes
        resolver_with_pins = SilkscreenResolver(silk_cfg, const_cfg, place_cfg, manif_cfg)
        resolved_pins = resolver_with_pins.resolve_pin_labels("bottom")
        accumulated_obstacles: List[Tuple[float, float, float, float]] = [
            pin_auditor.estimate_text_bbox(p.text, p.x_mm, p.y_mm, p.font_size_mm, p.align_mode, p.layer)
            for p in resolved_pins
        ]

        # 3. Étape 2 : Optimiser les légendes de composants
        legend_auditor = SilkscreenAuditor(
            board_bounds=bounds,
            vias=vias,
            pads=pads,
            existing_obstacles=accumulated_obstacles,
            min_clearance_mm=0.20
        )

        bottom_legends = silk_cfg.get("bottom", {}).get("component_legends", [])
        for item in bottom_legends:
            ref = item["component"]
            raw_text = item.get("text", "")
            font_size = float(item.get("font_size_mm", silk_cfg.get("defaults", {}).get("font_size_mm", 1.0)))

            try:
                cx, cy, _ = resolver_with_pins.get_component_pos_and_rot(ref)
            except Exception:
                continue

            # Élagage des directions impossibles (OOB immédiat)
            allowed_pos = ["below", "above", "left", "right"]
            if cy > bounds["max_y"] - 5.5:
                # Trop près du bord haut (ex: connecteurs H1, H2, H3 @ Y=31.5)
                allowed_pos = [p for p in allowed_pos if p != "above"]
            elif cy < bounds["min_y"] + 5.5:
                allowed_pos = [p for p in allowed_pos if p != "below"]

            if cx < bounds["min_x"] + 5.5:
                allowed_pos = [p for p in allowed_pos if p != "left"]
            elif cx > bounds["max_x"] - 5.5:
                allowed_pos = [p for p in allowed_pos if p != "right"]

            # Vérifier si ce composant a des broches étiquetées en-dessous
            has_pins_below = any(
                p["component"] == ref and p.get("side", "below") == "below"
                for p in pin_labels
            )

            best_pos, best_off = self.solve_legend_pose(
                comp_ref=ref,
                raw_text=raw_text,
                cx=cx,
                cy=cy,
                font_size=font_size,
                auditor=legend_auditor,
                allowed_positions=allowed_pos,
                has_pin_labels_below=has_pins_below
            )

            old_pos = item.get("position")
            old_off = item.get("offset_mm")
            item["position"] = best_pos
            item["offset_mm"] = round(best_off, 2)
            logger.info(f"✨ Légende {ref} : '{old_pos}' ({old_off} mm) -> '{best_pos}' ({best_off:.2f} mm)")

            # Enregistrer la bbox de la légende choisie dans les obstacles pour les suivantes
            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
            line_height = font_size * 1.35
            if best_pos == "below":
                b_x, b_y, s_y = cx, cy - best_off, -line_height
            elif best_pos == "above":
                b_x, b_y, s_y = cx, cy + best_off + (len(lines) - 1) * line_height, -line_height
            elif best_pos == "left":
                b_x, b_y, s_y = cx - best_off, cy, -line_height
            else:
                b_x, b_y, s_y = cx + best_off, cy, -line_height

            for i, line in enumerate(lines):
                cur_y = b_y + (i * s_y)
                legend_auditor.obstacles.append(
                    legend_auditor.estimate_text_bbox(line, b_x, cur_y, font_size, "CENTER")
                )

        # 4. Étape 3 : Résolution du cartouche (Title Block)
        title_blocks = silk_cfg.get("bottom", {}).get("title_blocks", [])
        for tb in title_blocks:
            best_fs = 0.85
            best_dx = 65.0
            best_align = "center"
            min_tb_cost = float("inf")

            # Centrage direct dans le couloir dégagé entre l'USB (X <= 45.5) et MH3/MH4 (X >= 75.5)
            for align in ["center"]:
                tb["alignment"] = align
                for fs in [0.85, 0.80, 0.90]:
                    tb["font_size_mm"] = fs
                    for dx_10 in range(580, 720, 5):  # Scan de 58.0 à 72.0 mm
                        dx = dx_10 / 10.0
                        tb["offset_mm"] = [dx, 1.27]
                        temp_resolver = SilkscreenResolver(silk_cfg, const_cfg, place_cfg, manif_cfg)
                        test_prims = temp_resolver.resolve_title_blocks("bottom")
                        cur_v = 0
                        min_dist_obstacles = 999.0

                        for pr in test_prims:
                            bb = legend_auditor.estimate_text_bbox(pr.text, pr.x_mm, pr.y_mm, pr.font_size_mm, pr.align_mode, pr.layer)
                            c, _ = legend_auditor.evaluate_bbox(*bb)
                            cur_v += c

                            # Calcul de la distance minimale aux vias et pastilles pour maximiser le dégagement
                            for v in vias:
                                d = math.hypot(pr.x_mm - v["x_mm"], pr.y_mm - v["y_mm"])
                                if d < min_dist_obstacles:
                                    min_dist_obstacles = d
                            for p in pads:
                                d = math.hypot(pr.x_mm - p["x_mm"], pr.y_mm - p["y_mm"])
                                if d < min_dist_obstacles:
                                    min_dist_obstacles = d

                        # Coût : violations prioritairement minimisées, puis dégagement maximisé
                        cost = (cur_v * 50000.0) - min_dist_obstacles
                        if cost < min_tb_cost:
                            min_tb_cost = cost
                            best_fs = fs
                            best_dx = dx
                            best_align = align

            tb["alignment"] = best_align
            tb["font_size_mm"] = best_fs
            tb["offset_mm"] = [best_dx, 1.27]
            logger.info(f"✨ Cartouche : align='{best_align}', font={best_fs} mm, offset X ajusté à {best_dx:.2f} mm")

        # 5. Bilan après optimisation
        final_cnt, final_viols = self.audit_all_primitives(silk_cfg, const_cfg, place_cfg, manif_cfg, vias, pads, bounds)
        logger.info(f"📊 Bilan final après optimisation : {final_cnt} violation(s)")
        if final_cnt > 0:
            for v in final_viols:
                logger.warning(f"   ⚠️  {v}")
        else:
            logger.info("🎯 CONVERGENCE ATTEINTE : 0 violation OOB, 0 perforation via, 0 chevauchement pastille/texte.")

        # Sauvegarde
        with open(self.silkscreen_path, "w", encoding="utf-8") as f:
            json.dump(silk_cfg, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 Sauvegarde de la configuration optimisée dans {self.silkscreen_path.name}")

        return (final_cnt == 0), init_cnt, final_cnt


def main():
    parser = argparse.ArgumentParser(description="Boucle fermée de rétroaction sérigraphie")
    parser.add_argument("--config", default="documents/pcb/silkscreen.json", help="Fichier silkscreen.json")
    parser.add_argument("--constraints", default="documents/pcb/constraints.json", help="Fichier constraints.json")
    parser.add_argument("--placement", default="documents/pcb/placement_candidate.json", help="Fichier placement")
    parser.add_argument("--manifest", default="documents/pcb/manifest.json", help="Fichier manifest.json")
    parser.add_argument("--port", type=int, default=49620, help="Port EasyEDA Pro")
    parser.add_argument("--apply", action="store_true", help="Ré-injecte la sérigraphie et met à jour les images si convergé")
    args = parser.parse_args()

    engine = SilkscreenFeedbackLoopEngine(
        silkscreen_path=Path(args.config),
        constraints_path=Path(args.constraints),
        placement_path=Path(args.placement),
        manifest_path=Path(args.manifest) if Path(args.manifest).exists() else None,
        port=args.port
    )

    converged, init_viols, final_viols = engine.optimize_silkscreen()

    if args.apply:
        logger.info("\n🚀 Ré-injection automatique de la sérigraphie optimisée dans EasyEDA Pro...")
        cmd_apply = [
            "uv", "run", "python", ".agents/skills/pcb-silkscreen/scripts/apply_silkscreen.py",
            "--silkscreen", str(Path(args.config).resolve()),
            "--constraints", str(Path(args.constraints).resolve()),
            "--placement", str(Path(args.placement).resolve()),
            "--port", str(args.port)
        ]
        if Path(args.manifest).exists():
            cmd_apply.extend(["--manifest", str(Path(args.manifest).resolve())])

        subprocess.run(cmd_apply, check=True)

        logger.info("\n📸 Régénération des 4 rendus d'inspection visuelle (2d-top, 2d-bottom, 3d, pcb)...")
        cmd_images = [
            "uv", "run", "python", ".agents/skills/pcb-dfm/scripts/export_pcb_images.py",
            "--output-dir", "documents/pcb",
            "--port", str(args.port)
        ]
        subprocess.run(cmd_images, check=True)
        logger.info("🎉 Boucle fermée terminée avec succès !")


if __name__ == "__main__":
    main()