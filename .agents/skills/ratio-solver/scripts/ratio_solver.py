#!/usr/bin/env python3
"""
ratio_solver.py - Moteur algorithmique d'optimisation et de calcul de couples de résistances.

Conforme à la Règle 0 (AGENTS.md) :
- Moteur purement mathématique et agnostique.
- Aucune référence en dur à un composant ou circuit spécifique.
- Données injectées via arguments CLI ou fichiers JSON de catalogue.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def parse_engineering_value(text: str | float | int) -> float:
    """Convertit une chaîne en notation ingénieur (ex: 10k, 1.91k, 1M, 100R, 100) en nombre flottant (Ohms)."""
    if isinstance(text, (int, float)):
        return float(text)
    
    clean = str(text).strip().replace("Ω", "").replace("ohm", "").replace("Ohm", "").strip()
    match = re.match(r"^([0-9.]+)\s*([kKMmRruUnNpP]?)$", clean)
    if not match:
        raise ValueError(f"Impossible de convertir la valeur de résistance : '{text}'")
    
    val = float(match.group(1))
    unit = match.group(2).upper()
    
    multipliers = {
        "": 1.0,
        "R": 1.0,
        "K": 1e3,
        "M": 1e6,
        "U": 1e-6,
        "N": 1e-9,
        "P": 1e-12,
    }
    return val * multipliers.get(unit, 1.0)


def format_resistance(value: float) -> str:
    """Formate une résistance en Ohms avec unité d'ingénierie lisible (ex: 10 kΩ, 1.91 kΩ, 100 Ω)."""
    if value >= 1e6:
        v = value / 1e6
        return f"{v:g} MΩ"
    elif value >= 1e3:
        v = value / 1e3
        return f"{v:g} kΩ"
    else:
        return f"{value:g} Ω"


def load_e_series(series_name: str = "E96", ref_path: Optional[Path] = None) -> List[float]:
    """Charge les valeurs normalisées d'une série EIA (E12, E24, E96) étendues sur les décades 10^0 à 10^6."""
    if ref_path is None:
        ref_path = Path(__file__).parent.parent / "references" / "e_series.json"
    
    base_values: List[float] = []
    if ref_path.exists():
        data = json.loads(ref_path.read_text(encoding="utf-8"))
        base_values = data.get(series_name.upper(), [])
    
    if not base_values:
        # Fallback E24 en dur si fichier manquant
        base_values = [
            1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0,
            3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1
        ]
    
    pool: List[float] = []
    for decade in range(0, 7):  # 1 ohm à 9.76 Mohm
        multiplier = 10 ** decade
        for b in base_values:
            val = round(b * multiplier, 2 if decade == 0 else 1)
            pool.append(val)
    return pool


@dataclass
class SolutionPair:
    r1_top: float
    r2_bottom: float
    r1_formatted: str
    r2_formatted: str
    target_metric: str  # "Vout", "Attenuation", "Gain"
    calculated_metric_val: float
    target_metric_val: float
    error_pct: float
    divider_current_ma: float
    thevenin_resistance: float
    series_name: str = "custom"


