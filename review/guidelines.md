# Reviewer Guidelines — ESP32 OBD-II Scanner

Welcome! This document outlines instructions, technical requirements, and reporting standards for any **reviewer** (AI agent or human engineer) auditing the **ESP32 OBD-II Scanner** project.

The goal of a technical review is to provide rigorous critical scrutiny on the electrical schematic, PCB layout, routing, automotive EMC compliance, bill of materials (BOM), or firmware architecture, ensuring reliable, safe, and cost-effective hardware.

---

## 1. Format & Naming Conventions

### File Naming
Submit your review inside the `review/` directory using the following format:
`review/reviewXXX.md` *(e.g. `review001.md`, `review_schematic_01.md`, `review_pcb_02.md`)*.

> [!NOTE]
> **Lifecycle:** Once your review is placed in `review/`, the project team (user and AI coding assistant) will evaluate your observations, arbitrate each item, integrate accepted action points into `todo.md`, and then **delete** your `reviewXXX.md` file. Deletion signifies full resolution and keeps the intake clean for subsequent reviews.

### Mandatory Metadata Header
Every review **must begin** with this metadata block to guarantee full audit traceability:

```markdown
# Technical Review: [Short and descriptive title]

- **Reviewer / Agent Name:** [E.g. Claude 3.7 Sonnet, GPT-4o, Hardware Expert, etc.]
- **Date:** [YYYY-MM-DD]
- **Audited Scope:** [Schematic P1 / PCB Layout / Routing / BOM / Architecture / Firmware]
- **Examined Reference / Version:** [Git commit hash or document version]
- **Overall Verdict:** [🟢 Approved / 🟠 Approved with Reservations / 🔴 Rejected (Critical fixes required)]
```

---

## 2. Hardware Context & Pitfalls to Avoid (Read Before Auditing)

To prevent false alarms and off-topic observations, you **must integrate** the following fundamental project constraints:

0. **Auditor Mindset: Tabula Rasa & Evidence-Based Scrutiny**
   - If you are an AI model with conversational memory on this repository or an engineer familiar with its history, you **must completely disregard past discussions**. Adopt the stance of an impartial third-party auditor discovering the board fresh.
   - Every observation must be **strictly grounded in versioned repository files** (schematic PNG renders, bill of materials [`bom.json`](../documents/schema/bom.json), official datasheets archived under [`documents/datasheets/references/`](../documents/datasheets/references/), and the technical reference [`datasheets.md`](../documents/datasheets/datasheets.md)).
   - **Mandatory Critical Thinking:** Never take text claims in documentation at face value. Systematically cross-check every guideline and statement against manufacturer datasheets.

1. **Target Vehicle Environment: 12V Passenger Cars Exclusively**
   - The scanner is engineered exclusively for 12V passenger cars (12.6V nominal battery, 14.4V alternator charging, moderate transients).
   - **Do not over-specify** for 24V heavy commercial vehicles or trucks (the Buck regulator U4 rated for 30V, protected by TVS `D1` rated at 16V with 26.0V clamp and P-MOSFET `Q1`, is specifically validated for 12V vehicles).

2. **Target MCU: ESP32-S3 (≠ Classic ESP32)**
   - The microcontroller is an **ESP32-S3-WROOM-1**.
   - *Pinout Notice:* ADC channels compatible with active Wi-Fi are located on **ADC1 (GPIO1 to GPIO10)**, unlike the classic ESP32.
   - *USB:* The ESP32-S3 features native on-chip USB OTG on GPIO19 (D-) and GPIO20 (D+).

3. **Manufacturing Constraints & JLCPCB Cost Optimization**
   - Standard **4-layer PCB** (JLC2313 stackup: Layer 1 Top signals/components, Layer 2 Inner 1 continuous GND ground plane, Layer 3 Inner 2 3.3V/5V/GND power rails, Layer 4 Bottom signals/GND with stitching vias).
   - **Absolute Priority for JLCPCB *Basic Parts*:** Any modification of passive or active components should favor Basic Parts from the LCSC/JLCPCB catalog to eliminate additional reel changeover fees (*Extended Part fee*).

4. **Consult Current Progress State**
   - Before raising an alert, quickly check [`todo.md`](../todo.md), [`hardware.md`](../documents/hardware.md), and [`bom.json`](../documents/schema/bom.json).
   - Many historical review remarks are already implemented or arbitrated (e.g. jumper JP1 on CAN termination, clamp diode D6, compensation capacitor C13 on COMP pin, etc.).

5. **K-Line Transceiver U3: 3.3V vs 5V VCC Supply & MCU Integrity**
   - *Do not demand switching VCC to 5V:* A frequent confusion assumes that the K-Line transceiver U3 requires VCC >= 4.5V or that its RX pin is a pure open collector requiring an external pull-up.
   - *ST Datasheet Specifications (Doc ID 1765 Rev 8, Table 5 & Note 1):*
     - The recommended operating supply range for VCC is **3.0 V to 7.0 V** (Table 5; the 4.5 V minimum threshold applies exclusively to battery supply VS, not VCC). Note 1 of Table 5 explicitly states: *« Specs are tested at 5 V only. Compliance on Vcc full range is guaranteed by design »*. Operation under VCC = 3.3V is therefore 100% compliant and guaranteed by design.
     - Pin 1 (`RX`) incorporates an **active internal pull-up resistor RRX ≈ 10 kΩ tied to VCC** (VRXH = VCC - 0.1V). It is NOT an open collector.
   - *Microcontroller Overvoltage Protection:* ESP32-S3 I/O pins are **not 5V tolerant** (absolute maximum voltage VDDIO + 0.3V = 3.6V). If VCC were tied to +5V, RX would inject ~4.9V directly into GPIO4, destroying the ESP32.
   - *Audit Directive:* Connecting pin 3 (VCC) to the regulated `3.3V` rail is **fully compliant and essential to MCU survival**. Do not report an anomaly on this design choice.

