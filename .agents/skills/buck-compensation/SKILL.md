---
name: buck-compensation
description: >-
  Small-signal modeling, loop calculation, and parametric optimization tool for Type II
  compensation networks of TI TPS543xx family buck converters (TPS54331, TPS54332, TPS54231, TPS54240).
  Evaluates loop stability (Bode plots, crossover frequency, phase margin, gain margin) and optimizes
  the (Rz, Cz, Cp) triplet using standard component libraries (JLCPCB Basic Parts) whenever the regulator,
  inductor L1, output capacitor Cout, or estimated load current changes.
compatibility: Python 3.8+
metadata:
  author: OBD2-Scanner-Dev
  version: "1.0.0"
---

# Skill: Buck Compensation (TI TPS543xx / TPS54331)

This skill provides an autonomous small-signal modeling and Type II loop compensation optimization environment for the **TPS54331** buck converter (or TPS543xx / TPS542xx derivatives) in the **ESP32 OBD-II Scanner** project.

It eliminates manual round-trips to the TI WEBENCH tool during schematic revisions or mechanical/thermal sizing updates.

---

## 1. Context & Physical Model

The TPS54331 family employs a fixed-frequency (570 kHz) **Peak Current-Mode Control** architecture. The outer voltage regulation loop is driven by a transconductance error amplifier connected to the `COMP` pin (pin 6).

### TPS54331 Internal Constants (TI SLVS839H)
* **Internal Reference Voltage (Vref):** `0.8 V`
* **Error Amplifier DC Voltage Gain (VGGM):** `800 V/V`
* **Error Amplifier Output Resistance (ROA):** `8.0 MΩ`
* **Error Amplifier Transconductance (gm,EA = VGGM / ROA):** `100 µS`
* **Power Stage Transconductance (gm,PS = gm,COMP):** `12.0 A/V`
* **Switching Frequency (Fsw):** `570 kHz`
* **Recommended Practical Crossover Frequency Upper Limit (Fco,max):** `25 kHz`

---

## 2. Type II Compensation Network Topology

The network is connected between the `COMP` pin and ground (`GND`):
1. **Series Zero / Low-Frequency Pole Branch:** Resistor Rz in series with capacitor Cz.
   * Loop zero: `fz1 = 1 / (2π · Rz · Cz)`
2. **Parallel High-Frequency Capacitor:** Capacitor Cp in parallel with the Rz + Cz branch.
   * High-frequency pole: `fp1 ≈ 1 / (2π · Rz · Cp)` (with Cz >> Cp)
   * Function: Attenuates high-frequency switching noise (570 kHz) on the high-impedance `COMP` pin.

---

## 3. Optimization Script Usage

The script is located at `scripts/tps54331_compensation.py`.

### A. Nominal Closed-Form Calculation (TI Equations 16-28)
Deterministic computation targeting a specific crossover frequency Fco and phase margin:
```bash
uv run python .agents/skills/buck-compensation/scripts/tps54331_compensation.py
```
*Optional arguments:* `--vout 5.0 --cout 15e-6 --iomax 0.6 --fco 20e3 --pm 65.0 --designator U4`

### B. Precise Evaluation of an Existing Triplet (`--eval`)
Exact small-signal analysis by resolving the open-loop transfer function T(s):
```bash
uv run python .agents/skills/buck-compensation/scripts/tps54331_compensation.py --eval --rz 10000 --cz 3.3e-9 --cp 220e-12
```
*Provided outputs:*
* Exact crossover frequency Fco (gain = 0 dB)
* Nominal phase margin Φm
* Gain margin Gm
* Robustness sweep across the complete operating envelope (Io from 0.1 A to 1.0 A, and Cout from 10 µF to 20 µF)

### C. Parametric Optimization against the JLCPCB Catalog (`--optimize`)
Scans standard passive combinations available as **Basic Parts** and ranks the best candidates by stability score:
```bash
uv run python .agents/skills/buck-compensation/scripts/tps54331_compensation.py --optimize
```

### D. JSON-Formatted Output for Automated Agent Consumption (`--json`)
```bash
uv run python .agents/skills/buck-compensation/scripts/tps54331_compensation.py --eval --rz 10000 --cz 3.3e-9 --cp 220e-12 --json
```

---

## 4. Automatic Trigger Conditions

The agent must rerun this script whenever any of the following events occur:
1. Modification of the output capacitor `Cout` (nominal value, dielectric technology, or rated voltage affecting DC-bias derating).
2. Modification of the power inductor `L` (nominal inductance or saturation current).
3. Re-evaluation of the circuit's maximum current consumption (e.g., concurrent Wi-Fi + BLE + transceiver activation).
4. Detection of a discrepancy greater than **15%** between the schematic values and the optimal calculated values.
