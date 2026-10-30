---
name: pcb-stitcher
description: "Auto-stitching, escape via routing, and multi-layer copper island bridging engine for EasyEDA Pro. Enforces electrical ground (GND) and power rail continuity under DRC and EMC constraints."
---

# Skill: PCB Stitcher for EasyEDA Pro

## 1. Overview & Architecture

The `pcb-stitcher` skill is an algorithmic engine providing automated electrical continuity for copper pour regions (reference ground `GND`, power rails, or thermal planes) within EasyEDA Pro.

Following automated signal routing (e.g., via FreeRouting) and polygon pour regeneration (`rebuildCopperRegion`), two recurrent physical issues arise:
1. **Isolated SMD Pads:** Ground pads on top (or bottom) layers lack escape vias to reach the opposite ground plane.
2. **Disconnected Copper Islands:** Through-hole or transverse signal traces segment copper planes into peninsulas or floating copper islands (`Connection Error` in DRC checks).

### Pipeline Execution Flow:
```
[EasyEDA Pro PCB (Pours Rebuilt)]
       │
       ▼ (1) fanout_stitcher.py: Detect SMD pads lacking vias & inject escape fanout vias
[Pours Rebuilt + DRC Audit]
       │
       ▼ (2) island_bridger.py: 3D multi-layer A* router bridging isolated islands to reference plane
[Pours Rebuilt]
       │
       ▼ (3) stitcher_pipeline.py: Final validation with strict DRC = 0
```

---

## 2. Project Rules Compliance (AGENTS.md)

- **Rule 1 (Modularity & Agnostic Engine):**
  - **Zero hardcoded components:** No component references (`U4`, `R13`, `C7`, etc.), physical coordinates, or specific net names are hardcoded in the scripts.
  - **Data Origin:** All parameters (net name, trace width, clearance, via dimensions) originate exclusively from command-line arguments (`--net`, `--clearance-mm`, `--via-drill-mm`, etc.) or physical topology queried dynamically via the EasyEDA Pro API.
  - **Strict execution via `uv`:** Every Python script in this skill must be executed via `uv run python <script>.py`.
- **Rule 2 (Transparency and Safety):**
  - All modifications injected into the PCB document via the EasyEDA bridge (`http://localhost:49620`) must be explicitly declared beforehand (number of vias, line segment coordinates).

---

## 3. Skill Components

| Script | Role | Description |
| :--- | :--- | :--- |
| `geometry.py` | Agnostic geometric engine | Provides continuous line-to-line and line-to-point distance calculations, collision detection against tracks, pads, and vias, and enforcement of keepout zones and board outlines. |
| `fanout_stitcher.py` | Escape via solver | Identifies SMD pads on the target net requiring vias, radially samples candidate collision-free locations, and routes the short connecting trace. |
| `island_bridger.py` | Multi-layer A* router | Identifies disconnected islands (via DRC output), calculates 3D A* paths with via transitions and continuous clearance checks, and injects bridging traces. |
| `stitcher_pipeline.py` | Master orchestrator | Coordinates the full execution flow (Fanout -> Pour rebuilding -> DRC audit -> A* bridging -> Final DRC = 0 check). |

---

## 4. Command-Line Usage

### Complete Unified Pipeline (Recommended)
```bash
# Full pipeline execution with direct PCB application:
uv run python .agents/skills/pcb-stitcher/stitcher_pipeline.py --net GND --clearance-mm 0.23 --track-width-mm 0.30 --via-drill-mm 0.30 --via-diameter-mm 0.60 --apply

# Dry-run simulation (without modifying the PCB):
uv run python .agents/skills/pcb-stitcher/stitcher_pipeline.py --net GND --clearance-mm 0.23
```

### Pipeline Options:
- `--net <str>`: Target net name (default: `GND`).
- `--clearance-mm <float>`: Minimum guaranteed electrical clearance against all obstacles (default: `0.23` mm / 9.0 mil to satisfy JLCPCB standard DRC of 0.20 mm).
- `--track-width-mm <float>`: Width of escape traces and bridges (default: `0.30` mm / 12 mil).
- `--via-drill-mm <float>`: Drill hole diameter for stitching vias (default: `0.30` mm / 12 mil).
- `--via-diameter-mm <float>`: Outer pad ring diameter for stitching vias (default: `0.60` mm / 24 mil).
- `--grid-step-mil <float>`: Grid discretization step size for the A* pathfinding algorithm (default: `5.0` mil).
- `--port <int>`: HTTP port for local EasyEDA Pro bridge (default: `49620`).
- `--apply`: Injects primitives (vias, tracks) and triggers copper pour rebuilding in EasyEDA Pro.

---

## 5. 3D A* Routing Algorithm

The A* algorithm in `island_bridger.py` ensures:
- **Intelligent Layer Transitions:** A TopLayer <-> BottomLayer transition is only permitted at locations where a full through-hole via satisfies clearance rules across all conductive layers.
- **Via Cost Penalty:** An additional cost is assigned to layer transitions to favor planar routing on the most direct copper pour.
- **Continuous Clearance Verification:** Every line segment connecting two grid nodes is analytically verified (segment-to-segment distance) to eliminate diagonal clearance violations or pad corner clipping.
- **Collinear Path Smoothing:** Gridded paths are automatically simplified into straight and 45-degree diagonal segments matching standard PCB design practices.
