# Feuille de Route & Checklist du Projet (TODO)

Ce document constitue le plan d'action opérationnel du projet **Scanner OBD-II ESP32**.
Il suit la conception matérielle (schématique, PCB, fabrication) et logicielle (firmware ESP32, application mobile).

---

## 1. Intégration Mécanique & Enveloppe (Boîtier, Fixations, Connecteurs)

- [x] **1.1 Type de boîtier :** Boîtier sur mesure en résine SLA fabriqué chez JLCPCB (tolérance +/- 0.05 mm, gorge de verrouillage mécanique pour absorber l'effort d'insertion OBD de 40-60 N, inserts filetés laiton M2).
- [x] **1.2 Connecteur physique OBD-II (J1) :** Modèle mâle 16 broches (SAE J1962) coudé à 90° traversant (pas 4.00 mm), implanté sur le bord Ouest à (X = 1400 mil, Y = -600 mil, rotation 270°), parfaitement centré sur l'axe vertical.
- [ ] **1.3 Pont diviseur pour monitoring tension batterie (ESP32 ADC) :**
  - [x] Implantation physique initiale à droite de `J1` (`R12`, `R13`, `C10` et point de test `TP9` / `VBAT_SENSE`).
  - [x] **[TOP PRIORITÉ]** Revoir et arbitrer les valeurs de `R12` et `R13` (actuellement 100 kΩ / 20 kΩ) : ratio de division, plage de linéarité ADC ESP32, impédance d'entrée, courant de repos et sélection en catalogue de base JLCPCB.
