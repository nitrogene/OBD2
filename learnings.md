# Technical Knowledge Base & EasyEDA Pro Pitfalls Guide

This document serves as the **technical knowledge base** for the ESP32 OBD-II Scanner project. It catalogs non-obvious EasyEDA Pro API pitfalls and critical hardware design decisions that must not be regressed.

> [!NOTE]
> Mandatory workflow rules live in [`AGENTS.md`](AGENTS.md). Reusable algorithms and calculations live in `.agents/skills/<name>/`.

---

## 1. Knowledge Management Protocol

Any newly discovered anomaly or technical insight follows this lifecycle:
1. **Record** symptom, root cause, and verified workaround in this file.
2. **Route** to the right home:
   - Mandatory process/safety directive $\rightarrow$ [`AGENTS.md`](AGENTS.md)
   - Reusable algorithm/calculation $\rightarrow$ `.agents/skills/<name>/`
   - EasyEDA Pro API quirk $\rightarrow$ Section 2 below
   - Non-obvious hardware design decision / trap $\rightarrow$ Section 3 below
3. **Prune** periodically once knowledge is codified into a skill or rule.

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
| **Graphic `LINE` crossing a passive body** | A schematic `LINE` primitive accidentally crossing the body of a passive component (e.g., `C7`) shorts its two pads in the netlist without visual warnings. | Audit primitive continuity and never draw graphic lines across component pins/bodies. |
| **Multiline text annotations (`sch_PrimitiveText.create`)** | Multi-line text strings can require separate calls in some EDA tools. | `eda.sch_PrimitiveText.create` natively supports `\n` newlines. |
| **Automated project export (`sys_FileManager.getProjectFile`)** | `eda.sch_ManufactureData.getPngFile` is unavailable in some EasyEDA Pro runtimes. | Use `eda.sys_FileManager.getProjectFile('OBD2', undefined, 'epro2')` to extract the binary archive. |

### B. PCB Layout & Primitives (`eda.pcb_*`)

| Pitfall / Behavior | Cause & Risk | Proven Rule & Solution |
| :--- | :--- | :--- |
| **Signature of `pcb_PrimitiveVia.create` (CRITICAL)** | The API signature is `(net, x, y, holeDiameter, diameter)`. Inverting drill diameter and outer diameter creates an invalid via and blocks DRC. | **The drill diameter always precedes the outer diameter.** JLCPCB standard: `hole = 12 mil` (~0.3 mm), `diameter = 24 mil` (~0.6 mm). |
| **Signature of `pcb_PrimitiveLine.create` (CRITICAL)** | The API signature is `(net, layer, startX, startY, endX, endY, width)`. Placing width before coordinates offsets all arguments. | **Coordinates always precede track width.** |
| **Runtime units** | PCB API coordinates are expressed in **mils** (1 mil = 0.0254 mm, 1 mm = 39.3701 mil). | Always explicitly convert using `mm_to_mil()` and `mil_to_mm()`. |
| **Layer identifiers (Layers)** | Layers are referenced by integers: `1` = Top Layer, `2` = Bottom Layer, `11` = Board Outline, `12` = Multi-layer. | Use integer constants or the `EPCB_LayerId` enumeration. |
| **Moving / relocating a via** | Modifying existing via coordinates in place fails to trigger recalculation of copper clearance regions during polygon pouring. | **Delete the old via** (`delete([oldId])`), **create the new via**, then call `rebuildCopperRegion()`. |
| **Differential pair chamfering** | 90° bends cause impedance discontinuities and EMI radiation (critical for USB 480 Mbps and CAN 500 kbps). | **Always use 45° mitered corners** (Δx = Δy = 25 mil for a 10 mil track). |
| **Pad geometry extraction (`Pad`)** | Methods `getState_Width()` / `getState_Height()` do not exist on `pcb_PrimitivePad`. | **Use `p.getState_Pad()`** (`['RECT', w, h, r]`) and `p.getState_Hole()` (`['ROUND', drill]`). |

### C. Copper Pours, DRC & WebGL Cache

