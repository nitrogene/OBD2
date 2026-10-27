# Feuille de Route & Checklist Active (TODO)

Ce document constitue le plan d'action opérationnel du projet **Scanner OBD-II ESP32**.
Les phases d'ingénierie matérielle (Schéma, Auto-Placement, Auto-Routage, Vias de couture, Plans de masse et Sérigraphie) sont certifiées conformes (**ERC = 0, DRC = 0**).

---

## 🏁 Synthèse des Jalons Matériels Clôturés

- ✅ **Phase 1 : Schéma Électrique & BOM** : 85 composants validés, ERC = 0, nomenclature optimisée en Basic Parts JLCPCB ([`documents/schema/bom.json`](documents/schema/bom.json), [`documents/schema/semantics.json`](documents/schema/semantics.json)).
- ✅ **Phase 2 : Auto-Placement PCB (`pcb-placer`)** : 84 composants placés sans collision, dégagements IPC-7351 et courtyards validés ([`documents/pcb/placement.svg`](documents/pcb/placement.svg)).
- ✅ **Phase 3 : Auto-Routage Headless & Plans (`pcb-synthesizer`)** : 100 % des signaux routés, impédance différentielle USB/CAN, plans de masse multi-couches continus, stitching de bord de carte, DRC natif EasyEDA Pro = 0.
- ✅ **Phase 4 : Sérigraphie Déclarative (`pcb-silkscreen`)** : Sérigraphie fonctionnelle face arrière injectée et validée (J1, H1/CAN, H2/KLINE, H3/Bench, JP1/CAN, JP2/K-Line, cartouche) ([`documents/pcb/silkscreen.json`](documents/pcb/silkscreen.json)).

---

## 1. Révision Pré-Fabrication : Intégrité CEM & Re-Placement (Revue Claude Sonnet 5.5)

### Étape 1.1 : Ajustements Schéma & Sérigraphie
- [x] **Protection de Grille Q2 (`R5` sur `+12V_PROT`) :** Basculer la connexion haute de `R5` du rail `+12V` brut vers `+12V_PROT` (après `Q1` et la diode TVS `D1`) dans le schéma EasyEDA. Lors d'un transitoire d'alternateur écrêté à 26.0 V par `D1`, le diviseur 1:2 `R5`/`R17` borne strictement Vgs de `Q2` à <= 13.0 V (marge de 7 V sous la limite absolue de +-20 V du 2N7002), tout en conservant un amorçage sain par la diode de corps de `Q1` et un blocage hermétique en inversion de polarité.
- [x] **Sérigraphie H3 (`MEASURE ONLY`) :** Mettre à jour `documents/pcb/silkscreen.json` et la sérigraphie face arrière pour remplacer `SCANNER: POWER OUT` par `SCANNER: MEASURE ONLY` afin de prévenir tout court-circuit ou tirage de puissance non protégée sur le véhicule.

### Étape 1.2 : Re-Placement par Clusters CEM & Découplage Immédiat
- [x] **Compactage de la Boucle de Commutation Buck (I1) :** Regrouper le cluster Buck (`U4`, `L1`, `D2`, `C5`, `C7`, `C14`, `C16`, `C8`) avec la self `L1` à <= 8.0 mm de la broche 8 (`PH`) de `U4`, l'anode de la diode Schottky `D2` à <= 5.0 mm de `U4.7` (`GND`), et les condensateurs de sortie `C16`/`C8` immédiatement au contact de la broche 2 de `L1`, tout en maintenant une séparation >= 15.0 mm vis-à-vis de l'antenne radio ESP32-S3.
- [x] **Découplage HF Immédiat des Circuits Intégrés (I2) :** Rapprocher les condensateurs de découplage à <= 2.0 mm de leurs broches d'alimentation respectives (`C1`, `C2` et le réservoir bulk 10 µF `C11` sur la broche 2 `3V3` de `U1` ; le circuit RC de reset `C12`/`R15` sur la broche 3 `EN` ; `C15` sur `U2.3` `VCC` ; `C3` sur `U2.5` `VIO` ; `C4` sur `U3.3` `VCC` ; `C6` sur `U5.2` `VOUT` ; et un condensateur 10 µF d'entrée à <= 3.0 mm de `U5.3` `VIN`).
- [x] **Implantation Frontière des Protections TVS & Fusible (I3) :** Implanter la double TVS CAN `U8` et la TVS K-Line `D5` à <= 5.0 mm du connecteur diagnostic d'entrée `J1`, placer le fusible réarmable `F1` à <= 10.0 mm de `J1.1`, et positionner les diodes ESD `U6`/`U7` de manière symétrique et immédiate (< 5.0 mm) face aux broches USB D+/D- du connecteur `J2`.

