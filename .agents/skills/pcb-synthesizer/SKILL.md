---
name: pcb-synthesizer
description: "Closed-loop PCB synthesis engine (Co-design Placement -> Routing -> EMC Metrology -> Ground Stitching). Orchestrates the complete toolchain: EasyEDA Pro, FreeRouting, and PCB Stitcher with adaptive feedback and DRC = 0 certification."
---

# Skill: PCB Synthesizer (Closed-Loop Placement-Routing-EMC Synthesis)

## 1. Overview & Vision

The `pcb-synthesizer` skill is a top-level orchestrator unifying printed circuit board design under **EasyEDA Pro** into a fully transactional, closed-loop automated pipeline:

```
             ┌─────────────────────────────────────────────────────────────┐
             │                     PCB SYNTHESIZER                         │
             │                 (Closed-Loop Orchestrator)                  │
             └──────────────────────────────┬──────────────────────────────┘
                                            │
                                            ▼ (1)
             ┌─────────────────────────────────────────────────────────────┐
             │                         PCB-PLACER                          │
             │  Stochastic Placement & Physical EMC Simulated Annealing v2 │
             │  (0 Collisions, RF Keepouts, Anchors, H 1/r³ & E 1/r² Energy)│
             └──────────────────────────────┬──────────────────────────────┘
                                            │
                                            ▼ (2)
             ┌─────────────────────────────────────────────────────────────┐
             │                       APPLY PLACEMENT                       │
             │  EasyEDA Pro Batch Injection with Rollback Snapshot         │
             └──────────────────────────────┬──────────────────────────────┘
                                            │
                                            ▼ (3)
             ┌─────────────────────────────────────────────────────────────┐
             │                         FREEROUTING                         │
             │  DSN Export -> NetClasses Patching -> FreeRouting CLI       │
             │  -> SES Import into EasyEDA Pro                             │
             └──────────────────────────────┬──────────────────────────────┘
                                            │
                                            ▼ (4)
             ┌─────────────────────────────────────────────────────────────┐
             │                         DSN METRICS                         │
             │  Real Post-Routing Metrology Analyzer                       │
             │  - Actual polygonal loop area (Shoelace)                    │
             │  - Closed-loop inductance over GND plane (Grover/Rosa/Paul) │
             │  - Differential pair skew                                   │
             └──────────────────────────────┬──────────────────────────────┘
                                            │
                       [Compliant?] ────────┼──────── [Non-Compliant]
                            │               │                │
                           YES              │             NO (Cycle < 3)
                            │               │                │
                            ▼               │                ▼ (Feedback)
             ┌──────────────────────────────┴─┐   ┌───────────────────────────┐
             │          PCB-STITCHER          │   │ Adaptive Tightening       │
             │  GND escape fanout vias        │   │ of Local Constraints      │
             │  + 3D A* island bridging       │   │ and Feedback Loop to (1)  │
             │  + Polygon pour rebuilding     │   └───────────────────────────┘
             └──────────────┬─────────────────┘
                            │
                            ▼ (5)
             ┌─────────────────────────────────────────────────────────────┐
             │                    DRC = 0 CERTIFICATION                    │
             │               Final Physical Synthesis Report               │
             └─────────────────────────────────────────────────────────────┘
```

---

## 2. Project Rules Compliance (AGENTS.md)

- **Rule 1 (Modularity & Agnostic Engines):**
  - **Zero hardcoded components:** No components, nets, or coordinates are hardcoded. All rules are injected via `--manifest` (`manifest.json`) and `--config` (`constraints.json`).
  - **Strict execution via `uv`:** Every Python command must be launched via `uv run python ...`.
- **Rule 2 (Safety & EasyEDA Bridge Control):**
  - Atomic backups, HTTP connectivity checks on port 49620, and rollback on failure.
- **Rule 5 (Closure & Post-Validation):**
  - Blocking DRC = 0 and ERC = 0 checks before certification.

---

## 3. Skill Components

| File | Role | Description |
| :--- | :--- | :--- |
| `SKILL.md` | Specification | Architectural documentation and CLI user guide. |
| `dsn_metrics.py` | Post-routing metrology | Specctra DSN/SES parser extracting actual routed traces, computing true loop area and closed-loop inductance. |
| `synthesizer_pipeline.py` | Master orchestrator | Coordination engine driving the closed loop with iterative feedback (up to 3 cycles) and final certification. |
| `tests/test_dsn_metrics.py` | Test suite | Automated unit tests for metrology analysis of DSN/SES files. |

---

## 4. Command-Line Usage

### A. Full Closed-Loop Synthesis (Recommended)
```bash
uv run python .agents/skills/pcb-synthesizer/synthesizer_pipeline.py \
  --manifest documents/pcb/manifest.json \
  --board documents/pcb/constraints.json \
  --max-cycles 3 \
  --passes 10 \
  --apply
```

### B. Post-Routing Metrology Only (`dsn_metrics.py`)
```bash
uv run python .agents/skills/pcb-synthesizer/dsn_metrics.py \
  --dsn .agents/skills/freerouting/.cache/board.dsn \
  --manifest documents/pcb/manifest.json \
  --board documents/pcb/constraints.json
```

### C. Simulation Mode (Dry-Run without EasyEDA changes)
```bash
uv run python .agents/skills/pcb-synthesizer/synthesizer_pipeline.py \
  --manifest documents/pcb/manifest.json \
  --board documents/pcb/constraints.json \
  --dry-run
```

---

## 5. Generated Artifacts & Reports

Upon completion of synthesis, the pipeline produces and records the metrology and certification summary:
* [`documents/pcb/synthesis_report.json`](../../../documents/pcb/synthesis_report.json): Closed-loop execution report detailing DRC status, completed optimization cycles, critical loop areas computed via Shoelace formula, and differential skew.
