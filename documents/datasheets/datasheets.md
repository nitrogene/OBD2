# Integrated Circuit Datasheets & Compliance Audit Reference (DATASHEETS)

This document constitutes the **technical source of truth** for the **ESP32 OBD-II Scanner** project. It synthesizes official manufacturer specifications (Espressif, NXP, STMicroelectronics, Texas Instruments, onsemi) extracted from PDF documents archived in the [`references/`](references/) directory, defines strict electronic implementation and PCB routing requirements, and audits point-by-point compliance of the actual hardware circuit.

---

## 1. Index of Referenced Manufacturer Files

| Designator | Integrated Circuit | Manufacturer | Functional Role | Source Archived PDF File |
| :--- | :--- | :--- | :--- | :--- |
| **`U1`** | **ESP32-S3-WROOM-1-N16R2** | Espressif Systems | Dual-Core 240 MHz SoC, 2.4 GHz Wi-Fi, BLE 5.0, Native USB, TWAI (–40 °C to +85 °C) | [`references/ESP32-S3-WROOM-1.pdf`](references/ESP32-S3-WROOM-1.pdf) |
| **`U2`** | **TJA1051T/3/1J** | NXP Semiconductors | High-Speed CAN Transceiver (up to 5 Mbit/s) with 3.3V VIO Level Translation | [`references/TJA1051T.pdf`](references/TJA1051T.pdf) |
| **`U3`** | **E-L9637D013TR (L9637D)** | STMicroelectronics | Bidirectional 12V ISO 9141 / KWP2000 K-Line Transceiver | [`references/E-L9637D013TR (L9637).pdf`](references/E-L9637D013TR%20%28L9637%29.pdf) |
| **`U4`** | **TPS54331DR** | Texas Instruments | 12V → 5V Step-Down Buck Converter (3A, 570 kHz, Eco-mode) | [`references/TPS54331.pdf`](references/TPS54331.pdf) |
| **`U5`** | **LDL1117S33R** | STMicroelectronics | Low-Noise Linear LDO Regulator 5V → 3.3V, PSRR 87 dB, 1.2A | [`references/LDL1117S33R(DS_ldl1117).pdf`](references/LDL1117S33R%28DS_ldl1117%29.pdf) |
| **`U8`** | **NUP2105LT1G** | onsemi | Dual 24V Differential TVS Diode Array for CAN Bus Transient Protection | [`references/NUP2105L-D.PDF`](references/NUP2105L-D.PDF) |
| **`J1`** | **WJ250B-3.5-05P-11-00A** | Ningbo Kangnex | 5-Contact Screwless Spring Terminal Block (3.5 mm pitch, 250V 8A, –40 °C to +105 °C) | [`references/WJ250B-3.5-06P.pdf`](references/WJ250B-3.5-06P.pdf) ([2D Drawing](references/WJ250B-3.5-06P.png)) |
| **`U6`/`U7`** | **SESD05C** | Semiware | Discrete Bidirectional 5V TVS Diodes for USB D+/D- ESD Protection | LCSC Catalog Part [`C720025`](../schema/bom.json) |

---

## 2. Detailed Technical Datasheets & Implementation Guidelines

---

### U1 — Wi-Fi & BLE SoC: ESP32-S3-WROOM-1-N16R2

* **Manufacturer Datasheet:** [`references/ESP32-S3-WROOM-1.pdf`](references/ESP32-S3-WROOM-1.pdf) (Espressif Systems)
* **Package:** 41-Pin SMD Module + Central Thermal Pad (25.5 × 18.0 mm).
* **Electrical Role:** Master compute core, OBD-II diagnostic protocol engine, 802.11 b/g/n Wi-Fi, Bluetooth LE 5.0, TWAI controller (CAN 2.0B), native USB OTG interface.

#### A. Electrical Specifications & Maximum Ratings
| Parameter | Symbol | Min | Typical | Max | Unit | Manufacturer Notes |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Supply Voltage** | VDD | 3.0 | 3.3 | 3.6 | V | ±5% stability required under transient load steps. |
| **Peak Supply Current** | IDD_peak | 500 | — | — | mA | Absolute requirement during Wi-Fi TX bursts. |
| **Absolute Maximum Supply** | VDD_max | -0.3 | — | +3.6 | V | **Not 5V tolerant**. Permanent silicon breakdown risk. |
| **GPIO Input Voltage** | VIO_in | -0.3 | — | VDD + 0.3 | V | Hard ceiling at 3.60V (under 3.3V VDD). Clamp diodes required. |
| **Reset Threshold (CHIP_PU / EN)** | VIL_EN / VIH_EN | — / 0.75 VDD | — | 0.25 VDD / — | V | High activation threshold at 2.475 V (for VDD = 3.3V). |