### Étape 1.3 : Re-Routage Specctra, Plans de Masse & Finition DFM
- [x] **Règles d'attache formelles (`constraints.json` & `manifest.json`) :** Déclarer les contraintes obligatoires d'attache « composant -> broche » et de micro-clusters (découplages <= 2.0 mm de chaque broche avec via GND adjacente, TVS <= 5.0 mm de J1/J2, boucle Buck compacte avec L1, D2, C8, C16) pour forcer `pcb-placer` à respecter la compacité CEM et ne plus disperser les passifs.
- [x] **Auto-routage & Paires Différentielles :** Relancer `freerouting` pour router les pistes optimisées en respectant les paires différentielles CAN et USB.
- [x] **Couture de Masse & Plans GND (`pcb-stitcher`) :** Restaurer la continuité des plans de masse, minimiser les boucles de retour et régénérer `documents/pcb/placement.svg` avec certification DRC EasyEDA Pro = 0.

## 2. Dossier de Fabrication & Finition DFM (JLCPCB)

### Étape 2.1 : Ajustements DFM de Finition (Post-Rapport JLCDFM)
- [ ] **Ponts de vernis épargne à pas fin (*Soldermask Bridge* >= 0.10 mm) :** Réduire l'expansion du vernis épargne (*Solder Mask Expansion*) de 0.05 mm à 0.02–0.03 mm sur les broches à pas dense (connecteur USB-C `J2` et module ESP32-S3 `U1`) afin de préserver un barrage de vernis physique >= 0.10 mm (seuil capability verte JLCPCB) et éliminer les 12 alertes Danger de fusion en *gang mask*.
- [ ] **Sécurisation & Recouvrement des Vias CMS (*Via to Pad / Tenting*) :** Décaler les vias de couture ou d'échappement en contact direct (0 mm) avec les pastilles de composants CMS pour insérer un col de piste de dégagement >= 0.15–0.20 mm (*dog-bone*), et certifier le recouvrement de vernis (*Via Tenting* Top & Bottom à 100%) afin d'éliminer les 50 alertes Danger de siphonnage de brasure (*solder wicking*).
- [ ] **Dégagement Sérigraphie / Pastilles & Perçages (*Silkscreen to Pad / Hole*) :** Décaler les désignateurs trop proches des ouvertures de vernis épargne et configurer la règle DRC de clearance sérigraphie >= 0.15 mm dans EasyEDA Pro pour éliminer les 50 alertes *Silkscreen to Pad* et 60 alertes *Silkscreen to Hole* et éviter tout rognage automatique (*auto-clipping*) de texte par JLCPCB.
- [ ] **Épaisseur des traits de sérigraphie (*Stroke Width*) :** Porter l'épaisseur des traits de texte et de contour à 0.18–0.20 mm (notamment dans `documents/pcb/silkscreen.json` et EasyEDA) pour garantir une impression nette et contrastée face au seuil d'alerte DFM de 0.15 mm.
- [ ] **Validation des fentes de fixation USB-C (*Plated Slots* `J2`) :** Confirmer la bonne déclaration des 4 perçages oblongs (0.4 x 0.8 mm) pour le blindage mécanique du connecteur `J2` dans le fichier de perçage `Drill_PTH_Through.DRL` (avertissement DFM standard à acquitter).

### Étape 2.2 : Génération du Dossier de Fabrication
- [x] **Génération des fichiers Gerber & Drill :** Export standard 4 couches (JLC2313) depuis EasyEDA Pro avec perçages PTH/NPTH.
- [x] **Option d'assemblage traversant (THT) & Shunts :** Valider avec JLCPCB l'option d'assemblage THT pour les 6 connecteurs (`J1`, `H1`, `H2`, `H3`, `JP1`, `JP2`) ou prévoir la brasure manuelle post-SMT ; approvisionner 2 shunts 2.54 mm pour cavaliers `JP1` et `JP2`.
- [x] **Export BOM SMT :** Nomenclature consolidée au format JLCPCB SMT avec codes LCSC validés ([`documents/schema/bom.json`](documents/schema/bom.json)).
- [x] **Export Pick & Place (CPL) :** Fichier de centroïdes avec coordonnées XY et rotations corrigées pour l'assemblage CMS automatisé.

---

## 3. Recette Matérielle & Protocole de Bring-up (Mise en service)

Procédure séquentielle de mise sous tension et de validation des cartes à réception d'usine :

