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

## 1. Dossier de Fabrication (JLCPCB)

- [ ] **Génération des fichiers Gerber & Drill :** Export standard 4 couches (JLC2313) depuis EasyEDA Pro avec perçages PTH/NPTH.
- [ ] **Export BOM SMT :** Nomenclature consolidée au format JLCPCB SMT avec codes LCSC validés ([`documents/schema/bom.json`](documents/schema/bom.json)).
- [ ] **Export Pick & Place (CPL) :** Fichier de centroïdes avec coordonnées XY et rotations corrigées pour l'assemblage CMS automatisé.

---

## 2. Recette Matérielle & Protocole de Bring-up (Mise en service)

Procédure séquentielle de mise sous tension et de validation des cartes à réception d'usine :

### Étape 2.1 : Contrôles Visuels & Mécaniques (Hors Tension)
- [ ] **Inspection optique sous microscope/loupe :**
  - Vérifier l'absence de ponts d'étain (solder bridges), particulièrement sur `U1` (ESP32-S3), `U4` (TPS54331), `U2` (TJA1051) et `U3` (L9637D).
  - Contrôler l'alignement et la polarité des composants critiques : diodes (`D1`, `D2`, `D3`, `D4`, `D5`, `D6`), condensateurs polarisés et CI (broche 1).
  - Vérifier la netteté de la sérigraphie face arrière et l'intégrité des 4 perçages mécaniques M2.

### Étape 2.2 : Contrôle d'Isolement & Dépistage de Courts-Circuits (Hors Tension)
- [ ] **Mesure de résistance à l'ohmmètre face au plan GND :**
  - Rail `+12V` (broche 1 de `J1` ou `H3`) face à `GND` : résistance attendue > 10 kΩ (montée capacitive).
  - Rail `+5V` (`TP2` / sortie Buck `U4` / `VBUS`) face à `GND` : résistance attendue > 1 kΩ.
  - Rail `3.3V` (`TP6` / sortie LDO `U5` / alimentation ESP32) face à `GND` : résistance attendue > 500 Ω.
  - Lignes de bus : vérifier l'isolement entre `CANH`, `CANL`, `K-LINE` et la masse (`GND`).

### Étape 2.3 : Bring-up Alimentation USB Seule (VBUS 5V)
- [ ] **Mise sous tension via USB-C (`J2`) avec surveillance de courant :**
  - Alimenter via un port USB avec wattmètre / limitation à 250 mA.
  - Vérifier le courant de repos : attendu entre 30 mA et 70 mA (ESP32 non programmé / en bootloader).
  - Mesurer la tension `3.3V` sur `TP6` : doit être comprise entre 3.25V et 3.35V.
  - Vérifier que `VBAT_SENSE` (`TP7`) est inférieur à 0.3V (signature USB-seule sans fausse détection batterie).
  - Valider l'énumération USB du microcontrôleur sur le PC hôte (périphérique USB JTAG/serial ou port COM natif).
  - Flash d'un micro-firmware de test (« blinky » sur `LED1` et sortie texte série UART).

### Étape 2.4 : Bring-up Alimentation Laboratoire 12V (Bench Power H3)
- [ ] **Mise sous tension 12V sécurisée :**
  - Régler l'alimentation de laboratoire à 12.0V avec limitation de courant stricte à 100 mA (OCP).
  - Raccorder sur l'embase `H3` (broche 1 = `+12V`, broche 2 = `GND`).
  - Mesurer le courant d'entrée global : attendu entre 20 mA et 45 mA à vide.
  - Valider la tension du rail Buck `+5V` sur `TP2` : doit être stable entre 4.90V et 5.15V.
  - Valider la tension du rail LDO `3.3V` sur `TP6` : 3.30V ± 2 %.
  - Mesurer le diviseur ADC `VBAT_SENSE` sur `TP7` : attendu ~1.09V pour VIN = 12.0V (rapport nominal 1/11).
  - Vérifier la propreté spectrale (ondulation / ripple résiduel) au multimètre AC / oscilloscope sur les rails 5V et 3.3V (< 50 mV crête).

### Étape 2.5 : Validation des Émetteurs-Récepteurs CAN & K-Line
- [ ] **Test de la terminaison et du transceiver CAN (`U2`) :**
  - Cavalier `JP1` fermé (mode SIMU) : vérifier que la résistance entre `CANH` et `CANL` sur `J1` vaut environ 120 Ω.
  - Cavalier `JP1` ouvert (mode SCANNER) : résistance > 10 kΩ.
  - Émission de trames CAN de test (TWAI loopback / écoute passive) : contrôler les signaux `CANH` (~3.5V dominant) et `CANL` (~1.5V dominant) au scope.
- [ ] **Test de la ligne K-Line (`U3`) :**
  - Cavalier `JP2` fermé (mode SCANNER) : vérifier la présence du pull-up vers +12V (niveau haut au repos ~12V).
  - Cavalier `JP2` ouvert (mode SIMU) : niveau haute impédance (bus flottant / sans pull-up fort).
  - Test d'écho / boucle locale UART : injecter une séquence 0x55 (Fast-Init) et vérifier le décodage sans gigue sur la broche RX.

### Étape 2.6 : Test Radiofréquence & Immunité Transitoire
- [ ] **Test d'émission Wi-Fi / BLE :**
  - Activer la transmission RF maximale (802.11b/g/n) et surveiller la stabilité du régulateur `U5` (aucun brownout lors des appels de courant crête ~250-350 mA).

---

## 3. Conception du Boîtier & Intégration Mécanique

- [ ] **Maintien mécanique du faisceau OBD-II :** Concevoir le serre-câble / passe-fil pour décharger mécaniquement les contraintes de traction sur le connecteur `J1` (JST-XH 5P coudé).
- [ ] **Accès connectique & interfaces :** Dégager les ouvertures pour le connecteur USB-C `J2`, le bouton Flash `SW1` et le guide de lumière de `LED1`.
- [ ] **Fixation carte :** Intégrer les 4 bossages de fixation M2 alignés avec les perçages du PCB (entraxes conformes à [`constraints.json`](documents/pcb/constraints.json)).
- [ ] **Modélisation 3D (STEP / STL) :** Export et validation des tolérances d'assemblage pour impression 3D / usinage.

---

## 4. Dépôt Firmware & Logiciel Embarqué

Le développement du firmware est déporté dans un dépôt Git dédié (`obd2-esp32-firmware`).
L'ensemble des spécifications matérielles, registres et protocoles est consigné dans [`documents/software.md`](documents/software.md).
