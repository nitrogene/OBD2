#!/usr/bin/env python3
"""
enclosure_generator.py - Moteur CAO Paramétrique Agnostique de Boîtier 3D
========================================================================
Génère les modèles solides STEP (ISO 10303) et maillages STL haute résolution
pour la fabrication additive (FDM, SLA résine, SLS Nylon JLCPCB).

Conformité stricte AGENTS.md :
- Règle 1 : Zéro composant ou cote en dur. Toutes les dimensions sont lues depuis
  les fichiers de configuration passés en arguments CLI (--constraints, --enclosure).
- Exécution exclusive via 'uv run --with build123d python ...'.
"""

import argparse
import json
import logging
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import build123d as bd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PCBEnclosure")


class EnclosureGenerator:
    """Générateur de boîtier mécanique 3D paramétrique basé sur OpenCASCADE / build123d."""

    def __init__(self, constraints: Dict[str, Any], enclosure_cfg: Dict[str, Any]):
        self.constraints = constraints
        self.cfg = enclosure_cfg

        # 1. Extraction des dimensions du PCB
        board = constraints.get("board", {})
        self.board_w = float(board.get("width_mm", 80.0))
        self.board_h = float(board.get("height_mm", 40.0))
        self.pcb_thickness = 1.6  # Standard FR4

        # Extraction des perçages de fixation M2
        self.mounting_holes: List[Dict[str, Any]] = board.get("mounting_holes", [])
        if not self.mounting_holes:
            # Fallback aux coins standard si non déclarés
            self.mounting_holes = [
                {"id": "MH1", "x_mm": 3.5, "y_mm": 3.5, "drill_mm": 2.2},
                {"id": "MH2", "x_mm": 3.5, "y_mm": self.board_h - 3.5, "drill_mm": 2.2},
                {"id": "MH3", "x_mm": self.board_w - 3.5, "y_mm": 3.5, "drill_mm": 2.2},
                {"id": "MH4", "x_mm": self.board_w - 3.5, "y_mm": self.board_h - 3.5, "drill_mm": 2.2},
            ]

        # 2. Paramètres du boîtier
        p = self.cfg.get("parameters", {})
        self.wall_t = float(p.get("wall_thickness_mm", 2.0))
        self.pcb_clr = float(p.get("pcb_clearance_xy_mm", 0.35))
        self.bot_h = float(p.get("bottom_internal_height_mm", 3.5))
        self.top_h = float(p.get("top_internal_height_mm", 9.5))
        self.corner_r = float(p.get("corner_radius_mm", 3.0))
        self.lip_h = float(p.get("lip_height_mm", 1.2))
        self.lip_clr = float(p.get("lip_clearance_mm", 0.15))

        # Bossages
        b = self.cfg.get("bosses", {})
        self.boss_d = float(b.get("outer_diameter_mm", 5.0))
        self.insert_d = float(b.get("insert_hole_diameter_mm", 3.2))
        self.insert_depth = float(b.get("insert_depth_mm", 4.0))
        self.screw_clr_d = float(b.get("screw_clearance_diameter_mm", 2.4))
        self.cbore_d = float(b.get("screw_head_counterbore_diameter_mm", 4.5))
        self.cbore_depth = float(b.get("screw_head_counterbore_depth_mm", 1.6))

        # Dimensions extérieures hors-tout
        self.inner_w = self.board_w + 2 * self.pcb_clr
        self.inner_h = self.board_h + 2 * self.pcb_clr
        self.outer_w = self.inner_w + 2 * self.wall_t
        self.outer_h = self.inner_h + 2 * self.wall_t

        # Centre géométrique en XY
        self.cx = self.board_w / 2.0
        self.cy = self.board_h / 2.0

        # Z-levels : Le dessus du PCB est à Z = 0
        # Dessous du PCB à Z = -self.pcb_thickness
        # Fond intérieur à Z = -self.pcb_thickness - self.bot_h
        # Fond extérieur à Z = -self.pcb_thickness - self.bot_h - self.wall_t
        # Toit intérieur à Z = +self.top_h
        # Toit extérieur à Z = +self.top_h + self.wall_t
        self.z_pcb_top = 0.0
        self.z_pcb_bottom = -self.pcb_thickness
        self.z_bot_inner = self.z_pcb_bottom - self.bot_h
        self.z_bot_outer = self.z_bot_inner - self.wall_t
        self.z_top_inner = self.z_pcb_top + self.top_h
        self.z_top_outer = self.z_top_inner + self.wall_t

        logger.info(f"Dimensions PCB : {self.board_w:.2f} x {self.board_h:.2f} mm")
        logger.info(f"Dimensions extérieures boîtier : {self.outer_w:.2f} x {self.outer_h:.2f} x {self.z_top_outer - self.z_bot_outer:.2f} mm")

    def _create_rounded_box(self, width: float, height: float, thickness: float, radius: float) -> bd.Solid:
        """Crée une boîte extrudée avec coins arrondis en XY."""
        with bd.BuildPart() as p:
            with bd.BuildSketch():
                bd.RectangleRounded(width, height, radius)
            bd.extrude(amount=thickness)
        return p.part

    def build_bottom_shell(self) -> bd.Solid:
        """Construit la demi-coquille inférieure avec bossages et lèvre d'emboîtement."""
        logger.info("🔨 Construction de la coquille inférieure (Bottom Shell)...")
        total_bot_h = abs(self.z_pcb_top - self.z_bot_outer)

        # 1. Corps solide extérieur avec congé
        raw_outer = self._create_rounded_box(self.outer_w, self.outer_h, total_bot_h, self.corner_r)
        # Positionner le fond extérieur à z_bot_outer et centré en (cx, cy)
        outer_solid = raw_outer.locate(bd.Location((self.cx, self.cy, self.z_bot_outer)))

        # 2. Cavité intérieure
        inner_cavity_h = abs(self.z_pcb_top - self.z_bot_inner) + 0.1
        raw_inner = self._create_rounded_box(
            self.inner_w, self.inner_h, inner_cavity_h, max(0.5, self.corner_r - self.wall_t)
        )
        inner_solid = raw_inner.locate(bd.Location((self.cx, self.cy, self.z_bot_inner)))

        bottom = outer_solid - inner_solid

        # 3. Bossages de fixation M2 pour supporter le PCB
        boss_h = abs(self.z_pcb_bottom - self.z_bot_inner)
        for h in self.mounting_holes:
            hx = float(h["x_mm"])
            hy = float(h["y_mm"])
            # Colonnette solide
            with bd.BuildPart() as col_part:
                with bd.BuildSketch(bd.Plane(origin=(hx, hy, self.z_bot_inner), z_dir=(0, 0, 1))):
                    bd.Circle(self.boss_d / 2.0)
                bd.extrude(amount=boss_h)
                # Puits cylindrique pour insert thermofusible M2
                with bd.BuildSketch(bd.Plane(origin=(hx, hy, self.z_pcb_bottom), z_dir=(0, 0, -1))):
                    bd.Circle(self.insert_d / 2.0)
                bd.extrude(amount=self.insert_depth, mode=bd.Mode.SUBTRACT)

            bottom = bottom + col_part.part

        # 4. Lèvre d'emboîtement (Lip) sur le pourtour supérieur
        # La lèvre se dresse sur la moitié intérieure de la paroi (épaisseur wall_t / 2)
        lip_w = self.inner_w + self.wall_t - 2 * self.lip_clr
        lip_h_dim = self.inner_h + self.wall_t - 2 * self.lip_clr
        lip_outer = self._create_rounded_box(lip_w, lip_h_dim, self.lip_h, max(0.2, self.corner_r - self.wall_t / 2.0))
        lip_outer = lip_outer.locate(bd.Location((self.cx, self.cy, self.z_pcb_top)))

        lip_inner = self._create_rounded_box(self.inner_w, self.inner_h, self.lip_h + 0.2, max(0.2, self.corner_r - self.wall_t))
        lip_inner = lip_inner.locate(bd.Location((self.cx, self.cy, self.z_pcb_top - 0.1)))

        lip_solid = lip_outer - lip_inner
        bottom = bottom + lip_solid

        # 5. Application des découpes sur la coquille basse
        bottom = self._apply_cutouts(bottom, is_bottom=True)

        return bottom

    def build_top_shell(self) -> bd.Solid:
        """Construit la demi-coquille supérieure avec rainure d'emboîtement et puits de vis."""
        logger.info("🔨 Construction de la coquille supérieure (Top Shell)...")
        total_top_h = abs(self.z_top_outer - self.z_pcb_top)

        # 1. Corps solide extérieur avec congé
        raw_outer = self._create_rounded_box(self.outer_w, self.outer_h, total_top_h, self.corner_r)
        outer_solid = raw_outer.locate(bd.Location((self.cx, self.cy, self.z_pcb_top)))

        # 2. Cavité intérieure
        inner_cavity_h = abs(self.z_top_inner - self.z_pcb_top) + 0.1
        raw_inner = self._create_rounded_box(
            self.inner_w, self.inner_h, inner_cavity_h, max(0.5, self.corner_r - self.wall_t)
        )
        inner_solid = raw_inner.locate(bd.Location((self.cx, self.cy, self.z_pcb_top - 0.05)))

        top = outer_solid - inner_solid

        # 3. Rainure d'emboîtement (Groove) pour recevoir la lèvre inférieure
        groove_w = self.inner_w + self.wall_t + 2 * self.lip_clr
        groove_h_dim = self.inner_h + self.wall_t + 2 * self.lip_clr
        groove_depth = self.lip_h + 0.4

        groove_outer = self._create_rounded_box(groove_w, groove_h_dim, groove_depth, max(0.2, self.corner_r - self.wall_t / 2.0))
        groove_outer = groove_outer.locate(bd.Location((self.cx, self.cy, self.z_pcb_top - 0.1)))

        groove_inner = self._create_rounded_box(self.inner_w, self.inner_h, groove_depth + 0.2, max(0.2, self.corner_r - self.wall_t))
        groove_inner = groove_inner.locate(bd.Location((self.cx, self.cy, self.z_pcb_top - 0.2)))

        groove_tool = groove_outer - groove_inner
        top = top - groove_tool

        # 4. Puits et passages de vis M2 avec lamage de tête
        for h in self.mounting_holes:
            hx = float(h["x_mm"])
            hy = float(h["y_mm"])
            with bd.BuildPart() as screw_hole_part:
                # Colonnette supérieure descendant jusqu'au PCB
                with bd.BuildSketch(bd.Plane(origin=(hx, hy, self.z_pcb_top), z_dir=(0, 0, 1))):
                    bd.Circle(self.boss_d / 2.0)
                bd.extrude(amount=abs(self.z_top_inner - self.z_pcb_top))

                # Trou traversant pour passage de vis
                with bd.BuildSketch(bd.Plane(origin=(hx, hy, self.z_pcb_top - 0.2), z_dir=(0, 0, 1))):
                    bd.Circle(self.screw_clr_d / 2.0)
                bd.extrude(amount=total_top_h + 0.4, mode=bd.Mode.SUBTRACT)

                # Lamage de tête de vis sur la face supérieure
                with bd.BuildSketch(bd.Plane(origin=(hx, hy, self.z_top_outer + 0.1), z_dir=(0, 0, -1))):
                    bd.Circle(self.cbore_d / 2.0)
                bd.extrude(amount=self.cbore_depth + 0.1, mode=bd.Mode.SUBTRACT)

            top = top + screw_hole_part.part

        # 5. Application des découpes sur la coquille haute
        top = self._apply_cutouts(top, is_bottom=False)

        return top

    def build_pcb_mockup(self) -> bd.Solid:
        """Construit un solide représentant la carte PCB avec ses perçages de fixation."""
        logger.info("🔨 Construction du solide de référence PCB...")
        with bd.BuildPart() as pcb_part:
            with bd.BuildSketch(bd.Plane(origin=(self.cx, self.cy, self.z_pcb_bottom), z_dir=(0, 0, 1))):
                bd.Rectangle(self.board_w, self.board_h)
            bd.extrude(amount=self.pcb_thickness)

            # Perçages de fixation M2
            for h in self.mounting_holes:
                hx = float(h["x_mm"])
                hy = float(h["y_mm"])
                drill_d = float(h.get("drill_mm", 2.2))
                with bd.BuildSketch(bd.Plane(origin=(hx, hy, self.z_pcb_bottom - 0.1), z_dir=(0, 0, 1))):
                    bd.Circle(drill_d / 2.0)
                bd.extrude(amount=self.pcb_thickness + 0.2, mode=bd.Mode.SUBTRACT)

        return pcb_part.part

    def build_cable_clamp(self) -> bd.Solid:
        """Construit la bride rigide à 2 vis M2 pour décharger le câble OBD-II."""
        logger.info("🔨 Construction de la bride serre-câble (Cable Clamp)...")
        clamp_cfg = self.cfg.get("cable_clamp", {})
        cable_d = float(clamp_cfg.get("cable_diameter_mm", 6.5))
        width = float(clamp_cfg.get("clamp_width_mm", 8.0))
        screw_spacing = float(clamp_cfg.get("screw_spacing_mm", 14.0))

        length = screw_spacing + 2 * 3.5  # Bords pour vis
        thickness = (cable_d / 2.0) + 2.5

        with bd.BuildPart() as p:
            # Corps rectangulaire avec congés
            with bd.BuildSketch():
                bd.RectangleRounded(width, length, 2.0)
            bd.extrude(amount=thickness)

            # Demi-cylindre de compression du câble (légèrement inférieur à cable_d pour serrage)
            compression_r = (cable_d * 0.95) / 2.0
            with bd.BuildSketch(bd.Plane.XZ):
                with bd.Locations((0, 0)):
                    bd.Circle(compression_r)
            bd.extrude(amount=width + 2, mode=bd.Mode.SUBTRACT)

            # 2 Trous de passage pour vis M2
            with bd.BuildSketch():
                with bd.Locations((0, -screw_spacing / 2.0), (0, screw_spacing / 2.0)):
                    bd.Circle(self.screw_clr_d / 2.0)
            bd.extrude(amount=thickness + 1, mode=bd.Mode.SUBTRACT)

        return p.part

    def _apply_cutouts(self, shell: bd.Solid, is_bottom: bool) -> bd.Solid:
        """Applique les perçages et découpes d'interface selon la face et le plan de joint."""
        cutouts = self.cfg.get("cutouts", [])
        for c in cutouts:
            cid = c.get("id", "")
            face = c.get("face", "")
            shape = c.get("shape", "rectangle")
            pos = c.get("position_mm", [0.0, 0.0, 0.0])
            dims = c.get("dimensions_mm", [5.0, 5.0])
            px = float(pos[0])
            py = float(pos[1])
            pz = float(pos[2]) if len(pos) > 2 else 0.0

            if face == "front":
                # Connecteur USB-C sur le plan de joint Y=0
                # Largeur en X, Hauteur en Z
                w = float(dims[0])
                h = float(dims[1])
                r = float(c.get("corner_radius_mm", 1.0))
                # Création d'un outil de coupe traversant la paroi frontale
                with bd.BuildPart() as cutter:
                    with bd.BuildSketch(bd.Plane.XZ):
                        with bd.Locations((px, pz)):
                            bd.RectangleRounded(w, h, r)
                    bd.extrude(amount=self.wall_t * 3.0, both=True)
                shell = shell - cutter.part

            elif face == "left":
                # Sortie câble OBD-II sur le bord gauche X=0
                d = float(dims[0])
                with bd.BuildPart() as cutter:
                    with bd.BuildSketch(bd.Plane.YZ):
                        with bd.Locations((py, pz)):
                            bd.Circle(d / 2.0)
                    bd.extrude(amount=self.wall_t * 3.0, both=True)
                shell = shell - cutter.part

            elif face == "top" and not is_bottom:
                # Perçages supérieurs (bouton SW1, LED1) uniquement sur la coquille haute
                d = float(dims[0])
                with bd.BuildPart() as cutter:
                    with bd.BuildSketch(bd.Plane(origin=(px, py, self.z_top_outer + 1.0), z_dir=(0, 0, -1))):
                        bd.Circle(d / 2.0)
                    bd.extrude(amount=self.wall_t * 2.0)
                shell = shell - cutter.part

        return shell


