# Feuille de Route & Checklist Active (TODO)

Ce document constitue le plan d'action opérationnel du projet **Scanner OBD-II ESP32**.
Il est structuré en **3 grandes parties fondamentales** ordonnées selon le cycle d'ingénierie :
1. **Pipeline de Conception & Fabrication du PCB** (Le Virtuel / CAD — Chronologie d'exécution)
2. **Protocole de Bring-up & Recette Matérielle** (Le Physique / Banc d'essai à réception usine)
3. **Méta-Skill de Cycle de Vie Matériel (« Hardware Spec-Kit »)** (La Méthodologie & R&D)

---

## 🏁 Synthèse des Jalons Matériels Clôturés

- ✅ **Schéma Électrique & BOM** : 85 composants validés, ERC = 0, nomenclature 100% optimisée en Basic Parts JLCPCB ([`documents/schema/bom.json`](documents/schema/bom.json), [`documents/schema/semantics.json`](documents/schema/semantics.json)).
- ✅ **Auto-Placement PCB (`pcb-placer`)** : 84 composants placés sans collision, découplage immédiat < 2 mm, boucle Buck compacte, courtyards IPC-7351 validés ([`documents/pcb/placement.svg`](documents/pcb/placement.svg)).
- ✅ **Auto-Routage Headless & Plans (`pcb-synthesizer`)** : 100 % des signaux routés, paires différentielles USB/CAN, plans de masse multi-couches continus, DRC natif EasyEDA Pro = 0.
- ✅ **Sérigraphie Déclarative & Boucle Fermée (`pcb-silkscreen`)** : 25 primitives face arrière injectées, 0 OOB, 0 perforation via, 0 conflit pastille, 4 rendus d'inspection générés ([`documents/pcb/silkscreen.json`](documents/pcb/silkscreen.json), [`documents/pcb/2d-bottom.png`](documents/pcb/2d-bottom.png)).
- ✅ **Modélisation Mécanique du Boîtier (`pcb-enclosure`)** : Coques 3D et bride serre-câble 2 vis M2 générées en STEP/STL ([`documents/enclosure/`](documents/enclosure/)).

---

## PARTIE 1 : Pipeline de Conception & Fabrication du PCB (Le Virtuel / CAD)

Cette section est organisée **strictement selon l'ordre séquentiel d'exécution**, depuis l'initialisation du PCB brut jusqu'au dossier final de fabrication.

### Étape 0 : Amont & Bootstrap Automatique du PCB Brut
- [ ] **[BLOQUANT] Bootstrap PCB Idempotent :** Ajouter une étape d'initialisation au début de `PcbSynthesizer.execute_closed_loop()` dans `synthesizer_pipeline.py` qui exécute automatiquement via `EasyEDAClient` :
  1. Validation `ERC = 0` via `eda.sch_Drc.check(true, false, true)` et conformité sémantique via `sync_semantics.py check`.
  2. Synchronisation schéma vers PCB `sync_schematic_to_pcb(auto_confirm=True)`.
  3. Configuration du stackup 4 couches `eda.pcb_Layer.setTheNumberOfCopperLayers(4)`.
  4. Création idempotente du contour de carte sur Layer 11 depuis `outline_polygon_mm`.
  5. Instanciation des perçages de fixation mécanique `MH1` à `MH4` (trous M2, net `GND`).

### Étape 1 : Modélisation des Données & Manifeste Dynamique
- [ ] **[BLOQUANT] Générateur Dynamique de Manifeste (`manifest_builder.py`) :** Extraire les composants synchronisés dans EasyEDA Pro (`getState_BBox()`, centroïdes, pastilles) et croiser ces données avec `semantics.json` (rôles fonctionnels, découplages, boucles critiques) et `constraints.json` (`anchors`, keepouts) pour synthétiser `manifest.json` automatiquement et éliminer toute maintenance manuelle.
- [ ] **[IMPORTANT] Séparation Profil Fabricant (`rules_jlcpcb.json`) vs Contraintes Projet (`constraints.json`) :** Extraire les constantes d'usine (DFM, tolérances, stackup JLC2313) dans `.agents/skills/pcb-dfm/config/rules_jlcpcb.json` et alléger `constraints.json` pour qu'il ne conserve que les entrées spécifiques à la carte (ancres, dimensions, classes de nets).

### Étape 2 : Placement sous Contraintes CEM & Découplage HF
- [x] **Placement Initial Validé :** 84 composants implantés sans chevauchement, découplage immédiat < 2 mm et boucle Buck compacte ([`documents/pcb/placement.svg`](documents/pcb/placement.svg)).
- [ ] **[IMPORTANT] Harmonisation CEM Recuit Simulé (`simulated_annealing.py`) & Juge (`score.py`) :** Intégrer dans le calcul incrémental de recuit les termes CEM `net_compact` (`PH_BUCK`) et `cluster_cohesion` (< 10 mm), respecter les `hard_proximities` lors de la légalisation (`legalize()`), et activer l'atténuation angulaire magnétique à 90° (`magnetic_field_coupling`).
- [ ] **[IMPORTANT] Découplage Hors-Ligne de la Boucle de Synthèse (`Extract Once -> Loop Offline -> Materialize Once`) :** Permettre l'enchaînement complet placement (`simulated_annealing.py`), routage (`FreeRoutingRunner`), métrologie (`dsn_metrics.py`), couture de masse (`pcb-stitcher`) et sérigraphie en pur Python/Java sans requêtes intermédiaires bloquantes, en n'injectant le résultat final dans EasyEDA Pro qu'une seule fois après convergence.

### Étape 3 : Routage Différentiel & Métrologie CEM Post-Routage
- [x] **Routage 4 Couches Certifié :** 100% des signaux routés, paires différentielles USB/CAN, 0 croisement, DRC = 0.
- [ ] **[BLOQUANT] Condition d'Arrêt Métrologique CEM :** Remplacer le critère d'arrêt basique dans `synthesizer_pipeline.py` par l'exigence `report.is_valid` pour que tout dépassement d'aire de boucle critique (`PC_BUCK_HOT_LOOP`), de skew différentiel (`USB_D+`/`USB_D-`, `CANH`/`CANL`) ou de nombre de vias sur signaux critiques déclenche le resserrement adaptatif des contraintes de placement.

### Étape 4 : Continuité de Masse & Couture de Blindage
- [x] **Plans de Masse & Vias de Couture :** Continuité GND multi-couches et blindage périphérique de carte via `pcb-stitcher` (DRC = 0).

### Étape 5 : Sérigraphie Fonctionnelle & Contrôle Visuel 2D/3D
- [x] **Boucle Fermée Sérigraphie Validée :** Moteur `silkscreen_feedback_loop.py` et `export_pcb_images.py` opérationnels (0 OOB, 0 perforation via, 0 conflit pastille sur les 25 primitives face arrière, et génération automatique de `2d-top.png`, `2d-bottom.png`, `3d.png`, `pcb.png`).

### Étape 6 : Audit DFM & Finitions Physiques (JLCPCB)
- [ ] **Ponts de vernis épargne à pas fin (*Soldermask Bridge* >= 0.10 mm) :** Réduire l'expansion du vernis épargne (*Solder Mask Expansion*) de 0.05 mm à 0.025 mm (1 mil) sur les broches à pas dense (connecteur USB-C `J2` et module ESP32-S3 `U1`) afin de préserver un barrage de vernis physique >= 0.10 mm (seuil capability verte JLCPCB) et éliminer les 12 alertes Danger de fusion en *gang mask*.
- [ ] **Sécurisation & Recouvrement des Vias CMS (*Via to Pad / Tenting*) :** Décaler les vias de couture ou d'échappement en contact direct (0 mm) avec les pastilles de composants CMS pour insérer un col de piste de dégagement >= 0.15–0.20 mm (*dog-bone*), et certifier le recouvrement de vernis (*Via Tenting* Top & Bottom à 100%) afin d'éliminer les 50 alertes Danger de siphonnage de brasure (*solder wicking*).
- [ ] **Épaisseur des traits de sérigraphie (*Stroke Width*) :** Porter l'épaisseur des traits de texte et de contour à 0.18–0.20 mm (notamment dans [`documents/pcb/silkscreen.json`](documents/pcb/silkscreen.json) et EasyEDA) pour garantir une impression nette et contrastée face au seuil d'alerte DFM de 0.15 mm.

### Étape 7 : Packaging Production Clé en Main & Assemblage 3D
- [ ] **[BLOQUANT] Chaînage Automatique des Livrables de Production :** Chaîner automatiquement à la fin de `synthesizer_pipeline.py` (dès que `DRC == 0`) :
  1. Export usine Gerber, Drill, CPL et BOM SMT via `export_fabrication.py` vers `documents/production/`.
  2. Génération du pack d'images de contrôle (`2d-top.png`, `2d-bottom.png`, `3d.png`, `pcb.png`) via `export_pcb_images.py`.
  3. Export du projet natif `documents/easyeda/OBD2.epro2` via `eda.sys_FileManager.getProjectFile()`.
  4. Export du STEP 3D du PCBA garni via `eda.pcb_ManufactureData.get3DFile()`.
- [ ] **[IMPORTANT] Contrôle de Collision 3D Assemblage PCBA + Boîtier :** Importer le STEP 3D du PCBA garni dans `enclosure_generator.py` via `bd.import_step()`, calculer par opération booléenne OpenCASCADE le volume d'interférence avec les coques (`collision_volume == 0`) et générer `documents/enclosure/enclosure_pcba_full.step`.
- [ ] **[MINEUR] Commande CLI Unique Clé en Main (`--turnkey`) :** Piloter l'ensemble de la chaîne (Étapes 0 à 7) via un point d'entrée unique autonome.

---

## PARTIE 2 : Protocole de Bring-up & Recette Matérielle (Le Physique / Banc d'essai)

Cette section détaille la procédure séquentielle de mise sous tension et de validation des cartes à réception des prototypes physiques de l'usine JLCPCB.

### 2.1 Contrôles Visuels & Mécaniques (Hors Tension)
- [ ] **Inspection optique sous microscope/loupe :**
  - Vérifier l'absence de ponts d'étain (*solder bridges*), particulièrement sur `U1` (ESP32-S3), `U4`, `U5`, `U2` et `U3`.
  - Contrôler l'alignement et la polarité des composants critiques : diodes (`D1` à `D6`), condensateurs polarisés et repère broche 1 des circuits intégrés.
  - Vérifier la netteté de la sérigraphie face arrière et l'intégrité des 4 perçages mécaniques M2 (`MH1` à `MH4`).

### 2.2 Contrôle d'Isolement & Dépistage de Courts-Circuits (Hors Tension)
- [ ] **Mesure de résistance à l'ohmmètre face au plan GND :**
  - Rail `+12V` (broche 1 de `J1` ou `H3`) face à `GND` : résistance attendue > 10 kΩ (charge capacitive).
  - Rail `+5V` (`TP5` / sortie Buck `U4` / `VBUS`) face à `GND` : résistance attendue > 1 kΩ.
  - Rail `3.3V` (`TP6` / sortie LDO `U5` / alim ESP32) face à `GND` : résistance attendue > 500 Ω.
  - Lignes de bus : vérifier l'isolement entre `CANH`, `CANL`, `K-LINE` et la masse (`GND`).

### 2.3 Bring-up Alimentation USB Seule (VBUS 5V)
- [ ] **Mise sous tension via USB-C (`J2`) avec surveillance de courant :**
  - Alimenter via port USB sécurisé avec wattmètre / limitation de courant à 250 mA.
  - Vérifier le courant de repos : attendu entre 30 mA et 70 mA (ESP32 vierge / bootloader).
  - Mesurer la tension `3.3V` sur `TP6` : attendu entre 3.25V et 3.35V.
  - Mesurer `VBAT_SENSE` (`TP9`) sous USB seul : vérifier la tension résiduelle (~0.35–0.45V due à la remontée du 5V USB à travers L1 et la diode de corps High-Side de U4 vers `+12V_PROT` ; Q1 bloque hermétiquement tout retour vers J1/H3) — calibrer le seuil logiciel de détection batterie présente à Vbat > 6.0V (VBAT_SENSE > 0.64V) pour immuniser le firmware contre toute fausse détection.
  - *Note :* Le rail +5V sous USB seul est à ~4.35V (chute Schottky D4) < VCC min 4.5V du TJA1051T ; tester les transceivers exclusivement sous alimentation 12V.
  - Valider l'énumération USB du microcontrôleur sur le PC hôte (périphérique USB JTAG/serial natif).
  - Flash d'un micro-firmware de test (« blinky » sur `LED1` et sortie texte UART).

### 2.4 Bring-up Alimentation Laboratoire 12V (Bench Power H3)
- [ ] **Mise sous tension 12V sécurisée :**
  - Régler l'alimentation de laboratoire à 12.0V avec limitation de courant stricte à 100 mA (OCP).
  - Raccorder sur l'embase `H3` (broche 1 = `+12V`, broche 2 = `GND`).
  - Mesurer le courant d'entrée global : attendu entre 20 mA et 45 mA à vide.
  - Valider la tension du rail Buck `+5V` sur `TP5` : attendu stable entre 4.90V et 5.15V.
  - Valider la tension du rail LDO `3.3V` sur `TP6` : 3.30V ± 2 %.
  - Mesurer le diviseur ADC `VBAT_SENSE` sur `TP9` : attendu ~1.29V pour VIN = 12.0V (rapport nominal 1/9.33).
  - Contrôler l'ondulation résiduelle (*ripple*) à l'oscilloscope sur les rails 5V et 3.3V (< 50 mV crête).

### 2.5 Validation des Émetteurs-Récepteurs CAN & K-Line
- [ ] **Test du transceiver CAN (`U2` TJA1051T) & Terminaison :**
  - Cavalier `JP1` fermé (mode SIMU) : vérifier que la résistance entre `CANH` et `CANL` sur `J1` vaut 120 Ω.
  - Cavalier `JP1` ouvert (mode SCANNER) : vérifier une résistance > 10 kΩ.
  - Émission de trames CAN de test (TWAI loopback / écoute passive) : contrôler les niveaux `CANH` (~3.5V dominant) et `CANL` (~1.5V dominant) à l'oscilloscope.
- [ ] **Test de la ligne K-Line (`U3` SI9241A) & Pull-up :**
  - Cavalier `JP2` fermé (mode SCANNER) : vérifier la présence du pull-up vers +12V (niveau haut repos ~12V).
  - Cavalier `JP2` ouvert (mode SIMU) : niveau haute impédance (bus flottant / sans pull-up fort).
  - Test d'écho UART : injecter une séquence 0x55 (Fast-Init) et vérifier le décodage sans gigue sur RX.

### 2.6 Test Radiofréquence & Immunité Transitoire
- [ ] **Validation RF Wi-Fi / BLE :**
  - Activer la transmission RF maximale (802.11b/g/n) et surveiller la stabilité du régulateur `U5` (aucun brownout lors des appels de courant crête ~250–350 mA).

---

## PARTIE 3 : Méta-Skill de Cycle de Vie Matériel (« Hardware Spec-Kit ») (La R&D Méthodologique)

Cette section capitalise l'outillage et les algorithmes développés sur ce projet pour en faire un framework d'ingénierie matérielle modulaire et réutilisable piloté par spécification (*Spec-Driven Hardware Engineering*).

### 3.1 Vision & Principes d'Ingénierie Matérielle Pilotée par l'IA
- **Analogie GitHub Spec-Kit :** Formaliser un cadre méthodologique outillé de bout en bout où chaque étape de conception est strictement cadrée par des spécifications formelles (`spec.json`, `semantics.json`, `constraints.json`, `manifest.json`), interdisant toute modification en aveugle.
- **Approche *Contract-First* :** Définition de schémas JSON stricts à chaque jalon. Aucune transition de phase n'est autorisée tant que les critères d'acceptation physiques et normatifs ne sont pas formellement certifiés par l'agent.

### 3.2 Machine à États Finis du Matériel (Phase Gates 0 à 7)
- [ ] **Formalisation des 8 Phase Gates du cycle matériel :**
  1. *Gate 0 (Besoin & Architecture) :* Expression fonctionnelle formelle (`spec.json` : rails d'alimentation, topologies, bus, interfaces, contraintes dimensionnelles, budget).
  2. *Gate 1 (Sémantique & BOM) :* Graphe de connectivité, calcul mathématique des composants (`ratio-solver`, `buck-compensation`), sélection optimale Basic Parts JLCPCB (`stingy-schematics`), certification `ERC = 0`.
  3. *Gate 2 (Mécanique & Floorplan) :* Définition des ancres, connecteurs frontières, keepouts RF et intégration boîtier 3D paramétrique (`pcb-enclosure`).
  4. *Gate 3 (Placement par Contraintes) :* Auto-placement stochastique par recuit simulé sous contraintes CEM/thermiques (`pcb-placer`, découplage HF < 2 mm, boucles de commutation compactes, génération SVG).
  5. *Gate 4 (Routage & Continuité de Masse) :* Routage différentiel Specctra (`freerouting`), plans de masse continus, stitching de bord et pontage d'îlots (`pcb-stitcher`), certification `DRC = 0`.
  6. *Gate 5 (Sérigraphie & Détrompage) :* Marquage fonctionnel déclaratif, repérage des cavaliers et du brochage, boucle fermée sans collision (`pcb-silkscreen`).
  7. *Gate 6 (Assurance Qualité DFM/SMT) :* Audit automatisé de fabricabilité (`pcb-dfm`, 0 alerte Danger de vernis/via-to-pad, cohérence BOM/CPL).
  8. *Gate 7 (Release & Fabrication) :* Exportation automatique du dossier de production usine (`export_fabrication`, Gerbers 4 couches, centroïdes CPL, nomenclature SMT, rendus 2D/3D).

### 3.3 Orchestration Modulaire de la Suite de Skills
- [ ] **Découplage pur des moteurs algorithmiques (Règle 1 AGENTS.md) :**
  - Maintien strict de zéro composant codé en dur dans `.agents/skills/*`.
  - Standardisation des interfaces CLI (`--config`, `--constraints`, `--placement`, `--output`).
  - Encapsulation des interactions logicielles dans des connecteurs EDA indépendants (EasyEDA Pro, KiCad à terme).

---

## 📌 Répertoire Logiciel & Firmware Embarqué

Le développement logiciel du firmware applicatif est déporté dans un dépôt Git dédié (`obd2-esp32-firmware`).
L'ensemble des spécifications matérielles, registres et protocoles de communication est documenté dans [`documents/software.md`](documents/software.md).