class RatioOptimizer:
    """Solveur d'optimisation de paires de résistances par balayage contraint."""

    @staticmethod
    def solve_regulator(
        target_vout: float,
        vref: float,
        resistor_pool: Sequence[float],
        min_current_a: float = 1e-5,   # 10 µA min
        max_current_a: float = 5e-3,   # 5 mA max
        min_r: float = 100.0,
        max_r: float = 1e6,
        max_error_pct: float = 0.5,
        max_results: int = 5,
        series_label: str = "E96",
    ) -> List[SolutionPair]:
        """
        Résout Vout = Vref * (1 + R1 / R2).
        R1 = pont haut, R2 = pont bas.
        """
        solutions: List[SolutionPair] = []
        filtered_pool = [r for r in resistor_pool if min_r <= r <= max_r]

        for r2 in filtered_pool:
            ideal_r1 = r2 * ((target_vout - vref) / vref)
            if ideal_r1 < min_r or ideal_r1 > max_r:
                continue

            for r1 in filtered_pool:
                # Évaluation de la tension réelle produite
                vout_calc = vref * (1.0 + (r1 / r2))
                error = abs((vout_calc - target_vout) / target_vout) * 100.0

                if error <= max_error_pct:
                    current = target_vout / (r1 + r2)
                    if min_current_a <= current <= max_current_a:
                        r_th = (r1 * r2) / (r1 + r2)
                        solutions.append(
                            SolutionPair(
                                r1_top=r1,
                                r2_bottom=r2,
                                r1_formatted=format_resistance(r1),
                                r2_formatted=format_resistance(r2),
                                target_metric="Vout (V)",
                                calculated_metric_val=round(vout_calc, 4),
                                target_metric_val=target_vout,
                                error_pct=round(error, 3),
                                divider_current_ma=round(current * 1000.0, 3),
                                thevenin_resistance=round(r_th, 1),
                                series_name=series_label,
                            )
                        )

        # Tri : erreur minimale d'abord, puis courant modéré
        solutions.sort(key=lambda s: (s.error_pct, abs(s.divider_current_ma - 0.5)))
        
        # Déduplication des ratios identiques
        unique_solutions: List[SolutionPair] = []
        seen_ratios: Set[Tuple[float, float]] = set()
        for s in solutions:
            pair = (s.r1_top, s.r2_bottom)
            if pair not in seen_ratios:
                seen_ratios.add(pair)
                unique_solutions.append(s)
            if len(unique_solutions) >= max_results:
                break

        return unique_solutions

    @staticmethod
    def solve_divider(
        target_vout: float,
        vin: float,
        resistor_pool: Sequence[float],
        min_current_a: float = 1e-6,   # 1 µA
        max_current_a: float = 5e-3,   # 5 mA
        max_thevenin_r: Optional[float] = None,
        min_r: float = 100.0,
        max_r: float = 2e6,
        max_error_pct: float = 0.5,
        max_results: int = 5,
        series_label: str = "E96",
    ) -> List[SolutionPair]:
        """
        Résout Vout = Vin * (R2 / (R1 + R2)).
        R1 = pont haut, R2 = pont bas.
        """
        solutions: List[SolutionPair] = []
        filtered_pool = [r for r in resistor_pool if min_r <= r <= max_r]
        ratio_target = target_vout / vin

        for r2 in filtered_pool:
            ideal_r1 = r2 * ((1.0 - ratio_target) / ratio_target)
            if ideal_r1 < min_r or ideal_r1 > max_r:
                continue

            for r1 in filtered_pool:
                vout_calc = vin * (r2 / (r1 + r2))
                error = abs((vout_calc - target_vout) / target_vout) * 100.0

                if error <= max_error_pct:
                    current = vin / (r1 + r2)
                    r_th = (r1 * r2) / (r1 + r2)

                    if max_thevenin_r is not None and r_th > max_thevenin_r:
                        continue

                    if min_current_a <= current <= max_current_a:
                        solutions.append(
                            SolutionPair(
                                r1_top=r1,
                                r2_bottom=r2,
                                r1_formatted=format_resistance(r1),
                                r2_formatted=format_resistance(r2),
                                target_metric="Vout (V)",
                                calculated_metric_val=round(vout_calc, 4),
                                target_metric_val=target_vout,
                                error_pct=round(error, 3),
                                divider_current_ma=round(current * 1000.0, 3),
                                thevenin_resistance=round(r_th, 1),
                                series_name=series_label,
                            )
                        )

        solutions.sort(key=lambda s: (s.error_pct, s.thevenin_resistance))
        unique_solutions: List[SolutionPair] = []
        seen_pairs: Set[Tuple[float, float]] = set()
        for s in solutions:
            pair = (s.r1_top, s.r2_bottom)
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                unique_solutions.append(s)
            if len(unique_solutions) >= max_results:
                break

        return unique_solutions


