# Technical Knowledge Base & EasyEDA Pro Pitfalls Guide

This document serves as the **technical knowledge base** and **engineering lessons learned journal** for the ESP32 OBD-II Scanner project. It catalogs nuances, workarounds, and undocumented behaviors of EasyEDA Pro, as well as the protocol for capturing future engineering findings.

---

## 1. Technical Knowledge Management Protocol for Future Findings

To keep the repository clean, modular, and directly actionable for AI agents, any newly discovered anomaly, tip, or technical insight must follow this lifecycle:

```
[New Finding / Erratum Encountered]
                    │
                    ▼
  1. Record in learnings.md (Section 3: Journal)
     • Date, technical context, and symptom description
     • Identified root cause
     • Verified solution or workaround
                    │
                    ▼
  2. Qualification & Routing:
     ├── If it is a Design / Safety Rule:
     │   └── Repatriate the mandatory directive into agents.md
     ├── If it is a Reusable Algorithm / Calculation:
     │   └── Encapsulate it in a dedicated Skill (.agents/skills/<name>/)
     └── If it is an EasyEDA Pro API Pitfall:
         └── Update the corresponding cheat sheet in Section 2
                    │
                    ▼
  3. Periodic Pruning:
     As soon as knowledge is codified into a Skill or rule, summarize the journal
     to prevent unnecessary verbosity.
```

---

## 2. Quick-Reference Cheat Sheets: EasyEDA Pro API Pitfalls & Golden Rules

### A. Schematic (`eda.sch_*`)

| Pitfall / Behavior | Cause & Risk | Proven Rule & Solution |
| :--- | :--- | :--- |
| **Network flag (`NetFlag`) without physical wire** | Placing a NetFlag directly onto a pin pad without a physical wire segment causes EasyEDA to treat the pin as **floating**, generating an orphan net in the PCB netlist (`$1N...`). | **Always insert a physical wire (`sch_PrimitiveWire.create([x1, y1, x2, y2])`)** between the pin pad and the NetFlag. |
| **"Multiple net names" warning on wire** | Assigning an explicit net name to a wire segment already connected to a NetFlag or NetPort triggers `[Warn] : Wire has multiple net names`. | **Omit the net name parameter** during `sch_PrimitiveWire.create(line)` if the wire connects to a NetPort/NetFlag: net propagation is automatic. |
| **Empty stubs in `createNetLabel`** | `eda.sch_PrimitiveAttribute.createNetLabel()` is an unimplemented empty stub in the current runtime. | **Use NetPorts instead:** `eda.sch_PrimitiveComponent.createNetPort(...)`, which immediately binds any overlapping wire. |
| **Component instantiation in scripts** | Passing a lightweight object `{ libraryUuid, uuid }` stalls execution with a 30-second timeout. | **Resolve the full Device object first** via `eda.lib_Device.search(...)` before calling `sch_PrimitiveComponent.create(devs[0], ...)`. |
| **Schematic Y-axis orientation** | On a schematic sheet (`documentType: 1`), **the Y-axis points UPWARD** (inverted compared to the PCB canvas coordinate system). | Always verify coordinates: `y = 0` is at the bottom of the A4 page, `y = 825` is at the top. |
| **Multi-sheet enumeration (`sch_PrimitiveComponent.getAll`)** | `eda.sch_PrimitiveComponent.getAll(undefined, true)` may omit components if their corresponding sheets have not been opened in the editor (not loaded in memory). | **Iterate through sheets via `eda.dmt_Schematic.getAllSchematicPagesInfo()`**, activate each tab with `eda.dmt_EditorControl.openDocument(page.uuid)`, then call `getAll()` sheet by sheet. |
| **Multiline text annotations (`sch_PrimitiveText.create`)** | Multi-line text strings can be truncated or require separate primitive calls in some EDA software. | `eda.sch_PrimitiveText.create` natively supports `\n` newline characters. Pass `(x, y, content, rotation, textColor, fontName, fontSize, bold)` to inject formatted blocks in a single operation. |
| **Automated project export (`sys_FileManager.getProjectFile`)** | `eda.sch_ManufactureData.getPngFile` is unavailable in some EasyEDA Pro web/desktop runtimes. | Use `eda.sys_FileManager.getProjectFile('OBD2', undefined, 'epro2')` which returns a complete `File` object, convertible to `ArrayBuffer` then Base64 for direct binary saving on the host filesystem. |

### B. PCB Layout & Primitives (`eda.pcb_*`)

