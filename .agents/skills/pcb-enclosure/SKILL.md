---
name: pcb-enclosure
description: Agnostic parametric 3D mechanical enclosure generation engine (STEP & STL) for FDM 3D printing, SLA resin, and JLCPCB SLS Nylon.
---

# Skill: pcb-enclosure

Parametric, agnostic, and automated 3D mechanical modeling engine for electronic enclosures.
It is built upon the industrial **OpenCASCADE (OCCT)** geometric kernel via the Python library `build123d`, ensuring 100% headless command-line execution and direct export of standard solid **STEP files (ISO 10303 AP214)** and **high-resolution STL meshes** ready for ordering via JLCPCB 3D Printing.

---

## 1. Engineering Principles & AGENTS.md Compliance

- **Rule 1 (Zero hardcoded components):** The engine contains no hardcoded components, dimensions, or coordinates. All values originate exclusively from formal configuration files:
  - [`documents/pcb/constraints.json`](../../../documents/pcb/constraints.json): PCB outline (`W`, `H`), mounting holes (`mounting_holes`).
  - [`documents/pcb/enclosure.json`](../../../documents/pcb/enclosure.json): Wall thicknesses, mechanical clearances, standoffs, interface cutouts, and cable clamp dimensions.
- **Rule 1 (Exclusive execution via `uv`):** All scripts are executed using `uv run --with build123d python ...`.
- **Rule 6 (Strict typography):** No LaTeX markup for physical dimensions or tolerances.

---

## 2. Generated Geometric Architecture

The engine automatically generates three complementary mechanical parts:

```
             ┌──────────────────────────────────────────────┐
             │                  TOP SHELL                   │  (Top Shell)
             │   - Counterbored holes for M2 screws         │
             │   - Cutouts for Flash button & LED light pipe│
             │   - Interlocking perimeter groove (lip joint)│
             └──────────────┬───────────────────────────────┘
                            │ Parting Line
             ┌──────────────┴───────────────────────────────┐
             │                  PCB BOARD                   │  (Positioned on standoffs)
             └──────────────┬───────────────────────────────┘
                            │
             ┌──────────────┴───────────────────────────────┐
             │                BOTTOM SHELL                  │  (Bottom Shell)
             │   - 4 standoffs with heat-set M2 insert wells│
             │   - Cradle for OBD-II wire harness           │
             │   - Interlocking perimeter mating lip        │
             │   - 2-screw cable clamp (enclosure_clamp)    │
             └──────────────────────────────────────────────┘
```

### 1. Bottom Shell (`enclosure_bottom`)
- Base plate with nominal thickness `T` and exterior fillets `R`.
- 4 mounting standoffs aligned with PCB mounting holes, with pre-calibrated pockets for M2 brass heat-set threaded inserts.
- Recessed lower cavity for cable routing and bottom-side through-hole pin clearance.
- Clamping cradle for the OBD-II harness cable with 2 threaded pockets for the clamp.
- Perimeter mating lip providing play-free alignment and dust sealing.

### 2. Top Shell (`enclosure_top`)
- Top cover with nominal thickness `T` and complementary interlocking lip groove.
- 4 through-hole screw counterbores for M2 screws, recessing screw heads flush below the surface.
- Upper half-opening for the USB-C connector along the parting line.
- Actuation hole for the Flash/Boot push-button (accessible via stylus or flexible pusher).
- Light pipe tunnel for the status LED.

### 3. Cable Clamp (`enclosure_clamp`)
- Rigid 2-screw M2 clamp securing the outer jacket of the OBD-II cable firmly into its cradle.
- Complete mechanical strain relief: zero tensile or torsional stress is transmitted to connector J1 solder joints on the PCB.

---

## 3. Command-Line Usage (CLI)

```bash
# Full generation of STEP and STL models for the OBD-II project
uv run --with build123d python .agents/skills/pcb-enclosure/scripts/enclosure_generator.py \
    --constraints documents/pcb/constraints.json \
    --enclosure documents/pcb/enclosure.json \
    --output-dir documents/enclosure

# Run geometric unit tests
uv run --with build123d python .agents/skills/pcb-enclosure/tests/test_enclosure.py

# Convert and optimize a STEP solid to WebGL STL (for GitHub)
uv run --with build123d python scripts/convert_step_to_stl.py --input documents/pcb/scanner.step --output documents/pcb/scanner.stl
```

---

## 4. Generated Artifacts in `documents/enclosure/`

| File | Format | Description | Destination |
| :--- | :--- | :--- | :--- |
| `enclosure_bottom.step` | STEP AP214 | Bottom shell solid model | CAD Archive / JLCPCB 3D |
| `enclosure_bottom.stl` | STL (binary) | High-res bottom shell mesh | 3D Slicer / JLCPCB 3D |
| `enclosure_top.step` | STEP AP214 | Top shell solid model | CAD Archive / JLCPCB 3D |
| `enclosure_top.stl` | STL (binary) | High-res top shell mesh | 3D Slicer / JLCPCB 3D |
| `enclosure_clamp.step` | STEP AP214 | Cable clamp solid model | CAD Archive / JLCPCB 3D |
| `enclosure_clamp.stl` | STL (binary) | High-res cable clamp mesh | 3D Slicer / JLCPCB 3D |
| `enclosure_assembly.step` | STEP AP214 | Complete mated enclosure assembly | CAD verification and fit check |
