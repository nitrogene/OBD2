# Extra Hardware, Fasteners & External Connectors (Per Complete Unit)

This document lists all mechanical fasteners, external connectors, and accessories **not included in the PCBA SMT/THT BOM** ([`bom.json`](schema/bom.json)) that are required to assemble **one complete enclosure and OBD-II harness**.

All dimensions are derived directly from [`documents/pcb/enclosure.json`](pcb/enclosure.json), [`documents/pcb/constraints.json`](pcb/constraints.json), and [`enclosure_generator.py`](../.agents/skills/pcb-enclosure/scripts/enclosure_generator.py).

---

## 1. Enclosure Fasteners (M2 Hardware)

| Item | Qty / Enclosure | Specification | Mechanical Details & Stack-Up |
| :--- | :---: | :--- | :--- |
| **Heat-Set Brass Threaded Inserts** | **6** | **M2**, OD `3.2–3.5 mm`, Length `3.5–4.0 mm` | 4 × PCB/shell standoffs (`MH1`–`MH4`) + 2 × cable clamp (`enclosure_clamp`). Printed pocket: Ø `3.2 mm`, depth `4.0 mm`, boss OD `5.0 mm`. |
| **Shell Closure Screws** *(Top → PCB → Bottom)* | **4** | **M2 × 16 mm** *(or `M2 × 18 mm`)*, head Ø `≤ 4.4 mm` | Stack-up: top shell `14.0 mm` − counterbore `1.6 mm` + PCB `1.6 mm` = `14.0 mm` to insert entry. `16 mm` engages `2.0 mm` into the insert; `18 mm` reaches the `4.0 mm` pocket bottom. |
| **Cable Clamp Screws** (`enclosure_clamp`) | **2** | **M2 × 8 mm** *(or `M2 × 6 mm`)*, head Ø `≤ 4.4 mm` | Clamp thickness `5.75 mm` − counterbore `1.6 mm` = `4.15 mm` to insert entry. `8 mm` engages `3.85 mm` into the `4.0 mm` insert pocket. |

> [!NOTE]
> **Screw Head Clearance:** Both the top shell and the cable clamp use through-holes of Ø `2.4 mm` with counterbores of **Ø `4.5 mm` × `1.6 mm` depth**. Choose socket head cap screws (DIN 912 / ISO 4762, head Ø `3.8 mm`) or low-profile / pan head M2 screws with head diameter **≤ 4.4 mm**.

---

## 2. External Connectors & Harness (JST-XH & OBD-II)

The board-mounted diagnostic connector `J1` is a 5-pin right-angle **JST-XH** male header (`2.50 mm` pitch, MPN: `S5B-XH-A-1(LF)(SN)`, LCSC `C163038`).

| Item | Qty / Unit | MPN / Specification | Role & Notes |
| :--- | :---: | :--- | :--- |
| **5-Pin Female Housing** | **1** | **JST `XHP-5`** (`2.50 mm` pitch, 5P) | Mates with PCB header `J1`. *(Order 2 if building an inter-board bench test cable).* |
| **Female Crimp Terminals** | **5** *(+ spares)* | **JST `SXH-001T-P0.6`** *(AWG 22–28)* or `SXH-002T-P0.6` *(AWG 26–30)* | Crimp contacts for `XHP-5` housing. Pre-crimped JST-XH 5P pigtails can also be used. |
| **OBD-II Male Plug & Cable** | **1** | **SAE J1962 Type A** (12V) + 5-wire cable, outer Ø `≈ 6.5 mm` | Matches the `6.5 mm` strain-relief cradle in `enclosure_bottom` / `enclosure_clamp`. |

---

## 3. Configuration Jumpers (`2.54 mm` Shunts)

Both `JP1` (120 Ω CAN termination) and `JP2` (500 Ω K-Line pull-up) use standard `2.54 mm` 1×2 pin headers.

| Operating Mode | Qty / Unit | Specification | Jumper Positions (`JP1` / `JP2`) |
| :--- | :---: | :--- | :--- |
| **Scanner Mode** *(In-Vehicle, Case 1 & Case 2)* | **1** | Standard `2.54 mm` 1×2 jumper shunt | `JP1` **OPEN** (vehicle bus already terminated) · `JP2` **CLOSED** (ISO 9141-2 tester pull-up) |
| **ECU Simulator Mode** *(Benchtop Testbench, Case 3)* | **1** | Standard `2.54 mm` 1×2 jumper shunt | `JP1` **CLOSED** (120 Ω bench termination) · `JP2` **OPEN** (passive high-Z ECU state) |

> [!TIP]
> In **Dual-Board Benchtop Mode (Case 3)**, the paired **Scanner** board requires **2 × `2.54 mm` jumper shunts** (`JP1` **CLOSED** + `JP2` **CLOSED**), while the **ECU Simulator** board uses **1** (`JP1` **CLOSED**, `JP2` **OPEN**), for a total of **3 shunts** across the two-board bench setup.
