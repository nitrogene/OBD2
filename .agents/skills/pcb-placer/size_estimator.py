#!/usr/bin/env python3
"""
Moteur d'Estimation et de Suggestion Dimensionnelle de PCB (Agnostique)
========================================================================
Calcule la surface minimale, nominale et confortable requise pour un PCB
à partir de l'inventaire des composants, de leurs empreintes (courtyards IPC-7351),
des keepouts incompressibles et du nombre de couches de cuivre.

Conformément à la règle 0 d'AGENTS.md, ce moteur est agnostique :
il s'appuie sur une table générique de boîtiers et accepte en entrée
soit un fichier de configuration (floorplan.json), soit une nomenclature (BOM.md).
"""

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# =============================================================================
# Constantes & Tables Génériques IPC-7351 (Courtyards en mm²)
# =============================================================================

# Surface typique occupée par le composant incluant ses pastilles de soudure
# et la zone de sécurité mécanique (Courtyard IPC-7351 standard)
STANDARD_COURTYARDS_MM2: Dict[str, Tuple[float, float, str]] = {
    # Format: package_key -> (width_mm, height_mm, category)
    # Passifs CMS
    "0402": (1.6, 1.0, "Passif CMS ultra-miniature"),
    "0603": (2.2, 1.4, "Passif CMS standard"),
    "0805": (2.8, 1.8, "Passif CMS standard puissance"),
    "1206": (4.0, 2.2, "Passif CMS haute puissance / filtrage"),
    "1210": (4.0, 3.2, "Passif CMS puissance"),
    "1812": (5.5, 4.0, "Fusible PPTC / condensateur lourd"),
    "2010": (5.8, 3.2, "Résistance forte puissance"),
    "2512": (7.2, 3.8, "Shunt de mesure de courant"),

    # Diodes CMS
    "SOD-123": (3.8, 1.8, "Diode Schottky / commutation"),
    "SOD-123FL": (3.8, 1.8, "Diode TVS compacte"),
    "SOD-323": (2.7, 1.4, "Diode ESD ultra-compacte"),
    "SOD-523": (1.8, 1.0, "Diode ESD signal"),
    "SMA": (5.2, 2.7, "Diode Schottky / redressement 1A-3A"),
    "DO-214AC": (5.2, 2.7, "Diode SMA"),
    "SMB": (5.5, 3.9, "Diode TVS 600W / Schottky 3A-5A"),
    "DO-214AA": (5.5, 3.9, "Diode SMB"),
    "SMC": (8.0, 6.0, "Diode TVS 1500W"),
    "DO-214AB": (8.0, 6.0, "Diode SMC"),

    # Transistors & Petits Boîtiers
    "SOT-23": (3.0, 2.5, "Transistor / MOSFET / Diode double"),
    "SOT-23-3": (3.0, 2.5, "Transistor petit signal"),
    "SOT-23-5": (3.1, 2.8, "Régulateur LDO / switch"),
    "SOT-23-6": (3.1, 2.8, "Driver / circuit intégré miniature"),
    "SOT-89": (4.6, 4.2, "Transistor puissance moyen"),
    "SOT-223": (6.7, 7.3, "Régulateur linéaire LDO moyen"),
    "SOT-223-4": (6.7, 7.3, "Régulateur linéaire LDO 1.2A"),
    "DPAK": (10.0, 6.7, "Transistor / LDO forte puissance"),
    "TO-252": (10.0, 6.7, "Transistor DPAK"),

    # Circuits Intégrés CMS
    "SOIC-8": (5.0, 6.2, "Circuit intégré SOIC-8 pas 1.27 mm"),
    "SOIC-8-150MIL": (5.0, 6.2, "Transceiver / Régulateur SOIC-8"),
    "SOIC-14": (8.8, 6.2, "Circuit intégré SOIC-14"),
    "SOIC-16": (10.0, 6.2, "Circuit intégré SOIC-16"),
    "MSOP-8": (3.2, 5.0, "Circuit intégré MSOP-8 miniature"),
    "TSSOP-8": (3.2, 6.5, "Circuit intégré TSSOP-8"),
    "TSSOP-14": (5.2, 6.5, "Circuit intégré TSSOP-14"),
    "TSSOP-16": (5.2, 6.5, "Circuit intégré TSSOP-16"),
    "QFN-16": (3.5, 3.5, "Circuit QFN 3x3 mm"),
    "QFN-24": (4.5, 4.5, "Circuit QFN 4x4 mm"),
    "QFN-32": (5.5, 5.5, "Microcontrôleur QFN 5x5 mm"),

    # Modules & Électromécanique
    "SMD,25.5X18MM": (26.0, 18.5, "Module radio SoC ESP32-S3"),
    "ESP32-S3": (26.0, 18.5, "Module radio SoC ESP32-S3"),
    "SMD,6X6MM": (6.8, 6.8, "Inductance blindée de puissance"),
    "CONN-TH_5P-P3.50_WJ250B-3.50-5P": (18.5, 12.0, "Bornier sans vis 5 contacts pas 3.5 mm"),
    "TYPE-C-31-M-12": (9.5, 9.0, "Prise USB Type-C 16P CMS"),
    "USB-C": (9.5, 9.0, "Prise USB Type-C"),
    "PZ2.54-1*2": (5.2, 2.8, "Embase cavalier sélecteur 2 broches pas 2.54 mm"),
    "2.54-1*3P": (7.8, 2.8, "Embase header diagnostic 3 broches pas 2.54 mm"),
    "TS-1187A-B-A-B": (5.5, 5.5, "Bouton poussoir tactile CMS"),
    "TESTPOINT": (1.6, 1.6, "Pastille de point de test cuivre"),
}