### Étape 3.1 : Contrôles Visuels & Mécaniques (Hors Tension)
- [ ] **Inspection optique sous microscope/loupe :**
  - Vérifier l'absence de ponts d'étain (solder bridges), particulièrement sur `U1` (ESP32-S3), `U4`, `U5`, `U2` et `U3`.
  - Contrôler l'alignement et la polarité des composants critiques : diodes (`D1`, `D2`, `D3`, `D4`, `D5`, `D6`), condensateurs polarisés et CI (broche 1).
  - Vérifier la netteté de la sérigraphie face arrière et l'intégrité des 4 perçages mécaniques M2.

### Étape 3.2 : Contrôle d'Isolement & Dépistage de Courts-Circuits (Hors Tension)
- [ ] **Mesure de résistance à l'ohmmètre face au plan GND :**
  - Rail `+12V` (broche 1 de `J1` ou `H3`) face à `GND` : résistance attendue > 10 kΩ (montée capacitive).
  - Rail `+5V` (`TP5` / sortie Buck `U4` / `VBUS`) face à `GND` : résistance attendue > 1 kΩ.
  - Rail `3.3V` (`TP6` / sortie LDO `U5` / alimentation ESP32) face à `GND` : résistance attendue > 500 Ω.
  - Lignes de bus : vérifier l'isolement entre `CANH`, `CANL`, `K-LINE` et la masse (`GND`).

### Étape 3.3 : Bring-up Alimentation USB Seule (VBUS 5V)
- [ ] **Mise sous tension via USB-C (`J2`) avec surveillance de courant :**
  - Alimenter via un port USB avec wattmètre / limitation à 250 mA.
  - Vérifier le courant de repos : attendu entre 30 mA et 70 mA (ESP32 non programmé / en bootloader).
  - Mesurer la tension `3.3V` sur `TP6` : doit être comprise entre 3.25V et 3.35V.
  - Mesurer `VBAT_SENSE` (`TP9`) en alimentation USB seule : vérifier la tension résiduelle (~0.35–0.45V due à la remontée du 5V USB à travers L1 et la diode de corps High-Side de U4 vers `+12V_PROT` ; Q1 bloque hermétiquement tout retour vers J1/H3) — calibrer le seuil logiciel de détection batterie présente à Vbat > 6.0V (soit VBAT_SENSE > 0.64V) pour immuniser le firmware contre toute fausse détection.
  - *Note alimentation USB-seule :* Le rail +5V sous USB seul est à ~4.35V (chute Schottky D4) < VCC min 4.5V du TJA1051T ; valider les transceivers CAN et K-Line exclusivement sous alimentation 12V (H3 ou véhicule).
  - Valider l'énumération USB du microcontrôleur sur le PC hôte (périphérique USB JTAG/serial ou port COM natif).
  - Flash d'un micro-firmware de test (« blinky » sur `LED1` et sortie texte série UART).

### Étape 3.4 : Bring-up Alimentation Laboratoire 12V (Bench Power H3)
- [ ] **Mise sous tension 12V sécurisée :**
  - Régler l'alimentation de laboratoire à 12.0V avec limitation de courant stricte à 100 mA (OCP).
  - Raccorder sur l'embase `H3` (broche 1 = `+12V`, broche 2 = `GND`).
  - Mesurer le courant d'entrée global : attendu entre 20 mA et 45 mA à vide.
  - Valider la tension du rail Buck `+5V` sur `TP5` : doit être stable entre 4.90V et 5.15V.
  - Valider la tension du rail LDO `3.3V` sur `TP6` : 3.30V ± 2 %.
  - Mesurer le diviseur ADC `VBAT_SENSE` sur `TP9` : attendu ~1.29V pour VIN = 12.0V (rapport nominal 1/9.33).
  - Vérifier la propreté spectrale (ondulation / ripple résiduel) au multimètre AC / oscilloscope sur les rails 5V et 3.3V (< 50 mV crête).

### Étape 3.5 : Validation des Émetteurs-Récepteurs CAN & K-Line
- [ ] **Test de la terminaison et du transceiver CAN (`U2`) :**
  - Cavalier `JP1` fermé (mode SIMU) : vérifier que la résistance entre `CANH` et `CANL` sur `J1` vaut environ 120 Ω.
  - Cavalier `JP1` ouvert (mode SCANNER) : résistance > 10 kΩ.
  - Émission de trames CAN de test (TWAI loopback / écoute passive) : contrôler les signaux `CANH` (~3.5V dominant) et `CANL` (~1.5V dominant) au scope.
