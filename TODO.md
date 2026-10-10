# Feuille de Route & Checklist Active (TODO)

Ce document constitue le plan d'action opérationnel du projet **Scanner OBD-II ESP32**.
Il suit la conception matérielle (schéma, placement, routage, fabrication) et logicielle (firmware ESP32).

---

## Schéma Électrique & Nomenclature (BOM)

---

## Phase 2 : Placement PCB & Skill `pcb-placer`

### 2.1 Refonte & Implémentation du skill `pcb-placer` (v2.0)

#### Phase 0 : Fondations de Données & Extraction Géométrique Live
- [x] **Validation des schémas & Cohérence des données (`validate.py`) :**
  - Écrire et exécuter le validateur formel vérifiant la cohérence stricte entre `circuit_manifest.json` et `board_constraints.json`.
  - Contrôler l'alignement des 84 composants avec la BOM, les boîtiers IPC, les ancres de bordure fixes (`J1`, `J2`, `U1`), les 4 trous M2 et les keepouts.
- [x] **Extracteur géométrique EasyEDA (`export_geometry.py`) :**
  - Développer l'extraction live via l'API EasyEDA Pro : récupération de l'état actuel du PCB, des dimensions réelles des pads, de leurs offsets $(dx, dy)$ à rotation 0°, et du graphe broche-à-broche de la netlist.
  - Stocker ces données de manière transparente en cache local (sans polluer Git).

#### Phase 1 : Évaluateur Indépendant (`score.py`) & Rendu SVG
- [x] **Moteur de score physique normalisé (`score.py`) :**
  - Implémenter le calcul objectif des termes adimensionnés : HPWL global de câblage, proximités pad-à-pad CEM, compacité de la boucle chaude `PH_BUCK`, séparation agresseurs/victimes, accessibilité bord de carte.
  - Intégrer la détection stricte des contraintes dures : hors-carte, chevauchement de courtyards, intrusion keepout RF, collisions avec les têtes de vis M2.
- [x] **Générateur vectoriel SVG (`render_svg.py`) :**
  - Générer un rendu visuel vectoriel du placement : contour de carte, vis M2, courtyards colorés par bloc fonctionnel, zones keepout hachurées, et vecteurs de force élastiques.
- [x] **Mesure de la Baseline (Score de référence) :**
  - Évaluer le score du placement manuel existant sur le PCB pour établir la note de référence absolue à battre.

#### Phase 2 : Moteur de Placement Global par Recuit Simulé (Étage B)
- [x] **Solveur Stochastique Global (`simulated_annealing.py`) :**
  - Développer le moteur de recuit multi-départs parallélisé (16 à 64 graines aléatoires).
  - Inclure un départ initialisé sur la baseline existante (garantie mathématique de non-régression).
  - Implémenter les mouvements de voisinage : translation gaussienne, swap de composants de gabarits compatibles, rotation selon `allowed_rotations`, attraction barycentrique vers les broches connectées.
  - Valider l'obtention d'un placement complet sans aucune violation dure (0 chevauchement, 0 keepout) et améliorant le score face à la baseline. *(Validé : 0 collision, 0 violation dure, score 8.2732 vs baseline invalide)*

#### Phase 3 : Micro-Placement CP-SAT (Étage A) & Raffinement LNS (Étage C)
- [ ] **Solveur Exact de Clusters Rigides (`cpsat_cluster.py`) :**
  - Modéliser sous OR-Tools CP-SAT le micro-placement exact des clusters critiques (`G_BUCK_CORE`, `G_ESP32_CORE`).
  - Optimiser au millimètre la boucle chaude de découpage et le découplage HF immédiat.
  - Figer les clusters résolus en macro-composants indéformables injectés dans l'Étage B.
- [ ] **Raffineur Local LNS (`lns_refiner.py`) :**
  - Implémenter l'optimisation par fenêtres glissantes résolues par CP-SAT sur les zones congestionnées (8 à 15 composants).
  - N'accepter les modifications que si `score.py` valide une amélioration stricte.
- [ ] **Légalisation finale :**
  - Alignement des composants libres sur la grille de fabrication finale (0.635 mm / 25 mil).

#### Phase 4 : Injection EasyEDA Pro & Certification DRC
- [x] **Actionneur d'injection atomique (`apply_placement.py`) :**
  - Application en lot des nouvelles coordonnées et orientations dans EasyEDA Pro via `eda.pcb_PrimitiveComponent.modify()`. *(Validé : 84 composants repositionnés en 4.32 s)*
