# Project Roadmap & Active Checklist (TODO)

This document constitutes the operational action plan for the **ESP32 OBD-II Scanner** project.
It is structured into **3 core fundamental parts** aligned with the hardware engineering lifecycle:
1. **PCB Design & Manufacturing Pipeline** (Virtual / CAD — Sequential execution order)
2. **Bring-up Protocol & Hardware Acceptance Testing** (Physical / Lab bench test upon factory delivery)
3. **Hardware Lifecycle Meta-Skill ("Hardware Spec-Kit")** (Methodology & R&D Framework)

---

## 🏁 Summary of Completed Hardware Milestones

- ✅ **Schematic Design & BOM**: 85 components validated, ERC = 0, bill of materials 100% optimized for JLCPCB Basic Parts ([`documents/schema/bom.json`](documents/schema/bom.json), [`documents/schema/semantics.json`](documents/schema/semantics.json)).
- ✅ **Automated PCB Placement (`pcb-placer`)**: 85 components placed without collision (70 physical + 15 test point pads), immediate decoupling < 2 mm, compact Buck loop, IPC-7351 courtyards validated ([`documents/pcb/placement.svg`](documents/pcb/placement.svg)).
- ✅ **Headless Auto-Routing & Planes (`pcb-synthesizer`)**: 100% of signals routed, USB/CAN differential pairs, continuous multi-layer ground planes, native EasyEDA Pro DRC = 0.
- ✅ **Declarative Silkscreen & Closed-Loop Feedback (`pcb-silkscreen`)**: 25 bottom-layer primitives injected, 0 out-of-bounds, 0 via drill collisions, 0 pad conflicts, 4 inspection renders generated ([`documents/pcb/silkscreen.json`](documents/pcb/silkscreen.json), [`documents/pcb/2d-bottom.png`](documents/pcb/2d-bottom.png)).
- ✅ **Parametric Enclosure 3D Modeling (`pcb-enclosure`)**: 3D shells and 2-screw M2 strain relief clamp generated in STEP/STL formats ([`documents/enclosure/`](documents/enclosure/)).

---

## PART 1: PCB Design & Manufacturing Pipeline (Virtual / CAD)

This section is organized **strictly in chronological execution order**, from raw PCB initialization to the final factory manufacturing package.

### Step 0: Upstream & Raw PCB Idempotent Bootstrap
- [ ] **[BLOCKING] Idempotent PCB Bootstrap:** Add an initialization stage at the beginning of `PcbSynthesizer.execute_closed_loop()` in `synthesizer_pipeline.py` that executes automatically via `EasyEDAClient`:
  1. Validate `ERC = 0` via `eda.sch_Drc.check(true, false, true)` and semantic compliance via `sync_semantics.py check`.
  2. Synchronize schematic to PCB via `sync_schematic_to_pcb(auto_confirm=True)`.
  3. Configure 4-layer copper stackup via `eda.pcb_Layer.setTheNumberOfCopperLayers(4)`.
  4. Create idempotent board outline on Layer 11 from `outline_polygon_mm`.
  5. Instantiate mechanical mounting holes `MH1` to `MH4` (M2 drill, `GND` net).

### Step 1: Data Modeling & Dynamic Manifest
- [ ] **[BLOCKING] Dynamic Manifest Builder (`manifest_builder.py`):** Extract synchronized components from EasyEDA Pro (`getState_BBox()`, centroids, pads) and cross-reference with `semantics.json` (functional roles, decoupling, critical loops) and `constraints.json` (`anchors`, keepouts) to synthesize `manifest.json` automatically, eliminating manual maintenance.
- [ ] **[IMPORTANT] Fabricator Profile (`rules_jlcpcb.json`) vs Project Constraints (`constraints.json`) Separation:** Move factory constants (DFM rules, tolerances, JLC2313 stackup) into `.agents/skills/pcb-dfm/config/rules_jlcpcb.json`, keeping `constraints.json` dedicated to board-specific constraints (anchors, outline dimensions, net classes).

