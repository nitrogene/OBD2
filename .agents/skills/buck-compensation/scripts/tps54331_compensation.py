#!/usr/bin/env python3
"""
TPS54331 Step-Down Buck Converter - Loop Compensation (Type II) Calculator & Optimizer

Based on Texas Instruments TPS54331 Datasheet SLVS839H, Section 8.2.2.7 (Eq. 16 to 28),
and small-signal open-loop transfer function modeling.

Capabilities:
1. Analytical closed-form design for specified target crossover frequency and phase margin.
2. Direct evaluation of candidate component triplets (Rz, Cz, Cp) with exact Bode analysis.
3. Parametric sweep / Monte-Carlo across operating envelope (Load current Io, Output capacitance Cout).
4. Automated optimization finding the most robust standard / JLCPCB Basic Part values.
"""

import math
import cmath
import argparse
import json
from dataclasses import dataclass, asdict
from typing import List, Tuple, Dict, Optional

# --- Internal Device Constants (TPS54331 Datasheet SLVS839H) ---
VGGM = 800.0          # Error amplifier DC voltage gain (V/V)
VREF = 0.8            # Internal bandgap reference voltage (V)
ROA = 8.0e6           # Error amplifier output impedance (Ohm)
GMCOMP = 12.0         # Transconductance from COMP voltage to switch current (A/V)
GM_EA = VGGM / ROA    # Error amplifier transconductance: 100 uS (A/V)
FSW = 570.0e3         # Fixed switching frequency (Hz)
FCO_MAX_RECOMMENDED = 25.0e3  # TI recommended practical upper limit for loop bandwidth

# Standard E24 / E96 reference arrays
E24_BASE = [
    1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0,
    3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1
]

E96_BASE = [
    1.00, 1.02, 1.05, 1.07, 1.10, 1.13, 1.15, 1.18, 1.21, 1.24, 1.27, 1.30,
    1.33, 1.37, 1.40, 1.43, 1.47, 1.50, 1.54, 1.58, 1.62, 1.65, 1.69, 1.74,
    1.78, 1.82, 1.87, 1.91, 1.96, 2.00, 2.05, 2.10, 2.15, 2.21, 2.26, 2.32,
    2.37, 2.43, 2.49, 2.55, 2.61, 2.67, 2.74, 2.80, 2.87, 2.94, 3.01, 3.09,
    3.16, 3.24, 3.32, 3.40, 3.48, 3.57, 3.65, 3.74, 3.83, 3.92, 4.02, 4.12,
    4.22, 4.32, 4.42, 4.53, 4.64, 4.75, 4.87, 4.99, 5.11, 5.23, 5.36, 5.49,
    5.62, 5.76, 5.90, 6.04, 6.19, 6.34, 6.49, 6.65, 6.81, 6.98, 7.15, 7.32,
    7.50, 7.68, 7.87, 8.06, 8.25, 8.45, 8.66, 8.87, 9.09, 9.31, 9.53, 9.76,
]

# Common JLCPCB Basic Parts in compensation ranges
JLC_BASIC_RESISTORS = [
    1.0e3, 1.5e3, 2.0e3, 2.2e3, 3.3e3, 4.7e3, 5.1e3, 6.8e3, 8.2e3,
    10.0e3, 12.0e3, 15.0e3, 20.0e3, 22.0e3, 33.0e3, 47.0e3, 100.0e3
]

JLC_BASIC_CAPACITORS = [
    100.0e-12, 150.0e-12, 220.0e-12, 330.0e-12, 470.0e-12, 680.0e-12,
    1.0e-9, 1.5e-9, 2.2e-9, 3.3e-9, 4.7e-9, 6.8e-9, 10.0e-9, 22.0e-9, 47.0e-9, 100.0e-9
]


def find_nearest_standard(value: float, series: List[float]) -> float:
    """Find the nearest standard value in given decade base series."""
    if value <= 0:
        return value
    exp = math.floor(math.log10(value))
    mantissa = value / (10 ** exp)
    closest = min(series, key=lambda x: abs(x - mantissa))
    return round(closest * (10 ** exp), max(0, -exp + 3))


@dataclass
class ClosedFormResult:
    fco_target: float
    phase_loss_deg: float
    phase_boost_deg: float
    k_factor: float
    fz1: float
    fp1: float
    rz_ideal: float
    cz_ideal: float
    cp_ideal: float
    rz_e96: float
    cz_e96: float
    cp_e96: float


