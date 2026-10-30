---
name: freerouting
description: "Agnostic headless auto-routing engine integrating FreeRouting CLI and EasyEDA Pro. Manages portable OpenJDK JRE 25 bootstrapping, Specctra DSN/SES export/import, net class and geometric/EMC constraint injection, and optimization pass monitoring."
---

# Skill: Headless FreeRouting for EasyEDA Pro

## 1. Overview & Architecture

The `freerouting` skill provides an autonomous and portable software suite for automated printed circuit board routing in EasyEDA Pro using the open-source **FreeRouting v2.4.1** engine executed in command-line mode.

### Pipeline Execution Flow:
```
[EasyEDA Pro PCB]
       │
       ▼ (1) dsn_exporter.py: Specctra DSN export via the EasyEDA Pro API
[board_raw.dsn]
       │
       ▼ (2) dsn_patcher.py: Constraint injection from --config (widths, clearances, vias)
[board_patched.dsn]
       │
       ▼ (3) router.py: Headless CLI FreeRouting execution (OpenJDK Temurin JRE 25)
[board_routed.ses]
       │
       ▼ (4) ses_importer.py: Re-import SES session file into EasyEDA Pro
[Routed EasyEDA Pro PCB]
```

---

## 2. Project Rules Compliance (AGENTS.md)

- **Rule 1 (Modularity & Agnostic Engine):**
  - **Zero hardcoded components:** No component references (`U4`, `R13`, etc.), physical coordinates, or specific net names are hardcoded in the scripts.
  - **Data source:** All rules (net classes, trace widths, clearances, via diameters) originate exclusively from the formal configuration file provided as a CLI argument (`--config <file.json>`).
  - **Strict execution via `uv`:** Every Python script in this skill must be executed via `uv run python <script>.py`.
- **Rule 2 (Transparency and Safety):**
  - All interactions with the local EasyEDA bridge (`http://localhost:49620`) must be explicitly declared before execution (intent, technical rationale, concrete action).

---

## 3. Skill Components

| Script | Role | Description |
| :--- | :--- | :--- |
| `jre_manager.py` | Environment manager | Automatically downloads and unpacks the portable OpenJDK Temurin JRE 25 runtime and FreeRouting v2.4.1 JAR into `.cache/runtime/` if not present. |
| `dsn_exporter.py` | DSN exporter | Queries the EasyEDA Pro API (`eda.pcb_ManufactureData.getDsnFile`) to export the live PCB layout in Specctra DSN format. |
| `dsn_patcher.py` | Constraint patcher | Parses the Specctra DSN, converts millimeter dimensions into DSN units (mils), injects custom via padstacks, and updates net class rules based on the JSON configuration. |
| `router.py` | Headless runner | Drives FreeRouting via the command line, parses real-time routing progress (fanout, autoroute passes, optimization), and outputs the `.ses` session file. |
| `ses_importer.py` | SES importer | Injects the `.ses` file into the active PCB document via `eda.pcb_Document.importAutoRouteSesFile`. |
| `drc_checker.py` | EasyEDA DRC checker | Triggers the physical DRC audit in EasyEDA Pro via the API (`eda.pcb_Drc.check`) and summarizes errors and warnings. |
| `freerouting_pipeline.py` | Master orchestrator | Coordinates steps 1 through 4 into a unified pipeline with error handling and summary metrics. |

---

## 4. Command-Line Usage

### Complete Unified Pipeline (Recommended)
```bash
# Full routing run from EasyEDA Pro with automatic re-import
uv run python .agents/skills/freerouting/freerouting_pipeline.py --config documents/pcb/constraints.json --passes 10

# Incremental routing mode (preserves pre-existing routed traces)
uv run python .agents/skills/freerouting/freerouting_pipeline.py --config documents/pcb/constraints.json --incremental

# Generate the SES file without re-importing into the PCB (simulation / analysis)
uv run python .agents/skills/freerouting/freerouting_pipeline.py --config documents/pcb/constraints.json --no-import
```

### Pipeline Options:
- `--config <path>`: JSON file containing design rules and net classes (default: `documents/pcb/constraints.json`).
- `--dsn <path>`: Source DSN file (optional; if omitted, exported directly from EasyEDA Pro).
- `--passes <int>`: Maximum number of autorouting passes (default: `10`).
- `--threads <int>`: Number of engine threads (default: `1` to avoid clearance violations during optimization).
- `--strategy <str>`: Routing update strategy (`greedy`, `global`, `hybrid`; default: `hybrid`).
- `--incremental`: Protects pre-existing traces in the DSN (`type protect`).
- `--no-import`: Runs routing and produces the `.ses` file without injecting it into EasyEDA Pro.
- `--save`: Automatically saves the PCB document after import.
- `--route-all-nets`: Forces track routing of all nets including ground planes (by default, nets declared in `plane_nets` like `GND` are excluded from track routing and reserved for copper pours).

### Modular Script Usage

#### 1. JRE Environment Verification / Installation:
```bash
uv run python .agents/skills/freerouting/jre_manager.py --check
```

#### 2. DSN Export Only:
```bash
uv run python .agents/skills/freerouting/dsn_exporter.py --out .agents/skills/freerouting/.cache/board.dsn
```

#### 3. Constraint Patching Only:
```bash
uv run python .agents/skills/freerouting/dsn_patcher.py --dsn input.dsn --config documents/pcb/constraints.json --out patched.dsn
```

#### 4. Routing Engine Execution Only:
```bash
uv run python .agents/skills/freerouting/router.py --dsn patched.dsn --ses output.ses --passes 10 --threads 1
```

#### 5. SES File Import Only:
```bash
uv run python .agents/skills/freerouting/ses_importer.py --ses output.ses
```

---

## 5. Constraint File Specification (`--config`)

The `dsn_patcher.py` engine expects a `net_classes` section structured as follows:

```json
{
  "net_classes": {
    "POWER_12V": {
      "nets": ["+12V", "+12V_FUSED", "+12V_PROT", "VBAT_OBD"],
      "track_width_mm": 0.8,
      "clearance_mm": 0.25,
      "via_drill_mm": 0.4,
      "via_diameter_mm": 0.8
    },
    "POWER_REGULATED": {
      "nets": ["+5V", "VBUS_5V", "3.3V", "3.3V_PRE"],
      "track_width_mm": 0.6,
      "clearance_mm": 0.20,
      "via_drill_mm": 0.4,
      "via_diameter_mm": 0.8
    },
    "DIFF_USB": {
      "nets": ["USB_D+", "USB_D-"],
      "track_width_mm": 0.30,
      "clearance_mm": 0.20
    },
    "DEFAULT": {
      "track_width_mm": 0.254,
      "clearance_mm": 0.20,
      "via_drill_mm": 0.3,
      "via_diameter_mm": 0.6
    }
  }
}
```

All PCB signals not explicitly listed in a specific class automatically inherit the constraints defined in the `DEFAULT` class.