#### B. Manufacturer Schematic Design Guidelines
1. **Power-On Reset Timing (Pin 3 - `EN`):**
   * To prevent erratic bootloader behavior during 3.3V rail rise, the `EN` pin must be held low until VDD reaches 2.8V - 3.0V.
   * **Mandatory External RC Delay:** Pull-up resistor R = 10 kΩ to 3.3V and capacitor C = 1 µF to GND (tau = 10 ms). EN rise time > 50 µs.
2. **Local Power Supply Decoupling:**
   * A bulk reservoir ceramic capacitor of at least **10 µF** (low ESR, X5R/X7R rated >= 10V) must be placed directly across pin 2 (VDD) and pin 1 (GND).
   * A high-frequency **100 nF** ceramic capacitor in parallel.
3. **Strapping & Boot Configuration Pins:**
   * `GPIO0` (pin 27): Must be HIGH when reset is released to boot from SPI Flash. A robust external pull-up `R21` (10 kΩ 0805) to 3.3V secures this logic level against automotive EMI. Can be pulled to GND via test point `TP10` for ROM recovery mode.
4. **USB D+ / D- Data Lines:**
   * Direct connection to `IO20` (D+) and `IO19` (D-). The ESP32-S3 integrates internal software-controlled USB pull-ups; no external pull-up resistor should be added to D+!

#### C. Manufacturer PCB Layout Guidelines
* **Antenna RF Keepout Clearance:**
   * The integrated meander PCB antenna must overhang or align flush with the board edge.
   * **Strict All-Layer Keepout:** No ground planes, signal traces, power polygons, or metal components within **15 mm** of the antenna radiating zone.
* **Thermal Ground EPAD (Pin 42):**
   * Must be soldered to the host PCB ground plane through a thermal via array (at least 9 to 16 vias of 0.3 mm drill) for heat dissipation and RF grounding.
* **Reset Circuit (`R15`, `C12`, `SW1`):**
   * Must be placed immediately adjacent to pin 3 (`EN`) (< 2 mm) to prevent inductive loops from picking up 2.4 GHz RF energy from the nearby antenna.

#### D. Schematic Compliance Audit
* [x] **Compliant:** Reset RC delay implemented with `R15` (10 kΩ) and `C12` (1 µF) on the EN pin.
* [x] **Compliant:** Local bulk capacitor `C11` (10 µF 25V 0805) and decoupling `C1`, `C2` (100 nF) placed directly on power pins.
* [x] **Compliant:** USB D+/D- routed directly to IO20/IO19 with external TVS diodes `U6`/`U7` without parasitic pull-ups.
* [x] **Compliant:** Robust pull-up `R21` (10 kΩ to 3.3V) and test point `TP10` present on `IO0`. Pushbutton `SW1` on `EN`.

---

### U2 — High-Speed CAN Transceiver: TJA1051T/3/1J

* **Manufacturer Datasheet:** [`references/TJA1051T.pdf`](references/TJA1051T.pdf) (NXP Semiconductors)
* **Package:** SOIC-8 (150 mil).
* **Electrical Role:** ISO 11898-2:2016 and CAN FD compliant high-speed physical transceiver (up to 5 Mbit/s) interfacing 5V differential bus signals to the 3.3V logic domain of the ESP32 via its VIO pin.

#### A. Electrical Specifications & Maximum Ratings
| Parameter | Symbol | Min | Typical | Max | Unit | Manufacturer Notes |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Analog Supply Voltage** | VCC | 4.5 | 5.0 | 5.5 | V | **Nominal 5V mandatory**. Will not operate at 3.3V! |
| **Logic I/O Supply** | VIO | 2.8 | 3.3 | 5.5 | V | Tied to 3.3V for direct adaptation to ESP32 GPIOs. |
| **Supply Current** | ICC | — | 45 | 70 | mA | In dominant transmit state. |
| **Continuous DC Voltage on CANH / CANL** | VCANH/L | **-58.0** | — | **+58.0** | V | Continuous tolerance to battery/ground shorts. |
| **Transient Voltage on CANH / CANL** | V_transient | **-150** | — | **+100** | V | Per automotive ISO 7637-2 / 7637-3 pulses. |
| **Recessive Differential Voltage** | Vdiff(r) | -500 | 0 | +50 | mV | CANH = 2.5V, CANL = 2.5V nominal. |
| **Dominant Differential Voltage** | Vdiff(d) | 1.5 | 2.0 | 3.0 | V | CANH = 3.5V, CANL = 1.5V nominal. |

