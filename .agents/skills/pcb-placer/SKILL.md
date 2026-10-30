---
name: pcb-placer
description: >-
  Agnostic auto-placement engine driven by geometric, EMC, and thermal constraints for EasyEDA Pro.
  Requires a formal configuration file (--config floorplan.json), estimates and suggests minimal PCB
  dimensions per IPC-7351 standards, verifies constraints (mechanical anchors, decoupling, critical loops, keepouts),
  audits clearances, and executes single-pass placement injection via the local EasyEDA bridge.
compatibility: Python 3.8+, Node.js 18+, uv, EasyEDA Pro desktop with run-api-gateway
metadata:
  author: OBD2-Scanner-Dev
  version: "2.1.0"
---

# Skill: PCB Placer (Agnostic Auto-Placement & Board Sizing Engine)

This skill provides a **pure algorithmic engine** for geometric calculation, dimensional estimation, EMC/thermal constraint validation, and single-pass injection for printed circuit board layout in **EasyEDA Pro**.

In compliance with Rule 1 of [`agents.md`](../../../agents.md), this skill is **completely agnostic**: it contains no hardcoded references to specific components, footprints, or physical coordinates. All data must be passed via a formal configuration file (`--config <file.json>`) or bill of materials (`--bom <bom.json>`).

It relies on the [easyeda-api](../easyeda-api/SKILL.md) skill and its local bridge (port 49620).

---

## 1. Module Architecture

```
.agents/skills/pcb-placer/
├── SKILL.md                 # Documentation and user guide
├── auto_place.py            # Auto-placement engine and single-pass injector
├── apply_placement.py       # Batch injection actuator & DRC certification
├── audit_placement.py       # Geometric auditor for critical EMC distances and board outline
├── easyeda_client.py        # Python client communicating with EasyEDA Pro
├── emc_physics.py           # EMC physics modeling (magnetic field 1/r³ and electric field 1/r²)
├── export_geometry.py       # Geometry and component bounding-box exporter
├── label_placer.py          # Silkscreen label placement & normalization engine (IPC-7351)
├── placement_constraints.py # Geometric and technological constraint loader and verifier
├── placement_resolver.py    # Spatial resolver and functional block partitioner
├── render_svg.py            # SVG vector visualization generator
├── score.py                 # Multi-criteria objective evaluator (HPWL, collisions, EMC, thermal)
├── simulated_annealing.py   # Multi-start simulated annealing & geometric legalizer engine
├── size_estimator.py        # Dimensional estimation & suggestion engine (IPC-7351)
├── validate.py              # Input data integrity and consistency controller
└── tests/                   # Automated unit test suite
    ├── __init__.py          # Test package declaration
    ├── test_annealing.py    # Simulated annealing convergence tests
    ├── test_geometry.py     # Tests of geometric operations, projections, and rotations
    ├── test_legalizer.py    # Tests of legalization engine and non-overlapping repulsion
    ├── test_loop_physics.py # Tests of physical modeling for EMC switching loops
    └── test_score_physics.py# Tests of score functions and physical penalties
```

---

## 2. Quick Usage (via `uv run`)

> [!IMPORTANT]
> In accordance with project rules, all Python scripts must be executed via `uv run`, and the `--config` (or `--bom`) argument is **mandatory**.

### A. Estimate and Suggest Ideal PCB Dimensions (`size_estimator.py`)
Before freezing a board outline or to assess routing feasibility:
```bash
# Sizing estimation from floorplan and comparison with current outline
uv run .agents/skills/pcb-placer/size_estimator.py --config floorplan.json

# Estimation specifying a 4-layer stackup
uv run .agents/skills/pcb-placer/size_estimator.py --config floorplan.json --layers 4

# Direct estimation from the BOM bill of materials
uv run .agents/skills/pcb-placer/size_estimator.py --bom documents/schema/bom.json --layers 2

# Via auto_place.py
uv run .agents/skills/pcb-placer/auto_place.py --config floorplan.json --suggest-size
```

#### Sizing Mathematical Model
The calculation relies on standardized component placement courtyards (**IPC-7351B**):
$$S_{\text{PCB}} = \frac{\sum S_{\text{components}} + S_{\text{Keepouts}}}{\eta_{\text{routing}}}$$

- **Surface Efficiency Ratio ($\eta_{\text{routing}}$):**
  - **2 layers:** `30% to 35%` (Packing factor 2.8x to 3.3x) to preserve a continuous GND plane.
  - **4 layers:** `50% to 60%` (Packing factor 1.7x to 2.0x) enabled by dedicated internal power/ground planes.
