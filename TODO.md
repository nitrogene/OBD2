# Feuille de Route & Checklist Active (TODO)

Ce document constitue le plan d'action opérationnel du projet **Scanner OBD-II ESP32**.
Il suit la conception matérielle (schéma, placement, routage, fabrication) et logicielle (firmware ESP32).

---

## Phase 1 : Schéma Électrique & Nomenclature (BOM)

### 1.1 Correctifs critiques & robustesse (issus des revues techniques)
- [x] **[CONFORME / VALIDÉ] Câblage d'alimentation, de mode et terminaison du transceiver CAN `U2` (TJA1051T) :** Pontage erroné supprimé entre broche 2 (`GND`) et broche 3 (`VCC`), broche 2 reliée à `GND`, broche 8 (`S`) reliée à `GND` (mode silencieux désactivé, communication active), broche 3 sous `+5V` avec découplage `C15` (100 nF) vers `GND` sans croisement de `RXD`, et cavalier `JP1` recâblé strictement en série avec la terminaison `R8` (120 Ω) entre `CANH` et `CANL` (page 2 du schéma validée).
- [ ] **[BLOQUANT] Sécuriser la grille du N-MOS `Q2` (2N7002) contre le claquage diélectrique sous Load-Dump :** Remplacer la simple résistance série `R5` par un pont diviseur 1:2 (10 kΩ / 10 kΩ) vers la masse pour borner strictement $V_{GS}$ à 14.6 V (bien sous la limite absolue de $\pm 20\,\text{V}$) lors des transitoires d'alternateur où la TVS `D1` écrête à 29.2 V.
- [x] **[CONFORME / VALIDÉ] Raccordement de la broche VS de `U3` (L9637D) [I4] :** Broche 7 (VS) de `U3` et pull-up `R16` (1 kΩ) raccordées au rail sécurisé `+12V_PROT` (après le fusible `F1` et le MOSFET anti-inversion `Q1`) via NetPorts dédiés.
- [x] **[CONFORME / VALIDÉ] Alimentation logique VCC de `U3` (L9637D) [B3] :** Maintenue sous le rail régulé `3.3V` (LDO). *Justification technique :* La plage admissible de $V_{CC}$ s'étend de 3.0V à 7.0V (Table 5 datasheet ST L9637D). La broche RX intégrant un pull-up actif interne vers $V_{CC}$ ($R_{RX} \approx 10\,\text{k}\Omega$, $V_{RXH} = V_{CC} - 0.1\,\text{V}$), alimenter $V_{CC}$ en 5V injecterait ~4.9V dans le GPIO4 de l'ESP32-S3 qui n'est pas tolérant 5V (limite absolue à 3.6V), provoquant sa destruction. Le raccordement 3.3V actuel est 100% conforme et protège le MCU.
- [ ] **[IMPORTANT] Calibrer le fusible réarmable `F1` pour la robustesse thermique [I3] :** Remplacer le PPTC 0.5A par un modèle 0.75A ou 1.1A en boîtier 1812 (ex. Bourns MF-MSMF075-2 / MF-MSMF110-2) pour éliminer le risque de déclenchement intempestif sous température habitacle (50-60°C), inrush et pics Wi-Fi TX.
- [ ] **[IMPORTANT] Ajouter un condensateur de Slow-Start $C_{SS}$ sur la broche 5 (`SS`) de `U4` (TPS54331) [I1] :** Implanter un condensateur céramique $C_{SS} = 10\,\text{nF}$ 50V 0603 (*Basic Part* JLCPCB) entre la broche 5 (`SS`) et GND pour porter le temps de démarrage progressif à ~4 ms, supprimant l'inrush brutal et les surtensions (*overshoot*) sur le rail +5V à l'enfichage OBD.
- [ ] **[IMPORTANT] Sécuriser la stabilité de boucle du LDO `U5` (LDL1117S33R) [I2] :** Remplacer le condensateur `C6` (1 µF sur le net `3.3V_PRE` avant `FB1`) par un condensateur de 10 µF 50V 1206 (`C13585` - *Basic Part*) pour satisfaire l'exigence formelle $C_{OUT} \ge 4.7\,\mu\text{F}$ de la datasheet ST directement sur la broche de sortie du régulateur (la perle `FB1` isolant $C_{11}$).
- [ ] **[IMPORTANT] Réassigner les broches TWAI CAN de l'ESP32-S3 pour libérer l'UART0 [I5] :** Déplacer `TWAI_TX` et `TWAI_RX` actuellement sur GPIO43 / GPIO44 (broches matérielles réservées par défaut à la console et au bootloader `U0TXD`/`U0RXD`) vers les GPIO15 et GPIO16 (ou GPIO36/37) pour éviter tout blocage de flash/log série.
- [ ] **[IMPORTANT] Remplacer la diode anti-retour banc `D4` par une Schottky de puissance [I6] :** Remplacer la double diode `BAT54CW` (limitée à 200 mA / 400 mA pontée avec fort $V_F$) par une diode Schottky 1A / 40V ou 2A en boîtier SOD-123 ou SMA (*Basic Part* JLCPCB, ex. `B5819W` / `SS14` / `SS24`) pour encaisser sans surchauffe ni chute de tension les pointes de consommation Wi-Fi (~500 mA) lors des tests sur port USB-C.
- [ ] **[IMPORTANT] Optimiser la marge de protection Buck `U4` (TVS `D1`) [M5 review] :** Évaluer l'adoption d'une TVS SMBJ16A (VRWM = 16 V, VCL = 26.0 V) pour dégager une marge sécuritaire de 4.0V sous les 30.0V de limite absolue du Buck TPS54331 en environnement 12V VL.
- [ ] **[MINEUR] Ajouter une pull-up externe sur la broche de strapping `IO0` (`U1` pin 27 / `TP10`) [M1 review] :** Ajouter une résistance `R17` de 10 kΩ 0805 (*Basic Part* `C17414`) vers le rail 3.3V sur la ligne `IO0` pour renforcer l'immunité au bruit en habitacle et fiabiliser le boot normal face aux parasites (ne pas dépendre uniquement de la pull-up interne faible de 45 kΩ).
- [x] **[CONFORME / VALIDÉ] Modularité schéma : Rapprocher les symboles de découplage `C3` et `C4` [M2 review] :** Symbole `C3` déplacé sur la page 2 (au contact direct de la broche 5 `VIO` de `U2`) et symbole `C4` déplacé sur la page 3 (au contact direct de la broche 3 `VCC` de `U3`).
- [ ] **[MINEUR] Modularité schéma : Rapatrier les condensateurs de découplage `C1` et `C2` sur la page 4 (ESP32-S3) [M2 review suite] :**
  - **Supprimer le bloc résiduel :** Supprimer le bloc de découplage orphelin situé en bas à droite de la page 4.
  - **Positionnement & Câblage :** Placer `C1` (100 nF) et `C2` (100 nF) au contact direct des broches d'alimentation du module ESP32-S3 `U1`, en parallèle avec le condensateur réservoir `C11` (10 µF) :
    - Borne 1 de chaque condensateur reliée au rail `3.3V` (broche 2 `3V3` de `U1`).
    - Borne 2 de chaque condensateur reliée à la masse `GND` (broche 1 `GND` de `U1`).
  - **Nettoyage documentaire :** Purgé toute référence au « bloc de découplage » dans la documentation technique ([`HARDWARE.md`](HARDWARE.md), [`README.md`](README.md)), le découplage étant désormais intégralement modélisé au niveau local de chaque IC.