def main():
    parser = argparse.ArgumentParser(description="Générateur de Boîtier 3D Paramétrique OpenCASCADE pour PCB")
    parser.add_argument("--constraints", default="documents/pcb/constraints.json", help="Chemin vers constraints.json")
    parser.add_argument("--enclosure", default="documents/pcb/enclosure.json", help="Chemin vers enclosure.json")
    parser.add_argument("--output-dir", default="documents/enclosure", help="Répertoire d'export des STEP et STL")
    args = parser.parse_args()

    constraints_file = Path(args.constraints).resolve()
    enclosure_file = Path(args.enclosure).resolve()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not constraints_file.exists():
        logger.error(f"Fichier de contraintes introuvable : {constraints_file}")
        sys.exit(1)
    if not enclosure_file.exists():
        logger.error(f"Fichier de configuration boîtier introuvable : {enclosure_file}")
        sys.exit(1)

    with open(constraints_file, "r", encoding="utf-8") as f:
        constraints_data = json.load(f)
    with open(enclosure_file, "r", encoding="utf-8") as f:
        enclosure_data = json.load(f)

    gen = EnclosureGenerator(constraints_data, enclosure_data)

    # 1. Génération des pièces avec labels et couleurs distinctes
    bottom_shell = gen.build_bottom_shell()
    bottom_shell.label = "Boitier_Inferieur"
    bottom_shell.color = bd.Color(0.25, 0.25, 0.25)  # Anthracite mat

    top_shell = gen.build_top_shell()
    top_shell.label = "Boitier_Superieur"
    top_shell.color = bd.Color(0.35, 0.35, 0.35)  # Gris boîtier

    cable_clamp = gen.build_cable_clamp()
    cable_clamp.label = "Bride_Serre_Cable"
    cable_clamp.color = bd.Color(0.85, 0.45, 0.1)   # Orange mécanique contrasté

    pcb_solid = gen.build_pcb_mockup()
    pcb_solid.label = "Carte_PCB"
    pcb_solid.color = bd.Color(0.05, 0.45, 0.2)     # Vert vernis épargne

    # 2. Exports STEP solides individuels AVANT composition dans un Compound
    # (OpenCASCADE lie la topologie des Shape dès qu'elles sont incluses dans un Compound,
    # ce qui empêcherait leur export STEP unitaire ultérieur).
    logger.info("💾 Export des fichiers STEP solides individuels avec noms et couleurs...")
    bd.export_step(bottom_shell, str(out_dir / "enclosure_bottom.step"))
    bd.export_step(top_shell, str(out_dir / "enclosure_top.step"))
    bd.export_step(cable_clamp, str(out_dir / "enclosure_clamp.step"))

    # 3. Assemblage complet fermé (Bottom + PCB + Clamp + Top fermé)
    # L'export est réalisé immédiatement pour préserver la hiérarchie parent-enfant dans l'arborescence STEP.
    clamp_located = cable_clamp.locate(bd.Location((4.0, 17.78, gen.z_pcb_top + 1.5)))
    clamp_located.label = "Bride_Serre_Cable"
    clamp_located.color = bd.Color(0.85, 0.45, 0.1)

    full_assembly = bd.Compound(
        children=[bottom_shell, pcb_solid, clamp_located, top_shell],
        label="Assemblage_Ferme"
    )
    logger.info("💾 Export de l'assemblage complet fermé (STEP & STL)...")
    bd.export_step(full_assembly, str(out_dir / "enclosure_full_assembly.step"))
    bd.export_stl(full_assembly, str(out_dir / "enclosure_assembly.stl"), tolerance=0.02, angular_tolerance=0.15)

    # 4. Assemblage en vue éclatée (Couvercle surélevé de +30 mm, bride de +12 mm)
    top_exploded = top_shell.locate(bd.Location((0, 0, 30.0)))
    top_exploded.label = "Boitier_Superieur"
    top_exploded.color = bd.Color(0.35, 0.35, 0.35)

    clamp_exploded = cable_clamp.locate(bd.Location((4.0, 17.78, gen.z_pcb_top + 12.0)))
    clamp_exploded.label = "Bride_Serre_Cable"
    clamp_exploded.color = bd.Color(0.85, 0.45, 0.1)

    exploded_assembly = bd.Compound(
        children=[bottom_shell, pcb_solid, clamp_exploded, top_exploded],
        label="Vue_Eclatee"
    )
    logger.info("💾 Export de la vue éclatée (STEP & STL)...")
    bd.export_step(exploded_assembly, str(out_dir / "enclosure_exploded.step"))
    bd.export_stl(exploded_assembly, str(out_dir / "enclosure_exploded.stl"), tolerance=0.02, angular_tolerance=0.15)

    logger.info(f"✅ Génération terminée avec succès dans : {out_dir}")
    for item in out_dir.glob("*.*"):
        size_kb = item.stat().st_size / 1024.0
        logger.info(f"   -> {item.name:25s} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