- **Reported Sizing Profiles:**
  1. *Minimal Envelope:* Ultra-dense and compact routing.
  2. *Recommended Envelope (Nominal):* Optimal balance among EMC, ground continuity, and standard JLCPCB manufacturing.
  3. *Relaxed Envelope:* Spacious layout with maximized thermal relief.

---

### B. Verify Connection with EasyEDA Pro (`easyeda_client.py`)
```bash
uv run .agents/skills/pcb-placer/easyeda_client.py
```
Displays bridge connection status, active project, PCB document name, component count, net count, track primitives count, and mechanical outline (Layer 11).

---

### C. Audit Physical Placement & EMC Rules (`audit_placement.py`)
```bash
uv run .agents/skills/pcb-placer/audit_placement.py --config floorplan.json
```
Rigorously checks 24 physical design rules:
* **Mechanical Outline:** Presence and dimensional conformance of outline on Layer 11 (`BOARD_OUTLINE`).
* **Edge Clearance:** Adherence to edge clearance (>= 1.0 mm) for all non-anchor components.
* **Fixed Anchors:** Exact coordinates for connectors (`J1`, `J2`) and the SoC (`U1`).
* **EMC Proximity:** HF decoupling (< 2.0 mm), reset filters (< 2.0 mm), ESD/TVS protections (< 5.0 mm).
* **Keepout Zones:** Complete absence of components within the 2.4 GHz meandered RF antenna keepout.

---

### D. Execute Single-Pass Auto-Placement (`auto_place.py`)
```bash
# 1. Simulation without injection (dry-run displaying coordinates and grid)
uv run .agents/skills/pcb-placer/auto_place.py --config floorplan.json

# 2. Live injection into EasyEDA Pro + auto-create board outline if missing + DRC + save
uv run .agents/skills/pcb-placer/auto_place.py --config floorplan.json --apply

# 3. Full injection immediately followed by certification audit
uv run .agents/skills/pcb-placer/auto_place.py --config floorplan.json --apply --audit

# 4. Automatic sync from schematic (importChanges) prior to injection and audit
uv run .agents/skills/pcb-placer/auto_place.py --config floorplan.json --sync --apply --audit
```

---

### E. Solve Global Placement via Simulated Annealing (`simulated_annealing.py`)
Generates a collision-free optimized solution using multi-start simulated annealing incorporating uniform 2D density, colonization operators, and deterministic IPC-compliant geometric legalization:
```bash
# Standard run (4 starts, 0.20 mm spacing margin, candidate JSON and SVG export)
uv run .agents/skills/pcb-placer/simulated_annealing.py \
  --manifest documents/pcb/manifest.json \
  --board documents/pcb/constraints.json \
  --starts 4 \
  --steps 40000 \
  --spacing 0.20 \
  --out placement_candidate.json \
  --svg documents/pcb/placement.svg
```
> **Project Rule:** Whenever placement is modified or recalculated using `pcb-placer`, the [`documents/pcb/placement.svg`](../../../documents/pcb/placement.svg) file must be updated systematically.

---

### F. Inject Placement & Certify DRC (`apply_placement.py`)
Applies placement coordinates from a placement file in a single batch transaction into EasyEDA Pro and initiates DRC certification:
```bash
# Simulation without modifying the PCB
uv run .agents/skills/pcb-placer/apply_placement.py --placement placement_candidate.json --dry-run

# Batch injection, native DRC check, and automatic save
uv run .agents/skills/pcb-placer/apply_placement.py --placement placement_candidate.json
```

---

### G. Optimize & Normalize Silkscreen (`label_placer.py`)
Automatically positions and aligns all designator labels on the top silkscreen layer (Top Silk) conforming to IPC-7351 §3.4.7 and IPC-A-610:
```bash
# Simulation without modifying the PCB (collision and orientation audit)
uv run .agents/skills/pcb-placer/label_placer.py --dry-run

# Live injection, orthogonal normalization (0°/90°), copper clearance (>= 0.25 mm), and save
uv run .agents/skills/pcb-placer/label_placer.py
```

---

## 3. Automated Test Suite

The skill includes a comprehensive suite of unit tests covering EMC physics, geometric legalization, and simulated annealing:
```bash
uv run pytest .agents/skills/pcb-placer/tests/
```
Test modules:
* `tests/test_geometry.py`: Tests of geometric operations, projections, and rotations.
* `tests/test_legalizer.py`: Tests of legalization engine and non-overlapping repulsion.
* `tests/test_loop_physics.py`: Tests of physical modeling for EMC switching loops.
* `tests/test_score_physics.py`: Tests of score functions and physical penalties.
* `tests/test_annealing.py`: Simulated annealing convergence tests.