| Pitfall / Behavior | Cause & Risk | Proven Rule & Solution |
| :--- | :--- | :--- |
| **Signature of `pcb_PrimitiveVia.create` (CRITICAL)** | The API signature is `(net, x, y, holeDiameter, diameter)`. Inverting drill diameter and outer diameter creates an invalid via and blocks DRC. | **The drill diameter always precedes the outer diameter.** JLCPCB standard: `hole = 12 mil` (~0.3 mm), `diameter = 24 mil` (~0.6 mm). |
| **Signature of `pcb_PrimitiveLine.create` (CRITICAL)** | The API signature is `(net, layer, startX, startY, endX, endY, width)`. Placing width before coordinates offsets all arguments. | **Coordinates always precede track width.** |
| **Runtime units** | PCB API coordinates are expressed in **mils** (1 mil = 0.0254 mm, 1 mm = 39.3701 mil). | Always explicitly convert using `mm_to_mil()` and `mil_to_mm()`. |
| **Layer identifiers (Layers)** | Layers are referenced by integers: `1` = Top Layer, `2` = Bottom Layer, `11` = Board Outline, `12` = Multi-layer. | Use integer constants or the `EPCB_LayerId` enumeration. |
| **Moving / relocating a via** | Modifying existing via coordinates in place fails to trigger recalculation of copper clearance regions during polygon pouring. | **Delete the old via** (`delete([oldId])`), **create the new via**, then call `rebuildCopperRegion()`. |
| **Differential pair chamfering** | 90° bends cause impedance discontinuities and EMI radiation (critical for USB 480 Mbps and CAN 500 kbps). | **Always use 45° mitered corners** (Δx = Δy = 25 mil for a 10 mil track). |
| **Pad geometry extraction (`Pad`)** | Methods `getState_Width()` / `getState_Height()` do not exist on `pcb_PrimitivePad`. | **Use `p.getState_Pad()`** which returns `['RECT', width_mil, height_mil, radius]` and `p.getState_Hole()` which returns `['ROUND', drill_mil]` for through-hole pads. |

### C. Copper Pours, DRC & WebGL Cache

| Pitfall / Behavior | Cause & Risk | Proven Rule & Solution |
| :--- | :--- | :--- |
| **Persistence of old track labels (WebGL Cache)** | After updating a net via the API, the text displayed on the WebGL canvas retains the old name as long as the tab remains open. | **Close and reopen the PCB document**: `save()`, `closeDocument(tabId)`, then `openDocument(pcbUuid)`. |
| **Copper micro-slivers between SMD pads** | Ground plane pouring can introduce parasitic copper slivers between tightly spaced pads (0603/0805). | Insert a local `NO_POURS` keepout region (`ruleType: [7]`) between pads via `pcb_PrimitiveRegion.create()`. |
| **Multi-layer RF antenna keepout** | The ESP32-S3 PCB antenna requires a total copper void under and around the 2.4 GHz meander trace across all layers. | Create a region on layer `12` (`MULTI`) with `ruleType: [5, 6, 7]` (`NO_WIRES`, `NO_FILLS`, `NO_POURS`). |
| **Ground plane continuity verification** | After calling `rebuildCopperRegion()`, verify that the plane has not fragmented into isolated islands. | Check via `pcb_PrimitivePoured.getAll()` that `pouredCount == 2` (1 Top region, 1 Bottom region). |

---

## 3. Historical Engineering Journal & Lessons Learned

* **[2026-09-03 / 2026-09-06] Primitives & Basic Routing:**
  - Identified universal unit `mil` and hierarchical linkage `pad.primitiveId.startsWith(comp.primitiveId)`.
  - Established verbose DRC diagnosis (`eda.pcb_Drc.check(true, false, true)`).
* **[2026-09-07 / 2026-09-11] Critical Topologies & EMC:**
  - High-frequency transceiver decoupling topology (via -> capacitor pad -> IC pin).
  - Fine-pitch USB-C pin fanout (0.8 mm) and 45° differential routing.
  - Thermal dissipation via matrix beneath central exposed pad 41 of the ESP32-S3.
* **[2026-09-19] Regulation Modeling & Stability:**
  - Validated TPS54331 Type II compensation network triplet (`R11 = 10 kΩ`, `C9 = 3.3 nF`, `C13 = 220 pF`) ensuring phase margin between 61.7° and 68.8°.
* **[2026-09-20] Review Triage & Critical Thinking:**
  - Highlighted hardware variant confusions in peer reviews (ADC pinout discrepancies between classic ESP32 and ESP32-S3).
  - Identified requirement for strong 1 kΩ pull-up to 12V on the K-Line bus (ISO 9141-2).
  - Created the constraint-driven auto-placement engine `pcb-placer`.