- [x] **[CONFORME / VALIDÉ] Raccorder l'entrée non utilisée `LI` (Loop Input) de `U3` à GND [M3 review] :** Broche 8 (`LI`) de `U3` (L9637D) reliée à la masse `GND` pour éliminer tout flottement haute impédance du comparateur de ligne L non utilisé.
- [ ] **[MINEUR] Fiabiliser la mesure ADC de tension batterie face au courant de fuite de `D6` [M4 review] :** Remplacer la diode Schottky `D6` (`BAT54WS`, dont la fuite inverse de 5 à 10 µA à 70°C induit une erreur de mesure batterie > 0.5 V) par une diode silicium à ultra-faible fuite (ex. `BAV199` ou `BAV99`, fuite < 5 nA à chaud) pour préserver la fidélité de l'ADC.
- [ ] **[MINEUR] Renforcer le boîtier de la résistance de terminaison CAN `R8` (120 Ω) :** Qualifier `R8` en boîtier 0805 ou 1206 (*Basic Part* JLCPCB) pour encaisser sans surchauffe les surtensions transitoires jusqu'à 1 W en cas de court-circuit accidentel de la ligne CANH vers le rail batterie (+12V/14V).
- [ ] **[MINEUR] Compléter les points de test (Test Points) sur les nœuds critiques :** Ajouter des mires de test TP pour le nœud de commutation Buck `SW/PH` (TP12), la broche `COMP` (TP13), le rail intermédiaire `3.3V_PRE` (TP14) et la ligne K-Line physique `K_PIN` (TP15) afin de faciliter la mise au point et les mesures à l'oscilloscope sur prototype.