MM_TO_MIL = 39.37007874
MIL_TO_MM = 0.0254


@dataclass
class SizingEstimate:
    """Résultat de l'estimation dimensionnelle du PCB."""
    components_count: int
    raw_components_area_mm2: float
    keepouts_area_mm2: float
    layers_count: int
    aspect_ratio: float  # Largeur / Hauteur
    efficiency_factor: float

    # Surfaces estimées
    min_area_mm2: float
    nominal_area_mm2: float
    comfortable_area_mm2: float

    # Dimensions recommandées (nominales)
    nominal_width_mm: float
    nominal_height_mm: float
    nominal_width_mil: float
    nominal_height_mil: float

    # Dimensions confortables (aérées pour CEM)
    comfortable_width_mm: float
    comfortable_height_mm: float
    comfortable_width_mil: float
    comfortable_height_mil: float

    # Détails par famille de composants
    breakdown_by_category: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class PCBSizeEstimator:
    """Moteur d'estimation de surface et de gabarit de circuit imprimé."""

    # Efficacité de routage typique (Surface composants / Surface carte)
    # Norme IPC-2221 et bonnes pratiques de l'industrie :
    # En 2 couches : 30% à 38% max (pour garder plan de masse continu)
    # En 4 couches : 50% à 62% (les plans d'alim/masse internes libèrent les faces)
    PACKING_EFFICIENCY = {
        2: {"tight": 0.40, "nominal": 0.33, "comfortable": 0.28},
        4: {"tight": 0.60, "nominal": 0.52, "comfortable": 0.45},
        6: {"tight": 0.70, "nominal": 0.62, "comfortable": 0.55}
    }

    def __init__(self, custom_courtyards: Optional[Dict[str, Tuple[float, float, str]]] = None):
        self.courtyards = dict(STANDARD_COURTYARDS_MM2)
        if custom_courtyards:
            self.courtyards.update(custom_courtyards)

    def resolve_package_area(self, package_name: str, designator: str = "") -> Tuple[float, str]:
        """Résout la surface estimée (en mm²) et la description à partir du nom du package."""
        clean_pkg = package_name.strip().upper()

        # Points de test (pads nus ou vias)
        if designator.startswith("TP") or "TESTPOINT" in clean_pkg:
            return (1.6 * 1.6, "Mire de test (TP)")

        # Recherche directe
        if clean_pkg in self.courtyards:
            w, h, desc = self.courtyards[clean_pkg]
            return (w * h, desc)

        # Recherche par sous-chaîne
        for key, (w, h, desc) in self.courtyards.items():
            if key in clean_pkg:
                return (w * h, desc)

        # Fallback heuristique basé sur la taille du texte
        if "0603" in clean_pkg:
            return (2.2 * 1.4, "Passif 0603")
        if "0805" in clean_pkg:
            return (2.8 * 1.8, "Passif 0805")
        if "1206" in clean_pkg:
            return (4.0 * 2.2, "Passif 1206")
        if "SOT" in clean_pkg:
            return (3.0 * 2.5, "Boîtier SOT")
        if "SOIC" in clean_pkg or "SOP" in clean_pkg:
            return (5.0 * 6.2, "Boîtier SOIC")
        if "QFN" in clean_pkg:
            return (5.0 * 5.0, "Boîtier QFN")

        # Valeur moyenne conservatrice par défaut
        return (10.0, f"Boîtier non répertorié '{package_name}' (estimé 10 mm²)")

    def estimate_from_bom(
        self,
        bom_path: str,
        layers: int = 2,
        aspect_ratio: float = 2.28,  # Format rectangulaire oblong par défaut
        rf_keepout_mm2: float = 120.0,
        edge_clearance_mm: float = 1.0
    ) -> SizingEstimate:
        """Estime les dimensions à partir d'un fichier Markdown de nomenclature (BOM.md)."""
        p = Path(bom_path)
        if not p.exists():
            raise FileNotFoundError(f"Fichier BOM introuvable : {bom_path}")

        text = p.read_text(encoding="utf-8")
        # Format attendu du tableau BOM: | **Désignateur** | Valeur | MPN | LCSC | Statut | Empreinte | Rôle |
        pattern = r"\|\s*\*\*([A-Z0-9]+)\*\*\s*\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|\s*`?([^`|\n]+)`?\s*\|"
        matches = re.findall(pattern, text)

        components = []
        for des, pkg in matches:
            components.append({"designator": des, "package": pkg.strip()})

        return self.estimate_from_components(
            components=components,
            layers=layers,
            aspect_ratio=aspect_ratio,
            rf_keepout_mm2=rf_keepout_mm2,
            edge_clearance_mm=edge_clearance_mm
        )

    def estimate_from_floorplan(
        self,
        floorplan_path: str,
        layers: Optional[int] = None,
        aspect_ratio: Optional[float] = None
    ) -> Tuple[SizingEstimate, Dict[str, Any]]:
        """Estime les dimensions à partir de floorplan.json et compare avec les dimensions actuelles."""
        p = Path(floorplan_path)
        if not p.exists():
            raise FileNotFoundError(f"Fichier floorplan introuvable : {floorplan_path}")

        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)

        board_info = data.get("board", {})
        cur_w_mm = board_info.get("width_mm", 81.28)
        cur_h_mm = board_info.get("height_mm", 35.56)
        cur_aspect = cur_w_mm / cur_h_mm if cur_h_mm > 0 else 2.28

        # Calcul de la surface cumulée des Keepouts dans le floorplan
        keepouts_mm2 = 0.0
        for k in data.get("keepout_zones", []):
            kw_mil = abs(k.get("x_max_mil", 0) - k.get("x_min_mil", 0))
            kh_mil = abs(k.get("y_max_mil", 0) - k.get("y_min_mil", 0))
            keepouts_mm2 += (kw_mil * MIL_TO_MM) * (kh_mil * MIL_TO_MM)

        # Liste des composants et recherche des boîtiers dans circuit_manifest.json ou BOM.md
        manifest_path = p.parent / "circuit_manifest.json"
        manifest_comps = {}
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as mf:
                    manifest_comps = json.load(mf).get("components", {})
            except Exception:
                pass

        bom_path = p.parent / "BOM.md"
        bom_pkg_map = {}
        if bom_path.exists():
            text = bom_path.read_text(encoding="utf-8")
            pattern = r"\|\s*\*\*([A-Z0-9]+)\*\*\s*\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|\s*`?([^`|\n]+)`?\s*\|"
            bom_pkg_map = {des: pkg.strip() for des, pkg in re.findall(pattern, text)}

        raw_comps = data.get("components", {}) or manifest_comps

        comps = []
        for des, c in raw_comps.items():
            pkg = c.get("package") or c.get("footprint") or bom_pkg_map.get(des, c.get("desc", ""))
            comps.append({"designator": des, "package": pkg})

        estimate = self.estimate_from_components(
            components=comps,
            layers=layers or 2,
            aspect_ratio=aspect_ratio or cur_aspect,
            rf_keepout_mm2=keepouts_mm2 if keepouts_mm2 > 0 else 120.0,
            edge_clearance_mm=board_info.get("edge_clearance_mm", 1.0)
        )

        comparison = {
            "current_width_mm": cur_w_mm,
            "current_height_mm": cur_h_mm,
            "current_area_mm2": cur_w_mm * cur_h_mm,
            "delta_area_nominal_percent": ((cur_w_mm * cur_h_mm) - estimate.nominal_area_mm2) / estimate.nominal_area_mm2 * 100.0,
            "current_aspect_ratio": cur_aspect
        }

        return estimate, comparison

    def estimate_from_components(
        self,
        components: List[Dict[str, str]],
        layers: int = 2,
        aspect_ratio: float = 2.28,
        rf_keepout_mm2: float = 120.0,
        edge_clearance_mm: float = 1.0
    ) -> SizingEstimate:
        """Cœur algorithmique de calcul de surface."""
        eff_table = self.PACKING_EFFICIENCY.get(layers, self.PACKING_EFFICIENCY[2])

        total_comp_area = 0.0
        breakdown: Dict[str, Dict[str, Any]] = {}

        for item in components:
            des = item["designator"]
            pkg = item.get("package", "")
            area, cat = self.resolve_package_area(pkg, des)
            total_comp_area += area

            if cat not in breakdown:
                breakdown[cat] = {"count": 0, "total_area_mm2": 0.0, "components": []}
            breakdown[cat]["count"] += 1
            breakdown[cat]["total_area_mm2"] += area
            breakdown[cat]["components"].append(des)

        active_area = total_comp_area + rf_keepout_mm2

        min_area = active_area / eff_table["tight"]
        nominal_area = active_area / eff_table["nominal"]
        comfortable_area = active_area / eff_table["comfortable"]

        # Calcul des dimensions rectangulaires : Area = W * H, avec W = Aspect * H  ==>  H = sqrt(Area / Aspect)
        def calc_dims(area_val: float) -> Tuple[float, float]:
            h = math.sqrt(area_val / aspect_ratio)
            w = h * aspect_ratio
            # Ajout des marges de bord de carte (2 * edge_clearance)
            return (w + 2 * edge_clearance_mm, h + 2 * edge_clearance_mm)

        nom_w_mm, nom_h_mm = calc_dims(nominal_area)
        comf_w_mm, comf_h_mm = calc_dims(comfortable_area)

        return SizingEstimate(
            components_count=len(components),
            raw_components_area_mm2=total_comp_area,
            keepouts_area_mm2=rf_keepout_mm2,
            layers_count=layers,
            aspect_ratio=aspect_ratio,
            efficiency_factor=eff_table["nominal"],
            min_area_mm2=min_area,
            nominal_area_mm2=nominal_area,
            comfortable_area_mm2=comfortable_area,
            nominal_width_mm=nom_w_mm,
            nominal_height_mm=nom_h_mm,
            nominal_width_mil=nom_w_mm * MM_TO_MIL,
            nominal_height_mil=nom_h_mm * MM_TO_MIL,
            comfortable_width_mm=comf_w_mm,
            comfortable_height_mm=comf_h_mm,
            comfortable_width_mil=comf_w_mm * MM_TO_MIL,
            comfortable_height_mil=comf_h_mm * MM_TO_MIL,
            breakdown_by_category=breakdown
        )

    def print_report(self, estimate: SizingEstimate, comparison: Optional[Dict[str, Any]] = None):
        """Affiche le rapport détaillé d'estimation dimensionnelle."""
        print("\n" + "=" * 80)
        print(" RAPPORT D'ESTIMATION & SUGGESTION DIMENSIONNELLE DU PCB")
        print("=" * 80)
        print(f"Composants pris en compte : {estimate.components_count}")
        print(f"Surface brute composants  : {estimate.raw_components_area_mm2:.1f} mm²")
        print(f"Surface Keepout RF        : {estimate.keepouts_area_mm2:.1f} mm²")
        print(f"Nombre de couches cibles  : {estimate.layers_count} couches (Cuivre Top/Bottom)")
        print(f"Ratio d'aspect cible      : {estimate.aspect_ratio:.2f}:1")
        print(f"Taux d'efficacité nominal : {estimate.efficiency_factor * 100:.0f}% (Packing Factor {1.0 / estimate.efficiency_factor:.2f}×)")
        print("-" * 80)

        print("\n📊 RÉPARTITION SURFACIQUE PAR FAMILLE DE COMPOSANTS :")
        for cat, data in sorted(estimate.breakdown_by_category.items(), key=lambda x: -x[1]["total_area_mm2"]):
            pct = (data["total_area_mm2"] / estimate.raw_components_area_mm2) * 100.0 if estimate.raw_components_area_mm2 > 0 else 0
            print(f"   • {cat:<40} : {data['count']:>2} pièces | {data['total_area_mm2']:>7.1f} mm² ({pct:>4.1f}%)")

        print("\n" + "-" * 80)
        print("📐 SUGGESTIONS DIMENSIONNELLES DU PCB :")
        print("-" * 80)
        print(f"1. Gabarit Minimal (Très compact, routage dense) :")
        print(f"   Surface : {estimate.min_area_mm2:.0f} mm²")

        print(f"\n2. Gabarit Recommandé (Nominal, équilibre CEM & coût JLCPCB standard) :")
        print(f"   Surface : {estimate.nominal_area_mm2:.0f} mm²")
        print(f"   Dimensions : {estimate.nominal_width_mm:.2f} × {estimate.nominal_height_mm:.2f} mm  ({estimate.nominal_width_mil:.0f} × {estimate.nominal_height_mil:.0f} mil)")

        print(f"\n3. Gabarit Confortable (Aéré, boucles Buck découplées, plans de masse GND optimaux) :")
        print(f"   Surface : {estimate.comfortable_area_mm2:.0f} mm²")
        print(f"   Dimensions : {estimate.comfortable_width_mm:.2f} × {estimate.comfortable_height_mm:.2f} mm  ({estimate.comfortable_width_mil:.0f} × {estimate.comfortable_height_mil:.0f} mil)")

        if comparison:
            print("\n" + "=" * 80)
            print("🔍 CONFRONTATION AVEC LE FLOORPLAN ACTUEL :")
            print("=" * 80)
            cur_w = comparison["current_width_mm"]
            cur_h = comparison["current_height_mm"]
            cur_area = comparison["current_area_mm2"]
            delta = comparison["delta_area_nominal_percent"]

            print(f"Dimensions actuelles floorplan : {cur_w:.2f} × {cur_h:.2f} mm ({cur_w * MM_TO_MIL:.0f} × {cur_h * MM_TO_MIL:.0f} mil)")
            print(f"Surface actuelle               : {cur_area:.0f} mm²")
            print(f"Écart face au nominal suggéré  : {delta:+.1f}%")

            if abs(delta) <= 15.0:
                print("✅ Parfaite adéquation : Les dimensions actuelles sont idéalement calibrées pour un routage 2 couches sans compromis !")
            elif delta > 15.0:
                print("ℹ️  Carte spacieuse : Le PCB dispose d'une marge généreuse facilitant la continuité des plans de masse et l'isolation CEM.")
            else:
                print("⚠️  Carte très dense : Prévoir un routage minutieux des bus et rails d'alimentation ou envisager un passage en 4 couches.")

        print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Moteur d'estimation et suggestion dimensionnelle de PCB (agnostique)."
    )
    parser.add_argument(
        "--config",
        help="Chemin vers le fichier de floorplan JSON (ex: floorplan.json)"
    )
    parser.add_argument(
        "--bom",
        help="Chemin vers le fichier de nomenclature Markdown (ex: BOM.md)"
    )
    parser.add_argument(
        "--layers",
        type=int,
        default=2,
        choices=[2, 4, 6],
        help="Nombre de couches de cuivre (par défaut: 2)"
    )
    parser.add_argument(
        "--ratio",
        type=float,
        default=2.28,
        help="Ratio d'aspect Largeur / Hauteur (par défaut: 2.28 format oblong)"
    )

    args = parser.parse_args()

    if not args.config and not args.bom:
        # Si aucun argument n'est fourni, tenter de localiser floorplan.json ou BOM.md localement
        if Path("floorplan.json").exists():
            args.config = "floorplan.json"
        elif Path("BOM.md").exists():
            args.bom = "BOM.md"
        else:
            parser.error("Veuillez spécifier soit --config <floorplan.json>, soit --bom <BOM.md>.")

    estimator = PCBSizeEstimator()

    if args.config:
        estimate, comparison = estimator.estimate_from_floorplan(
            floorplan_path=args.config,
            layers=args.layers,
            aspect_ratio=args.ratio
        )
        estimator.print_report(estimate, comparison)
    else:
        estimate = estimator.estimate_from_bom(
            bom_path=args.bom,
            layers=args.layers,
            aspect_ratio=args.ratio
        )
        estimator.print_report(estimate)


if __name__ == "__main__":
    main()