### Step 2: Placement under EMC Constraints & HF Decoupling
- [x] **Initial Placement Validated:** 85 components placed without overlap (70 physical + 15 test point pads), immediate decoupling < 2 mm, and compact Buck switching loop ([`documents/pcb/placement.svg`](documents/pcb/placement.svg)).
- [ ] **[IMPORTANT] EMC Alignment for Simulated Annealing (`simulated_annealing.py`) & Evaluator (`score.py`):** Integrate incremental cost terms for `net_compact` (`PH_BUCK`) and `cluster_cohesion` (< 10 mm), enforce `hard_proximities` during legalization (`legalize()`), and activate 90° magnetic field angular attenuation (`magnetic_field_coupling`).
- [ ] **[IMPORTANT] Offline Decoupling for Synthesis Loop (`Extract Once -> Loop Offline -> Materialize Once`):** Allow full chaining of placement (`simulated_annealing.py`), routing (`FreeRoutingRunner`), metrology (`dsn_metrics.py`), stitching (`pcb-stitcher`), and silkscreen in pure Python/Java without blocking intermediate HTTP calls, materializing the converged layout into EasyEDA Pro in a single final transaction.

### Step 3: Differential Routing & Post-Routing EMC Metrology
- [x] **Certified 4-Layer Routing:** 100% of active signals routed, USB/CAN differential pairs, 0 crossings, DRC = 0.
- [ ] **[BLOCKING] EMC Metrological Stop Condition:** Upgrade stop criteria in `synthesizer_pipeline.py` to require `report.is_valid`, ensuring any exceeded critical loop area (`PC_BUCK_HOT_LOOP`), differential skew (`USB_D+`/`USB_D-`, `CANH`/`CANL`), or excessive signal via count triggers adaptive constraint tightening and feedback re-placement.

### Step 4: Ground Plane Continuity & Shielding Stitching
- [x] **Ground Planes & Stitching Vias:** Multi-layer continuous GND ground planes and board perimeter stitching via `pcb-stitcher` (DRC = 0).

### Step 5: Functional Silkscreen & 2D/3D Visual Verification
- [x] **Closed-Loop Silkscreen Validated:** `silkscreen_feedback_loop.py` engine and `export_pcb_images.py` fully operational (0 out-of-bounds, 0 via drill collisions, 0 pad conflicts across 25 bottom-layer primitives, automated export of `2d-top.png`, `2d-bottom.png`, `3d.png`, `pcb.png`).

### Step 6: DFM Audit & Physical Board Finish (JLCPCB)
- [ ] **Fine-Pitch Solder Mask Dams (*Soldermask Bridge* >= 0.10 mm):** Reduce solder mask expansion from 0.05 mm to 0.025 mm (1 mil) on dense ICs (USB-C connector `J2` and ESP32-S3 `U1`) to preserve physical solder mask dams >= 0.10 mm (JLCPCB green mask standard capability) and eliminate gang-mask shorting risks.
- [ ] **Via Protection & Offsetting (*Via to Pad / Tenting*):** Offset stitching and fanout vias that are in direct contact with SMD pads by adding dog-bone necks >= 0.15–0.20 mm, and enforce 100% via tenting on Top and Bottom layers to eliminate 50 solder wicking alerts.
- [ ] **Silkscreen Stroke Width:** Increase text and border stroke widths to 0.18–0.20 mm (notably in [`documents/pcb/silkscreen.json`](documents/pcb/silkscreen.json) and EasyEDA) to guarantee crisp silkscreen contrast against the 0.15 mm DFM alert threshold.

### Step 7: Turnkey Production Packaging & 3D Assembly
- [ ] **[BLOCKING] Automated Manufacturing Deliverables Chaining:** Automatically chain at the end of `synthesizer_pipeline.py` (once `DRC == 0`):
  1. Export factory Gerber, Drill, CPL, and SMT BOM via `export_fabrication.py` into `documents/production/`.
  2. Generate inspection image pack (`2d-top.png`, `2d-bottom.png`, `3d.png`, `pcb.png`) via `export_pcb_images.py`.
  3. Export native project archive `documents/easyeda/OBD2.epro2` via `eda.sys_FileManager.getProjectFile()`.
  4. Export populated PCBA 3D STEP solid via `eda.pcb_ManufactureData.get3DFile()`.
