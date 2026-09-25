# Feuille de Route & Checklist Active (TODO)

Ce document constitue le plan d'action opérationnel du projet **Scanner OBD-II ESP32**.
Il suit la conception matérielle (schéma, placement, routage, fabrication) et logicielle (firmware ESP32).

---

## Phase 1 : Schéma Électrique & Nomenclature (BOM)

### 1.1 Correctifs critiques & robustesse (issus des revues techniques)
- [ ] **[IMPORTANT] Sécuriser la grille du N-MOS `Q2` (2N7002) contre le Load-Dump :** Remplacer `R5` par un pont diviseur (ex. 10 kΩ / 10 kΩ) ou ajouter une diode Zener de clamp 12V/15V sur la grille de `Q2` pour garantir que Vgs ne dépasse jamais sa limite absolue (±20 V) lors des transitoires 29.2V.
- [ ] **[IMPORTANT] Corriger le raccordement de la broche VS de `U3` (L9637D) :** Raccorder la broche 7 (VS) de `U3` au rail `+12V_PROT` (après le fusible `F1` et le MOSFET anti-inversion `Q1`) au lieu du `+12V` brut, et rectifier la mention erronée `U3(3)` dans [`HARDWARE.md`](HARDWARE.md).
- [ ] **[IMPORTANT] Mettre en conformité l'alimentation logique VCC de `U3` (L9637D) :** Alimenter VCC en `+5V` au lieu de `3.3V` pour respecter la plage constructeur nominale (4.5 V à 5.5 V), la ligne RX restant en collecteur ouvert compatible 3.3V avec pull-up vers le 3.3V.
- [ ] **[IMPORTANT] Calibrer le fusible réarmable `F1` pour la robustesse thermique :** Remplacer le PPTC 0.5A par un modèle 0.75A ou 1.1A en boîtier 1812 (ex. Bourns MF-MSMF075-2 / MF-MSMF110-2) pour éliminer le risque de déclenchement intempestif sous température habitacle (50-60°C), inrush et pics Wi-Fi TX.
- [ ] **[IMPORTANT] Optimiser la marge de protection Buck `U4` (TVS `D1`) :** Évaluer l'adoption d'une TVS SMBJ16A (VRWM = 16 V, VCL = 26.0 V) pour dégager une marge sécuritaire de 4.0V sous les 30.0V de limite absolue du Buck TPS54331 en environnement 12V VL.

### 1.2 Optimisation du catalogue (Bascule Basic Parts JLCPCB)
- [x] **Bouton poussoir tactile `SW1` :** Remplacé `C480267` (*Extended*) par `C318884` (`TS-1187A-B-A-B` - *Basic Part*, même empreinte 5.1×5.1 mm).
- [ ] **Capacité de sortie Buck `C8` :** Remplacer la 22 µF 1206 *Extended* par 2 × 10 µF 50V 1206 (`C13585` - *Basic Part* déjà présente en BOM) en parallèle pour réduire le DC-bias et supprimer les frais de setup SMT.

### 1.3 Validation Schéma
- [ ] Exécuter et valider le contrôle ERC sous EasyEDA Pro (0 erreur, 0 avertissement).
- [ ] Mettre à jour la documentation technique ([`HARDWARE.md`](HARDWARE.md), [`BOM.md`](BOM.md)).

---

## Phase 2 : Préparation & Placement PCB (Floorplanning)

### 2.1 Synchronisation & Mécanique
- [ ] Synchroniser le schéma vers le PCB (*« Update PCB from Schematic »* dans EasyEDA Pro) pour importer les nouvelles empreintes (`R16`, `C15`) et aligner la netlist à 100%.
- [ ] Valider le contour mécanique (81.28 × 35.56 mm / 3200 × 1400 mil), l'affleurement de `J2` (USB-C) au Sud pour la coque et l'emplacement de `LED1` face au puits de lumière.
- [ ] Mettre à jour [`floorplan.json`](floorplan.json) avec la BOM consolidée et injecter le placement initial via le skill `pcb-placer`.

### 2.2 Agencement des clusters & Règles CEM de proximité (< 2 mm)
- [ ] **Bloc Puissance & Protection (Ouest) :** Compacité extrême de la boucle Buck SW-L1-D2-C8, isolement de la broche COMP (`C13`, `R11`, `C9`) face au nœud bruité PH, diode clamp `D6` collée à `R13`/`C10` (< 2 mm).
- [ ] **Bloc Transceivers & Interfaces (Centre) :** Diodes TVS `U8` et `D5` collées à `J1` (< 5 mm), pull-up K-Line `R16` en zone aérée (< 5 mm de `J1`), cavalier de terminaison CAN `JP1` accessible.
- [ ] **Bloc USB-C & ESD (Sud) :** Diodes ESD `U6`/`U7` et résistances pull-down CC `R3`/`R4` alignées immédiatement sur les pastilles de `J2`.
- [ ] **Bloc ESP32-S3 & Radio (Est) :** Condensateur réservoir Bulk `C11` (10 µF) collé aux pins 1-2 (< 2 mm), filtre Reset `C12`/`R15` collé à la pin EN (< 2 mm), point de test `TP10` (`IO0`) accessible près de GND.