### 1.2 Optimisation du catalogue (Bascule Basic Parts JLCPCB) & Revue de Schéma
- [x] **Bouton poussoir tactile `SW1` :** Remplacé `C480267` (*Extended*) par `C318884` (`TS-1187A-B-A-B` - *Basic Part*, même empreinte 5.1×5.1 mm).
- [x] **Capacité de sortie Buck `C8` / `C16` :** Remplacé la 22 µF 1206 *Extended* par 2 × 10 µF 50V 1206 (`C13585` - *Basic Part*) en parallèle (`C8`, `C16`) pour réduire le DC-bias et supprimer les frais de setup SMT.
- [ ] **Revue complète du schéma électronique :** Faire une revue systématique et approfondie de l'intégralité du schéma sous EasyEDA Pro en s'appuyant notamment sur [`DATASHEETS.md`](DATASHEETS.md) (vérification rigoureuse des préconisations constructeurs, alimentations, découplages, broches non connectées, seuils logiques et protections).

### 1.3 Référentiel Technique & Datasheets ICs
- [x] **Créer le dossier `datasheet/` et le référentiel technique [`DATASHEETS.md`](DATASHEETS.md) :** Centralisation des 6 datasheets officielles (`U1` ESP32-S3, `U2` TJA1051T, `U3` L9637D, `U4` TPS54331, `U5` LDL1117S33R, `U8` NUP2105L), extraction des caractéristiques électriques, limites absolues (*Absolute Maximum Ratings*), règles d'implantation PCB (keepouts, boucles di/dt, thermiques) et matrice d'audit de conformité servant de source de vérité technique.

### 1.4 Validation Schéma
- [ ] Exécuter et valider le contrôle ERC sous EasyEDA Pro (0 erreur, 0 avertissement).
- [ ] Mettre à jour la documentation technique ([`HARDWARE.md`](HARDWARE.md), [`BOM.md`](BOM.md)).

---

## Phase 2 : Préparation & Placement PCB (Floorplanning)

### 2.1 Synchronisation & Mécanique
- [ ] Synchroniser le schéma vers le PCB (*« Update PCB from Schematic »* dans EasyEDA Pro) pour importer les nouvelles empreintes (`R16`, `C15`, `C16`) et aligner la netlist à 100%.
- [ ] Valider le contour mécanique (81.28 × 35.56 mm / 3200 × 1400 mil), l'affleurement de `J2` (USB-C) au Sud pour la coque et l'emplacement de `LED1` face au puits de lumière.
- [ ] Mettre à jour [`floorplan.json`](floorplan.json) avec la BOM consolidée et injecter le placement initial via le skill `pcb-placer`.

### 2.2 Agencement des clusters & Règles CEM de proximité (< 2 mm)
- [ ] **Bloc Puissance & Protection (Ouest) :** Compacité extrême de la boucle Buck SW-L1-D2-C8/C16, isolement de la broche COMP (`C13`, `R11`, `C9`) face au nœud bruité PH, diode clamp `D6` collée à `R13`/`C10` (< 2 mm).
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
- [ ] **Sérigraphie complète [M4] :** Polarités des diodes, repères pin 1 sur tous les circuits intégrés et connecteurs (`J1` OBD-II, `J2` USB-C), texte explicite sur le cavalier `JP1` (*« OPEN = CAR / SHUNT = BENCH »*), identification claire de tous les points de test `TP1` à `TP15`.
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