- [x] **1.4 Revue du schéma par l'utilisateur :** Contrôle, vérification et validation visuelle/technique du schéma complet par l'utilisateur (raccordement de J1, pont diviseur batterie, NetPorts miroirs +12V, CANH, CANL, K_LINE, points de test et ERC = 0) avant de figer les fixations mécaniques et d'engager la synchronisation PCB.
- [x] **1.5 Fixations mécaniques :** Déterminer et placer les trous de perçage pour vis M2 (diamètre 2.2 mm avec zone d'exclusion de 4.5 mm pour tête de vis et inserts de colonnettes).
- [ ] **1.6 Traiter les retours du reviewer :**
  - [x] **Point Critique — Chaîne de tenue en tension et protection Load-Dump :** (Résolu à 100% : Q1 60V, D3 Zener 12V + R14, C7 50V et D1 SMBJ18A VCL 29.2V < 30V).
    - [x] Remplacer le P-MOSFET Q1 (IRLML2244, VDS max 20V) par le modèle 60V CJ2309A (VDS max 60V, ID 2A, boîtier SOT-23 compatible).
    - [x] Ajouter une diode Zener de protection 12V (D3 BZX84C12) entre Source et Grille de Q1 avec résistance série (R14 10 kΩ) pour borner VGS en régime permanent (14.4V alternateur) et lors des transitoires.
    - [x] Remplacer le condensateur d'entrée C7 (25V) par une référence qualifiée 50V (10 µF 1206 50V) pour résister sans claquage à la tension d'écrêtage de D1 (VCL max ~39V).
    - [x] Arbitrer la tenue du régulateur Buck U4 (TPS54331, VIN max absolu 30V) face aux transitoires : résolu par l'adoption de la TVS SMBJ18A (écrêtage crête VCL = 29.2V < 30V).
  - [ ] **Points Importants (Architecture & Robustesse) :**
    - [x] Rendre la terminaison CAN R8 (120 ohms) déconnectable : résolu par l'ajout du cavalier sélecteur JP1 (PZ2.54-1*2). Shunt requis sur banc de test / simulateur d'ECU ; laissé ouvert par défaut pour utilisation directe et conforme dans une voiture.
    - [x] Raccorder VBUS_5V au rail +5V via une diode Schottky anti-retour : résolu par l'ajout de D4 (BAT54CW, boîtier SOT-323, C962771) avec anodes 1 et 2 reliées à VBUS_5V et cathode commune reliée à +5V pour l'alimentation autonome USB et la protection anti-retour.
    - [x] Ajouter un condensateur réservoir (bulk 10-22 µF) sur le rail 3.3V au plus près du module ESP32-S3 U1 pour lisser les pics de courant Wi-Fi TX (500 mA) : résolu par l'ajout de C11 (10 µF 25V X5R 0805 Samsung CL21A106KAYNNNE / C15850, Basic Part).
    - [x] Sécuriser la broche EN (CHIP_PU) de l'ESP32 avec une résistance pull-up externe de 10 k ohms vers 3.3V et un condensateur de 1 µF vers GND contre les resets intempestifs en environnement bruité (R15, C12, SW1, TP11).
    - [x] Ajouter des protections transitoires/ESD dédiées sur les lignes CANH, CANL et K_LINE au niveau du connecteur OBD J1 : résolu par l'ajout de U8 (double TVS 24V NUP2105LT1G en SOT-23 sur CANH/CANL) et D5 (TVS 24V SMF24CA en SOD-123FL sur K_LINE).
  - [ ] **Points Mineurs & Pratique :**
    - [x] Ajuster la résistance série R6 de LED1 (verte) pour augmenter la luminosité visible en plein jour dans l'habitacle : résolu par l'adoption de R6 = 100 Ω (0805W8F1000T5E, LCSC C17408, Basic Part JLCPCB) portant le courant à ~3.6 mA (~280 mcd).
    - [x] Prévoir un point de test / strap de mise à la masse pour GPIO0 afin de garantir un accès matériel fiable au mode bootloader / flash de secours (TP10 / IO0).
- [ ] **1.7 Contour de carte & façade USB :** Contour ajusté à 81.28 x 35.56 mm (3200 x 1400 mil) ; valider l'affleurement de la prise USB-C J2 au Sud pour la découpe de coque.
- [ ] **1.8 Emplacement de la LED témoin :** Positionner LED1 pour un alignement optimal avec le puits de lumière du boîtier.

---

## 2. Complétude du Schéma & Synchronisation Netlist

- [x] **2.1 Ajout du connecteur OBD-II (J1) sur le schéma :** Intégrer le symbole du connecteur 16 broches avec son empreinte PCB assignée.
- [x] **2.2 Câblage des 5 liaisons fonctionnelles OBD :**
  - Pin 16 (+12V Batterie) reliée au fusible PPTC F1 et à la TVS D1 via le rail +12V.
  - Pin 4 (Masse châssis) et Pin 5 (Masse signal) reliées au plan commun GND.
  - Pin 6 (CAN High) et Pin 14 (CAN Low) reliées à la terminaison 120 ohms R8 et au transceiver CAN U2 via CANH et CANL.
  - Pin 7 (Ligne K) reliée au transceiver K-Line U3 via K_LINE.
- [x] **2.3 Contrôle ERC strict :** Valider l'intégrité électrique sous EasyEDA Pro (0 fatal error, 0 error, 0 warning).
- [ ] **2.4 Synchronisation Schéma -> PCB :** Exécuter « Update PCB from Schematic » pour instancier les pastilles de J1 et aligner la netlist à 100%.

---

## 3. Disposition Macro & Placement Optimisé des Composants (Floorplanning)

- [ ] **3.1 Organisation des 4 blocs fonctionnels :**
  - *Bloc Puissance & Protection (Ouest) :* F1, D1, Q1, Q2, étage Buck (U4, L1, D2, C7, C8, R9, R10, R11, C9) et LDO (U5, FB1, C6).
  - *Bloc Transceivers & Interfaces (Centre) :* CAN (U2, R8, JP1, TVS U8) et K-Line (U3, R1, R2, TVS D5).
  - *Bloc USB-C & ESD (Sud-Centre) :* Connecteur horizontal J2, pull-downs R3/R4, diodes ESD U6/U7, point de test TP1.
  - *Bloc Cœur de Calcul & Radio (Est) :* ESP32-S3 (U1) avec son antenne orientée vers le bord extérieur libre.
- [ ] **3.2 Optimisation du cluster USB Sud :**
  - Aligner les diodes ESD U6 et U7 côte à côte au plus près des broches d'entrée de J2 pour un clamp immédiat des décharges électrostatiques.
  - Aligner les résistances pull-down 5.1 k ohms R3 (CC1) et R4 (CC2) de manière symétrique face aux broches A5 et B5.
- [ ] **3.3 Optimisation du découplage HF & Réservoir d'énergie Bulk :**
  - Positionner les condensateurs de découplage HF `C1` et `C2` (100 nF) à moins de 2 mm des broches d'alimentation de l'ESP32.
  - **Implanter impérativement le condensateur réservoir Bulk `C11` (10 µF 25V 0805) au plus près immédiat des broches 1 (`GND`) et 2 (`3V3`) de l'ESP32 `U1` (distance < 2 à 3 mm)** avec des pistes directes larges et un via de masse franc vers le plan interne GND, pour étouffer les appels de courant transitoires de 500 mA lors des transmissions radio Wi-Fi.
  - Positionner `C3` au plus près de la broche 5 (`VIO`) de `U2`.
  - Positionner `C4` au plus près de la broche 3 (`VCC`) de `U3`.
  - Positionner `C6` au plus près de la sortie de `U5`/`FB1`.
- [ ] **3.4 Optimisation de l'étage Reset & Bootloader :**
  - **Implanter impérativement le condensateur RC `C12` (1 µF) et la résistance pull-up `R15` (10 kΩ) au plus près immédiat de la broche 3 (`EN`) de l'ESP32 `U1` (distance < 2 mm)** pour minimiser la surface de boucle haute impédance et immuniser la ligne contre les bruits RF 2.4 GHz et transitoires automobiles.
  - Positionner le bouton poussoir `SW1` avec orientation et dégagement adaptés pour un alignement propre avec l'orifice trou d'épingle (*pinhole*) prévu sur la coque du boîtier.
  - Positionner le point de test `TP10` (`IO0`) à proximité de la broche 27 de `U1` et proche d'une zone GND pour faciliter la mise à la masse en cas de récupération bootloader.
- [ ] **3.5 Optimisation des protections transitoires OBD (U8, D5) :**
  - Positionner la double diode TVS `U8` au plus près des broches `CANH` (Pin 6) et `CANL` (Pin 14) du connecteur OBD `J1` pour un clamp immédiat avant la terminaison `R8`/`JP1` et le transceiver `U2`.
  - Positionner la diode TVS `D5` au plus près de la broche `K_LINE` (Pin 7) de `J1` pour dériver les transitoires avant le transceiver `U3` et le point de test `TP2`.
- [ ] **3.6 Alignement esthétique & lisibilité :** Vérifier l'orientation horizontale de toutes les sérigraphies de composants (règle AGENTS.md) et la cohérence visuelle.

---

## 4. Routage des Signaux Critiques & Paires Différentielles

- [ ] **4.1 Paire différentielle USB (USB_D+ / USB_D-) :** Routage d'impédance contrôlée depuis J2 à travers les pastilles de U6/U7 jusqu'aux broches IO20 et IO19 de l'ESP32.
- [ ] **4.2 Paire différentielle bus CAN (CANH / CANL) :** Routage symétrique à 45° reliant U2, la terminaison 120 ohms R8 et les broches 6 et 14 du connecteur OBD-II J1.
- [ ] **4.3 Lignes numériques UART et TWAI :** Routage direct des liaisons UART K-Line (K_RX_IC, UART_RX_MCU, K_TX_IC, UART_TX_MCU via R1/R2) et TWAI CAN (TXD, RXD).
- [ ] **4.4 Lignes de configuration et contrôle :** Routage des lignes CC1 et CC2 vers R3/R4, du point de test VBUS_USB vers TP1, et du signal LED_STATUS vers LED1 via R6.

---

## 5. Routage des Rails de Puissance & Alimentations

- [ ] **5.1 Rail 12V d'entrée sécurisé :** Pistes larges (0.8 mm à 1.0 mm) pour +12V, +12V_FUSED et +12V_PROT depuis la broche 16 OBD jusqu'au convertisseur Buck U4.
- [ ] **5.2 Boucle de commutation Buck haute fréquence (570 kHz) :** Boucle minimale ultra-courte entre U4 (PH), l'inductance blindée L1 et la diode Schottky D2, avec condensateur bootstrap C5 et réseau de compensation (R11/C9) isolé du bruit magnétique.
- [ ] **5.3 Distribution des rails 5V et 3.3V :** Distribution à faible impédance du 5V vers U5 et U2, puis du 3.3V purifié via la perle de ferrite FB1 vers l'ESP32 et les étages logiques.

---

## 6. Plans de Masse, Gestion RF & Vias de Couture

- [ ] **6.1 Zone d'exclusion RF d'antenne (Keepout multicouche) :** Définir sur toutes les couches (All Layers) la zone d'exclusion stricte sous et autour de l'antenne méandre 2.4 GHz de l'ESP32 (NO_WIRES, NO_FILLS, NO_POURS).
- [ ] **6.2 Plans de masse Top et Bottom (GND) :** Coulage des plans de masse avec dégagement conforme (0.254 mm) et freins thermiques.
- [ ] **6.3 Matrice thermique et vias de couture :**
  - Matrice de vias de masse sous le pad thermique central de l'ESP32 (broche 41) pour la dissipation thermique.
  - Vias de couture réguliers le long du contour de carte et aux condensateurs de découplage.
- [ ] **6.4 Résorption des îlots et micro-zones d'exclusion :** Éliminer les îlots flottants et placer les micro-zones NO_POURS si nécessaire pour éliminer toute micro-intrusion de cuivre.

---

## 7. Contrôles, Sérigraphie & Validation

- [ ] **7.1 Sérigraphie explicative :** Délimitation visuelle et étiquetage clair des zones logiques sur le PCB (Alimentation, K-Line, CAN, USB, MCU).
- [ ] **7.2 Contrôle DRC physique strict :** Exécuter le DRC PCB sous EasyEDA Pro et valider 0 erreur, 0 avertissement.
- [ ] **7.3 Contrôle ERC schématique strict :** Vérifier que le schéma reste à 0 erreur, 0 avertissement.
- [ ] **7.4 Visualisation 3D finale :** Contrôle visuel 3D de l'assemblage complet, du contour et des dégagements de connectique.

---

## 8. Dossier de Fabrication

- [ ] **8.1 Fichiers Gerber & Drill :** Génération des fichiers de fabrication pour production standard JLCPCB.
- [ ] **8.2 Fichier de nomenclature (BOM) :** Export de la liste complète des composants avec références LCSC ([BOM.md](BOM.md)).
- [ ] **8.3 Fichier de placement (CPL / Pick & Place) :** Export des coordonnées de montage pour assemblage CMS automatisé.

---

## 9. Firmware & Logiciel Embarqué

- [ ] **9.1 Architecture logicielle & Stack FreeRTOS :**
  - Tâche de communication TWAI (Bus CAN ISO 15765-4).
  - Tâche de communication UART (K-Line ISO 9141-2 / KWP2000 Daewoo Kalos).
  - Tâche réseau (Serveur WebSocket / BLE GATT).
  - Tâche de surveillance système (Watchdog, mesure tension batterie ADC1).