* **[2026-09-26] Schematic Semantic Decoupling & Review Skill:**
  - Refuted erroneous 5V VCC recommendation for L9637D (L9637D features an internal active pull-up on RX to VCC, which would destroy the non-5V-tolerant ESP32-S3 under 5V).
  - Detected missing gate divider on 2N7002 (Vgs max ±20V exceeded during 29.2V Load Dump) and ground short / silent mode misconfiguration on TJA1051T.
  - Created standalone skill [`.agents/skills/review/`](.agents/skills/review/SKILL.md) to standardize review auditing, validation, and issue extraction into [`todo.md`](todo.md).
  - **Created semantic repository [`documents/schema/semantics.json`](documents/schema/semantics.json):** Proprietary CAD files (EasyEDA, KiCad) store geometry and net connections, but lack engineering intent (functional role, critical tolerance, substitution policy). Creating this repository fills that gap and forms the foundation for cost optimization (`stingy-schematics`), automated auditing, and auto-placement.
* **[2026-09-27] Critical Audit, Schematic Pitfalls & Normative Compliance:**
  - **LDO Topology & Ferrite Bead (LDL1117):** The output regulation and loop stability capacitor Cout >= 4.7 µF (`C6` = 10 µF) must be directly connected across output pin Vout (`3.3V_PRE`) upstream of ferrite bead `FB1`. Inserting an inductive bead between the LDO and its primary output capacitor shifts internal feedback phase and creates severe risk of high-frequency oscillation.
  - **EasyEDA Graphic Primitive Pitfall (`LINE`):** A line segment accidentally crossing the body of a passive component (e.g., `C7`) shorts its two pads in the netlist without visual warnings, causing a hard short between power and ground. Essential to audit primitive continuity and geometric integrity.
  - **Explicit TPS54331 Buck Power Net:** Formally verified connection of NetPort `+12V_PROT` to the input decoupling stage (`C14`, `C7`) and pin 2 (`VIN`).
  - **Formal Standards Framework:** Integrated Design Compliance Assessment matrix covering 8 targeted automotive standards (SAE J1962, ISO 11898-2, ISO 9141-2, ISO 14230, ISO 15765-4, ISO 7637-2, ISO 16750-2, ISO 10605).
* **[2026-09-28] TODO Methodology & Component Designator Assignment:**
  - **Proscription of Anticipated Designators in TODO:** Prematurely fixing an identifier (e.g., `R18`, `R21`, `C18`, `TP12`) in a roadmap task before physical implementation is a major source of inconsistencies. When task execution order changes or priorities flip (e.g., adding UVLO resistors `R19`/`R20` before `IO0` pull-up), gaps or duplicate designators occur.
  - **Methodological Rule:** A task in `todo.md` or a review finding must define components purely functionally (role, value, tolerance, package, constraints, Basic Part catalog reference). Official designators are assigned only upon physical schematic integration, taking the next free sequential number in the Bill of Materials (BOM).
* **[2026-09-28] K-Line Transceiver L9637D & Buck TVS Protection:**
  - **Review Pitfall on L-Line Input `LI` (L9637D pin 8):** `LI` is not a 3.3V logic input but a high-voltage analog input whose switching threshold is proportional to supply voltage (Vth = 0.5 × VS ≈ 6V). Tying it to 3.3V would keep it permanently in the active/dominant state (3.3V < 0.45 × VS) with reverse current leakage through its internal pull-up to VS. Tying it directly to adjacent pin 7 (`VS` / `+12V_PROT`) locks the comparator in the idle state, guarantees zero current draw (0 µA), and immunizes the stage against EMC noise without routing across the board.
  - **Buck Protection Margin Optimization (TVS `D1`):** Replaced `SMBJ18A` (Vcl = 29.2V) with `SMBJ16A` (Vcl = 26.0V): secures a robust **4.0 V** safety margin (instead of 0.8 V) below the 30.0 V destruction ceiling of the TPS54331, while remaining transparent during standard alternator charging (VRWM = 16.0V > 14.8V).