| Pitfall / Behavior | Cause & Risk | Proven Rule & Solution |
| :--- | :--- | :--- |
| **Persistence of old track labels (WebGL Cache)** | After updating a net via the API, the text displayed on the WebGL canvas retains the old name as long as the tab remains open. | **Close and reopen the PCB document**: `save()`, `closeDocument(tabId)`, then `openDocument(pcbUuid)`. |
| **Copper micro-slivers between SMD pads** | Ground plane pouring can introduce parasitic copper slivers between tightly spaced pads (0603/0805). | Insert a local `NO_POURS` keepout region (`ruleType: [7]`) between pads via `pcb_PrimitiveRegion.create()`. |
| **Multi-layer RF antenna keepout** | The ESP32-S3 PCB antenna requires a total copper void under and around the 2.4 GHz meander trace across all layers. | Create a region on layer `12` (`MULTI`) with `ruleType: [5, 6, 7]` (`NO_WIRES`, `NO_FILLS`, `NO_POURS`). |
| **Ground plane continuity verification** | After calling `rebuildCopperRegion()`, verify that the plane has not fragmented into isolated islands. | Check via `pcb_PrimitivePoured.getAll()` that `pouredCount == 2` (1 Top region, 1 Bottom region). |

---

## 3. Critical Hardware Design Decisions (Do Not Regress)

* **`L9637D` (`U3`) Logic Supply & `LI` Pin:**
  * `VCC` (pin 3) **must stay at `3.3V`** (never `5V`): `U3` has an internal pull-up on `RX` to `VCC`, which would destroy the non-5V-tolerant ESP32-S3 (`Vmax = 3.6 V`).
  * `LI` (pin 8, L-Line input) has a threshold of `0.5 × VS` (~6 V). Tying it to `3.3V` would lock it dominant; tying it directly to adjacent `VS` (`+12V_PROT`, pin 7) holds it idle with `0 µA` draw.
* **`VBAT_SENSE` Clamp Diode (`D6 = BAV199`, not `BAV99` or `BAT54WS`):**
  * With `R12 = 100 kΩ`, reverse leakage `Ir` scales directly to battery error: $\Delta V_{BAT} = I_R \times 100\,\text{k}\Omega$. At 85 °C cabin temperature, `BAT54WS` (Schottky) leaks 5–10 µA (+0.5 to +1.0 V error) and `BAV99` leaks ~1 µA (+100 mV error). Only **`BAV199`** (< 100 pA at 85 °C) keeps error `< 0.01 mV`.
* **`LDL1117S33R` (`U5`) Output Capacitor Placement:**
  * `C6` (`10 µF`) must sit **directly on `Vout` (`3.3V_PRE`) upstream of ferrite bead `FB1`**. Placing `FB1` between `U5` and `C6` shifts feedback phase and risks oscillation.
* **Reverse Polarity & TVS Placement (`D1`, `Q1`, `Q2`, `D5`):**
  * Primary TVS `D1` (`SMBJ16A`, `Vcl = 26.0 V < 30.0 V` max of `U4`) must sit **downstream** of P-MOSFET `Q1` (at `Q1` Source/`+12V_PROT` side, not ahead of `Q1`), otherwise `-12V` reverse polarity forward-biases `D1` and blows `F1`.
  * `Q2` (`2N7002`) gate divider `R5`/`R17` (`10 kΩ` / `10 kΩ`) caps `Vgs <= 13.0 V` at `26.0 V` clamp (below `±20 V` max).
  * K-Line TVS `D5` (`SMF24A`) must be **unidirectional** (not `SMF24CA`) because `L9637D` pin K absolute max negative rating is `-24.0 V`.
* **`TPS54331` (`U4`) UVLO & Type II Compensation:**
  * `EN` hysteresis depends only on high-side resistor `R19`: $\Delta V_{HYS} = 3\,\mu\text{A} \times R_{19}$. Basic Parts `R19 = 470 kΩ` / `R20 = 68 kΩ` yield `VSTART = 9.42 V`, `VSTOP = 8.01 V` (`1.41 V` hysteresis).
  * Validated Type II compensation triplet: `R11 = 10 kΩ`, `C9 = 3.3 nF`, `C13 = 220 pF` (61.7°–68.8° phase margin).
* **Jumpers & Bus Terminations (`JP1`, `JP2`):**
  * `JP1` (`120 Ω` CAN) uses a `1206` (`250 mW`) resistor (`R8`) for fault thermal margin; keep `JP1` **OPEN** in-vehicle.
  * `JP2` (`500 Ω` K-Line pull-up `R16 // R18`) must be **CLOSED** in-vehicle (Scanner = Diagnostic Tester role per ISO 9141-2) and **OPEN** on the ECU Simulator board.
