---
name: ratio-solver
description: Mathematical optimization engine calculating resistor pairs for voltage dividers, regulator feedback networks (Buck/Boost/LDO), ADC attenuators, and op-amp gain stages.
---

# Skill: ratio-solver

Universal and agnostic algorithmic engine (Rule 1) designed to solve the optimization problem for resistor pairs `(R1, R2)` across standardized E-series (E12, E24, E96, E192) loaded from [`references/e_series.json`](references/e_series.json) or from a constrained stock catalog of available components (e.g., JLCPCB *Basic Parts*).

---

## 1. Principles & Modeled Equations

### A. Regulator Feedback Mode (`regulator`)
Used to determine the feedback divider network for buck converters (e.g., TPS54331), boost converters, or linear LDO regulators:
$$V_{out} = V_{ref} \times \left(1 + \frac{R_1}{R_2}\right)$$
* `R1`: High-side resistor (connected between output Vout and feedback pin FB).
* `R2`: Low-side resistor (connected between feedback pin FB and ground GND).
* Theoretical ratio: $\frac{R_1}{R_2} = \frac{V_{out} - V_{ref}}{V_{ref}}$.
* Divider quiescent current: $I_{div} = \frac{V_{out}}{R_1 + R_2}$.

### B. Divider / ADC Attenuator Mode (`divider`)
Used to scale a high input voltage (e.g., automotive 12V battery rail) down into the input dynamic range of an analog-to-digital converter (e.g., ESP32 ADC1, Vadc <= 1.3 V to 3.1 V):
$$V_{out} = V_{in} \times \frac{R_2}{R_1 + R_2}$$
* `R1`: High-side resistor (input Vin to measurement node).
* `R2`: Low-side resistor (measurement node to GND).
* Equivalent Thévenin resistance: $R_{th} = \frac{R_1 \times R_2}{R_1 + R_2}$ *(critical for ADC sample-and-hold capacitor charging time)*.

---

## 2. CLI Usage Guide

The solver is always executed via `uv run`:

### Example 1: 5.0V Buck Feedback Network (Vref = 0.8 V) using E96
```powershell
uv run python .agents/skills/ratio-solver/scripts/ratio_solver.py regulator --target-vout 5.0 --vref 0.8 --series E96
```

### Example 2: Feedback Network under E24 Series (Standard 5% or 1% Tolerance)
```powershell
uv run python .agents/skills/ratio-solver/scripts/ratio_solver.py regulator --target-vout 5.0 --vref 0.8 --series E24 --max-error 0.5
```

### Example 3: ADC Attenuator (12V -> 1.285V for Automotive Battery Sizing)
```powershell
uv run python .agents/skills/ratio-solver/scripts/ratio_solver.py divider --vin 12.0 --target-vout 1.2857 --series E96 --max-rth 20000
```

### Example 4: Optimization with a Constrained Catalog (e.g., JLCPCB Basic Parts)
```powershell
uv run python .agents/skills/ratio-solver/scripts/ratio_solver.py regulator --target-vout 5.0 --vref 0.8 --pool-file available_resistors.json --json
```

---

## 3. Filtering Parameters & Constraints

| Parameter | Description | Default |
| :--- | :--- | :--- |
| `--max-error` | Maximum allowable relative error in % on the target voltage | `0.5%` |
| `--min-current` | Minimum current through the divider (avoids high impedances susceptible to noise pick-up) | `50 µA` |
| `--max-current` | Maximum current through the divider (limits no-load quiescent consumption) | `2 mA` |
| `--max-rth` | Maximum Thévenin equivalent resistance in Ohms (`divider` mode to comply with ADC source impedance) | Unlimited |
| `--top-n` | Maximum number of ranked candidate pairs returned | `5` |
| `--json` | Structured JSON output for programmatic consumption by another skill | Disabled |
