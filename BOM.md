# Nomenclature Complète des Composants (BOM)

Inventaire complet des **60 composants** du projet **Scanner OBD-II ESP32**, extrait directement du projet actif sous EasyEDA Pro (Schéma complet validé DRC / ERC = 0).

---

## 1. Tableau Récapitulatif de la Nomenclature

| Désignateur | Valeur (`Value`) | Référence Fabricant (`Device`) | Empreinte (`Footprint`) | Rôle & Fonction Électrique |
| :--- | :--- | :--- | :--- | :--- |
| **C1** | 100nF | CL10B104KB8NNNC | `C0603` | Découplage alimentation ESP32 (rail 3.3V) |
| **C2** | 100nF | CL10B104KB8NNNC | `C0603` | Découplage alimentation ESP32 (rail 3.3V) |
| **C3** | 100nF | CL10B104KB8NNNC | `C0603` | Découplage alimentation transceiver CAN `U2` |
| **C4** | 100nF | CL10B104KB8NNNC | `C0603` | Découplage alimentation transceiver K-Line `U3` |
| **C5** | 1uF | CL10A105KA8NNNC | `C0603` | Bootstrap convertisseur Buck `U4` (broches BOOT → PH) |
| **C6** | 1uF | CL10A105KA8NNNC | `C0603` | Filtrage sortie régulateur LDO `U5` (rail 3.3V) |
| **C7** | 10uF | CL31A106KBHNNNE (C14236) | `C1206` | Condensateur réservoir entrée Buck `U4` qualifié 50V X5R (Basic Part JLCPCB) |
| **C8** | 22uF | TCC1206X5R226K250HT | `C1206` | Condensateur filtrage sortie Buck `U4` (dérivation rail 5V vers GND) |
| **C9** | 3.3nF | CL10B332KB8NNNC | `C0603` | Condensateur de compensation de boucle Buck `U4` (broche COMP vers GND) |
| **C10** | 100nF | CL10B104KB8NNNC | `C0603` | Filtrage HF et réservoir de charge ADC pont diviseur batterie `VBAT_SENSE` |
| **C11** | 10uF | CL21A106KAYNNNE (C15850) | `C0805` | Condensateur réservoir local Bulk 10 µF 25V X5R (absorption pics Wi-Fi 500 mA - Basic Part) |
| **C12** | 1uF | CL10A105KB8NNNC (C15849) | `C0603` | Temporisation RC Power-On-Reset (10 ms) et filtre anti-rebond broche `EN` (Basic Part) |
| **D1** | *—* | SMBJ18A_C5860928 | `SMB_L4.6-W3.6-LS5.3-RD` | Diode TVS 18V unidirectionnelle (écrêtage 29.2V protégeant U4 TPS54331) |
| **D2** | *—* | SS34_C52023881 | `SMA_L4.3-W2.6-LS5.1-RD` | Diode Schottky 40V 3A de roue libre (Cathode sur PH, Anode sur GND) pour convertisseur Buck `U4` |
| **D3** | *—* | BZX84C12 | `SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR` | Diode Zener 12V d'écrêtage tension Grille-Source Vgs P-MOSFET Q1 |
| **D4** | BAT54CW | BAT54CW (C962771) | `sot-323-3_l2.0-w1.3-p1.30-ls2.1-br` | Diode Schottky double 30V 2x200mA cathode commune (alimentation autonome USB et protection anti-retour) |
| **D5** | 24V | SMF24CA (C3117728) | `SOD-123FL_L2.8-W1.8-LS3.7-BI` | Diode TVS 24V bidirectionnelle protection transitoire ligne K-Line (`K_LINE`) |
| **F1** | *—* | MF-MSMF050-2 | `F1812` | Fusible réarmable PPTC 0.5A protection ligne 12V |
| **FB1** | *—* | BLM18PG121SN1D_C14709 | `L0603` | Perle de ferrite pour filtrage HF du rail 3.3V LDO |
| **J1** | *—* | OBD2-M-90D | `CONN-TH_OBD2` | Connecteur mâle OBD-II standard SAE J1962 coudé 90° (16 broches traversantes) |
| **J2** | *—* | TYPE-C-31-M-12 | `USB-C_SMD-TYPE-C-31-M-12_1` | Connecteur USB Type-C 16 broches horizontal CMS (flash, debug et banc 5V) |
| **JP1** | PZ2.54-1*2 | PZ2.54-1*2 (C6180457) | `hdr-th_2p-p2.54-v-m-3` | Cavalier sélecteur terminaison CAN 120Ω (Shunt requis sur banc de test ; ouvert par défaut en voiture) |
| **L1** | 10uH | YNR6045-100M | `IND-SMD_L6.0-W6.0` | Inductance blindée 10µH étage Buck `U4` |
| **LED1** | *—* | PSC-1608U52GC-G4 | `LED0603-RD_GREEN` | LED d'état verte pilotée par la broche IO2 de l'ESP32 |
| **Q1** | *—* | CJ2309A | `SOT-23-3_L2.9-W1.6-P1.90-LS2.8-BR` | P-MOSFET 60V 2A protection contre l'inversion de polarité 12V |
| **Q2** | *—* | 2N7002_C50176485 | `SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR` | N-MOSFET commande et commutation alimentation |
| **R1** | 10Ω | FRC0805F10R0TS | `R0805` | Résistance série amortissement ligne K-Line RX |
| **R2** | 10Ω | FRC0805F10R0TS | `R0805` | Résistance série amortissement ligne K-Line TX |
| **R3** | 5.1kΩ | 0805W8F5101T5E | `R0805` | Résistance pull-down USB-C configuration CC1 |
| **R4** | 5.1kΩ | 0805W8F5101T5E | `R0805` | Résistance pull-down USB-C configuration CC2 |
| **R5** | 10kΩ | 0805W8F1002T5E | `R0805` | Résistance de polarisation grille N-MOSFET Q2 |
| **R6** | 100Ω | 0805W8F1000T5E (C17408) | `R0805` | Résistance de limitation de courant LED1 (3.6 mA, visibilité plein jour) |
| **R7** | 10kΩ | 0805W8F1002T5E | `R0805` | Résistance de maintien pull-up grille P-MOSFET Q1 |
| **R8** | 120Ω | 0805W8F1200T5E | `R0805` | Résistance de terminaison de ligne différentielle CAN |
| **R9** | 10kΩ | 0805W8F1002T5E | `R0805` | Résistance haute pont diviseur feedback Buck `U4` (rail 5V vers VSENSE) |
| **R10** | 1.91kΩ | 0805W8F1911T5E | `R0805` | Résistance basse pont diviseur feedback Buck `U4` (VSENSE vers GND) |
| **R11** | 10kΩ | 0805W8F1002T5E | `R0805` | Résistance série compensation de boucle Buck `U4` (broche COMP) |
| **R12** | 100kΩ | 0805W8F1003T5E | `R0805` | Résistance haute pont diviseur monitoring tension batterie (+12V_PROT vers VBAT_SENSE) |
| **R13** | 20kΩ | 0805W8F2002T5E | `R0805` | Résistance basse pont diviseur monitoring tension batterie (VBAT_SENSE vers GND) |
| **R14** | 10kΩ | 0805W8F1002T5E | `R0805` | Résistance série limitation courant Zener D3 commande grille Q1 |
| **R15** | 10kΩ | 0805W8F1002T5E (C17414) | `R0805` | Résistance de pull-up externe broche `EN` vers le rail `3.3V` (Basic Part) |
| **SW1** | *—* | TS-1187A-C-A-B (C318884) | `SW-SMD_4P-L5.1-W5.1-P3.70-LS6.5-TL_H1.5` | Bouton poussoir tactile CMS de reset matériel (accessible via trou d'épingle boîtier) |
| **TP1** | *—* | Test-Point | `Test-Point-0.5mm` | Point de test pad cuivre pour le rail 5V USB (`VBUS_5V`) |
| **TP2** | K_LINE | Test-Point | `Test-Point-0.5mm` | Point de test pad cuivre pour la ligne K-Line ISO 9141-2 (`K_LINE`) |
| **TP3** | GND | Test-Point | `Test-Point-0.5mm` | Point de test pad cuivre pour la masse commune de référence (`GND`) |
| **TP4** | +12V_PROT | Test-Point | `Test-Point-0.5mm` | Point de test pad cuivre pour le rail 12V sécurisé (`+12V_PROT`) |
| **TP5** | +5V | Test-Point | `Test-Point-0.5mm` | Point de test pad cuivre pour le rail 5V régulé Buck (`+5V`) |
| **TP6** | 3.3V | Test-Point | `Test-Point-0.5mm` | Point de test pad cuivre pour le rail logique 3.3V filtré (`3.3V`) |
| **TP7** | CANH | Test-Point | `Test-Point-0.5mm` | Point de test pad cuivre pour la ligne différentielle CAN High (`CANH`) |
| **TP8** | CANL | Test-Point | `Test-Point-0.5mm` | Point de test pad cuivre pour la ligne différentielle CAN Low (`CANL`) |
| **TP9** | VBAT_SENSE | Test-Point | `Test-Point-0.5mm` | Point de test pad cuivre pour la mesure analogique tension batterie (`VBAT_SENSE`) |
| **TP10** | IO0 | Test-Point | `Test-Point-0.5mm` | Point de test pad cuivre pour forcer le mode bootloader de secours (`IO0` / Pin 27) |
| **TP11** | EN | Test-Point | `Test-Point-0.5mm` | Point de test pad cuivre pour le signal de reset matériel (`ESP_EN` / Pin 3) |
| **U1** | 2.4GHz | ESP32-S3-WROOM-1-N16R8 | `WIRELM-SMD_ESP32-S3-WROOM-1` | SoC ESP32-S3 Wi-Fi 2.4 GHz + BLE 5.0 (16MB Flash / 8MB PSRAM) |
| **U2** | *—* | TJA1051T/3/1J | `SOIC-8_L4.9-W3.9-P1.27-LS6.0-BL` | Transceiver CAN haute vitesse avec broche VIO (3.3V) |
| **U3** | *—* | E-L9637D013TR | `SOIC-8_L4.9-W3.9-P1.27-LS6.0-BL` | Transceiver K-Line ISO 9141 / KWP2000 |
| **U4** | *—* | TPS54331DR | `SOIC-8_L5.0-W4.0-P1.27-LS6.0-BL` | Régulateur abaisseur Step-Down Buck 12V → 5V, 3A |
| **U5** | *—* | LDL1117S33R | `SOT-223-4_L6.5-W3.5-P2.30-LS7.0-BR` | Régulateur linéaire LDO 5V → 3.3V faible bruit, 1.2A |
| **U6** | *—* | SD05C_C53238084 | `SOD-323_L1.7-W1.3-LS2.5-BI` | Diode ESD bidirectionnelle protection ligne USB D+ |
| **U7** | *—* | SD05C_C53238084 | `SOD-323_L1.7-W1.3-LS2.5-BI` | Diode ESD bidirectionnelle protection ligne USB D- |
| **U8** | 24V | NUP2105LT1G (C5983786) | `SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR` | Diode double TVS 24V bidirectionnelle protection transitoire/ESD bus CAN (`CANH`/`CANL`) |

---

## 2. Optimisation Assemblage JLCPCB (Basic Parts)

Afin de réduire les coûts d'assemblage CMS automatisé chez JLCPCB (suppression des frais de changement de bobine *Extended Parts*), les composants passifs suivants sont sélectionnés en catégorie **Basic Part** :

* **`C7` (10 µF 50V 1206) :** `CL31A106KBHNNNE` (LCSC `C14236`) — Basic Part
* **`C11` (10 µF 25V 0805) :** `CL21A106KAYNNNE` (LCSC `C15850`) — Basic Part
* **`C12` (1 µF 50V 0603) :** `CL10A105KB8NNNC` (LCSC `C15849`) — Basic Part
* **`R6` (100 Ω 0805) :** `0805W8F1000T5E` (LCSC `C17408`) — Basic Part
* **`R15` (10 kΩ 0805) :** `0805W8F1002T5E` (LCSC `C17414`) — Basic Part
