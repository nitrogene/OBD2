---
name: pcb-dfm
description: "Automated DFM (Design for Manufacturing) and SMT assembly audit engine for EasyEDA Pro and JLCPCB. Checks solder mask bridges, via-to-pad clearances (solder wicking), silkscreen clearances, copper clearances, drill holes, SMD component spacing, and BOM/CPL consistency."
---

# Skill: PCB & SMT DFM Auditor for EasyEDA Pro & JLCPCB

## 1. Overview & Architecture

The `pcb-dfm` skill is an industrial-grade engineering and quality assurance engine designed to automate Design for Manufacturing (**DFM**) and automated Surface Mount Technology (**SMT**) assembly checks against standard factory capabilities for **JLCPCB** (4-layer JLC2313 stackup, 1.6 mm thickness, 1 oz copper).

In an AI-assisted design workflow, EasyEDA Pro's native DRC verifies only electrical connectivity constraints (absence of short circuits, net isolation). However, it does not detect physical manufacturing flaws that lead to fab rejections or critical assembly failures:
- **Solder Mask Bridges too narrow (Solder Mask Bridge < 0.10 mm):** Mask peeling creating a gang mask, promoting solder bridging between fine-pitch pins (e.g., USB-C, ESP32-S3, integrated circuits).
- **Vias tangent to or on SMD pads (Via to Pad < 0.15 mm):** Solder paste capillary wicking into the via during reflow, causing dry joints or component tombstoning.
- **Silkscreen / Solder Mask Overlap (Silkscreen to Pad / Hole):** Automatic clipping of text by the fab house or non-conductive ink deposited on copper pads.
- **SMD Component Clearances:** Insufficient clearance for automated Pick & Place nozzles.
- **BOM / CPL Consistency:** Discrepancies between bill of materials and physical centroid coordinates.

### DFM Pipeline Execution Flow:
```
[Active EasyEDA Pro PCB]
       │
       ▼ (1) drc_bridge.py: Instant primitive extraction (mils -> mm)
[Normalized Geometric Primitives]
       │
       ├─► (2) pcb_dfm_auditor.py: Solder mask bridges, via-to-pad clearances, silkscreen, board edge, hole sizes
       │
       └─► (3) smt_dfm_auditor.py: Component spacing, conveyor margins, optical fiducials, BOM consistency
               │
               ▼ (4) report_generator.py
[Markdown Report (documents/pcb/dfm_report.md) & JSON (documents/pcb/dfm_report.json)]
```

---

## 2. Project Rules Compliance (AGENTS.md)

- **Rule 1 (Modularity & Agnostic Engine):**
  - **Zero hardcoded components:** No component references (`U4`, `R13`, `C8`), physical coordinates, or nets are hardcoded in Python scripts.
  - **Configuration-driven injection:** All thresholds originate from the declarative rules file (`config/rules_jlcpcb.json`) and the injected BOM (`--bom`).
  - **Strict execution via `uv`:** Every Python script in this skill must be executed via `uv run` (direct `python` calls are prohibited).
- **Rule 2 (Safety & EasyEDA Bridge Control):**
  - The local bridge listens on port 49620 in read-only geometric query mode.
- **Rule 6 (Typography & Formulas):**
  - Zero LaTeX formatting for components or values (no `$10\,\text{k}\Omega$`; exclusively plain Markdown/code: `10 kΩ`, `0.10 mm`, `3.3V`).

---

## 3. Skill Components

