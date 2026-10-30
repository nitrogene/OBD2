# DFM Manufacturability & SMT Assembly Audit Report

- **Audit Date:** 2026-10-30 19:54:53
- **Overall Verdict:** 🔴 DFM Rejection: Critical Anomalies Detected
- **Target Manufacturer:** JLCPCB (JLC2313 4-Layer Stackup)

---

## 1. Metrology Summary

| Domain | Status | Danger (Blocking) | Warning | Info / Recommendation |
| :--- | :---: | :---: | :---: | :---: |
| **Bare PCB DFM** | ❌ NON-COMPLIANT | 53 | 66 | 0 |
| **SMT Assembly DFM** | ✅ COMPLIANT | 0 | 1 | 2 |

### Assembly Distribution:
- SMD Components (Automated Pick & Place): **78**
- Through-Hole THT Components (Manual / Selective Soldering): **7** (H1, H2, H3, J1, J2, JP1, JP2)

---

## 2. 🔴 Critical Anomalies (DANGER — Must fix before production order)

| # | Category | Technical Description | Value | Threshold | Coordinates (X, Y) |
| :---: | :--- | :--- | :---: | :---: | :---: |
| 1 | `PCB_DFM_SOLDERMASK_BRIDGE` | Insufficient solder mask dam (-0.017 mm < 0.10 mm) between pads '2' and '2' (layer 1). Solder bridge / gang mask risk. | -0.017 mm | 0.1 mm | (14.08, 7.12) mm |
| 2–14 | `PCB_DFM_SOLDERMASK_BRIDGE` | Insufficient solder mask dam (-0.102 mm < 0.10 mm) on dense pins (U1 ESP32-S3). Solder bridge / gang mask risk. | -0.102 mm | 0.1 mm | Pins 1 to 14 |
| 15–27 | `PCB_DFM_SOLDERMASK_BRIDGE` | Insufficient solder mask dam (-0.102 mm < 0.10 mm) on dense pins (U1 ESP32-S3). Solder bridge / gang mask risk. | -0.102 mm | 0.1 mm | Pins 27 to 40 |
| 28–33 | `PCB_DFM_SOLDERMASK_BRIDGE` | Insufficient solder mask dam (-0.102 mm < 0.10 mm) between fine pitch IC pads (layer 1). Gang mask risk. | -0.102 mm | 0.1 mm | SOIC packages |
| 34–39 | `PCB_DFM_VIA_IN_PAD` | Via directly intersects SMD pad (edge distance < 0.0 mm). Solder wicking risk during reflow. | < 0.0 mm | 0.0 mm | Critical nets |
| 40 | `PCB_DFM_VIA_TO_PAD_PROXIMITY` | Via too close to SMD pad (0.033 mm < 0.15 mm). Insert >= 0.15 mm dog-bone trace. | 0.033 mm | 0.15 mm | (12.24, 4.67) mm |
| 41–53 | `PCB_DFM_VIA_IN_PAD` | Via directly intersects SMD pad (edge distance < 0.0 mm). Solder wicking risk during reflow. | < 0.0 mm | 0.0 mm | Various nets |

---

## 3. 🟠 DFM Warnings (WARNING — Marginal factory tolerances)

| # | Category | Observation | Measurement | Standard Threshold | Coordinates |
| :---: | :--- | :--- | :---: | :---: | :---: |
| 1–7 | `PCB_DFM_SOLDERMASK_BRIDGE` | Marginal solder mask dam (0.096 mm to 0.099 mm < 0.10 mm) between USB-C pads. Gang mask risk. | ~0.098 mm | 0.1 mm | J2 connector |
| 8–19 | `PCB_DFM_VIA_TO_PAD_PROXIMITY` | Via too close to SMD pad (0.064 mm to 0.140 mm < 0.15 mm). Dog-bone neck >= 0.15 mm recommended. | < 0.15 mm | 0.15 mm | Various pads |
| 20–25 | `PCB_DFM_SILKSCREEN_STROKE` | Silkscreen stroke width too fine (0.150 mm). Increase to >= 0.18 mm for crisp print contrast. | 0.1499 mm | 0.15 mm | Text labels |
| ... | ... | *(plus 42 additional similar warnings)* | ... | ... | ... |

---

## 4. Immediate Recommended Corrective Actions

- **Solder Mask Dams:** Reduce solder mask expansion from 0.05 mm to 0.025 mm (1 mil) on dense ICs to restore physical dams >= 0.10 mm.
- **Via to Pad Distance / Tenting:** Offset stitching vias by adding dog-bone necks >= 0.15–0.20 mm, or enforce 100% via tenting on both layers to stop solder wicking.
- **Silkscreen Clearances:** Maintain >= 0.15 mm clearance from exposed copper and configure stroke width >= 0.18 mm.
- **Fiducials:** Ensure 3 standard 1.0 mm optical fiducials on board margins or confirm factory tooling rails during panelization.