#### B. Manufacturer Schematic Design Guidelines
1. **Mandatory High-Frequency Dual Decoupling:**
   * Pin 3 (VCC): Ceramic capacitor C >= 100 nF (50V rated) to GND to supply high switching currents.
   * Pin 5 (VIO): Ceramic capacitor C >= 100 nF to GND to filter the RXD comparator logic reference.
2. **Pin 8 Management (`S` - Silent Mode):**
   * Pin 8 selects silent mode. Internally pulled high to VIO by default (silent mode, transmitter disabled).
   * **Imperative Rule:** For normal bidirectional communication, pin 8 must be **firmly tied to GND**.
3. **Differential CAN Termination (120 Ω):**
   * Specification mandates 120 Ω at bus endpoints. On in-vehicle OBD-II ports, termination already exists in the harness.
   * A jumper (`JP1`) disconnecting resistor `R8` (120 Ω) is the recommended compliant solution: **JP1 OPEN in car / CLOSED on test bench**.

#### C. Manufacturer PCB Layout Guidelines
* **Differential Routing CANH / CANL:**
   * Controlled differential impedance Zdiff = 120 Ω ± 10%.
   * Symmetrical, parallel routing of matched length (skew < 1 mm) with 45° bends.
* **Transient Protection Placement:**
   * TVS diode (`U8` - NUP2105L) must be placed **adjacent to connector `J1`** (< 5 mm). Transients must hit the TVS before reaching `U2`.
* **Decoupling Proximity:**
   * `C15` (pin 3) and `C3` (pin 5) within 2 mm of respective pins with short paths to GND plane.

#### D. Schematic Compliance Audit
* [x] **Compliant:** VCC powered by regulated +5V rail (Buck) with dedicated decoupling `C15` (100 nF 50V).
* [x] **Compliant:** VIO powered by clean 3.3V rail (LDO) with decoupling `C3` (100 nF 50V).
* [x] **Compliant:** Pin 8 (`S`) grounded to GND.
* [x] **Compliant:** Jumper `JP1` and termination `R8` (120 Ω) compliant for bench/car configuration.
* [x] **Compliant:** TVS diode `U8` (NUP2105L) connected across CANH/CANL.

---

### U3 — ISO 9141 K-Line Transceiver: E-L9637D013TR (L9637D)

* **Manufacturer Datasheet:** [`references/E-L9637D013TR (L9637).pdf`](references/E-L9637D013TR%20%28L9637%29.pdf) (STMicroelectronics)
* **Package:** SOIC-8.
* **Electrical Role:** Dedicated transceiver providing bidirectional half-duplex communication on the single-wire 12V K-Line (ISO 9141-2 and ISO 14230 KWP2000).

#### A. Electrical Specifications & Maximum Ratings
| Parameter | Symbol | Min | Typical | Max | Unit | Manufacturer Notes |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Battery Supply Voltage** | VS (Pin 7) | 4.5 | 12.0 | 36.0 | V | Nominal 12V automotive operation. |
| **Logic Supply Voltage** | VCC (Pin 3) | **3.0** | **3.3 / 5.0** | **7.0** | V | Operating range (Table 5). Note 1: "Specs tested at 5V only, compliance on Vcc full range guaranteed by design". 3.3V fully supported. |
| **Absolute Battery Voltage VS** | VS_max | -24.0 | — | +40.0 | V | Reverse polarity protection down to -24V. |
| **Battery Voltage Transients** | VS_transient | -100 | — | +100 | V | ISO 7637-1 transient pulses. |
| **Absolute Maximum on K Pin (Pin 6)** | VK_max | -24.0 | — | VS + 0.3 | V | Clamped upper bound by VS (max 40V). |
| **TX Input Logic Maximum** | VTX_max | -0.3 | — | VCC + 0.3 | V | Clamped by logic supply VCC. |
| **K-Line Threshold Voltage** | VK_th | 0.45 VS | 0.50 VS | 0.55 VS | V | Threshold proportional to battery voltage. |
| **Thermal Shutdown** | TJ_sd | 150 | 175 | — | °C | Thermal protection under short circuits. |