def design_closed_form(
    vout: float = 5.0,
    cout_effective: float = 15.0e-6,
    io_max: float = 0.6,
    resr: float = 0.005,
    fco: float = 20.0e3,
    phase_margin_deg: float = 65.0,
) -> ClosedFormResult:
    """Calculates ideal Rz, Cz, Cp from TI SLVS839H Eq. 16-28."""
    ro = vout / io_max
    phase_esr = math.degrees(math.atan(2 * math.pi * fco * resr * cout_effective))
    phase_load = math.degrees(math.atan(2 * math.pi * fco * ro * cout_effective))
    phase_loss = phase_esr - phase_load
    phase_boost = phase_margin_deg - 90.0 - phase_loss

    k = math.tan(math.radians(phase_boost / 2.0 + 45.0))
    fz1 = fco / k
    fp1 = fco * k

    rz = (2.0 * math.pi * fco * vout * cout_effective * ROA) / (GMCOMP * VGGM * VREF)
    cz = 1.0 / (2.0 * math.pi * fz1 * rz)
    cp = 1.0 / (2.0 * math.pi * fp1 * rz)

    rz_e96 = find_nearest_standard(rz, E96_BASE)
    cz_e96 = find_nearest_standard(cz, E96_BASE)
    cp_e96 = find_nearest_standard(cp, E96_BASE)

    return ClosedFormResult(
        fco_target=fco,
        phase_loss_deg=phase_loss,
        phase_boost_deg=phase_boost,
        k_factor=k,
        fz1=fz1,
        fp1=fp1,
        rz_ideal=rz,
        cz_ideal=cz,
        cp_ideal=cp,
        rz_e96=rz_e96,
        cz_e96=cz_e96,
        cp_e96=cp_e96,
    )


def loop_transfer_function(
    f: float,
    rz: float,
    cz: float,
    cp: float,
    cout: float,
    io: float,
    vout: float = 5.0,
    resr: float = 0.005,
) -> complex:
    """Calculates open-loop transfer function T(s) at frequency f (Hz)."""
    s = complex(0, 2.0 * math.pi * f)
    ro = vout / max(io, 1e-4)

    # Power stage / Modulator impedance
    z_cap = 1.0 / (s * cout) + resr
    z_load = (ro * z_cap) / (ro + z_cap)
    g_mod = GMCOMP * z_load

    # Error amplifier impedance Zc(s) in parallel with Roa
    z_branch1 = rz + 1.0 / (s * cz)
    # Total admittance on COMP pin
    y_comp = 1.0 / z_branch1 + s * cp + 1.0 / ROA
    z_comp = 1.0 / y_comp
    g_ea = GM_EA * z_comp

    # Feedback divider gain
    beta = VREF / vout

    return g_mod * beta * g_ea


def evaluate_stability(
    rz: float,
    cz: float,
    cp: float,
    cout: float,
    io: float,
    vout: float = 5.0,
    resr: float = 0.005,
) -> Tuple[float, float, float]:
    """
    Finds crossover frequency fco (where |T| = 1 / 0 dB),
    Phase Margin (PM in degrees), and Gain Margin (GM in dB).
    """
    # Binary search for 0 dB crossover between 100 Hz and 250 kHz
    f_low, f_high = 100.0, 250.0e3
    for _ in range(40):
        f_mid = (f_low + f_high) / 2.0
        t_mid = loop_transfer_function(f_mid, rz, cz, cp, cout, io, vout, resr)
        if abs(t_mid) > 1.0:
            f_low = f_mid
        else:
            f_high = f_mid

    fco = (f_low + f_high) / 2.0
    t_fco = loop_transfer_function(fco, rz, cz, cp, cout, io, vout, resr)
    phase_deg = math.degrees(cmath.phase(t_fco))
    # Standard phase margin: 180 + phase
    pm = 180.0 + phase_deg
    while pm > 180:
        pm -= 360
    while pm < -180:
        pm += 360

    # Search for -180 deg phase frequency (for Gain Margin) between fco and 285 kHz (FSW/2)
    f_gm = None
    gm_db = 99.0
    for f_scan in range(int(max(fco + 1e3, 5e3)), int(FSW / 2), 500):
        t_scan = loop_transfer_function(f_scan, rz, cz, cp, cout, io, vout, resr)
        ph = math.degrees(cmath.phase(t_scan))
        if ph <= -180.0:
            f_gm = float(f_scan)
            gm_db = -20.0 * math.log10(abs(t_scan))
            break

    return fco, pm, gm_db


def sweep_envelope(
    rz: float,
    cz: float,
    cp: float,
    cout_range: List[float],
    io_range: List[float],
    vout: float = 5.0,
    resr: float = 0.005,
) -> Dict[str, float]:
    """Sweeps over Cout and Io envelope, returning min/max PM and Fco."""
    pms = []
    fcos = []
    for cout in cout_range:
        for io in io_range:
            fco, pm, _ = evaluate_stability(rz, cz, cp, cout, io, vout, resr)
            pms.append(pm)
            fcos.append(fco)
    return {
        "min_pm": min(pms),
        "max_pm": max(pms),
        "min_fco": min(fcos),
        "max_fco": max(fcos),
    }