- [ ] **[IMPORTANT] 3D Interference Check PCBA + Enclosure:** Import the populated PCBA 3D STEP into `enclosure_generator.py` using `bd.import_step()`, compute boolean collision volume with the enclosure shells (`collision_volume == 0`), and export `documents/enclosure/enclosure_pcba_full.step`.
- [ ] **[MINOR] Turnkey Single CLI Command (`--turnkey`):** Drive the entire sequence (Steps 0 to 7) via a single unified command-line entry point.

---

## PART 2: Bring-up Protocol & Hardware Acceptance Testing (Physical / Lab Bench)

This section details the step-by-step procedure for safely powering up and validating prototype boards upon delivery from JLCPCB.

### 2.1 Visual & Mechanical Inspection (Unpowered)
- [ ] **Optical Microscope / Magnifier Inspection:**
  - Verify absence of solder bridges, specifically on `U1` (ESP32-S3), `U4`, `U5`, `U2`, and `U3`.
  - Check alignment and polarity of critical components: diodes (`D1` to `D6`), polarized capacitors, and pin 1 index markers on all ICs.
  - Verify crisp bottom-layer silkscreen legibility and integrity of the 4 mechanical M2 mounting holes (`MH1` to `MH4`).

### 2.2 Isolation & Short-Circuit Screening (Unpowered)
- [ ] **Resistance Measurement to GND Plane:**
  - `+12V` rail (pin 1 of `J1` or `H3`) to `GND`: expected resistance > 10 kΩ (capacitive charging).
  - `+5V` rail (`TP5` / Buck `U4` output / `VBUS`) to `GND`: expected resistance > 1 kΩ.
  - `3.3V` rail (`TP6` / LDO `U5` output / ESP32 VDD) to `GND`: expected resistance > 500 Ω.
  - Communication bus lines: verify high-impedance isolation between `CANH`, `CANL`, `K-LINE`, and `GND`.

### 2.3 USB Power Bring-up Only (VBUS 5V)
- [ ] **Power-up via USB-C (`J2`) with Current Monitoring:**
  - Power through current-limited USB supply / USB power meter capped at 250 mA.
  - Verify quiescent current: expected between 30 mA and 70 mA (blank ESP32 / ROM bootloader).
  - Measure `3.3V` rail on `TP6`: expected stable between 3.25V and 3.35V.
  - Measure `VBAT_SENSE` (`TP9`) under USB power alone: verify residual voltage (~0.35–0.45V due to 5V backfeed through L1 and U4 high-side body diode into `+12V_PROT`; Q1 blocks backflow to J1/H3) — calibrate firmware battery presence threshold to Vbat > 6.0V (VBAT_SENSE > 0.64V) to immunize against false battery detection.
  - *Note:* Under USB power alone, the +5V rail is at ~4.35V (D4 Schottky drop) < VCC min 4.5V for TJA1051T; test transceivers exclusively under 12V supply.
  - Validate USB enumeration on host PC (native ESP32-S3 USB JTAG/serial controller).
  - Flash minimal test firmware ("blinky" on `LED1` and UART text output).

### 2.4 Laboratory 12V Bench Power Bring-up (Bench Power H3)
- [ ] **Safe 12V Power-up:**
  - Set lab power supply to 12.0V with strict overcurrent protection (OCP) at 100 mA.
  - Connect to header `H3` (pin 1 = `+12V`, pin 2 = `GND`).
  - Measure overall input current: expected between 20 mA and 45 mA idle.
  - Validate Buck `+5V` rail on `TP5`: expected stable between 4.90V and 5.15V.
  - Validate LDO `3.3V` rail on `TP6`: 3.30V ± 2%.
  - Measure ADC divider `VBAT_SENSE` on `TP9`: expected ~1.29V for VIN = 12.0V (nominal 1/9.33 ratio).
  - Check ripple voltage on 5V and 3.3V rails with an oscilloscope (< 50 mV peak-to-peak).