- [x] **Boucle de contrôle & Certification DRC :**
  - Exécution du DRC physique natif EasyEDA Pro via `eda.pcb_Drc.run()` et contrôle pad-à-pad.
  - Validation du critère bloquant : DRC = 0 erreur, 0 avertissement.
  - Sauvegarde automatique du document PCB (`eda.pcb_Document.save()`). *(Validé)*
- [x] **Consolidation & Documentation :**
  - Mettre à jour `SKILL.md` avec la documentation utilisateur et les options de ligne de commande unifiées. *(Validé)*

#### Phase 5 : Optimisation de la Sérigraphie & Positionnement des Désignateurs (`label_placer.py`)
- [x] **Moteur de placement & orientation des désignateurs (`label_placer.py`) :**
  - **Dégagement strict des pastilles de cuivre :** Détecter et éliminer tout chevauchement entre les étiquettes de désignateurs (`pcb_PrimitiveAttribute` de type *Designator*) et les pastilles de cuivre (pads CMS / traversants), perçages de vis M2 et vias, afin d'éviter le rognage à la fabrication JLCPCB. *(Validé : 100% à l'extérieur des pastilles avec garde >= 0.20 mm)*
  - **Résolution des collisions texte-texte :** Détecter et éliminer les superpositions entre étiquettes de composants voisins dans les zones denses de passifs (autour de `U4`, `U2`, `U3`, `SW1`, `J1`). *(Validé : 0 collision texte-texte avec garde >= 0.15 mm)*
  - **Normalisation de l'orientation & typographie :** Aligner tous les labels selon les standards de lisibilité IPC (orientations à 0° ou 90° exclusivement, suppression des textes inversés à 180° ou 270°), avec une taille de police lisible et uniforme (hauteur 0.8 mm à 1.0 mm, épaisseur 0.15 mm). *(Validé : 63 à 0°, 21 à 90°, 0 à 180°/270°)*
  - **Actionneur d'injection sérigraphie EasyEDA Pro :** Mettre à jour en lot les coordonnées `(x, y)` et angles des attributs désignateurs via l'API EasyEDA Pro (`pcb_PrimitiveAttribute.modify()`). *(Validé : 84/84 désignateurs repositionnés en 2.61 s)*
  - **Validation & Actualisation des rendus :** Régénération et contrôle visuel des rendus `PCB.png`, `2D-TOP.png`, `2D-BOTTOM.png` et `3D.png`. *(Validé : dégagement parfait de C15, TP3, TP2, TP4, TP7, TP8, TP13, TP15, LED1)*
- [x] **Annotations Schéma des Cavaliers [review004 M1 / review005 I1] :**
  - Cartouches d'instructions explicites ajoutés sur les pages 2 (`JP1` : CAN 120 Ω) et 3 (`JP2` : K-Line 500 Ω + titre de section) documentant les modes CAR vs BENCH. *(Validé : ERC = 0, source epro2 synchronisé)*

---

## Phase 3 : Routage PCB & Skill `freerouting`

### 3.1 Développement & Intégration du skill `freerouting`
- [x] **Gestionnaire d'environnement d'exécution sous Windows :**
  - Intégrer le téléchargement et le bootstrap automatique d'une JRE portable headless (Temurin OpenJDK 25 via API Adoptium) et du JAR FreeRouting CLI v2.4.1 dans le cache local du skill sans dépendance système. *(Validé)*