- [ ] **Test de la ligne K-Line (`U3`) :**
  - Cavalier `JP2` fermé (mode SCANNER) : vérifier la présence du pull-up vers +12V (niveau haut au repos ~12V).
  - Cavalier `JP2` ouvert (mode SIMU) : niveau haute impédance (bus flottant / sans pull-up fort).
  - Test d'écho / boucle locale UART : injecter une séquence 0x55 (Fast-Init) et vérifier le décodage sans gigue sur la broche RX.

### Étape 3.6 : Test Radiofréquence & Immunité Transitoire
- [ ] **Test d'émission Wi-Fi / BLE :**
  - Activer la transmission RF maximale (802.11b/g/n) et surveiller la stabilité du régulateur `U5` (aucun brownout lors des appels de courant crête ~250-350 mA).

---

## 4. Conception du Boîtier & Intégration Mécanique (Skill `pcb-enclosure`)

- [x] **Maintien mécanique du faisceau OBD-II :** Bride serre-câble rigide 2 vis M2 (`enclosure_clamp.step` / `.stl`) déchargeant totalement la traction sur le connecteur `J1`.
- [x] **Accès connectique & interfaces :** Découpes paramétriques sur plan de joint pour USB-C `J2` (10.2 x 4.2 mm), passage câble OBD-II (diamètre 6.8 mm), bouton Flash `SW1` (diamètre 3.0 mm) et voyant `LED1` (diamètre 2.0 mm).
- [x] **Fixation carte :** 4 bossages de fixation M2 alignés avec les perçages `MH1..MH4` du PCB (entraxes 74.28 x 28.56 mm), avec puits d'inserts thermofusibles diamètre 3.2 mm et lamages de vis diamètre 4.5 mm.
- [x] **Modélisation 3D (STEP / STL) :** Moteur OpenCASCADE paramétrique sous `.agents/skills/pcb-enclosure/`, exports STEP AP214 et STL haute résolution dans `documents/enclosure/` prêts pour impression 3D JLCPCB.

---

## 5. Dépôt Firmware & Logiciel Embarqué

Le développement du firmware est déporté dans un dépôt Git dédié (`obd2-esp32-firmware`).
L'ensemble des spécifications matérielles, registres et protocoles est consigné dans [`documents/software.md`](documents/software.md).

---

## 6. R&D & Outillage Méthodologique : Méta-Skill de Cycle de Vie Matériel ("Hardware Spec-Kit")

- [ ] **Conception d'un Méta-Skill de Gestion du Cycle de Vie Matériel (Analogie GitHub Spec-Kit) :**
  - **Vision & Cadrage :** Développer un moteur méthodologique d'orchestration de bout en bout pour guider l'agent IA et l'ingénieur à travers une démarche rigoureusement cadrée par la spécification (*Spec-Driven Hardware Engineering*).
  - **Machine à états finis du projet (Phase Gates formelles) :**
    1. *Gate 0 (Besoin & Architecture) :* Expression du besoin fonctionnel (`spec.json` : rails d'alimentation, tensions, bus, connectique, contraintes dimensionnelles, budget).
    2. *Gate 1 (Sémantique & BOM) :* Génération du graphe de nets, calcul théorique des composants (`ratio-solver`, `buck-compensation`), sélection optimale des références Basic Parts (`stingy-schematics`), certification ERC = 0.
    3. *Gate 2 (Mécanique & Floorplan) :* Définition des ancres, connecteurs frontières, zones d'exclusion RF et intégration boîtier 3D (`pcb-enclosure`).
    4. *Gate 3 (Placement par Contraintes) :* Auto-placement stochastique sous contraintes CEM/thermiques (`pcb-placer`, découplage immédiat < 2 mm, boucle Buck compacte, génération SVG).
    5. *Gate 4 (Routage & Continuité de Masse) :* Routage différentiel Specctra (`freerouting`), stitching de plans de masse et pontage d'îlots (`pcb-stitcher`), certification DRC = 0.
    6. *Gate 5 (Sérigraphie & Détrompage) :* Marquage fonctionnel déclaratif, repérage des cavaliers et du brochage (`pcb-silkscreen`).
    7. *Gate 6 (Assurance Qualité DFM/SMT) :* Audit industriel automatisé (`pcb-dfm`, 0 alerte Danger de vernis/via-to-pad, cohérence BOM/CPL).
    8. *Gate 7 (Release & Fabrication) :* Exportation automatique du dossier usine (`export_fabrication`, Gerbers 4 couches, centroïdes CPL, BOM SMT).
  - **Invariants & Contrats Formels :** Définition de schémas JSON stricts à chaque étape pour interdire toute transition de phase tant que les critères d'acceptation ne sont pas formellement certifiés.
