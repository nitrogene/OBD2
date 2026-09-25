# Nomenclature Complète des Composants (BOM)

Inventaire exhaustif des **66 composants** du projet **Scanner OBD-II ESP32**, synchronisé en temps réel avec le schéma actif sous EasyEDA Pro (ERC = 0, DRC = 0).

---

## 1. Tableau Récapitulatif de la Nomenclature Complète

| Désignateur | Valeur (`Value`) | Référence Fabricant (`MPN`) | Code LCSC | Statut JLCPCB | Empreinte (`Package`) | Rôle & Fonction Électrique |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **C1** | 100nF | `CC0603KRX7R9BB104` | `C14663` | **Basic Part** | `0603` | Découplage alimentation ESP32 (rail 3.3V) |
| **C2** | 100nF | `CC0603KRX7R9BB104` | `C14663` | **Basic Part** | `0603` | Découplage alimentation ESP32 (rail 3.3V) |
| **C3** | 100nF | `CC0603KRX7R9BB104` | `C14663` | **Basic Part** | `0603` | Découplage alimentation transceiver CAN U2 (rail 3.3V VIO) |
| **C4** | 100nF | `CC0603KRX7R9BB104` | `C14663` | **Basic Part** | `0603` | Découplage alimentation transceiver K-Line U3 (rail 3.3V VCC) |
| **C5** | 1uF | `CL10A105KB8NNNC` | `C15849` | **Basic Part** | `0603` | Bootstrap convertisseur Buck U4 (broches BOOT → PH) |
| **C6** | 1uF | `CL10A105KB8NNNC` | `C15849` | **Basic Part** | `0603` | Filtrage sortie régulateur LDO U5 (rail 3.3V) |
| **C7** | 10uF | `CL31A106KBHNNNE` | `C13585` | **Basic Part** | `1206` | Condensateur réservoir entrée Buck U4 qualifié 50V X5R |
| **C8** | 22uF | `TCC1206X5R226K250HT` | `C5448922` | Extended Part | `1206` | Condensateur filtrage sortie Buck U4 (dérivation rail 5V vers GND) |
| **C9** | 3.3nF | `CL10B332KB8NNNC` | `C1613` | **Basic Part** | `0603` | Condensateur de compensation de boucle Buck U4 (broche COMP vers GND) |
| **C10** | 100nF | `CC0603KRX7R9BB104` | `C14663` | **Basic Part** | `0603` | Filtrage HF et réservoir de charge ADC pont diviseur batterie VBAT_SENSE |
| **C11** | 10uF | `CL21A106KAYNNNE` | `C15850` | **Basic Part** | `0805` | Condensateur réservoir local Bulk 10 µF 25V X5R (pics Wi-Fi 500 mA) |
| **C12** | 1uF | `CL10A105KB8NNNC` | `C15849` | **Basic Part** | `0603` | Temporisation RC Power-On-Reset (10 ms) et filtre anti-rebond broche EN |
| **C13** | 220pF | `CL10B221KB8NNNC` | `C1603` | **Basic Part** | `0603` | Condensateur compensation HF boucle Buck U4 (Samsung 50V X7R) |
| **C14** | 100nF | `CC0603KRX7R9BB104` | `C14663` | **Basic Part** | `0603` | Découplage HF entrée Buck U4 (rail +12V_PROT vers GND) |
| **C15** | 100nF | `CC0603KRX7R9BB104` | `C14663` | **Basic Part** | `0603` | Découplage HF transceiver CAN U2 (rail +5V vers GND) |
| **D1** | — | `SMBJ18A` | `C5860928` | Extended Part | `SMB` | Diode TVS 18V unidirectionnelle (écrêtage 29.2V protégeant U4 TPS54331) |
| **D2** | — | `SS34` | `C8678` | **Basic Part** | `SMA` | Diode Schottky 40V 3A de roue libre pour convertisseur Buck U4 (MDD) |
| **D3** | — | `BZX84C12` | `C21547682` | Extended Part | `SOT-23` | Diode Zener 12V d'écrêtage tension Grille-Source Vgs P-MOSFET Q1 (DOWO) |
| **D4** | — | `BAT54CW` | `C962771` | Extended Part | `SOT-323-3` | Diode Schottky double 30V cathode commune (banc USB et anti-retour) |
| **D5** | — | `SMF24CA` | `C2891487` | Extended Part | `SOD-123FL` | Diode TVS 24V bidirectionnelle protection transitoire K-Line |
| **D6** | — | `BAT54WS` | `C17702994` | Extended Part | `SOD-323` | Diode Schottky rapide de clamp protection surtension ADC VBAT_SENSE |
| **F1** | — | `MF-MSMF050-2` | `C17313` | Extended Part | `1812` | Fusible réarmable PPTC 0.5A protection ligne 12V |
| **FB1** | — | `BLM18PG121SN1D` | `C14709` | **Basic Part** | `0603` | Perle de ferrite pour filtrage HF du rail 3.3V LDO |
| **J1** | — | `OBD2-male-16pin` | `C9900147921` | Extended Part | `弯插,P=4mm,16P` | Connecteur mâle OBD-II standard SAE J1962 coudé 90° (16 broches traversantes) |
| **J2** | — | `TYPE-C-31-M-12` | `C165948` | Extended Part | `SMD` | Connecteur USB Type-C 16 broches horizontal CMS (flash, debug et banc 5V) |
| **JP1** | — | `PZ2.54-1*2` | `C5360898` | Extended Part | `插件,P=2.54mm` | Cavalier sélecteur terminaison CAN 120Ω (Shunt = Banc ; Ouvert = Voiture) |
| **L1** | 10uH | `YNR6045-100M` | `C341067` | Extended Part | `SMD,6x6mm` | Inductance blindée 10µH étage Buck U4 |
| **LED1** | — | `PSC-1608U52GC-G4` | `C22371297` | Extended Part | `0603` | LED d'état verte pilotée par la broche IO2 de l'ESP32 |
| **Q1** | — | `CJ2309A` | `C7433254` | Extended Part | `SOT-23` | P-MOSFET 60V 2A protection contre l'inversion de polarité 12V |
| **Q2** | — | `2N7002` | `C8545` | **Basic Part** | `SOT-23` | N-MOSFET commande et commutation alimentation |
| **R1** | 10Ω | `0805W8F100JT5E` | `C17415` | **Basic Part** | `0805` | Résistance série amortissement ligne K-Line RX |
| **R2** | 10Ω | `0805W8F100JT5E` | `C17415` | **Basic Part** | `0805` | Résistance série amortissement ligne K-Line TX |
| **R3** | 5.1kΩ | `0805W8F5101T5E` | `C27834` | **Basic Part** | `0805` | Résistance pull-down USB-C configuration CC1 (5.1 kΩ) |
| **R4** | 5.1kΩ | `0805W8F5101T5E` | `C27834` | **Basic Part** | `0805` | Résistance pull-down USB-C configuration CC2 (5.1 kΩ) |
| **R5** | 10kΩ | `0805W8F1002T5E` | `C17414` | **Basic Part** | `0805` | Résistance de polarisation grille N-MOSFET Q2 (10 kΩ) |
| **R6** | 100Ω | `0805W8F1000T5E` | `C17408` | **Basic Part** | `0805` | Résistance de limitation courant LED1 (100 Ω, 3.6 mA visibilité habitacle) |
| **R7** | 10kΩ | `0805W8F1002T5E` | `C17414` | **Basic Part** | `0805` | Résistance de maintien pull-up grille P-MOSFET Q1 (10 kΩ) |
| **R8** | 120Ω | `0805W8F1200T5E` | `C17437` | **Basic Part** | `0805` | Résistance de terminaison de ligne différentielle CAN (120 Ω) |
| **R9** | 10kΩ | `0805W8F1002T5E` | `C17414` | **Basic Part** | `0805` | Résistance haute pont diviseur feedback Buck U4 (rail 5V vers VSENSE, 10 kΩ) |
| **R10** | 1.91kΩ | `0805W8F1911T5E` | `C17401` | Extended Part | `0805` | Résistance basse pont diviseur feedback Buck U4 (VSENSE vers GND, 1.91 kΩ) |
| **R11** | 10kΩ | `0805W8F1002T5E` | `C17414` | **Basic Part** | `0805` | Résistance série compensation de boucle Buck U4 (broche COMP, 10 kΩ) |
| **R12** | 100kΩ | `0805W8F1003T5E` | `C149504` | **Basic Part** | `0805` | Résistance haute pont diviseur monitoring tension batterie (100 kΩ) |
| **R13** | 12kΩ | `0805W8F1202T5E` | `C17444` | **Basic Part** | `0805` | Résistance basse pont diviseur monitoring tension batterie (12 kΩ) |
| **R14** | 10kΩ | `0805W8F1002T5E` | `C17414` | **Basic Part** | `0805` | Résistance série limitation courant Zener D3 commande grille Q1 (10 kΩ) |
| **R15** | 10kΩ | `0805W8F1002T5E` | `C17414` | **Basic Part** | `0805` | Résistance de pull-up externe broche EN vers rail 3.3V (10 kΩ) |
| **R16** | 1kΩ | `1206W4F1001T5E` | `C4410` | **Basic Part** | `1206` | Résistance de pull-up normalisée ISO 9141-2 (+12V_PROT vers K_LINE, 1 kΩ 1206) |
| **SW1** | — | `TS-1187A-B-A-B` | `C318884` | **Basic Part** | `SMD` | Bouton poussoir tactile CMS de reset matériel (trou d'épingle boîtier, 160 gf) |
| **TP1** | VBUS_5V | `—` | *—* | — | `—` | Point de test pad cuivre pour le rail 5V USB (VBUS_5V) |
| **TP2** | K_LINE | `—` | *—* | — | `—` | Point de test pad cuivre pour la ligne K-Line ISO 9141-2 (K_LINE) |
| **TP3** | GND | `—` | *—* | — | `—` | Point de test pad cuivre pour la masse commune de référence (GND) |
| **TP4** | +12V_PROT | `—` | *—* | — | `—` | Point de test pad cuivre pour le rail 12V sécurisé (+12V_PROT) |
| **TP5** | +5V | `—` | *—* | — | `—` | Point de test pad cuivre pour le rail 5V régulé Buck (+5V) |
| **TP6** | 3.3V | `—` | *—* | — | `—` | Point de test pad cuivre pour le rail logique 3.3V filtré (3.3V) |
| **TP7** | CANH | `—` | *—* | — | `—` | Point de test pad cuivre pour la ligne différentielle CAN High (CANH) |
| **TP8** | CANL | `—` | *—* | — | `—` | Point de test pad cuivre pour la ligne différentielle CAN Low (CANL) |
| **TP9** | VBAT_SENSE | `—` | *—* | — | `—` | Point de test pad cuivre pour la mesure analogique tension batterie (VBAT_SENSE) |
| **TP10** | IO0 | `—` | *—* | — | `—` | Point de test pad cuivre pour forcer le mode bootloader de secours (IO0) |
| **TP11** | EN | `—` | *—* | — | `—` | Point de test pad cuivre pour le signal de reset matériel (ESP_EN) |
| **U1** | 2.4GHz | `ESP32-S3-WROOM-1-N16R8` | `C2913202` | Extended Part | `SMD,25.5x18mm` | SoC ESP32-S3 Wi-Fi 2.4 GHz + BLE 5.0 (16MB Flash / 8MB PSRAM) |
| **U2** | — | `TJA1051T/3/1J` | `C38695` | Extended Part | `SOIC-8-150mil` | Transceiver CAN haute vitesse avec broche VIO (3.3V) |
| **U3** | — | `E-L9637D013TR` | `C153038` | Extended Part | `SOIC-8` | Transceiver K-Line ISO 9141 / KWP2000 |
| **U4** | — | `TPS54331DR` | `C9865` | Extended Part | `SOIC-8` | Régulateur abaisseur Step-Down Buck 12V → 5V, 3A (570 kHz) |
| **U5** | — | `LDL1117S33R` | `C435835` | Extended Part | `SOT-223-4` | Régulateur linéaire LDO 5V → 3.3V faible bruit, 1.2A |
| **U6** | — | `SESD05C` | `C720025` | Extended Part | `SOD-323` | Diode ESD bidirectionnelle 5V protection ligne USB D+ (Semiware) |
| **U7** | — | `SESD05C` | `C720025` | Extended Part | `SOD-323` | Diode ESD bidirectionnelle 5V protection ligne USB D- (Semiware) |
| **U8** | — | `NUP2105LT1G` | `C5261087` | Extended Part | `SOT-23` | Diode double TVS 24V bidirectionnelle protection transitoire/ESD bus CAN |

---

## 2. Analyse des Coûts d'Assemblage JLCPCB (Basic vs Extended Parts)

Sur les **66 composants** du circuit (dont 11 points de test sans composant physique à poser) :

- **Composants physiques à assembler :** 55 composants.
- **Basic Parts (0 $ de frais de chargement) :** **33 composants** (60% des composants assemblés).
- **Extended Parts (~3 $ par bobine changée) :** **22 composants** (strict minimum technique).

### A. Liste des Composants actuellement qualifiés en **Basic Part**

* **`C1`, `C2`, `C3`, `C4`, `C10`, `C14`, `C15`** (100nF 50V, `0603`) : `CC0603KRX7R9BB104` — LCSC `C14663` (**Basic Part**)
* **`C5`, `C6`, `C12`** (1uF 50V, `0603`) : `CL10A105KB8NNNC` — LCSC `C15849` (**Basic Part**)
* **`C7`** (10uF 50V, `1206`) : `CL31A106KBHNNNE` — LCSC `C13585` (**Basic Part**)
* **`C9`** (3.3nF, `0603`) : `CL10B332KB8NNNC` — LCSC `C1613` (**Basic Part**)
* **`C11`** (10uF 25V, `0805`) : `CL21A106KAYNNNE` — LCSC `C15850` (**Basic Part**)
* **`C13`** (220pF 50V, `0603`) : `CL10B221KB8NNNC` — LCSC `C1603` (**Basic Part**)
* **`D2`** (—, `SMA`) : `SS34` — LCSC `C8678` (**Basic Part**)
* **`FB1`** (—, `0603`) : `BLM18PG121SN1D` — LCSC `C14709` (**Basic Part**)
* **`Q2`** (—, `SOT-23`) : `2N7002` — LCSC `C8545` (**Basic Part**)
* **`R1`, `R2`** (10Ω, `0805`) : `0805W8F100JT5E` — LCSC `C17415` (**Basic Part**)
* **`R3`, `R4`** (5.1kΩ, `0805`) : `0805W8F5101T5E` — LCSC `C27834` (**Basic Part**)
* **`R5`, `R7`, `R9`, `R11`, `R14`, `R15`** (10kΩ, `0805`) : `0805W8F1002T5E` — LCSC `C17414` (**Basic Part**)
* **`R6`** (100Ω, `0805`) : `0805W8F1000T5E` — LCSC `C17408` (**Basic Part**)
* **`R8`** (120Ω, `0805`) : `0805W8F1200T5E` — LCSC `C17437` (**Basic Part**)
* **`R12`** (100kΩ, `0805`) : `0805W8F1003T5E` — LCSC `C149504` (**Basic Part**)
* **`R13`** (12kΩ, `0805`) : `0805W8F1202T5E` — LCSC `C17444` (**Basic Part**)
* **`R16`** (1kΩ, `1206`) : `1206W4F1001T5E` — LCSC `C4410` (**Basic Part**)
* **`SW1`** (—, `SMD`) : `TS-1187A-B-A-B` — LCSC `C318884` (**Basic Part**)

### B. Dernière Opportunité d'Optimisation (Passage en Basic Part)

* **`C8` (Capacité de sortie Buck) :** Actuellement `C5448922` (22 µF 1206 25V - Extended Part) ; peut être remplacé par 2 × 10 µF 50V 1206 (`C13585` - Basic Part déjà présente en BOM) en parallèle pour réduire le DC-bias et supprimer les frais de setup SMT.

### C. Synthèse de l'Optimisation des Coûts

L'ensemble des composants passifs, boutons et semi-conducteurs standards éligibles à une correspondance parfaite sont désormais basculés en **Basic Part** (12 composants basculés au total, soit **~36 $ d'économie de frais de bobines** sur chaque série). Les 22 autres composants restants sont strictement justifiés par l'architecture automobile (tenue 60V de `Q1`, LDO ultra-faible chute `U5`, derating 25V de `C8`, précision E96 de `R10`, protections transitoires et circuits intégrés dédiés).