def print_solutions_table(solutions: List[SolutionPair], mode_title: str) -> None:
    """Affiche les résultats d'optimisation sous forme d'un tableau lisible."""
    if not solutions:
        print(f"\n❌ Aucune combinaison trouvée satisfaisant les critères pour {mode_title}.")
        return

    print(f"\n=== Meilleurs Couples de Résistances pour : {mode_title} ===")
    header = (
        f"{'Rang':<5} | {'R_top (R1)':<12} | {'R_bottom (R2)':<14} | "
        f"{'Valeur Calc':<12} | {'Cible':<10} | {'Erreur':<8} | {'Courant':<10} | {'R_Thévenin':<12}"
    )
    sep = "-" * len(header)
    print(header)
    print(sep)

    for i, s in enumerate(solutions, start=1):
        print(
            f"#{i:<4} | {s.r1_formatted:<12} | {s.r2_formatted:<14} | "
            f"{s.calculated_metric_val:<12.4f} | {s.target_metric_val:<10.4f} | "
            f"{s.error_pct:>5.2f} % | {s.divider_current_ma:>6.3f} mA | {format_resistance(s.thevenin_resistance):<12}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Solveur d'optimisation mathématique de couples de résistances (E24/E96 ou catalogue spécifique)."
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    # 1. Mode Régulateur (Buck / Boost / LDO) : Vout = Vref * (1 + R1/R2)
    parser_reg = subparsers.add_parser("regulator", help="Optimise un pont de feedback pour régulateur (Vout = Vref * (1 + R1/R2)).")
    parser_reg.add_argument("--target-vout", type=float, required=True, help="Tension de sortie désirée Vout (ex: 5.0).")
    parser_reg.add_argument("--vref", type=float, required=True, help="Tension de référence interne Vref (ex: 0.8 pour TPS54331).")
    parser_reg.add_argument("--series", default="E96", choices=["E12", "E24", "E96"], help="Série EIA à utiliser (défaut: E96).")
    parser_reg.add_argument("--pool-file", help="Chemin vers un fichier JSON de valeurs de résistances personnalisées.")
    parser_reg.add_argument("--max-error", type=float, default=0.5, help="Erreur maximale admissible en pourcentage (défaut: 0.5%%).")
    parser_reg.add_argument("--min-current", type=float, default=0.00005, help="Courant minimal du pont en Ampères (défaut: 50 µA).")
    parser_reg.add_argument("--max-current", type=float, default=0.002, help="Courant maximal du pont en Ampères (défaut: 2 mA).")
    parser_reg.add_argument("--top-n", type=int, default=5, help="Nombre de solutions à retourner (défaut: 5).")
    parser_reg.add_argument("--json", action="store_true", help="Sortie structurée au format JSON.")

    # 2. Mode Diviseur / Atténuateur ADC : Vout = Vin * (R2 / (R1 + R2))
    parser_div = subparsers.add_parser("divider", help="Optimise un pont diviseur de mesure ou d'atténuation (Vout = Vin * R2 / (R1+R2)).")
    parser_div.add_argument("--target-vout", type=float, required=True, help="Tension de sortie désirée à l'ADC (ex: 1.285 pour Vin=12V).")
    parser_div.add_argument("--vin", type=float, required=True, help="Tension d'entrée nominale Vin (ex: 12.0).")
    parser_div.add_argument("--series", default="E96", choices=["E12", "E24", "E96"], help="Série EIA à utiliser (défaut: E96).")
    parser_div.add_argument("--pool-file", help="Chemin vers un fichier JSON de valeurs de résistances personnalisées.")
    parser_div.add_argument("--max-rth", type=float, help="Résistance équivalente de Thévenin maximale en Ohms (critique pour temps de charge ADC).")
    parser_div.add_argument("--max-error", type=float, default=0.5, help="Erreur maximale admissible en pourcentage (défaut: 0.5%%).")
    parser_div.add_argument("--min-current", type=float, default=0.00001, help="Courant minimal du pont en Ampères (défaut: 10 µA).")
    parser_div.add_argument("--max-current", type=float, default=0.002, help="Courant maximal du pont en Ampères (défaut: 2 mA).")
    parser_div.add_argument("--top-n", type=int, default=5, help="Nombre de solutions à retourner (défaut: 5).")
    parser_div.add_argument("--json", action="store_true", help="Sortie structurée au format JSON.")

    args = parser.parse_args()

    # Chargement de la réserve de valeurs
    if getattr(args, "pool_file", None):
        p_path = Path(args.pool_file)
        if not p_path.exists():
            sys.stderr.write(f"Erreur : fichier de valeurs introuvable : {p_path}\n")
            return 1
        raw_pool = json.loads(p_path.read_text(encoding="utf-8"))
        resistor_pool = [parse_engineering_value(v) for v in raw_pool]
        series_label = f"Custom ({p_path.name})"
    else:
        resistor_pool = load_e_series(args.series)
        series_label = args.series

    if args.mode == "regulator":
        solutions = RatioOptimizer.solve_regulator(
            target_vout=args.target_vout,
            vref=args.vref,
            resistor_pool=resistor_pool,
            min_current_a=args.min_current,
            max_current_a=args.max_current,
            max_error_pct=args.max_error,
            max_results=args.top_n,
            series_label=series_label,
        )
        if args.json:
            print(json.dumps([asdict(s) for s in solutions], indent=2, ensure_ascii=False))
        else:
            print_solutions_table(solutions, f"Régulateur Vout = {args.target_vout} V (Vref = {args.vref} V) [{series_label}]")

    elif args.mode == "divider":
        solutions = RatioOptimizer.solve_divider(
            target_vout=args.target_vout,
            vin=args.vin,
            resistor_pool=resistor_pool,
            min_current_a=args.min_current,
            max_current_a=args.max_current,
            max_thevenin_r=args.max_rth,
            max_error_pct=args.max_error,
            max_results=args.top_n,
            series_label=series_label,
        )
        if args.json:
            print(json.dumps([asdict(s) for s in solutions], indent=2, ensure_ascii=False))
        else:
            print_solutions_table(solutions, f"Pont Diviseur Vout = {args.target_vout} V pour Vin = {args.vin} V [{series_label}]")

    return 0 if solutions else 1


if __name__ == "__main__":
    sys.exit(main())