#### B. Manufacturer Schematic Design Guidelines
1. **Pinout & Pin Identification (ST L9637D Datasheet):**
   * **Pin 1: `RX`** (Logic output to MCU — Push-pull stage with internal pull-up R_RX ≈ 10 kΩ to VCC; V_RXH = VCC - 0.1 V).
   * **Pin 2: `LO`** (Loop Output — unused, leave open with NC flag).
   * **Pin 3: `VCC`** (Internal logic supply, tied to regulated 3.3V rail).
   * **Pin 4: `TX`** (Logic transmit input from MCU).
   * **Pin 5: `GND`** (Reference ground).
   * **Pin 6: `K`** (Bidirectional high-voltage 12V line to OBD port).
   * **Pin 7: `VS`** (High-voltage battery supply from `+12V_PROT`).
   * **Pin 8: `LI`** (Loop Input — unused, tied directly to adjacent pin 7 `VS`).
2. **Logic Supply VCC (Pin 3) Compliance & Safety:**
   * *ST Official Specification (Table 5, Note 1):* Recommended VCC range is **3.0 V to 7.0 V**. Note 1 states: *« Specs are tested at 5 V only. Compliance on Vcc full range is guaranteed by design »*. Operation at VCC = 3.3 V is 100% compliant and guaranteed by design.
   * *Internal RX Pull-up Structure:* Pin 1 (`RX`) features an active internal pull-up to VCC (R_RX ≈ 10 kΩ). It is NOT a pure open collector.
   * *MCU Protection:* ESP32-S3 GPIOs are **not 5V tolerant** (max 3.6 V). If VCC were 5V, RX would deliver ~4.9V into GPIO4, destroying it.
   * *Design Decision:* **VCC must remain tied to the `3.3V` rail** with decoupling capacitor `C4` (100 nF).
3. **Safe VS Connection (Pin 7):**
   * Connect downstream of reverse polarity protection `Q1` and fuse `F1` (`+12V_PROT`) to shield from transients.
4. **Locking Unused LI Input (Pin 8):**
   * Pin 8 (`LI`) is the L-Line input comparator. Tying it to adjacent pin 7 (`VS` / `+12V_PROT`) locks the comparator inactive (VLI = VS > 0.55 VS), eliminates EMI pickup, and guarantees 0 µA static drain.