* **[2026-09-29] Battery ADC Sensing & Clamp Diode Leakage Current Pitfall:**
  - **Thermal Sensitivity of High-Impedance ADC Dividers:** On a voltage divider `R12 = 100 kΩ` / `R13 = 12 kΩ` with ratio `k = R13 / (R12 + R13) ≈ 1 / 9.33`, any reverse leakage current Ir injected by a clamp diode connected to the 3.3V rail produces an error voltage ΔVsense = Ir × (R12 // R13). When scaled back to estimated battery voltage in firmware, the error becomes independent of `R13`:
    $$\Delta V_{BAT} = \frac{\Delta V_{SENSE}}{k} = I_R \times R_{12} = I_R \times 100\,\text{k}\Omega$$
  - **Schottky Diode Pitfall (`BAT54WS`):** At room temperature (25°C), Schottky leakage is low (~0.2 µA, ~20 mV error). But inside an automotive cabin exposed to sunlight (70°C to 85°C), Ir climbs exponentially to 5 µA – 10 µA, resulting in a dramatic overestimation of **+0.5 V to +1.0 V** on measured battery voltage, corrupting charge/discharge state diagnosis (a full battery at 12.6V vs depleted battery at 11.9V is separated by only 0.7V).
  - **Detecting Peer Review Confusions (`BAV99` vs `BAV199`):** Review M4 recommended either `BAV199` or `BAV99` claiming "< 5 nA hot leakage". Rigorous datasheet inspection reveals that `BAV99` is a standard switching diode whose leakage reaches 30 µA at 150°C (~1 µA at 85°C, yielding 100 mV residual error). Only **`BAV199`** is a true ultra-low-leakage planar diode (typical **3 pA** at 25°C, < 100 pA at 85°C, guaranteed < 5 nA at 75V), keeping voltage estimation error to ΔVbat < 0.01 mV (< 0.001 LSB of ADC).
  - **Rail-to-Rail SOT-23 Topology:** Adopting the dual-diode SOT-23 package, node `VBAT_SENSE` connects to the midpoint (pin 3), pin 1 to ground `GND` clamps negative inductive ringing below –0.65 V, and pin 2 to `3.3V` clamps transients above 3.95 V.
  - **CAN Termination Thermal Sizing under Vehicle Fault Conditions:** In normal vehicle operation, jumper `JP1` remains open. However, on a testbench or if inadvertently shunted on a vehicle, a dead short from a bus line to battery (+12V to +14.4V) produces a peak dissipation of P = V² / R ≈ 1.2 W to 1.7 W. While an 0805 resistor is limited to 125 mW, switching to a 1206 package (*Basic Part* `C17909`, 250 mW) doubles continuous power rating, provides a larger thermal contact area (3.2 × 1.6 mm) to conduct heat into ground planes, and reinforces surge thermal capacity.
  - **Schematic / Documentation Synchronization:** The absolute source of truth remains the CAD schematic (`documents/easyeda/OBD2.epro2`). Changes to the bill of materials (`documents/schema/bom.json`), semantics (`documents/schema/semantics.json`), and hardware architecture (`documents/hardware.md`) must only be applied after physical schematic validation.
* **[2026-09-30] Golden Rule of Documentation Sequencing (Post-Resolution Exclusive):**
  - **Strict Prohibition of Anticipated Updates:** Updating documentation files (`documents/schema/bom.json`, `documents/schema/semantics.json`, `documents/hardware.md`, `documents/pcb/constraints.json`) and checking off tasks in `todo.md` (`- [x]`) are strictly forbidden until the change has been physically implemented and validated by the user.
  - **Mandatory Workflow:**
    1. Agent analyzes the requirement, details the engineering solution, and provides step-by-step instructions (components, designators, values, footprints, nets, coordinates).
    2. User completes the operation in EasyEDA Pro and confirms validation.
    3. Agent *then and only then* updates documentation, syncs BOM / semantics, and checks off the task in `todo.md`.
* **[2026-10-02] Review LCSC Code Pitfall & Rigorous UVLO Divider Modeling (TI TPS54331):**
  - **Historical Review Erratum (review002):** A peer review proposal must never be accepted blindly (Rule 5). The review proposed `C17596` (510 kΩ) and `C17604` (91 kΩ) as 0805 Basic Parts. Verification via JLCPCB catalog API revealed that `C17596` is a 28.7 Ω resistor and `C17604` is a 2 kΩ resistor! The real codes for 510 kΩ (`C17733`) and 91 kΩ (`C17866`) are Extended Parts ($6.00 SMT fee).
  - **Exact UVLO Hysteresis Modeling (TI TPS54331 §7.3.4):** The `EN` pin sources an internal current: 1 µA before turn-on, plus 3 µA of hysteresis once active (4 µA total). Voltage hysteresis depends exclusively on the high-side resistor `R1`: `ΔVHYS = 3 µA × R1`.
  - **100% Basic Parts Resolution:** To eliminate tooling fees while preserving optimal 12V battery behavior, the pair `R19 = 470 kΩ` 0805 (`C17709`, Basic Part) and `R20 = 68 kΩ` 0805 (`C17801`, Basic Part) was validated. It sets thresholds of `VSTART = 9.42 V` and `VSTOP = 8.01 V` with a generous hysteresis of `1.41 V`, completely immunizing the converter against brownout chattering during ESP32 Wi-Fi current bursts (~500 mA). Also reassigned `R18` to `C4410` (1206 Basic Part shared with `R16`).
* **[2026-10-02] Markdown Typography & Component Notation:**
  - **Formal Refusal of Inline LaTeX for Components and Simple Quantities:** Using inline LaTeX (e.g., `J1`, `JP1`, `R16`, `D4` wrapped in dollar signs) degrades raw readability in IDEs, terminals, and standard Markdown viewers.
  - **Stylistic Rule:** Components, connectors, jumpers, pins, nets, and standard values must be referenced using plain text with inline code formatting (backticks), e.g., `J1`, `J2`, `JP1`, `JP2`, `R16`, `D4`, `60 Ω`, `10 kΩ`. LaTeX markup (`$ ... $`) is reserved strictly for complex mathematical equations (differential equations, transfer functions, loop stability calculations). Rule codified in Section 6 of [`agents.md`](agents.md).
* **[2026-10-02] Reverse-Polarity Topology, ISO 9141-2 Compliance & USB Integrity (Reviews 005 & 006):**
  - **Critical Placement of Primary TVS (`D1` SMBJ16A):** The primary surge TVS must be connected directly downstream of the reverse-polarity protection stage (at the Source of P-MOSFET `Q1`), and not upstream of fuse `F1`. If `D1` is connected ahead of `Q1`, vehicle battery reverse polarity (-12V) forward-biases the unidirectional TVS, creating a dead short that destroys the fuse or diode. Connecting `R7` and Zener `D3` to the Source of `Q1` (`+12V_PROT`) also ensures that under autonomous USB power (5V via `D4`), Vgs = 0V, preventing any backfeed toward OBD connector `J1`.
  - **ISO 9141-2 Diagnostic Tester Compliance & Jumper `JP2` Role:** Per ISO 9141-2 §4.2.1 and ST L9637D documentation (Fig. 4), the vehicle ECU presents a passive high-impedance input (Rin >= 100 kΩ). The Diagnostic Tester (our scanner) must provide the standardized 510 Ω pull-up (here 500 Ω via `R16` // `R18`) to the 12V rail. Jumper `JP2` must therefore be **CLOSED (with shunt)** by default when connected to a vehicle. On a dual-board bench (Case 3), only Board A (Scanner) closes `JP2`, while Board B (ECU Simulator) leaves it open to emulate ECU input impedance.
  - **Unidirectional K-Line Transient Protection (`D5` SMF24A):** Pin K (pin 6) of transceiver L9637D has an absolute maximum negative rating of –24.0 V. A bidirectional TVS (`SMF24CA`) would only clamp negative transients beyond –24V, exposing the IC to damage. Adopting a unidirectional TVS (`SMF24A`, cathode to `K_LINE`, anode to ground) ensures immediate forward clamping below –1.0 V, protecting the transceiver against ignition inductive transients.
  - **USB OTG Impedance Matching for ESP32-S3 (`R22`, `R23`):** Espressif recommends two 22 Ω 1% 0603 series damping resistors directly on differential lines `USB_D+` and `USB_D-`. They match line impedance to 90 Ω, suppress edge ringing, and improve EMC immunity over long test cables.
* **[2026-10-07] PCB Placement, IPC-7351 Footprints & Post-Annealing Legalization:**
  - **Component Body vs IPC Land Pattern & Courtyard:** Defining component bounds solely by nominal plastic dimensions (e.g., 0805 = 2.0 × 1.25 mm, SOIC-8 = 4.9 × 3.9 mm) underestimates physical space by 30% to 50%. Solder pads extend outward to form solder fillets (0805 = 3.35 × 1.50 mm, SOIC-8 = 5.20 × 7.40 mm, SOT-223 = 8.20 × 6.50 mm, connector J1 = 19.0 × 12.5 mm). Incorporating pad-to-pad footprints and IPC-7351 courtyards in [`documents/pcb/manifest.json`](documents/pcb/manifest.json) eliminated false negatives and physical overlapping on the PCB.
  - **Deterministic Post-Annealing Legalization:** Stochastic simulated annealing can occasionally converge near the global optimum while leaving tiny overlaps (tens of microns). Adding a deterministic legalization pass (minimal penetration vector pushback respecting fixed anchors and edge margins) mathematically guarantees 0 collisions and 0 hard violations.
  - **ESP32-S3 Antenna Alignment (`U1`):** Anchoring `U1` at `X = 63.00 mm` (instead of 64.77 mm) places the entire RF antenna meander inside the eastern board outline (`X = 81.28 mm`) with a 5.5 mm safety clearance.
* **[2026-10-07] Silkscreen, Designator Orientation & IPC-7351 §3.4.7 Compliance:**
  - **Decoupling Trace Rotation from Silkscreen Labels:** Rotating non-polarized components (resistors, ceramic capacitors) by 180° or 270° benefits routing by swapping pins without changing the netlist, eliminating crossings and vias. However, EasyEDA Pro by default rotates the designator label along with the footprint, generating upside-down 180° text that violates IPC-7351 §3.4.7.
  - **IPC Orthogonal Readability Rule:** IPC standards mandate that all component designators be readable either from the bottom (0°) or from the right (90°). Text must never appear at 180° or 270°.
  - **EasyEDA Pro Attribute Manipulation (`eda.pcb_PrimitiveAttribute`):** Designator labels are represented in EasyEDA Pro as instances of `pcb_PrimitiveAttribute` (linked by `parentPrimitiveId`). They are modified via `eda.pcb_PrimitiveAttribute.modify(id, { x, y, rotation, fontSize, lineWidth, alignMode })`. Using centered alignment (`alignMode: 5`) simplifies bounding box calculations and guarantees symmetric clearance from solder pads (>= 0.25 mm) and other labels (>= 0.20 mm).
* **[2026-10-07] 3D Silkscreen, Real Connector Envelope & Directional Ergonomics:**
  - **3D Model Overhangs & Mechanical Connectors (`3D Model Transform`):** Large mechanical components (such as terminal block `J1` and USB-C socket `J2`) have asymmetrical bodies offset from their pad centers (physical offsets of `-1.00 mm` in X and `-1.26 mm` in Y for `J1`). Dynamically parsing `otherProperty['3D Model Transform']` enables projecting the exact 3D bounding box onto the board plane and preventing label placement under component bodies (resolving overlap with `C15` and `TP3`).
  - **Clearance from Factory Silkscreen Graphics (Diodes, SMD LEDs):** Polarized discrete footprints (`LED1`, TVS diodes) feature factory silkscreen markings (polarity boxes, cathode bands, diode symbols) that extend `0.3 mm to 0.5 mm` beyond pads. A body margin of `0.30 mm` prevents designator labels from overlapping these polarity cues or lens chamfers.
  - **Directional Ergonomics Based on Aspect Ratio:** For vertical components (pads aligned along the Y-axis, e.g., `LED1`), the clearest placement positions are naturally on the East/West flanks, away from pads and power traces. For horizontal components (pads along X), favor North/South axes.
* **[2026-10-08] Test Point (TP) Silkscreen, Proximity Decoupling & Circular Keepouts:**
  - **Geometric Particularity of Single-Pad Test Points:** A test point (`TP`) is a bare round copper pad (0.5 mm diameter) without a plastic body. Its identification label (e.g., `TP15` = 2.0 mm wide) is 4 times larger than the pad itself, and must never overlap bare test copper.
  - **Absolute Assignment Priority (`priority = 0`):** Placing `TP`s at the end of the allocation queue caused them to be pushed 5–11 mm away from their pads by surrounding dense passives and ICs (`C15`, `R11`, `R16`, `U8`). Assigning priority 0 to single-pad components lets them immediately claim adjacent space (< 1.0 mm), while multi-pin components have much larger perimeters for label placement.
  - **Mutual Vector Repulsion Between Adjacent Test Points:** When two test points are close (e.g., `TP2` and `TP4` separated by only 2.0 mm), evaluating candidate positions along the inter-point vector and penalizing inward placements prevents labels from overlapping each other or bridging pads.
  - **Exact Geometric Modeling of Mounting Holes (Circles vs AABBs):** Modeling M2 screw holes as square bounding boxes (`7 × 7 mm`) artificially restricted corner routing and placement space (`4.95 mm` diagonal). Switching to exact circular testing (`d < r`) restored usable board space around mounting holes and allowed `C15` to sit directly above its body (`d = 1.2 mm`) without conflicting with `TP3`.
* **[2026-10-09] Uniform Spatial Density, Differentiated Courtyard Clearances & Line-of-Sight Silkscreen Algorithm:**
  - **Root Cause of Initial Congestion:** Pure HPWL and non-overlap optimization pulls all mobile passives toward left-hand input connectors (`X ∈ [15, 35] mm`), leaving the right half (around `U1` ESP32-S3) empty. This crowding squeezed inter-component spacing below `0.4 mm`, pushing silkscreen labels far away or behind third-party components (e.g., displaced `R14`).
  - **Uniform Spatial Density on a 2D Grid (`O(1)`) & Colonization Operator:** Partitioned the board into an `8 × 4` grid (`10.16 × 8.89 mm`) with incremental cell variance evaluation and a stochastic migration operator (15% of moves) drawing components into under-occupied cells. Areas above `U1` (5 components including `SW1`), below `U1` (13 components including bulk capacitors), and the Western corridor (5 components) were colonized evenly.
  - **Differentiated Courtyard Expansion (EMC vs Spacing):** Globally expanding all courtyards blocked high-speed switching loops (`G_BUCK_CORE`, `C14` / `U4`) from meeting strict EMC proximity bounds (e.g., `PC_C14_VIN <= 3.0 mm`). Retaining standard IPC margins (`0.0 mm` extra) for EMC-critical loops while applying `+0.20 mm` to unconstrained components ensured a clear `>= 0.90 mm` corridor between passives while preserving strict EMC compliance.
  - **Line-of-Sight Silkscreen Algorithm (`label_placer.py`):** Strictly forbade third-party components or labels from obstructing the direct path between a label and its parent component. Implemented via Liang-Barsky line clipping testing the ray from component center to label center against all obstacle bounding boxes. 100% of labels (84/84) are positioned unambiguously with an average distance of 2.36 mm.
* **[2026-10-09] Multiline Schematic Documentation & Binary Project Synchronization (`.epro2`):**
  - **Native Multiline Support in `sch_PrimitiveText`:** The `eda.sch_PrimitiveText.create` API cleanly handles newline characters (`\n`). It allows generating formatted instruction blocks and warning notes (e.g., documenting `JP1` and `JP2` jumper settings for *CAR* vs *BENCH* modes) in compact fonts (8 pt, bold) without cluttering schematic sheets.
  - **Programmatic `.epro2` Export Pipeline:** Extracting the up-to-date project archive is performed via `eda.sys_FileManager.getProjectFile('OBD2', undefined, 'epro2')`. The binary stream is Base64 encoded in 8 KB chunks inside the browser environment and reconstructed in Python, guaranteeing full project persistence in Git without manual user intervention.
* **[2026-10-10] Headless FreeRouting v2.4.1 Auto-Routing, Specctra DSN/SES Pipeline & EasyEDA Pro DRC:**
  - **JRE 25 Requirement for FreeRouting v2.4.1 (Bytecode 69.0):** Modern FreeRouting builds (v2.4.1) are compiled targeting Java 25 (class file version 69.0). Running the JAR under standard Java 21 JRE triggers `UnsupportedClassVersionError`. Bootstrapping a headless JRE must target Temurin OpenJDK 25 via Adoptium API (`https://api.adoptium.net/v3/binary/latest/25/ga/windows/x64/jre/hotspot/normal/eclipse`) to achieve 100% self-contained portability without host machine dependencies.
  - **FreeRouting CLI Flag Cleanup (`-l en`):** The `-l en` argument in FreeRouting v2.4.1 CLI is parsed as a relative folder path and generates a residual `./en/` directory. English is the default language, so omitting the flag prevents filesystem pollution.
  - **Silent Track Deletion Without Modal Dialogs (`--clean`):** Calling `eda.pcb_Document.clearRouting('all')` triggers a modal confirmation dialog in EasyEDA Pro UI, causing API timeouts. Programmatically deleting `pcb_PrimitiveLine` primitives on copper layers 1 (`TopLayer`) and 2 (`BottomLayer`) and `pcb_PrimitiveVia` allows instantaneous clearing while preserving the mechanical board outline on layer 11 (`BoardOutline`).
  - **DSN vs DRC Rounding Offsets (2-Micron Track-to-Via Gap):** EasyEDA Pro converts DSN coordinates to mils and reapplies an internal grid upon SES reimport. A via specified at 23.62 mil (0.60 mm) is reimported as 24.0 mil (0.61 mm). With a DSN clearance of 6.03 mil (0.153 mm), the measured track-to-via distance dropped to 0.150 mm against a DRC threshold of 0.152 mm, triggering dozens of false violations. Aligning via padstacks to 24.0 mil and setting the global structure rule to 0.20 mm (7.87 mil) permanently eliminated rounding discrepancies.
  - **SOIC-8 Transceiver Fanout (`U2` TJA1051T):** A differential clearance rule `DIFF_CAN.clearance_mm` of 0.25 mm blocked track fanout between 1.27 mm pitch pads (0.77 mm edge-to-edge pad gap). Aligning the clearance to 0.20 mm (identical to USB) unblocked 100% differential routing without compromising EMC.
  - **Routing Around Mechanical Cutout Slots (`Slot Region to Track`):** For SMD connectors with plated slots (USB-C receptacle `J2`), EasyEDA Pro enforces a >= 0.30 mm clearance between any track and the slot edge. Because FreeRouting considers only the copper pad, injecting an expanded 0.90 mm padstack into the `padstack_overrides` section of the DSN forces the router to respect the slot cutout clearance, achieving native EasyEDA Pro DRC = 0 violations.
* **[2026-10-12] Plane Net Exclusion in FreeRouting & Standalone `pcb-stitcher` Skill:**
  - **Excluding Ground Plane Nets (`plane_nets`):** Delegating `GND` routing to an auto-router creates thousands of thin wire fragments that fragment the board and prevent subsequent solid ground plane pouring. Stripping `GND` pins from the Specctra DSN before routing (standard EDA practice) allows FreeRouting to focus 100% of its optimization passes on differential buses (USB, CAN), digital signals, and power rails, leaving grounds to copper pours `POUR1` / `POUR2`.
  - **Formal Injection of Multi-Layer Keepouts into Specctra DSN:** Antenna RF keepout zones (ESP32 2.4 GHz meander) must be injected into the `(structure ...)` section of the DSN as `(keepout TopLayer ...)` and `(keepout BottomLayer ...)` blocks to prohibit both tracks and vias under the antenna, ensuring clean RF space from the first routing pass.
  - **Modularity and Standalone Skill `pcb-stitcher`:** Managing SMD ground returns and copper equipotentiality was encapsulated into the standalone skill `.agents/skills/pcb-stitcher/` (without hardcoded references to project components). It combines:
    1. An SMD via fanout solver (`fanout_stitcher.py`) respecting pad-to-via clearance rules.
    2. A continuous segment-to-segment geometric engine (`geometry.py`) accelerated by AABB pre-filtering (100x speedup).
    3. A 3D multi-layer A* island bridging router (`island_bridger.py`) based on connectivity graphs and Minimum Spanning Trees (MST / Prim).
  - **Obstacle Avoidance & Micro-Bridge DRC Clearance:** To bridge isolated ground islands without triggering `Clearance Error`, micro-traces must never be drawn straight between vias: the A* algorithm on a fine grid (5 to 10 mil) with neighbor penalties routes around active traces on layers 1 and 2 while maintaining clearance >= 0.20 mm.
* **[2026-10-12] Redundancy-Free Documentation Restructuring & Schematic / PCB Decoupling:**
  - **Strict Separation of Concerns:** To eliminate divergences between BOM, schematic intent, and physical placement:
    1. [`documents/schema/bom.json`](documents/schema/bom.json): Single PCBA procurement source of truth (structured JSON with unique keys, zero role duplication).
    2. [`documents/schema/semantics.json`](documents/schema/semantics.json): Pure schematic electrical and semantic intent (`power_rails`, `functional_blocks`, `substitutability`, `constraints`).
    3. [`documents/pcb/manifest.json`](documents/pcb/manifest.json): PCB physical geometry and placement (`packages` IPC-7351, `placement_constraints`, `rigid_groups`, `cem_target`). Points to `schema_semantics` for dynamic runtime hydration without data duplication.
    4. [`documents/pcb/constraints.json`](documents/pcb/constraints.json): Mechanical chassis and routing (`board` outline, M2 screws, fixed anchors, keepouts, and FreeRouting net classes).
  - **Agnostic Script Upgrades:** All automated tools (`pcb-placer`, `freerouting`, `stingy-schematics`, `review`) dynamically resolve these paths with in-memory semantic hydration.
* **[2026-10-13] Centralized Documentation, Root Cleanup & Visual Automation:**
  - **100% Centralized Directory under `documents/`:** Migrated all media, schematics, PCB renders, datasheets, hardware architecture ([`documents/hardware.md`](documents/hardware.md)), and EasyEDA project archive ([`documents/easyeda/OBD2.epro2`](documents/easyeda/OBD2.epro2)) into a unified `documents/` tree. Removed obsolete redundant files (`AUTOMATION.md`, `BOM.md`, `pcb-placer.md`, `images/`, `placement_*`, `preview_*`).
  - **Condensed Engineering Directives ([`agents.md`](agents.md)):** Streamlined and renamed `AGENTS.md` to `agents.md`, reduced to 36 clear operational directives (agnostic engines, Python execution strictly via `uv run`, EasyEDA bridge transparency, DRC/ERC = 0, explicit user confirmation prior to commit).
  - **Focused PCB Visuals:** Replaced scattered graphic previews with a single reference vector render [`documents/pcb/placement.svg`](documents/pcb/placement.svg) generated natively by `pcb-placer`.
  - **EasyEDA Bridge & IDE Hooks Integration:** Consolidated local bridge settings and Antigravity automated lifecycle hook directly into [`.agents/skills/easyeda-api/SKILL.md`](.agents/skills/easyeda-api/SKILL.md).