---

## Phase 3 : Routage, Plans de Masse & Finition PCB

### 3.1 Paires différentielles & Signaux critiques
- [ ] **Paire différentielle USB (`USB_D+` / `USB_D-`) :** Impédance contrôlée 90 Ω, skew < 2 mm, routage direct depuis `J2` à travers `U6`/`U7` vers GPIO19/20.
- [ ] **Paire différentielle CAN (`CANH` / `CANL`) :** Impédance contrôlée 120 Ω, skew < 5 mm, routage symétrique à 45° entre `U2`, `JP1` et `J1`.
- [ ] **Lignes numériques TWAI & UART :** Liaisons TWAI (`TXD`, `RXD`) et UART K-Line (`K_RX_IC`, `UART_RX_MCU`, `K_TX_IC`, `UART_TX_MCU` via résistances d'amortissement `R1`/`R2`).

### 3.2 Rails d'alimentation de puissance
- [ ] **Rails 12V d'entrée (`+12V`, `+12V_FUSED`, `+12V_PROT`) :** Pistes larges de 0.8 mm à 1.0 mm depuis la broche 16 OBD jusqu'au convertisseur Buck `U4`.
- [ ] **Distribution des rails régulés :** Distribution à faible impédance du `+5V` vers `U5` et `U2`, puis du `3.3V` purifié via la perle de ferrite `FB1` vers l'ESP32 et les étages logiques.

### 3.3 Plans de masse, CEM & Dissipation thermique
- [ ] **Keepout RF d'antenne multicouche :** Définir sur toutes les couches (*All Layers*) la zone d'exclusion stricte (NO_WIRES, NO_FILLS, NO_POURS) sous et autour de l'antenne méandre 2.4 GHz de l'ESP32.
- [ ] **Plans de masse continus Top et Bottom (GND) :** Coulage des plans de masse avec dégagement conforme (0.254 mm) et élimination des îlots flottants.
- [ ] **Vias de couture (stitching) :** Maillage régulier tous les 5 à 8 mm, renfort le long du contour de carte et aux condensateurs de découplage.
- [ ] **Vias thermiques de dissipation :** Matrice de vias thermiques sous le pad de cuivre du LDO `U5` (LDL1117) et sous le pad thermique central de l'ESP32 (`U1`).

### 3.4 Sérigraphie & Contrôles finaux
- [ ] **Sérigraphie complète :** Polarités des diodes, repères pin 1 sur tous les circuits intégrés, texte d'avertissement explicite sur le cavalier `JP1` (*« OPEN = CAR / SHUNT = BENCH »*), identification des points de test `TP1` à `TP11`.
- [ ] **Contrôle DRC physique strict :** Exécuter le DRC PCB sous EasyEDA Pro et valider 0 erreur, 0 avertissement.
- [ ] **Inspection 3D finale :** Contrôle visuel 3D de l'assemblage complet, du contour de carte et des dégagements mécaniques des connecteurs `J1` et `J2`.

---

## Phase 4 : Dossier de Fabrication (JLCPCB)

- [ ] Générer et valider les fichiers de fabrication Gerber & Drill (standard 2 couches JLCPCB).
- [ ] Exporter la nomenclature BOM consolidée au format JLCPCB SMT ([`BOM.md`](BOM.md)).
- [ ] Exporter le fichier de placement des composants (Pick & Place / CPL) pour l'assemblage CMS automatisé.

---

## Phase 5 : Firmware & Logiciel Embarqué

### 5.1 Architecture FreeRTOS & Drivers matériels
- [ ] **Driver TWAI CAN :** Implémentation du protocole ISO 15765-4 avec machine d'état de détection automatique (500 kbps puis 250 kbps).
- [ ] **Driver UART K-Line :** Gestion de l'initialisation ISO 9141-2 (init 5-baud) et du protocole rapide KWP2000 (*fast-init*).
- [ ] **Surveillance système & Télémétrie :** Détection brownout matérielle ESP32, watchdog FreeRTOS, mesure continue et étalonnage ADC1 de la tension batterie (`VBAT_SENSE`).

### 5.2 Connectivité & Interface utilisateur
- [ ] **Pile réseau :** Serveur WebSocket et/ou service BLE GATT pour communication avec l'application mobile / tablette / PC.
- [ ] **Gestion de la LED témoin `LED1` :** Machine d'état des séquences lumineuses (démarrage, recherche protocole, bus actif, erreur alimentation).