### 2.5 CAN & K-Line Transceiver Acceptance Testing
- [ ] **CAN Transceiver (`U2` TJA1051T) & Termination Test:**
  - Jumper `JP1` closed (SIMU mode): verify resistance between `CANH` and `CANL` on `J1` measures 120 Ω.
  - Jumper `JP1` open (SCANNER mode): verify resistance > 10 kΩ.
  - Transmit CAN test frames (TWAI loopback / passive listen): monitor `CANH` (~3.5V dominant) and `CANL` (~1.5V dominant) on oscilloscope.
- [ ] **K-Line Transceiver (`U3` L9637D) & Pull-up Test:**
  - Jumper `JP2` closed (SCANNER mode): verify 500 Ω pull-up to +12V (idle high ~12V).
  - Jumper `JP2` open (SIMU mode): verify high-impedance passive input (floating bus / no pull-up).
  - UART Echo test: inject 0x55 test pattern (Fast-Init) and verify jitter-free decoding on RX.

### 2.6 RF Testing & Transient Immunity
- [ ] **Wi-Fi / BLE RF Validation:**
  - Enable maximum RF output power (802.11b/g/n) and monitor `U5` LDO stability (verify zero brownout during ~250–350 mA peak RF bursts).

---

## PART 3: Hardware Lifecycle Meta-Skill ("Hardware Spec-Kit") (Methodology R&D)

This section capitalizes on the tools and algorithms developed in this project to formulate a modular, reusable, specification-driven hardware engineering framework (*Spec-Driven Hardware Engineering*).

### 3.1 AI-Driven Hardware Engineering Principles
- **GitHub Spec-Kit Analogy:** Establish an end-to-end tooled methodological framework where every design step is strictly constrained by formal machine-readable contracts (`spec.json`, `semantics.json`, `constraints.json`, `manifest.json`), preventing blind modifications.
- **Contract-First Approach:** Strict JSON schemas at every milestone. No phase gate transition is permitted until physical and normative acceptance criteria are certified.

### 3.2 Hardware Finite State Machine (Phase Gates 0 to 7)
- [ ] **Formalization of the 8 Hardware Lifecycle Phase Gates:**
  1. *Gate 0 (Requirements & Architecture):* Formal functional specification (`spec.json`: power rails, topologies, buses, interfaces, dimensional constraints, budget).
  2. *Gate 1 (Semantics & BOM):* Connectivity netlist, component mathematical modeling (`ratio-solver`, `buck-compensation`), JLCPCB Basic Parts optimization (`stingy-schematics`), `ERC = 0` certification.
  3. *Gate 2 (Mechanics & Floorplan):* Anchor definitions, boundary connectors, RF keepouts, and parametric 3D enclosure integration (`pcb-enclosure`).
  4. *Gate 3 (Constraint-Driven Placement):* Stochastic simulated annealing placement under EMC/thermal constraints (`pcb-placer`, HF decoupling < 2 mm, compact switching loops, SVG generation).
  5. *Gate 4 (Routing & Ground Continuity):* Specctra differential routing (`freerouting`), continuous ground planes, perimeter stitching and island bridging (`pcb-stitcher`), `DRC = 0` certification.
  6. *Gate 5 (Silkscreen & Functional Legend):* Declarative silkscreen labeling, jumper and pinout legends, collision-free closed-loop placement (`pcb-silkscreen`).
  7. *Gate 6 (DFM/SMT Quality Assurance):* Automated manufacturability audit (`pcb-dfm`, 0 Danger solder mask / via-to-pad alerts, BOM/CPL consistency).
  8. *Gate 7 (Release & Manufacturing):* Automated export of factory manufacturing package (`export_fabrication`, 4-layer Gerbers, CPL centroids, SMT BOM, 2D/3D renders).

### 3.3 Modular Skill Orchestration
- [ ] **Pure Algorithmic Decoupling (Rule 1 AGENTS.md):**
  - Strict preservation of zero hardcoded components in `.agents/skills/*`.
  - Standardized CLI interfaces (`--config`, `--constraints`, `--placement`, `--output`).
  - Encapsulation of software interactions inside independent EDA connectors (EasyEDA Pro, future KiCad backend).

---

## 📌 Software & Embedded Firmware Repository

Application firmware development is hosted in a dedicated Git repository (`obd2-esp32-firmware`).
Complete hardware interfaces, register maps, and communication protocols are documented in [`documents/software.md`](documents/software.md).
