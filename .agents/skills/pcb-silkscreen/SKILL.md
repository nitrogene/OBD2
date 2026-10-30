---
name: pcb-silkscreen
description: "Declarative and agnostic generation and injection engine for auxiliary silkscreen markings (functional labeling, pin markings, jumper instructions, title block) for EasyEDA Pro."
---

# Skill: PCB Silkscreen for EasyEDA Pro

## 1. Overview & Architecture

The `pcb-silkscreen` skill is an algorithmic engine for automated functional and documentation silkscreen generation in EasyEDA Pro.
It complements native component designator placement (`R1`, `C1`, `U1`, etc.) by parametrically and repeatably placing descriptive markings on the **Top Silkscreen** (`TopSilkLayer`, layer 3) and **Bottom Silkscreen** (`BottomSilkLayer`, layer 4) layers.

### Inputs and Data Flow:
```text
[documents/pcb/silkscreen.json] ──┐
[documents/pcb/silkscreen.schema.json] ──┼──► apply_silkscreen.py ──► EasyEDA Pro API (http://localhost:49620)
[EasyEDA Pro PCB (Pads & BBox)] ──┘             │
                                                ▼
                                    .cache/silkscreen_state.json (Idempotence)
```

---

## 2. Project Rules Compliance (AGENTS.md)

- **Rule 1 (Pure Agnosticism & Zero Hardcoded Components):**
  - Python code under `.agents/skills/pcb-silkscreen/` contains no hardcoded designators (`J1`, `H1`), XY coordinates, or labels.
  - All content and targets originate strictly from the declarative configuration file `--config documents/pcb/silkscreen.json`.
  - Exclusive execution via `uv run` (`uv run python .agents/skills/pcb-silkscreen/apply_silkscreen.py`).
- **Rule 2 (Safety & Idempotence):**
  - **Guaranteed Idempotence:** The engine first purges all primitives created in previous runs using its tracking registry (`.cache/silkscreen_state.json`), preventing ghost text or overlapping artifacts when modifying `silkscreen.json`.
  - **Non-destructive:** Native component designators are never modified.
- **Rule 6 (Typography):**
  - No LaTeX formatting in component labels or silkscreen text.

---

## 3. Supported Annotation Types

1. **`pin_labels` (Pin Markings):**
   - Automatically anchored adjacent to each target component pad (`Pad`) (`J1`, `H1`, etc.).
   - Accounts for component orientation and rotation.
2. **`component_legends` (Component Legends):**
   - Centered automatically relative to the component courtyard (`above`, `below`, `left`, `right`).
   - Ideal for jumper instructions (`JP1`, `JP2`) or LED status labels (`LED1`).
3. **`title_blocks` (Title Blocks and Documentation Frames):**
   - Anchored relative to board corners (`bottom_right`, `top_left`, etc.) dynamically computed from the board outline (`BoardOutline`).

---

## 4. Skill Components & Test Suite

| File | Role | Description |
| :--- | :--- | :--- |
| `scripts/apply_silkscreen.py` | Injection actuator | CLI entry point to purge and inject silkscreen annotations into EasyEDA Pro. |
| `scripts/silkscreen_resolver.py` | Geometric resolver | Calculates bounding boxes, orientations, mirroring, and text placement coordinates. |
| `scripts/silkscreen_feedback_loop.py` | Closed loop & Audit | Checks for clearance against pads and vias, optimizing placement coordinates. |
| `tests/test_silkscreen.py` | Unit test suite | Validates projection algorithms and silkscreen collision detection. |

```bash
# Run the unit test suite
uv run pytest .agents/skills/pcb-silkscreen/tests/test_silkscreen.py
```