5. **Standardized ISO 9141-2 Pull-Up (`R16` // `R18`):**
   * The standard mandates a **510 Ω (±5%)** pull-up to 12V on the tester for C <= 2 nF with tr < 2 µs.
   * Two parallel 1 kΩ 1206 resistors (`R16` and `R18`) yield Req = 500 Ω (–1.96% deviation, well within ±5%).
   * Peak power under 14.4 V is P = V² / R = (14.4V)² / 500 Ω ≈ 0.415 W, split into **2 × 207 mW** across two 1206 packages rated for 250 mW each, utilizing *Basic Part* `C4410`.

#### C. Manufacturer PCB Layout Guidelines
* **TVS Diode `D5` (`SMF24A`):**
   * Must be placed directly at OBD-II pin 7 input before pin 6 of `U3`.
* **Thermal Dissipation for `R16` and `R18`:**
   * Separate from sensitive components and surround with copper polygons to dissipate ~415 mW peak.
* **Damping Series Resistors (`R1`, `R2`):**
   * Place `R1` (10 Ω on RX) and `R2` (10 Ω on TX) halfway between `U3` and ESP32.

#### D. Schematic Compliance Audit
* [x] **[COMPLIANT / SAFE] VCC (Pin 3) at +3.3V:** Operates under 3.3V (3.0V–7.0V permitted). Protects ESP32-S3 GPIO4 against ~4.9V injection.
* [x] **[COMPLIANT / SAFE] Pin 7 (VS) Net Security:** Connected to `+12V_PROT` after `Q1`/`F1`.
* [x] **[COMPLIANT / SAFE] Unused LI (Pin 8) Tied to VS (Pin 7):** Locks comparator inactive, 0 µA, immune to EMI.
* [x] **Compliant:** Standard pull-up `R16` // `R18` (2 × 1 kΩ = 500 Ω) in 1206 packages on `+12V_PROT`.
* [x] **Compliant:** TVS diode `D5` (24V) on physical K-Line.

---

### U4 — Step-Down Buck Converter: TPS54331DR

* **Manufacturer Datasheet:** [`references/TPS54331.pdf`](references/TPS54331.pdf) (Texas Instruments)
* **Package:** SOIC-8.
* **Electrical Role:** High-frequency step-down switching regulator (570 kHz, 3A) converting automotive 12V down to regulated +5V to feed the CAN transceiver and 3.3V LDO with > 85% efficiency.

#### A. Electrical Specifications & Maximum Ratings
| Parameter | Symbol | Min | Typical | Max | Unit | Manufacturer Notes |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Input Voltage Range** | VIN | 3.5 | 12.0 | 28.0 | V | Recommended operating range. |
| **Output Voltage Range** | VOUT | 0.8 | 5.0 | 25.0 | V | Configurable via external divider. |
| **Continuous Output Current** | IOUT | — | — | 3.0 | A | With matched diode and inductor. |
| **Switching Frequency** | f_sw | 400 | 570 | 740 | kHz | Set internally by oscillator. |
| **Internal Reference Voltage** | Vref | 0.784 | **0.800** | 0.816 | V | ±2% accuracy over -40 °C to +125 °C. |
| **ABSOLUTE MAXIMUM INPUT VIN** | VIN_abs | **-0.3** | — | **+30.0** | V | **CRITICAL: Silicon breakdown above 30.0V!** |
| **Phase Pin Absolute Maximum (PH)** | VPH_abs | -0.6 | — | 30.0 | V | Transient tolerance -1.0V for < 10 ns. |
| **BOOT Pin Absolute Maximum** | VBOOT_abs | — | — | VPH + 8 | V | Internal charge pump. |
| **Error Amp Transconductance** | gm | 70 | 92 | 115 | µA/V | Output on COMP pin (Ro = 8.4 MΩ). |

#### B. Manufacturer Schematic & Sizing Guidelines
1. **Input Overvoltage Protection Against 30.0 V Ceiling:**
   * *TI Alert:* Maximum absolute voltage on pin 2 (`VIN`) is **30.0 V**. Load dump transients can exceed 40V to 60V.
   * *Clamping Requirement:* TVS `D1` must clamp below 30.0V.
   * *Selection:* `SMBJ16A` (VRWM = 16 V, VCL = 26.0 V) provides a **4.0 V safety margin** below the 30.0V limit.
2. **Input Capacitors (CIN):**
   * Ceramic decoupling capacitor **100 nF 50V X7R (`C14`)** directly at pin 2 (`VIN`).
   * Bulk reservoir **10 µF 50V X5R (`C7`)** to supply pulse currents.
3. **Freewheeling Schottky Diode (`D2`):**
   * Ultra-fast Schottky (VF < 0.5V), reverse rating >= 40 V, forward rating >= 3 A. `SS34` (40V, 3A, SMA) meets TI requirements.
4. **Bootstrap Capacitor (`C5`):**
   * Mandatory **0.1 µF (100 nF)** ceramic capacitor between `BOOT` (pin 1) and `PH` (pin 8). Implemented with **`C5` = 100 nF 50V X7R 0603** (`C14663`, *Basic Part*).
5. **Power Inductor (`L1`):**
   * 10 µH nominal for 20% to 40% ripple ratio.
   * Saturation current: Isat >= 3.0 A. Shielded `YNR6045-100M` (Isat = 3.6 A) prevents magnetic saturation.
6. **Feedback Divider (`R9`, `R10`):**
   * VOUT = 0.800 V * (1 + R9 / R10) = 0.8 * (1 + 10 kΩ / 1.91 kΩ) = 4.988 V ≈ 5.0 V (±0.24% of target).
7. **Type II Compensation Network (`COMP` - Pin 6):**
   * Triplet: R11 = 10 kΩ, C9 = 3.3 nF (zero fz ≈ 4.8 kHz), C13 = 220 pF (HF pole fp ≈ 77 kHz).
   * Validated via `buck-compensation` skill: **Phase Margin = 66.3°**, gain margin > 20 dB.

#### C. Manufacturer PCB Layout Guidelines
* **High-Frequency Critical Switching Loop (di/dt):**
   * Loop formed by `C14` / `C7` (VIN) → Pin 2 (`VIN`) → Pin 8 (`PH`) → Diode `D2` → GND must have **minimal loop area**.
* **Switching Node PH:**
   * Trace connecting pin 8, diode `D2`, and inductor `L1` must be short and wide, yet compact to limit capacitive dv/dt coupling.
* **Strict Isolation of Sensitive COMP / VSENSE Node:**
   * Keep compensation components (`R11`, `C9`, `C13`) and feedback divider (`R9`, `R10`) **isolated from the PH node** and shielded by ground plane.

#### D. Schematic Compliance Audit
* [x] **Compliant:** Type II compensation triplet (10 kΩ / 3.3 nF / 220 pF) validated for 570 kHz with 66.3° phase margin.
* [x] **Compliant:** Shielded 10 µH inductor (3.6A) and SS34 Schottky diode (40V 3A).
* [x] **Compliant:** Input filtering with 100 nF ceramic (`C14`) adjacent to VIN and 10 µF (`C7`).
* [x] **Compliant:** Output capacitance in Basic Parts (2 × 10 µF 50V `C8` // `C16`) halving ESR.
* [x] **[COMPLIANT / SAFE] TVS D1 Optimization:** Migration to `SMBJ16A` (`C353386`, `SMB`), ensuring Vcl = 26.0 V and **4.0 V safety margin** below the 30.0V absolute maximum of `U4`.

---

### U5 — Low-Noise LDO Regulator: LDL1117S33R

* **Manufacturer Datasheet:** [`references/LDL1117S33R(DS_ldl1117).pdf`](references/LDL1117S33R%28DS_ldl1117%29.pdf) (STMicroelectronics)
* **Package:** SOT-223.
* **Electrical Role:** Low Dropout linear regulator stepping +5V down to 3.3V logic with high PSRR (87 dB @ 120 Hz, > 60 dB @ 100 kHz) to remove residual 570 kHz ripple for the ESP32 SoC and 2.4 GHz radio.

#### A. Electrical Specifications & Maximum Ratings
| Parameter | Symbol | Min | Typical | Max | Unit | Manufacturer Notes |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Operating Input Voltage** | VIN | 2.5 | 5.0 | 18.0 | V | Powered from regulated +5V rail. |
| **Fixed Output Voltage** | VOUT | 3.234 | **3.300** | 3.366 | V | ±2% accuracy over -40 °C to +125 °C. |
| **Maximum Output Current** | IOUT | **1.2** | — | — | A | Generous current margin. |
| **Dropout Voltage** | Vdrop | — | 350 | 600 | mV | At full 1.2A load (< 150 mV at 500 mA). |
| **Absolute Maximum Input** | VIN_abs | -0.3 | — | +20.0 | V | Total margin against 5V input. |
| **Quiescent Current** | Iq | — | 250 | 500 | µA | Low standby power consumption. |
| **Power Supply Rejection (PSRR)** | PSRR | 75 | 87 | — | dB | At 120 Hz (ultra-quiet voltage rail). |

#### B. Manufacturer Guidelines — Loop Stability & Capacitors
1. **Input Capacitor (CIN):**
   * ST recommendation: CIN >= 1 µF ceramic placed near pin 3 (`VIN`). Fulfilled by +5V rail and Buck output capacitors `C8`/`C16` (20 µF).
2. **Output Capacitor (COUT) — Stability Criterion:**
   * *ST Warning:* Requires COUT >= 4.7 µF with ESR between 10 mΩ and 2 Ω for phase margin.
   * `C6` (directly at U5 output on `3.3V_PRE` before `FB1`) is sized at **10 µF 50V 1206** (`CL31A106KBHNNNE`, `C13585`, *Basic Part*).
   * Bulk capacitor `C11` (**10 µF**) completes filtering after ferrite bead `FB1` on `3.3V`.
   * **Compliance Certified:** With C6 = 10 µF >= 4.7 µF directly on `3.3V_PRE` before `FB1`, LDO stability is 100% guaranteed.

#### C. Manufacturer Guidelines — Layout & Thermal Management
* **Thermal Budget:**
   * Nominal load (~150 mA): Pdiss = (5.0 V - 3.3 V) * 0.15 A = 0.255 W.
   * Wi-Fi burst (450 mA): Pdiss = (5.0 V - 3.3 V) * 0.45 A = 0.765 W.
* **SOT-223 Layout Rules:**
   * Central Tab is tied to pin 2 (`VOUT`).
   * Extend copper polygon on PCB by at least **100 to 150 mm²** tied to Bottom layer via thermal vias to maintain ΔT < 30 °C inside the closed enclosure.

#### D. Schematic Compliance Audit
* [x] **Compliant:** 5V input and 1.7V headroom operates well above dropout (350 mV).
* [x] **Compliant:** Ferrite bead `FB1` (120 Ω @ 100 MHz) forms a Pi-filter with decoupling capacitors.
* [x] **[COMPLIANT] LDO Stability:** Capacitor `C6` at 10 µF 50V 1206 (*Basic Part* `C13585`) on `3.3V_PRE` satisfies ST guidelines (Cout >= 4.7 µF).

---

### U8 — Dual TVS CAN Bus Array: NUP2105LT1G

* **Manufacturer Datasheet:** [`references/NUP2105L-D.PDF`](references/NUP2105L-D.PDF) (onsemi)
* **Package:** SOT-23 (Pin 1: CANH, Pin 2: CANL, Pin 3: GND).
* **Electrical Role:** Electrostatic discharge (ESD) and surge transient protection for differential CAN lines per IEC 61000-4-2 and ISO 7637-3.

#### A. Electrical Specifications & Maximum Ratings
| Parameter | Symbol | Min | Typical | Max | Unit | Manufacturer Notes |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Reverse Standoff Voltage** | VRWM | — | — | **24.0** | V | Transparent under CAN signals and 24V jumps. |
| **Breakdown Voltage** | VBR | 26.2 | 27.5 | 32.0 | V | At IT = 1.0 mA. |
| **Peak Pulse Power** | Ppk | **350** | — | — | W | Standard 8/20 µs waveform. |
| **Peak Clamping Voltage** | VC | — | 35.0 | 44.0 | V | At IPP = 8.0 A (8/20 µs). |
| **Junction Capacitance** | Cj | — | **15** | **30** | pF | At VR = 0 V, f = 1 MHz. |
| **ESD Withstand (Contact)** | VESD_contact | ±30 | — | — | kV | IEC 61000-4-2 (standard = 8 kV). |
| **ESD Withstand (Air)** | VESD_air | ±30 | — | — | kV | IEC 61000-4-2 (standard = 15 kV). |

#### B. Manufacturer Guidelines — PCB Layout
* **Connector Boundary Placement:**
   * Place `U8` **adjacent to connector `J1`** (< 5 mm).
   * Differential tracks `CANH` and `CANL` must pass **directly through pads 1 and 2 of `U8`** before proceeding to `U2` and termination `R8`. No stubs permitted.
* **Ground Return Inductance:**
   * Pin 3 (GND) must connect to reference ground plane via a dedicated immediate via to preserve sub-nanosecond ESD clamping.

#### C. Schematic Compliance Audit
* [x] **Compliant:** Pin 1 to CANH, Pin 2 to CANL, Pin 3 to GND.
* [x] **Compliant:** Low 15 pF parasitic capacitance compatible with 500 kbps / 1 Mbps diagnostic bus rates.

---

### U6 / U7 — USB ESD Diodes: SESD05C

* **Manufacturer Reference:** `SESD05C` (Semiware) / LCSC [`C720025`](../schema/bom.json).
* **Package:** SOD-323 (discrete 2-pin diode).
* **Electrical Role:** Bidirectional TVS diodes providing ESD protection for Full-Speed USB data lines `USB_D+` and `USB_D-`.
* **Key Specifications:**
  * Standoff voltage: VRWM = 5.0 V.
  * Ultra-low capacitance: Cj < 3 pF (preserves signal edges).
  * ESD rating: ±15 kV contact per IEC 61000-4-2.
* **Layout Rule:** Place directly at contacts A6/B6 (`D+`) and A7/B7 (`D-`) of USB-C receptacle `J2`.

---

## 3. Synthesis Matrix & Manufacturer Compliance Audit

| IC | Manufacturer Guideline | OBD-II Scanner Implementation | Audit Status | Action Required |
| :--- | :--- | :--- | :---: | :--- |
| **`U1`** (ESP32-S3) | Power-On RC delay on EN (tau >= 10 ms) | R15 = 10 kΩ, C12 = 1 µF (tau = 10 ms) | **COMPLIANT** | None. |
| **`U1`** (ESP32-S3) | Supply current capability >= 500 mA peak | LDO U5 rated at 1.2 A max continuous | **COMPLIANT** | None. |
| **`U1`** (ESP32-S3) | Local bulk reservoir >= 10 µF at pins 1-2 | C11 = 10 µF 25V 0805 (< 2 mm) | **COMPLIANT** | None. |
| **`U1`** (ESP32-S3) | All-layer copper exclusion under antenna | 15 mm multi-layer keepout provided | **COMPLIANT** | Validated in floorplanning. |
| **`U2`** (TJA1051T) | Analog supply VCC = 5.0 V nominal | Regulated +5V rail (Buck) with C15 = 100 nF | **COMPLIANT** | None. |
| **`U2`** (TJA1051T) | Logic I/O adaptation VIO = 3.3 V | 3.3V rail (LDO) with C3 = 100 nF | **COMPLIANT** | None. |
| **`U2`** (TJA1051T) | Pin 8 (`S`) pulled to GND for active mode | Direct connection to GND net | **COMPLIANT** | None. |
| **`U2`** (TJA1051T) | Differential CAN transient protection | Dual TVS U8 (NUP2105L 24V) | **COMPLIANT** | None. |
| **`U3`** (L9637D) | Logic supply VCC between 3.0V and 7.0V | Connected to regulated 3.3V rail (C4 = 100 nF) | **COMPLIANT** | Table 5 Note 1. VCC = 3.3V protects ESP32-S3 GPIO4. |
| **`U3`** (L9637D) | Battery supply VS on protected rail | Pin 7 tied to `+12V_PROT` (after Q1/F1) | **COMPLIANT** | Protected against reverse polarity and surges. |
| **`U3`** (L9637D) | ISO 9141-2 standard pull-up (500 Ω) | R16 // R18 = 2 × 1 kΩ in 1206 (2 × 250 mW) | **COMPLIANT** | Meets 510 Ω ±5% requirement with 415 mW rating. |
| **`U3`** (L9637D) | Unused LI input tied inactive | Pin 8 bridged directly to Pin 7 (VS) | **COMPLIANT** | L comparator locked inactive, 0 µA, full EMI immunity. |
| **`U4`** (TPS54331) | **Absolute input ceiling VIN <= 30.0 V** | TVS D1 VCL = 26.0 V (4.0V margin) | **COMPLIANT** | TVS SMBJ16A validated. |
| **`U4`** (TPS54331) | Direct HF decoupling on pin 2 (`VIN`) | C14 = 100 nF 50V X7R (< 1.5 mm) | **COMPLIANT** | None. |
| **`U4`** (TPS54331) | Schottky diode >= 40 V, >= 3 A | Diode SS34 (40V, 3A, SMA) | **COMPLIANT** | None. |
| **`U4`** (TPS54331) | Type II stability (f_c ≈ 20 kHz, margin > 60°) | R11 = 10 k, C9 = 3.3 n, C13 = 220 p (margin 66.3°) | **COMPLIANT** | Validated via buck skill. |
| **`U5`** (LDL1117) | Output capacitor COUT >= 4.7 µF for stability | C6 = 10 µF 50V 1206 (Basic Part C13585) | **COMPLIANT** | Stability guaranteed at LDO output. |
| **`U8`** (NUP2105L) | Connector boundary placement | U8 < 5 mm from J1 (pass-through traces) | **COMPLIANT** | Validated in routing. |

---

## 4. Operational Layout Guidelines for PCB Implementation

1. **Priority 1 — Buck Loop U4 (SW / PH):** Place `C14`, `C7`, `U4`, `D2`, and `L1` in an ultra-compact cluster. Isolate compensation network (`R11`, `C9`, `C13`) from switching pin 8 (PH).
2. **Priority 2 — Input Boundary & ESD Protection:** Clamping components (`D1`, `D5`, `U8`, `U6`, `U7`) must physically intercept traces directly at the connector pins (`J1` OBD-II and `J2` USB-C) prior to entering transceivers or MCU.
3. **Priority 3 — ESP32 Radio Zone:** Maintain absolute RF keepout under the antenna meander, place `C11` (10 µF) and reset network `C12`/`R15` adjacent to pins 1, 2, and 3.
4. **Priority 4 — Thermal Dissipation:** Provide generous copper polygons and thermal via arrays for P-MOSFET `Q1` (60V), LDO `U5` (SOT-223), K-Line pull-up resistors `R16` // `R18` (2 × 1206), and the central ground EPAD of ESP32 `U1`.