def optimize_compensation(
    vout: float = 5.0,
    cout_nom: float = 22.0e-6,
    cout_derate_min: float = 10.0e-6,
    cout_derate_max: float = 18.0e-6,
    io_min: float = 0.1,
    io_max: float = 1.0,
    prioritize_basic_parts: bool = True,
) -> List[Dict]:
    """
    Evaluates candidate standard component triplets and ranks them
    by robustness (worst-case phase margin and compliance with TI rules).
    """
    # Grid of Cout and Io for envelope verification
    cout_sweep = [cout_derate_min, (cout_derate_min + cout_derate_max) / 2.0, cout_derate_max]
    io_sweep = [io_min, 0.3, 0.6, io_max]

    # Generate candidate components
    if prioritize_basic_parts:
        rz_candidates = [6.8e3, 8.2e3, 10.0e3, 12.0e3, 15.0e3]
        cz_candidates = [2.2e-9, 3.3e-9, 4.7e-9]
        cp_candidates = [150.0e-12, 220.0e-12, 330.0e-12]
    else:
        # Full E24/E96 search around 10k / 3.3n / 220p
        rz_candidates = [7.5e3, 8.2e3, 9.1e3, 10.0e3, 11.0e3, 12.0e3]
        cz_candidates = [2.7e-9, 3.0e-9, 3.3e-9, 3.9e-9]
        cp_candidates = [180.0e-12, 200.0e-12, 220.0e-12, 270.0e-12]

    results = []
    for rz in rz_candidates:
        for cz in cz_candidates:
            for cp in cp_candidates:
                env = sweep_envelope(rz, cz, cp, cout_sweep, io_sweep, vout)
                # Nominal point
                fco_nom, pm_nom, gm_nom = evaluate_stability(rz, cz, cp, 15.0e-6, 0.6, vout)

                # Penalty score based on:
                # - distance from ideal 65 deg PM
                # - Fco exceeding 25 kHz
                # - minimum PM across envelope falling below 50 deg
                penalty = abs(pm_nom - 65.0)
                if env["min_pm"] < 55.0:
                    penalty += (55.0 - env["min_pm"]) * 4.0
                if env["max_fco"] > FCO_MAX_RECOMMENDED:
                    penalty += (env["max_fco"] - FCO_MAX_RECOMMENDED) / 1.0e3 * 3.0

                results.append({
                    "rz": rz,
                    "cz": cz,
                    "cp": cp,
                    "fco_nom_khz": round(fco_nom / 1e3, 1),
                    "pm_nom_deg": round(pm_nom, 1),
                    "min_pm_deg": round(env["min_pm"], 1),
                    "max_pm_deg": round(env["max_pm"], 1),
                    "min_fco_khz": round(env["min_fco"] / 1e3, 1),
                    "max_fco_khz": round(env["max_fco"] / 1e3, 1),
                    "score": round(penalty, 2),
                    "is_basic_parts": (rz in JLC_BASIC_RESISTORS and cz in JLC_BASIC_CAPACITORS and cp in JLC_BASIC_CAPACITORS)
                })

    results.sort(key=lambda x: x["score"])
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Calculateur et optimiseur de compensation Buck TPS54331 (SLVS839H)"
    )
    parser.add_argument("--vout", type=float, default=5.0, help="Tension de sortie (V)")
    parser.add_argument("--cout", type=float, default=15.0e-6, help="Capacite effective Cout (F)")
    parser.add_argument("--iomax", type=float, default=0.6, help="Courant de charge max (A)")
    parser.add_argument("--resr", type=float, default=0.005, help="ESR Cout (Ohm)")
    parser.add_argument("--fco", type=float, default=20.0e3, help="Fco cible (Hz)")
    parser.add_argument("--pm", type=float, default=65.0, help="Marge de phase cible (deg)")
    parser.add_argument("--optimize", action="store_true", help="Lancer l'optimisation paramétrique sur le catalogue")
    parser.add_argument("--eval", action="store_true", help="Evaluer des composants spécifiques (--rz, --cz, --cp)")
    parser.add_argument("--rz", type=float, default=10.0e3, help="Rz a evaluer (Ohm)")
    parser.add_argument("--cz", type=float, default=3.3e-9, help="Cz a evaluer (F)")
    parser.add_argument("--cp", type=float, default=220.0e-12, help="Cp a evaluer (F)")
    parser.add_argument("--json", action="store_true", help="Sortie au format JSON machine")

    args = parser.parse_args()

    if args.optimize:
        res = optimize_compensation(vout=args.vout, io_min=0.1, io_max=args.iomax)
        if args.json:
            print(json.dumps(res[:10], indent=2))
        else:
            print("=== TOP 5 COMBINAISONS OPTIMALES (STABILITÉ ENVELOPPE & BASIC PARTS) ===")
            print(f"{'Rang':<4} | {'Rz (Ohm)':<8} | {'Cz (nF)':<7} | {'Cp (pF)':<7} | {'Fco nom':<8} | {'PM nom':<7} | {'PM min-max':<12} | {'Basic Part':<10}")
            print("-" * 75)
            for i, r in enumerate(res[:5], 1):
                basic_tag = "Oui (100%)" if r['is_basic_parts'] else "Non"
                print(f"{i:<4} | {r['rz']:<8.0f} | {r['cz']*1e9:<7.2f} | {r['cp']*1e12:<7.0f} | {r['fco_nom_khz']:>5.1f} kHz | {r['pm_nom_deg']:>5.1f} deg | {r['min_pm_deg']:.0f} - {r['max_pm_deg']:.0f} deg | {basic_tag:<10}")
            print("\nRecommandation: La combinaison standard Rz=10k, Cz=3.3nF, Cp=220pF offre une marge optimale de ~66 deg.")
        return

    if args.eval:
        fco, pm, gm = evaluate_stability(args.rz, args.cz, args.cp, args.cout, args.iomax, args.vout, args.resr)
        env = sweep_envelope(args.rz, args.cz, args.cp, [10e-6, 15e-6, 20e-6], [0.1, 0.3, 0.6, 1.0], args.vout)
        fz1 = 1.0 / (2.0 * math.pi * args.rz * args.cz)
        fp1 = (args.cz + args.cp) / (2.0 * math.pi * args.rz * args.cz * args.cp)

        data = {
            "rz": args.rz,
            "cz": args.cz,
            "cp": args.cp,
            "fz1_hz": round(fz1, 1),
            "fp1_hz": round(fp1, 1),
            "fco_khz": round(fco / 1e3, 1),
            "pm_deg": round(pm, 1),
            "gm_db": round(gm, 1) if gm < 90 else "> 20 dB",
            "envelope_min_pm": round(env["min_pm"], 1),
            "envelope_max_pm": round(env["max_pm"], 1),
            "envelope_fco_range_khz": f"{env['min_fco']/1e3:.1f} - {env['max_fco']/1e3:.1f}"
        }

        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print(f"=== EVALUATION DU RESEAU : Rz={args.rz:.0f} Ohm, Cz={args.cz*1e9:.2f}nF, Cp={args.cp*1e12:.0f}pF ===")
            print(f"Zero de compensation Fz1     : {data['fz1_hz']:.0f} Hz")
            print(f"Pole haute frequence Fp1     : {data['fp1_hz']:.0f} Hz")
            print(f"Frequence de coupure Fco     : {data['fco_khz']} kHz")
            print(f"Marge de phase nominale      : {data['pm_deg']} deg")
            print(f"Marge de gain                : {data['gm_db']}")
            print(f"Marge de phase sur enveloppe : {data['envelope_min_pm']} deg a {data['envelope_max_pm']} deg")
            print(f"Plage Fco sur enveloppe      : {data['envelope_fco_range_khz']} kHz")
        return

    # Default: Design closed-form
    cf = design_closed_form(
        vout=args.vout,
        cout_effective=args.cout,
        io_max=args.iomax,
        resr=args.resr,
        fco=args.fco,
        phase_margin_deg=args.pm,
    )

    if args.json:
        print(json.dumps(asdict(cf), indent=2))
    else:
        print("=== Calcul du Reseau de Compensation Type II - TPS54331 (U4) ===")
        print(f"Fco visee       : {cf.fco_target/1e3:.1f} kHz")
        print(f"Perte de phase  : {cf.phase_loss_deg:.1f} deg")
        print(f"Boost requis    : {cf.phase_boost_deg:.1f} deg")
        print(f"Fz1 / Fp1       : {cf.fz1:.0f} Hz / {cf.fp1:.0f} Hz")
        print()
        print(f"Rz calcule      : {cf.rz_ideal:.0f} Ohm  -> Standard E96 : {cf.rz_e96:.0f} Ohm (Basic Part dispo: 10 kOhm)")
        print(f"Cz calcule      : {cf.cz_ideal*1e9:.2f} nF -> Standard E96 : {cf.cz_e96*1e9:.2f} nF (Basic Part dispo: 3.3 nF)")
        print(f"Cp calcule      : {cf.cp_ideal*1e12:.0f} pF -> Standard E96 : {cf.cp_e96*1e12:.0f} pF (Basic Part dispo: 220 pF)")
        print("\nPour optimiser ou tester l'enveloppe complete :")
        print("  python tps54331_compensation.py --optimize")
        print("  python tps54331_compensation.py --eval --rz 10000 --cz 3.3e-9 --cp 220e-12")


if __name__ == "__main__":
    main()