- [x] **Pipeline Specctra DSN / SES :**
  - Extraction automatique du fichier `.dsn` depuis la session active EasyEDA Pro via `eda.pcb_ManufactureData.getDsnFile()`.
  - Patcher de contraintes DSN : injection des Net Classes et règles de routage depuis [`board_constraints.json`](board_constraints.json) (rails d'alimentation 12V à 0.8 mm, 5V/3V3 à 0.6 mm, signaux standards 0.254 mm, paires différentielles CAN/USB 0.30 mm / garde 0.20 mm, padstack_overrides fente USB-C).
  - Orchestration de l'exécution headless de FreeRouting avec suivi des passes et métriques d'achèvement.
  - Réimport automatisé du fichier `.ses` résultant dans EasyEDA Pro via `eda.pcb_Document.importAutoRouteSesFile()`. *(Validé)*
- [x] **Implémentation des modes opérationnels :**
  - **Mode `--incremental` :** Préservation stricte de toutes les pistes existantes verrouillées (`(fixed ...)` dans le format Specctra DSN), avec auto-routage ciblé du seul chevelu manquant.
  - **Mode `--clean` :** Dépouillement des pistes non protégées (couches cuivre 1 & 2 sans toucher au contour mécanique couche 11) et re-routage intégral à blanc du PCB selon les contraintes globales. *(Validé)*
- [x] **Validation du skill sur la carte OBD-II :**
  - Exécution du routage complet et vérification du taux de complétion (100% des connexions routées : 219/219, 0 non routée) et certification DRC EasyEDA Pro = 0 violation. *(Validé)*

### Paires différentielles & Signaux critiques
- [ ] **Paire différentielle USB (`USB_D+` / `USB_D-`) :** Impédance contrôlée 90 Ω, skew < 2 mm, routage direct depuis `J2` à travers `U6`/`U7` vers GPIO19/20, puis verrouillage des pistes.
- [ ] **Paire différentielle CAN (`CANH` / `CANL`) :** Impédance contrôlée 120 Ω, skew < 5 mm, routage symétrique à 45° entre `U2`, `JP1` et le bornier `J1`, puis verrouillage des pistes.
- [ ] **Lignes numériques TWAI & UART :** Liaisons TWAI (`TWAI_TX`, `TWAI_RX`) et UART K-Line (`K_RX_IC`, `KLINE_RX`, `K_TX_IC`, `KLINE_TX` via résistances d'amortissement `R1`/`R2`).

### Rails d'alimentation de puissance
- [ ] **Rails 12V d'entrée (`+12V`, `+12V_FUSED`, `+12V_PROT`) :** Pistes larges de 0.8 mm à 1.0 mm depuis le bornier d'entrée jusqu'au convertisseur Buck `U4`.
- [ ] **Distribution des rails régulés :** Distribution à faible impédance du `+5V` vers `U5` et `U2`, puis du `3.3V` purifié via la perle de ferrite `FB1` vers l'ESP32 et les étages logiques.

### Plans de masse, CEM & Dissipation thermique
- [ ] **Keepout RF d'antenne multicouche :** Définir sur toutes les couches (*All Layers*) la zone d'exclusion stricte (NO_WIRES, NO_FILLS, NO_POURS) sous et autour de l'antenne méandre 2.4 GHz de l'ESP32.
- [ ] **Plans de masse continus Top et Bottom (GND) :** Coulage des plans de masse avec dégagement conforme (0.254 mm) et élimination des îlots flottants.
- [ ] **Vias de couture (stitching) :** Maillage régulier tous les 5 à 8 mm, renfort le long du contour de carte et aux condensateurs de découplage.
- [ ] **Vias thermiques de dissipation :** Matrice de vias thermiques sous le pad de cuivre du LDO `U5` (LDL1117) et sous le pad thermique central de l'ESP32 (`U1`).
- [ ] **Règle de routage PCB - Retour de masse direct des TVS [review005 M4] :** Relier les broches de masse des diodes de protection (`D1`, `D5`, `U8`) à la broche 8 (`GND`) de `J1` par une zone de cuivre courte et large (>= 2 mm ou polygone dédié avec multiples vias) avant connexion au plan de masse principal pour dériver l'énergie des transitoires sans traverser la zone logique.

### Sérigraphie Finale & Contrôles post-routage
- [ ] **Sérigraphie PCB des Cavaliers [review004 M1 / review005 I1] :** Texte compact d'aide à l'utilisateur sur les cavaliers (`JP1` : *« OPEN = CAR / SHUNT = BENCH »*, `JP2` : *« SHUNT = CAR / OPEN = BENCH HI-Z »*) sur la couche Top Silk Layer après finalisation des pistes et plans de masse (itération Label <-> Routage).
- [ ] **Contrôle DRC physique strict post-routage :** Exécuter le DRC PCB sous EasyEDA Pro avec plans de masse coulés et valider 0 erreur, 0 avertissement.
- [ ] **Inspection 3D finale :** Contrôle visuel 3D de l'assemblage complet (`images/3D.png`, `images/2D-TOP.png` et `images/2D-BOTTOM.png`), du contour de carte et des dégagements mécaniques des connecteurs `J1` et `J2`.

---

## Conception du boitier

- [ ] S'assurer que le boitier va maintenir en place le câble OBD2.

---


## Dossier de Fabrication (JLCPCB)

- [ ] Générer et valider les fichiers de fabrication Gerber & Drill (standard 2 couches JLCPCB).
- [ ] Exporter la nomenclature BOM consolidée au format JLCPCB SMT ([`BOM.md`](BOM.md)).
- [ ] Exporter le fichier de placement des composants (Pick & Place / CPL) pour l'assemblage CMS automatisé.

---

## Firmware & Logiciel Embarqué

### Architecture OS
- [ ] **Choisir l'OS**
- [ ] **Surveillance système & Télémétrie :** Détection brownout matérielle ESP32, watchdog FreeRTOS, mesure continue et étalonnage ADC1 de la tension batterie (`VBAT_SENSE`). Traiter une lecture de `VBAT_SENSE` autour de 4.0 V–4.3 V comme signature « Alimentation USB seule (sans 12V véhicule) » [review005 I2].

### Drivers matériels
- [ ] **Driver TWAI CAN :** Implémentation du protocole ISO 15765-4 avec machine d'état de détection automatique (500 kbps puis 250 kbps).
- [ ] **Driver UART K-Line :** Gestion de l'initialisation ISO 9141-2 (init 5-baud) et du protocole rapide KWP2000 (*fast-init*).
- [ ] **Couche Protocolaire Constructeur GM-Daewoo (K-Line / Kalos T200) :**
  - Implémentation de la pile logicielle KWP2000 étendue sur la broche 7 physique (`K_LINE`) avec adressage physique multi-calculateurs : ECM Moteur (`0x10`/`0x11`), TCM Boîte auto (`0x28`), EBCM ABS (`0x58`), et SDM Airbag (`0x50`/`0x51`).
  - Intégration des services de diagnostic propriétaires GM-Daewoo / DST (*Daewoo Specific Tools*) : Service `0x21` / `0x22` (*Read Data By Identifier / Local ID* pour lecture des capteurs et PIDs constructeurs hors-OBD2), décodage des codes défauts propriétaires (`P1xxx`, `Bxxxx`, `Cxxxx`) et routines de tests d'actionneurs.
- [ ] **Gestion de l'alimentation & Veille automatique (Auto-Sleep / Deep-Sleep) [review006 I2] :** Implémenter une machine d'état de veille automatique abaissant la consommation globale sous 1 mA après 5 à 10 minutes d'inactivité de communication et coupure moteur (détection via `VBAT_SENSE` <= 12.8 V), avec réveil sur détection d'activité CAN/K-Line ou remontée de tension (démarrage moteur), prévenant toute décharge de la batterie du véhicule en Cas 1 permanent.

### Connectivité & Interface utilisateur (Mode Scanner)
- [ ] **Pile réseau :** Serveur WebSocket et/ou service BLE GATT pour communication avec l'application mobile / tablette / PC.
- [ ] **Gestion de la LED témoin `LED1` :** Machine d'état des séquences lumineuses (démarrage, recherche protocole, bus actif, erreur alimentation).

### Firmware Simulateur d'ECU / Banc de Test (Même carte matérielle flashée en Serveur)
- [ ] **Sélecteur de mode de compilation :** Configuration logicielle (cible binaire distincte ou flag de compilation `#define MODE_ECU_SIMULATOR`) permettant d'exécuter la pile serveur sur la même carte.
- [ ] **Serveur de diagnostic TWAI CAN (ISO 15765-4) :**
  - Émission de trames cycliques périodiques (régime moteur RPM, vitesse véhicule, couple, température liquide de refroidissement).
  - Traitement des requêtes normalisées OBD-II (Mode 01 PID temps réel, Mode 02 Freeze Frames, Mode 03 / 07 DTCs, Mode 04 Effacement).
  - Couche transport ISO-TP (ISO 15765-2) pour les messages multi-trames et contrôle de flux.
- [ ] **Serveur de diagnostic K-Line (ISO 9141-2 / ISO 14230 KWP2000) :**
  - Répondeur d'initialisation lente 5-baud (mots-clés `0x08`, `0x08` ou spécifiques GM-Daewoo) et rapide (*Fast-Init* 25 ms).
  - Émulation des calculateurs Daewoo Kalos T200 (ECM `0x10`, TCM `0x28`, ABS `0x58`).
- [ ] **Interface de pilotage & Injection de pannes (Console CLI USB-C / Web) :**
  - Commandes interactives pour modifier en direct les PIDs moteur (ex. `set rpm 3500`, `set speed 90`, `set coolant 95`).
  - Commandes d'injection de codes défauts DTCs (ex. `fault inject P0300`, `fault clear`).
  - Simulation de pannes capteurs et profils dynamiques d'accélération / décélération pour tester les algorithmes du scanner.