| Script | Role | Description |
| :--- | :--- | :--- |
| `config/rules_jlcpcb.json` | Factory specification | Declares standard JLCPCB dimensional thresholds (JLC2313, 4-layer, green solder mask). |
| `scripts/__init__.py` | Python package | Package declaration for the DFM audit module. |
| `scripts/drc_bridge.py` | EasyEDA connector | Extracts physical primitives (pads, vias, tracks, silkscreen, board outline) and converts mils to mm. |
| `scripts/pcb_dfm_auditor.py` | PCB DFM engine | Geometric analysis of the bare PCB (solder mask bridge, via-to-pad wicking, silkscreen clearances, drill holes). |
| `scripts/smt_dfm_auditor.py` | SMT DFM engine | Assembly analysis (SMD package spacing, conveyor edge clearances, fiducials, BOM vs CPL). |
| `scripts/report_generator.py` | Summary generator | Produces structured executive summaries in Markdown and JSON with status verdicts (🔴 Danger, 🟠 Warning, 🟢 Info). |
| `scripts/dfm_pipeline.py` | CLI & Orchestrator | Primary entry point for CI/CD automation and closed-loop execution in `pcb-synthesizer`. |
| `scripts/export_fabrication.py` | Production exporter | Automatically exports Gerber archives (ZIP), Pick & Place centroids (CPL CSV), and bill of materials (BOM CSV). |
| `scripts/export_pcb_images.py` | Graphic exporter | Captures and exports 2D Top/Bottom, 3D, and PCB renders via the EasyEDA Pro API. |

---

## 4. CLI Usage Guide

All commands must be executed via `uv run` from the workspace root:

### Full Standard Run (PCB + SMT + Reports):
```bash
uv run python .agents/skills/pcb-dfm/scripts/dfm_pipeline.py
```

### PCB DFM Audit Only:
```bash
uv run python .agents/skills/pcb-dfm/scripts/dfm_pipeline.py --pcb-only
```

### SMT Audit Only with Explicit BOM Specification:
```bash
uv run python .agents/skills/pcb-dfm/scripts/dfm_pipeline.py --smt-only --bom documents/schema/bom.json
```

### Strict Mode (Fails on WARNINGs):
```bash
uv run python .agents/skills/pcb-dfm/scripts/dfm_pipeline.py --strict
```

### Complete Fabrication Package Export (Gerber + CPL + BOM):
```bash
uv run python .agents/skills/pcb-dfm/scripts/export_fabrication.py --output-dir documents/production --prefix OBD2
```

### Command-Line Arguments:
- `--config <path>`: JSON manufacturing rules file (default: `.agents/skills/pcb-dfm/config/rules_jlcpcb.json`).
- `--bom <path>`: Bill of materials file (default: `documents/schema/bom.json`).
- `--output-json <path>`: Destination path for JSON report (default: `documents/pcb/dfm_report.json`).
- `--output-md <path>`: Destination path for Markdown report (default: `documents/pcb/dfm_report.md`).
- `--port <int>`: HTTP port for local EasyEDA bridge (default: `49620`).
- `--pcb-only`: Skips SMT assembly audit.
- `--smt-only`: Skips bare PCB audit.
- `--strict`: Returns exit code 1 if non-blocking warnings remain.

---

## 5. Summary of Audited Rules

| DFM / SMT Rule | Standard JLCPCB Threshold | Danger Threshold | Technical Impact |
| :--- | :---: | :---: | :--- |
| **Solder Mask Bridge** | `>= 0.10 mm` | `< 0.08 mm` | Mask peeling, solder bridging on fine-pitch packages (*gang mask*). |
| **Via-to-Pad Clearance** | `>= 0.15 mm` | `< 0.05 mm` | Solder paste wicking into drill hole, dry joints, tombstoning. |
| **Silkscreen on Pad** | `>= 0.15 mm` | Overlap | Non-conductive ink on copper, automatic clipping by fab house. |
| **Silkscreen Stroke Width** | `>= 0.15 mm` | `< 0.12 mm` | Unreadable text, ink bleeding during screen printing. |
| **Copper to Board Edge** | `>= 0.30 mm` | `< 0.20 mm` | Trace/via shearing during V-scoring or CNC routing. |
| **Annular Ring** | `>= 0.13 mm` | `< 0.10 mm` | Electrical breakout in case of drill misalignment. |
| **SMD Component Spacing** | `>= 0.50 mm` | `< 0.25 mm` | Pick & Place nozzle collision, reflow thermal shadowing. |
| **SMT Conveyor Edge Margin** | `>= 3.0 mm` | `< 1.5 mm` | Requires panel tooling rails for conveyor clamping. |
| **Fiducial Markers** | 3 optical fiducials | 0 | Automated optical alignment for SMT placement equipment. |