---

## 3. Mandatory Criticality Classification

Observations must be strictly categorized into 3 severity levels:

### 🔴 1. Blocking / Critical (*High / Critical*)
*Issues that prevent circuit operation or present component destruction risks.*
* Component destruction risk, overvoltage, overcurrent, unprotected reverse polarity.
* Absolute Maximum Ratings exceeded (VDS, VGS, VIN, junction temperature TJ).
* Hard short circuits, blocking ERC/DRC violations, floating critical pins (Reset, Boot, Power rails).
* Inability to establish communication (swapped CAN differential lines, invalid ISO 9141 voltage levels).

### 🟠 2. Important (*Medium*)
*Issues that compromise robustness, EMC compliance, or automotive reliability.*
* Insufficient decoupling or capacitors placed too far (> 2 mm from power pins).
* Poor switching loop layout (Buck: SW - L1 - D2 - Cout loop too wide, generating radiated EMI).
* Insufficient noise immunity (EN pin lacking RC filter, ESD transients not bypassed at OBD connector).
* Marginal regulation headroom (LDO dropout, feedback loop phase margin < 45°).
* Missing reverse-blocking diode between USB power and vehicle power.

### 🟢 3. Minor / Suggestion (*Low / Info*)
*Opportunities to optimize cost, manufacturability, or ergonomics.*
* Bill of Materials (BOM) optimization: substituting an *Extended Part* with an equivalent *Basic Part*.
* Silkscreen clarity (polarity markers, jumper configuration text such as `JP1: Shunt=Bench / Open=Car`).
* Indicator visibility (LED ballast resistor tuning) or test point accessibility (`TP1` to `TP15`).
* Schematic or documentation formatting and layout polish.

---

## 4. Expectations for High-Quality Feedback

For observations to be directly actionable, each remark must provide:

1. **Pinpoint Precision:**
   - Cite **exact designators** (`U4`, `R12`, `C10`, `TP9`).
   - Name **exact nets** (`+12V_PROT`, `CANH`, `ESP_EN`, `VBAT_SENSE`).
   - Specify **pin number and pin name** (`pin 2 VIN of U4`).

2. **Technical Demonstration (Why?):**
   - Move beyond subjective impressions.
   - Support analysis with **calculations**, **formulas**, **datasheet excerpts**, or **standards** (ISO 11898-2, ISO 9141-2, ISO 7637-2).

3. **Turnkey Actionable Solution (How to fix?):**
   - Provide concrete parameters: value, tolerance, package/footprint (0603, 0805, SOT-23...), exact manufacturer part number, and **LCSC code**.
   - Note whether the proposal qualifies as a JLCPCB *Basic Part*.

4. **New Components to Add (No advance designators):**
   - When suggesting new components, **do not assign speculative designators** (e.g. `R18`, `C18`, `TP12`).
   - Describe components strictly by function, value, footprint, and constraints (e.g. *« Add a 10 kΩ 0805 pull-up on IO0 »*).
   - The final sequential designator will be assigned at schematic integration time according to the next available number in the BOM.

---

## 5. Review Template (`reviewXXX.md`)

Copy and complete the template below in your `review/reviewXXX.md` file:

```markdown
# Technical Review: [Short title of your audit]

- **Reviewer / Agent Name:** [Your name / AI model]
- **Date:** [YYYY-MM-DD]
- **Audited Scope:** [Schematic P1 / PCB Layout / BOM / Routing]
- **Examined Reference / Version:** [Git commit hash or document version]
- **Overall Verdict:** [🟢 Approved / 🟠 Approved with Reservations / 🔴 Rejected]

---

## Executive Summary
[3 to 5 sentence summary on overall design health, compliance, and key priorities.]

---

## Observations Summary

| Ref | Severity | Components / Nets | Summary Description |
| :--- | :--- | :--- | :--- |
| **B1** | 🔴 Blocking | `...` | ... |
| **I1** | 🟠 Important | `...` | ... |
| **M1** | 🟢 Minor | `...` | ... |

---

## Detailed Observations & Recommendations

### 🔴 Blocking Observations (Critical)

#### B1. [Descriptive Title]
- **Affected Components / Nets:** `...` (e.g. `U4` pin 2, net `+12V_PROT`)
- **Technical Observation:** [Detailed problem description]
- **Justification & Risk:** [Datasheet citation, calculation, or standard demonstrating hazard]
- **Recommended Solution:** [Concrete action: part number, value, package, LCSC code]

---

### 🟠 Important Observations (Robustness & EMC)

#### I1. [Recommendation Title]
- **Affected Components / Nets:** `...`
- **Technical Observation:** [Description]
- **Justification:** [Impact on EMC immunity, vehicular durability, signal integrity]
- **Recommended Solution:** [Recommended component, layout change, or filter]

---

### 🟢 Minor Observations (Optimization & DFM)

#### M1. [Optimization Title]
- **Affected Components / Nets:** `...`
- **Observation & Proposal:** [E.g. Basic Part migration, silkscreen labeling]
- **Expected Benefit:** [Cost reduction, visual clarity, test accessibility]
```
