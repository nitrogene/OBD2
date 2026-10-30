---
name: stingy-schematics
description: SMT optimization engine and schematic semantic guardian. Analyzes the BOM and documents/schema/semantics.json to propose substituting Extended parts with JLCPCB Basic Parts (3.00 USD setup savings per component) without compromising quality or safety, with automated review report generation.
---

# Skill: stingy-schematics

Algorithmic and cost-optimization engine for PCBA bill of materials targeting assembly at **JLCPCB**.

---

## 1. Motivation & Purpose

At JLCPCB, SMD components are categorized into two tiers:
* **Basic Parts:** Permanently loaded onto Pick & Place machine feeder reels. **Tooling / setup fee = 0.00 USD**.
* **Extended Parts:** Require manual reel loading and feeder configuration. **Loading fee = 3.00 USD per unique line item**.

On a small prototype batch of 5 boards, replacing 5 to 10 Extended parts with Basic Parts saves **15.00 USD to 30.00 USD net** on the total assembly quote, without any change in circuit operation or reliability.

---

## 2. Non-Regression Principles & Golden Rules

`stingy-schematics` strictly forbids degrading signal integrity or hardware safety margins:

1. **Design Intent Contract (`documents/schema/semantics.json`):**
   The engine never operates blindly. It enforces the semantic contract defining each component's functional role and permitted substitution policy (`locked`, `direct_1to1`, `ratio_pair_recalc`, `topology_expansion_ok`).
2. **Inviolable Physical Guardrails:**
   * **Capacitors:** `V_rated,new >= V_rated,old`. Dielectric rating `>=` (`C0G/NP0 > X7R > X5R`). Absolute exclusion of unstable Y5V/Z5U dielectrics.
   * **Resistors:** Tolerance `Tol_new <= Tol_old` (a 1% resistor stays `<= 1%`). Power rating `P_new >= P_old`.
   * **Diodes:** `VR >= VR,old`, `IF >= IF,old`. Strict retention of junction technology (a Schottky diode must remain a Schottky diode).
   * **Protected Critical Nodes:** Strict lock on standardized lines (e.g., 5.1 kΩ 1% on USB-C CC1/CC2, 1206 1k 250mW pull-up on K-Line).

---

## 3. Architecture & Integrated Tools

The skill provides two agnostic tools in compliance with Rule 1 (agents.md):

```
.agents/skills/stingy-schematics/
├── SKILL.md
└── scripts/
    ├── jlcpcb_api.py       # Live HTTP client querying the JLCPCB SMT catalog
    ├── sync_semantics.py   # Integrity guardian between documents/schema/bom.json and documents/schema/semantics.json
    └── stingy.py           # Core optimization engine and reviewXXX.md generator
```

### A. Semantic Guardian (`sync_semantics.py`)
Verifies full alignment between the bill of materials and the intent contract:
```powershell
# Consistency check (semantic DRC, default paths)
uv run python .agents/skills/stingy-schematics/scripts/sync_semantics.py check

# Assisted scaffolding for newly added components
uv run python .agents/skills/stingy-schematics/scripts/sync_semantics.py scaffold
```

### B. SMT Optimization Engine (`stingy.py`)
Scans eligible Extended components, queries live JLCPCB stock, solves ratio recalculations via `ratio-solver`, and generates a formal review report in `review/`:
```powershell
uv run python .agents/skills/stingy-schematics/scripts/stingy.py
```

---

## 4. Integration into Design Workflow

1. **Run Optimizer:** `stingy.py` generates the next sequential `review/reviewXXX.md` file.
2. **Formal Validation:** The report is validated using the `review` skill:
   ```powershell
   uv run python .agents/skills/review/scripts/review_tool.py validate review/reviewXXX.md
   ```
3. **Arbitrage with Engineer:** Interactive review of quantified substitution proposals.
4. **Triage to TODO:** Approved modifications are triaged into `todo.md`, followed by deletion of the processed `reviewXXX.md` file.
