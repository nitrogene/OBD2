# Feuille de Route & Checklist Active (TODO)

Ce document constitue le plan d'action opérationnel du projet **Scanner OBD-II ESP32**.
Il suit la conception matérielle (schéma, placement, routage, fabrication) et logicielle (firmware ESP32).

---

## Phase 1 : Schéma Électrique & Nomenclature (BOM)

### 1.1 Correctifs critiques & robustesse (issus des revues techniques)
- [x] **[CONFORME / VALIDÉ] Câblage d'alimentation, de mode et terminaison du transceiver CAN `U2` (TJA1051T) :** Pontage erroné supprimé entre broche 2 (`GND`) et broche 3 (`VCC`), broche 2 reliée à `GND`, broche 8 (`S`) reliée à `GND` (mode silencieux désactivé, communication active), broche 3 sous `+5V` avec découplage `C15` (100 nF) vers `GND` sans croisement de `RXD`, et cavalier `JP1` recâblé strictement en série avec la terminaison `R8` (120 Ω) entre `CANH` et `CANL` (page 2 du schéma validée).
- [x] **[CONFORME / VALIDÉ] Sécuriser la grille du N-MOS `Q2` (2N7002) contre le claquage diélectrique sous Load-Dump :** Pont diviseur 1:2 (10 kΩ / 10 kΩ via `R5` et `R17`) câblé sur la grille de `Q2` vers la masse `GND`, bornant strictement $V_{GS}$ à 14.6 V (bien sous la limite absolue de $\pm 20\,\text{V}$) lors des transitoires d'alternateur à 29.2 V.
- [x] **[CONFORME / VALIDÉ] Raccordement de la broche VS de `U3` (L9637D) [I4] :** Broche 7 (VS) de `U3` et pull-up `R16` (1 kΩ) raccordées au rail sécurisé `+12V_PROT` (après le fusible `F1` et le MOSFET anti-inversion `Q1`) via NetPorts dédiés.
- [x] **[CONFORME / VALIDÉ] Alimentation logique VCC de `U3` (L9637D) [B3] :** Maintenue sous le rail régulé `3.3V` (LDO). *Justification technique :* La plage admissible de $V_{CC}$ s'étend de 3.0V à 7.0V (Table 5 datasheet ST L9637D, avec note 1 : *« Specs are tested at 5 V only. Compliance on Vcc full range is guaranteed by design »*). La broche RX intégrant un pull-up actif interne vers $V_{CC}$ ($R_{RX} \approx 10\,\text{k}\Omega$, $V_{RXH} = V_{CC} - 0.1\,\text{V}$), alimenter $V_{CC}$ en 5V injecterait ~4.9V dans le GPIO4 de l'ESP32-S3 qui n'est pas tolérant 5V (limite absolue à 3.6V), provoquant sa destruction. Le raccordement 3.3V actuel est 100% conforme et protège le MCU.
- [x] **[CONFORME / VALIDÉ] Calibrer le fusible réarmable `F1` pour la robustesse thermique [I3 review002] :** Fusible PPTC remplacé par le modèle Littelfuse `1812L110/33MR` (boîtier 1812, $I_{HOLD} = 1.10\,\text{A}$, $V_{MAX} = 33.0\,\text{V}$, LCSC `C142747`). Maintient $I_{HOLD} \ge 0.75\,\text{A}$ à 60°C (éliminant tout déclenchement intempestif sous forte chaleur habitacle et pics Wi-Fi), tout en garantissant une tenue sécurisée sous transitoires jusqu'à 33 V.
- [x] **[CONFORME / VALIDÉ] Ajouter un condensateur de Slow-Start $C_{SS}$ sur la broche 4 (`SS`) de `U4` (TPS54331) [I1] :** Condensateur céramique `C17` = 10 nF 50V 0603 (*Basic Part* JLCPCB `C57112`) câblé entre la broche 4 (`SS`) et la masse `GND`. Temps de démarrage progressif calibré à $T_{SS} = 4.0\,\text{ms}$, supprimant l'inrush brutal et tout risque de surtension (*overshoot*) sur le rail +5V lors du branchement à chaud sur le véhicule.
- [x] **[CONFORME / VALIDÉ] Sécuriser la stabilité de boucle du LDO `U5` (LDL1117S33R) [I2] :** Condensateur `C6` porté à 10 µF 50V 1206 (*Basic Part* LCSC `C13585`) pour satisfaire l'exigence formelle $C_{OUT} \ge 4.7\,\mu\text{F}$ de la datasheet ST directement sur l'étage de sortie du régulateur.
- [x] **[CONFORME / VALIDÉ] Raccorder la broche 2 (`VOUT`) de `U5` (LDL1117S33R) au net `3.3V_PRE` [I3 review002] :** Broche 2 raccordée au net `3.3V_PRE` via un NetPort dédié, assurant la continuité électrique avec la broche 4 (`VOUT` / TAB) pour maximiser la dissipation thermique sur le plan de cuivre PCB.
- [x] **[CONFORME / VALIDÉ] Implanter le pont diviseur UVLO sur la broche 3 (`EN`) de `U4` (TPS54331) [I4 review002] :** Calibré avec le couple 100% *Basic Parts* JLCPCB `R19` = 470 kΩ 0805 (`C17709`) entre `+12V_PROT` et `EN`, et `R20` = 68 kΩ 0805 (`C17801`) entre `EN` et `GND`. Calibre un seuil de coupure franche à $V_{STOP} = 8.01\,\text{V}$ et un seuil d'enclenchement net à $V_{START} = 9.42\,\text{V}$ avec une hystérésis robuste de $1.41\,\text{V}$, prévenant tout phénomène de pompage (*chattering*) lors des pics de transmission Wi-Fi et toute corruption de mémoire Flash NVS (page 1 du schéma validée).
- [x] **[CONFORME / VALIDÉ] Réassigner les broches TWAI CAN de l'ESP32-S3 pour libérer l'UART0 [I1 review002] :** Bus CAN déplacé depuis GPIO43/GPIO44 (UART0 console/boot) vers les **GPIO15 (pin 8) et GPIO16 (pin 9)** de `U1`. NetPorts renommés en **`TWAI_TX`** (broche 8 ESP32 et broche 1 `TXD` de `U2` TJA1051T) et **`TWAI_RX`** (broche 9 ESP32 et broche 4 `RXD` de `U2` TJA1051T), éliminant tout risque de collision série / boot. NetPorts K-Line également harmonisés en **`KLINE_RX`** (broche 4 ESP32 et `R1`) et **`KLINE_TX`** (broche 5 ESP32 et `R2`) (pages 2, 3 et 4 du schéma validées).
- [x] **[CONFORME / VALIDÉ] Basculer le SoC `U1` vers `ESP32-S3-WROOM-1-N16R2` (tenue thermique 85°C) [I2 review002] :** Module basculé sous la référence Quad-PSRAM `ESP32-S3-WROOM-1-N16R2` (LCSC `C2913205`, 16 Mo Flash, 2 Mo Quad-PSRAM) certifiée –40°C à +85°C native pour habitacle automobile, libérant les broches IO35, IO36, IO37 (page 4 du schéma validée pour U1).
- [x] **[CONFORME / VALIDÉ] Doubler la résistance de pull-up K-Line en 2 × 1 kΩ 1206 en parallèle (`R16` // `R18`) [I5 review002] :** Seconde résistance de 1 kΩ 1206 (`R18`, *Basic Part* `C4410`) implantée en parallèle direct avec `R16` entre `+12V_PROT` et `K_LINE` (page 3 du schéma), abaissant la pull-up normalisée ISO 9141-2 à 500 Ω ($t_r < 2\,\mu\text{s}$ sur faisceau capacitif 2 nF) et répartissant les 415 mW de dissipation crête en 2 × 207 mW sous la limite de 250 mW par boîtier 1206 (page 3 validée sous `R18`).
- [x] **[CONFORME / VALIDÉ] Remplacer la diode anti-retour banc `D4` par une Schottky de puissance [I6] :** Remplacée par la diode Schottky de puissance `B5819W SL` (LCSC `C8598`, boîtier SOD-123, 40 V / 1 A, *Basic Part* JLCPCB). Encaisse sans surchauffe ni chute excessive les pointes de consommation Wi-Fi (~500 mA) lors des sessions d'essais sur port USB-C et supprime les frais d'outillage SMT de 3,00 $ (page 4 du schéma validée).
- [x] **[CONFORME / VALIDÉ] Optimiser la marge de protection Buck `U4` (TVS `D1`) [M5 review] :** Remplacée par la TVS 600W unidirectionnelle `SMBJ16A` (LCSC `C353386`, boîtier `SMB`). Abaisse la tension d'écrêtage crête à $V_{CL} = 26.0\,\text{V}$ (au lieu de 29.2 V avec la SMBJ18A), garantissant une marge de sécurité robuste de **4.0 V** sous le seuil destructeur absolu de 30.0 V du convertisseur Buck `U4` (TPS54331) et réduisant la sollicitation de grille sur `Q2` (page 1 du schéma validée).
- [x] **[CONFORME / VALIDÉ] Ajouter une pull-up externe sur la broche de strapping `IO0` (`U1` pin 27 / `TP10`) [M1 review] :** Résistance de rappel externe `R21` = 10 kΩ 0805 (*Basic Part* `C17414`) implantée entre le rail 3.3V et la broche 27 (`IO0`), renforçant l'immunité au bruit en habitacle automobile et fiabilisant le boot normal depuis la Flash SPI face aux parasites (page 4 du schéma validée).
- [x] **[CONFORME / VALIDÉ] Ajouter un condensateur réservoir 10 µF sur `VBUS_5V` [M1 review002] :** Condensateur réservoir `C18` = 10 µF 50V 1206 (*Basic Part* `C13585`) implanté sur le net `VBUS_5V` en parallèle vers la masse au plus près du connecteur USB-C `J2`, absorbant les rebonds d'enfichage USB et amortissant les oscillations inductives de câble lors des sessions de mise au point sur banc (page 4 du schéma validée).
- [x] **[CONFORME / VALIDÉ] Modularité schéma : Rapprocher les symboles de découplage `C3` et `C4` [M2 review] :** Symbole `C3` déplacé sur la page 2 (au contact direct de la broche 5 `VIO` de `U2`) et symbole `C4` déplacé sur la page 3 (au contact direct de la broche 3 `VCC` de `U3`).
- [x] **[CONFORME / VALIDÉ] Modularité schéma : Rapatrier les condensateurs de découplage `C1` et `C2` sur la page 4 (ESP32-S3) [M2 review suite] :**
  - **Supprimer le bloc résiduel :** Bloc de découplage orphelin supprimé en bas à droite de la page 4.
  - **Positionnement & Câblage :** `C1` (100 nF) et `C2` (100 nF) implantés en parallèle direct avec le condensateur réservoir `C11` (10 µF) entre le rail `3.3V` (broche 2 `3V3` de `U1`) et la masse `GND` (broche 1 `GND` de `U1`).
  - **Nettoyage documentaire :** Purgé toute référence au « bloc de découplage » dans la documentation technique ([`HARDWARE.md`](HARDWARE.md), [`README.md`](README.md)), le découplage étant désormais intégralement modélisé au niveau local de chaque IC.
- [x] **[CONFORME / VALIDÉ] Sécuriser l'entrée non utilisée `LI` de `U3` (L9637D) sur `VS` (`+12V_PROT`) [M6 review002 arbitré] :** Broche 8 (`LI`) déconnectée de la masse et reliée directement à la broche 7 adjacente (`VS` / `+12V_PROT`), verrouillant le comparateur de ligne L au repos inactif ($V_{LI} = V_S > 0.55\,V_S$), supprimant tout risque d'antenne parasite CEM et annulant le courant de repos permanent ($0\,\mu\text{A}$) (page 3 du schéma validée).
- [x] **[CONFORME / VALIDÉ] Fiabiliser la mesure ADC de tension batterie face au courant de fuite de `D6` [M4 review] :** Diode Schottky `BAT54WS` remplacée sur le schéma (page 1) par la diode double silicium ultra-faible fuite `BAV199,215` (Nexperia, LCSC `C40919`, boîtier SOT-23, $I_R = 3\,\text{pA}$ typ à 25°C, $< 100\,\text{pA}$ à 85°C). Élimine rigoureusement la dérive thermique (erreur $\Delta V_{BAT} = I_R \times R_{12} < 0.01\,\text{mV}$ sur tout le domaine automobile au lieu de 0.5 V à 1.0 V) et procure un clamp rail-to-rail robuste (broche 1 à GND, broche 2 à 3.3V, broche 3 au point milieu `VBAT_SENSE`). Remplacement à coût d'outillage SMT neutre (page 1 du schéma validée).
- [x] **[CONFORME / VALIDÉ] Renforcer le boîtier de la résistance de terminaison CAN `R8` (120 Ω) :** Résistance `R8` basculée en boîtier 1206 via la référence `1206W4F1200T5E` (UNI-ROYAL, LCSC `C17909`, *Basic Part* JLCPCB, stock > 550k). Dissipation thermique nominale doublée à 250 mW (1/4 W vs 125 mW en 0805) et inertie thermique renforcée pour encaisser les surtensions transitoires en cas de court-circuit accidentel de la ligne CANH vers le rail batterie (+12V/+14V) avec `JP1` shunté. Coût d'outillage SMT nul (page 2 du schéma validée).
- [x] **[CONFORME / VALIDÉ] Compléter les points de test (Test Points) sur les nœuds critiques :** Mires de test pad cuivre CMS ajoutées dans le schéma pour le nœud de commutation Buck `PH_BUCK` (`TP12`), la broche de compensation `COMP_BUCK` (`TP13`), le rail intermédiaire LDO `3.3V_PRE` (`TP14`) sur la page 1 (Alimentation), et la ligne logique UART K-Line `KLINE_RX` (`TP15`) sur la page 3 (la ligne physique 12V K-Line étant déjà instrumentée par `TP2`). Portant le total à 15 points de test sans composant physique à approvisionner, facilitant le diagnostic oscilloscope et analyseur logique sur prototype.
- [x] **[CONFORME / VALIDÉ] [MINEUR M2, M3, M5 review002] Maintenance documentaire, Règle 0 et harmonisation projet :** Citations constructeur rectifiées dans [`DATASHEETS.md`](DATASHEETS.md) (bootstrap TI TPS54331 à 0.1 µF impératif, Table 5 Note 1 et Pin 3 pour L9637D VCC, C6 acté à 10 µF Basic Part), neutralisation de la Règle 0 dans les scripts et skills (`tps54331_compensation.py`, `easyeda_client.py`, `SKILL.md`), et harmonisation complète des références de l'archive projet vers `easyeda/OBD2.epro2` dans [`AGENTS.md`](AGENTS.md), [`AUTOMATION.md`](AUTOMATION.md) et [`README.md`](README.md).
- [x] **[CONFORME / VALIDÉ] Vérifier tous les NET PORTS (I, O, I/O) :** Audit exhaustif des 48 NetPorts du schéma physique (extraction binaire de `easyeda/OBD2.epro2` et vérification visuelle des planches HD). Correction de 11 ports qui étaient restés en bidirectionnel `BI` par défaut : signaux TWAI CAN (`TWAI_TX` en OUT MCU / IN transceiver, `TWAI_RX` en OUT transceiver / IN MCU), signaux UART K-Line (`KLINE_TX` en OUT MCU / IN transceiver, `KLINE_RX` en OUT transceiver / IN MCU), rails d'alimentation consommateurs en entrée `IN` sur page 3 (`+12V_PROT`, `3.3V`), et injection banc USB `+5V` en `OUT` sur page 4. Tous les flux électriques sont 100% cohérents.


### 1.2 Optimisation du catalogue (Bascule Basic Parts JLCPCB) & Revue de Schéma
- [x] **Bouton poussoir tactile `SW1` :** Remplacé `C480267` (*Extended*) par `C318884` (`TS-1187A-B-A-B` - *Basic Part*, même empreinte 5.1×5.1 mm).
- [x] **Capacité de sortie Buck `C8` / `C16` :** Remplacé la 22 µF 1206 *Extended* par 2 × 10 µF 50V 1206 (`C13585` - *Basic Part*) en parallèle (`C8`, `C16`) pour réduire le DC-bias et supprimer les frais de setup SMT.
- [x] **[CONFORME / VALIDÉ] Bascule Basic Part LED d'état `LED1` (0603) [review001 M1] :** Remplacement de la LED verte Extended `PSC-1608U52GC-G4` par la LED rouge Basic Part `KT-0603R` (LCSC `C2286`, boîtier 0603). Schéma EasyEDA mis à jour avec le symbole et device Basic Part, $V_F = 2.0\,\text{V}$, $I_F = 13.0\,\text{mA}$ sous $R_6 = 100\,\Omega$ ($P_{R6} = 16.9\,\text{mW}$), supprimant 3,00 $ de frais d'outillage SMT.
- [x] **[CONFORME / VALIDÉ] Bascule Basic Parts pont feedback Buck `R9` / `R10` [review001 M2, M3] :** Remplacement du couple R9 = 10 kΩ / R10 = 1.91 kΩ (Extended `C17401`) par R9 = 27 kΩ 0805 (*Basic Part* `C17593`) et R10 = 5.1 kΩ 0805 (*Basic Part* `C27834`), régulant Vout à 5.035 V (+0.7%) et supprimant les frais d'outillage de 3,00 $. Stabilité petit-signal auditée et confirmée ($\Phi_m = 66.3^\circ$, $F_{co} = 18.9\,\text{kHz}$).

### 1.3 Référentiel Technique & Datasheets ICs
- [x] **Créer le dossier `datasheet/` et le référentiel technique [`DATASHEETS.md`](DATASHEETS.md) :** Centralisation des 6 datasheets officielles (`U1` ESP32-S3, `U2` TJA1051T, `U3` L9637D, `U4` TPS54331, `U5` LDL1117S33R, `U8` NUP2105L), extraction des caractéristiques électriques, limites absolues (*Absolute Maximum Ratings*), règles d'implantation PCB (keepouts, boucles di/dt, thermiques) et matrice d'audit de conformité servant de source de vérité technique.

### 1.4 Architecture Bi-Mode (Banc ECU / Scanner OBD) & Connectique [review003]
- [x] **[CONFORME / VALIDÉ] Remplacement du connecteur OBD-II par un bornier PCB à ressort 5 contacts [review003 I2] :** Bornier PCB à ressort sans vis 5 contacts au pas 3.5 mm (Ningbo Kangnex `WJ250B-3.5-05P-11-00A`, LCSC `C8453`, 250V 8A, broches quinconce anti-arrachement, empreinte `CONN-TH_5P-P3.50_WJ250B-3.50-5P`). Implémentation physique validée sur la page 1 du schéma, contrôle ERC = 0 validé via API, affectation des 5 broches : Broche 4 `+12V`, Broche 8 `GND`, Broche 1 `K_LINE`, Broche 5 `CANH`, Broche 9 `CANL`. `BOM.md`, `circuit_semantics.json`, `floorplan.json` et `HARDWARE.md` 100% synchronisés.
- [x] **[CONFORME / VALIDÉ] Ajout d'un cavalier de débrayage de la pull-up K-Line [review003 I1] :** Embase mâle 1×2 broches au pas 2.54 mm (`JP2` : `PZ2.54-1*2`, LCSC `C5360898`) insérée en série stricte entre la pull-up 500 Ω (`R16` // `R18`) et la ligne `K_LINE` sur la page 3 du schéma (`easyeda/OBD2.epro2` et planche HD `SCH_Transceiver K-Line.png`). Contrôle ERC = 0 validé via API. Configuration bi-mode : ouvert par défaut en mode Voiture/Scanner ($R_{in} \ge 100\,\text{k}\Omega$ ISO 9141-2 sans shunt), fermé par shunt en mode Banc simulateur ECU (pull-up 500 Ω active). `BOM.md`, `circuit_semantics.json`, `HARDWARE.md` 100% synchronisés.
- [ ] **Découplage HF sur le rail d'alimentation USB-C VBUS [review003 M1] :** Ajouter un condensateur céramique de découplage de 100 nF 50V X7R 0603 (*Basic Part* `C14663`) en parallèle direct sur `VBUS_5V` au plus près du connecteur USB-C `J2` en complément du condensateur réservoir de 10 µF (`C18`) pour absorber les micro-transitoires lors des branchements à chaud sur PC.
- [x] **[CONFORME / VALIDÉ] Connecteurs de diagnostic & debug pour analyseur logique USB (`H1` et `H2`) :** Deux embases mâles 1×3 broches au pas 2.54 mm traversantes (`2.54-1*3P针`, LCSC `C49257`, empreinte `HDR-TH_3P-P2.54-V-M`) implantées sur le schéma : `H1` sur la page 3 (K-Line : broche 1 `KLINE_RX`, broche 2 `KLINE_TX`, broche 3 `GND`) et `H2` sur la page 2 (CAN : broche 1 `TWAI_RX`, broche 2 `TWAI_TX`, broche 3 `GND`), permettant le raccordement direct par câbles Dupont femelles d'un analyseur logique USB 24 MHz 8 voies pour espionnage et décodage simultané des protocoles. Planches HD exportées, `BOM.md`, `circuit_semantics.json`, `HARDWARE.md` et `floorplan.json` 100% synchronisés.
- [x] **[CONFORME / VALIDÉ] Vérification et alignement des codes LCSC pour `R18`, `R19` et `R20` (100% Basic Parts JLCPCB) :**
  - `R18` (pull-up K-Line 1 kΩ 1206) réassignée sur la *Basic Part* `1206W4F1001T5E_C4410` (LCSC `C4410`), partageant la même bobine que `R16` (économie de 3,00 $).
  - Clarification de l'erreur historique de review002 (`C17596` valait en réalité 28.7 Ω et `C17604` valait 2 kΩ, les 510 kΩ et 91 kΩ 0805 n'existant qu'en *Extended Parts*).
  - Pont UVLO recalculé et validé sur catalogue 100% *Basic Parts* JLCPCB : `R19` basculée à 470 kΩ 0805 (`0805W8F4703T5E`, LCSC `C17709`) et `R20` basculée à 68 kΩ 0805 (`0805W8F6802T5E`, LCSC `C17801`). Seuils nominaux $V_{START} = 9.42\,\text{V}$, $V_{STOP} = 8.01\,\text{V}$, hystérésis $\Delta V = 1.41\,\text{V}$ (économie nette de 6,00 $ d'outillage).
  - Implémentation physique validée sous EasyEDA Pro, schéma et archive `easyeda/OBD2.epro2` synchronisés, ERC = 0.
- [ ] **Documentation formelle des 3 cas d'usage cibles (`README.md`, `HARDWARE.md`) :** Rédiger les fiches d'architecture, schémas de câblage et tableaux d'état des cavaliers (cavalier CAN 120Ω et cavalier K-Line 500Ω) pour les 3 profils opérationnels : Cas 1 (Banc d'essais bi-cartes miroir avec alim de labo 12V et double USB-C), Cas 2 (Nominal véhicule via faisceau pigtail OBD-II), et Cas 3 (Nominal + Debug in situ avec PC sur batterie et règles d'isolation de masse).
- [ ] **Revue complète du schéma électronique :** Faire une revue systématique et approfondie de l'intégralité du schéma sous EasyEDA Pro en s'appuyant notamment sur [`DATASHEETS.md`](DATASHEETS.md) (vérification rigoureuse des préconisations constructeurs, alimentations, découplages, broches non connectées, seuils logiques et protections).

### 1.5 Validation Schéma
- [ ] Exécuter et valider le contrôle ERC sous EasyEDA Pro (0 erreur, 0 avertissement).
- [ ] Mettre à jour la documentation technique ([`HARDWARE.md`](HARDWARE.md), [`BOM.md`](BOM.md)).

---

## Phase 2 : Préparation & Placement PCB (Floorplanning)

### 2.1 Synchronisation & Mécanique
- [ ] Synchroniser le schéma vers le PCB (*« Update PCB from Schematic »* dans EasyEDA Pro) pour importer les nouvelles empreintes et aligner la netlist à 100%.
- [ ] Valider le contour mécanique (81.28 × 35.56 mm / 3200 × 1400 mil), l'affleurement de `J2` (USB-C) au Sud pour la coque et l'implantation du bornier 5P à l'Ouest.
- [ ] Mettre à jour [`floorplan.json`](floorplan.json) avec la BOM consolidée et injecter le placement initial (script de placement direct réutilisant le client pont d'API).

### 2.2 Agencement des clusters & Règles CEM de proximité (< 2 mm)
- [ ] **Bloc Puissance & Protection (Ouest) :** Compacité extrême de la boucle Buck SW-L1-D2-C8/C16, isolement de la broche COMP (`C13`, `R11`, `C9`) face au nœud bruité PH, diode clamp `D6` collée à `R13`/`C10` (< 2 mm).
- [ ] **Bloc Transceivers & Interfaces (Centre) :** Diodes TVS `U8` et `D5` collées à `J1` (< 5 mm), pull-up K-Line `R16` en zone aérée (< 5 mm de `J1`), cavalier de terminaison CAN `JP1` accessible.
- [ ] **Bloc USB-C & ESD (Sud) :** Diodes ESD `U6`/`U7` et résistances pull-down CC `R3`/`R4` alignées immédiatement sur les pastilles de `J2`.
- [ ] **Bloc ESP32-S3 & Radio (Est) :** Condensateur réservoir Bulk `C11` (10 µF) collé aux pins 1-2 (< 2 mm), filtre Reset `C12`/`R15` collé à la pin EN (< 2 mm), point de test `TP10` (`IO0`) accessible près de GND.

---

## Phase 3 : Routage, Plans de Masse & Finition PCB

### 3.1 Skill d'Auto-Routage FreeRouting (Remplacement de `pcb-placer`)
- [ ] **Développement & Intégration du skill `freerouting` :**
  - Supprimer le skill obsolète `.agents/skills/pcb-placer/` tout en récupérant ses briques réutilisables (client pont WebSocket/HTTP `easyeda_client.py`, parsing et schémas [`floorplan.json`](floorplan.json)).
  - Intégrer l'orchestration du moteur d'auto-routage FreeRouting (mode CLI headless) avec gestion automatique de l'environnement d'exécution sous Windows (ex. binaire autonome ou JRE portable).
  - Mettre en place le pipeline Specctra DSN / SES : export du fichier `.dsn` depuis EasyEDA Pro, injection des Net Classes et contraintes de routage issues de [`floorplan.json`](floorplan.json), résolution par FreeRouting, et réimport du fichier `.ses` dans EasyEDA Pro.
  - Implémenter les deux modes opérationnels :
    - **Mode `--incremental` :** Préservation stricte de toutes les pistes existantes verrouillées (`(fixed ...)` dans le format Specctra DSN, comme les paires différentielles sensibles USB/CAN préalablement routées ou les rails d'alimentation critiques), avec auto-routage ciblé du seul chevelu (*ratsnest*) manquant. Permet les itérations de schéma sans détruire le travail manuel validé.
    - **Mode `--clean` :** Dépouillement des pistes non protégées et re-routage intégral à blanc de tout le PCB selon les contraintes globales.
  - Configurer les classes de nets (*Net Classes*) et contraintes dans [`floorplan.json`](floorplan.json) : largeurs pour les rails d'alimentation 12V/5V/3V3 ($\ge 0.6\,\text{mm}$ à $1.0\,\text{mm}$), signaux standards ($0.25\,\text{mm}$), isolements de sécurité ($0.20\,\text{mm}$), et respect absolu de la zone d'exclusion RF de l'antenne ESP32.

### 3.2 Paires différentielles & Signaux critiques
- [ ] **Paire différentielle USB (`USB_D+` / `USB_D-`) :** Impédance contrôlée 90 Ω, skew < 2 mm, routage direct depuis `J2` à travers `U6`/`U7` vers GPIO19/20, puis verrouillage des pistes.
- [ ] **Paire différentielle CAN (`CANH` / `CANL`) :** Impédance contrôlée 120 Ω, skew < 5 mm, routage symétrique à 45° entre `U2`, `JP1` et le bornier `J1`, puis verrouillage des pistes.
- [ ] **Lignes numériques TWAI & UART :** Liaisons TWAI (`TWAI_TX`, `TWAI_RX`) et UART K-Line (`K_RX_IC`, `KLINE_RX`, `K_TX_IC`, `KLINE_TX` via résistances d'amortissement `R1`/`R2`).

### 3.3 Rails d'alimentation de puissance
- [ ] **Rails 12V d'entrée (`+12V`, `+12V_FUSED`, `+12V_PROT`) :** Pistes larges de 0.8 mm à 1.0 mm depuis le bornier d'entrée jusqu'au convertisseur Buck `U4`.
- [ ] **Distribution des rails régulés :** Distribution à faible impédance du `+5V` vers `U5` et `U2`, puis du `3.3V` purifié via la perle de ferrite `FB1` vers l'ESP32 et les étages logiques.

### 3.4 Plans de masse, CEM & Dissipation thermique
- [ ] **Keepout RF d'antenne multicouche :** Définir sur toutes les couches (*All Layers*) la zone d'exclusion stricte (NO_WIRES, NO_FILLS, NO_POURS) sous et autour de l'antenne méandre 2.4 GHz de l'ESP32.
- [ ] **Plans de masse continus Top et Bottom (GND) :** Coulage des plans de masse avec dégagement conforme (0.254 mm) et élimination des îlots flottants.
- [ ] **Vias de couture (stitching) :** Maillage régulier tous les 5 à 8 mm, renfort le long du contour de carte et aux condensateurs de découplage.
- [ ] **Vias thermiques de dissipation :** Matrice de vias thermiques sous le pad de cuivre du LDO `U5` (LDL1117) et sous le pad thermique central de l'ESP32 (`U1`).

### 3.5 Sérigraphie & Contrôles finaux
- [ ] **Sérigraphie complète [M4] :** Polarités des diodes, repères pin 1 sur tous les circuits intégrés et connecteurs (`J1` OBD-II, `J2` USB-C), texte explicite sur le cavalier `JP1` (*« OPEN = CAR / SHUNT = BENCH »*), identification claire de tous les points de test `TP1` à `TP15`.
- [ ] **Contrôle DRC physique strict :** Exécuter le DRC PCB sous EasyEDA Pro et valider 0 erreur, 0 avertissement.
- [ ] **Inspection 3D finale :** Contrôle visuel 3D de l'assemblage complet, du contour de carte et des dégagements mécaniques des connecteurs `J1` et `J2`.

---

## Phase 4 : Conception du boitier

- [ ] S'assurer que le boitier va maintenir en place le câble OBD2.

---


## Phase 5 : Dossier de Fabrication (JLCPCB)

- [ ] Générer et valider les fichiers de fabrication Gerber & Drill (standard 2 couches JLCPCB).
- [ ] Exporter la nomenclature BOM consolidée au format JLCPCB SMT ([`BOM.md`](BOM.md)).
- [ ] Exporter le fichier de placement des composants (Pick & Place / CPL) pour l'assemblage CMS automatisé.

---

## Phase 6 : Firmware & Logiciel Embarqué

### 6.1 Architecture FreeRTOS & Drivers matériels
- [ ] **Driver TWAI CAN :** Implémentation du protocole ISO 15765-4 avec machine d'état de détection automatique (500 kbps puis 250 kbps).
- [ ] **Driver UART K-Line :** Gestion de l'initialisation ISO 9141-2 (init 5-baud) et du protocole rapide KWP2000 (*fast-init*).
- [ ] **Couche Protocolaire Constructeur GM-Daewoo (K-Line / Kalos T200) :**
  - Implémentation de la pile logicielle KWP2000 étendue sur la broche 7 physique (`K_LINE`) avec adressage physique multi-calculateurs : ECM Moteur (`0x10`/`0x11`), TCM Boîte auto (`0x28`), EBCM ABS (`0x58`), et SDM Airbag (`0x50`/`0x51`).
  - Intégration des services de diagnostic propriétaires GM-Daewoo / DST (*Daewoo Specific Tools*) : Service `0x21` / `0x22` (*Read Data By Identifier / Local ID* pour lecture des capteurs et PIDs constructeurs hors-OBD2), décodage des codes défauts propriétaires (`P1xxx`, `Bxxxx`, `Cxxxx`) et routines de tests d'actionneurs.
- [ ] **Surveillance système & Télémétrie :** Détection brownout matérielle ESP32, watchdog FreeRTOS, mesure continue et étalonnage ADC1 de la tension batterie (`VBAT_SENSE`).

### 6.2 Connectivité & Interface utilisateur
- [ ] **Pile réseau :** Serveur WebSocket et/ou service BLE GATT pour communication avec l'application mobile / tablette / PC.
- [ ] **Gestion de la LED témoin `LED1` :** Machine d'état des séquences lumineuses (démarrage, recherche protocole, bus actif, erreur alimentation).
