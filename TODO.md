# Feuille de Route & Checklist Active (TODO)

Ce document constitue le plan d'action opérationnel du projet **Scanner OBD-II ESP32**.
Il suit la conception matérielle (schéma, placement, routage, fabrication) et logicielle (firmware ESP32).

---

## Phase 1 : Schéma Électrique & Nomenclature (BOM)
- [x] **Schéma électrique complet & vérifié :** ERC = 0 strict sous EasyEDA Pro, nets explicites (aucun `$1N...`), ports et connecteurs reliés.
- [x] **Nomenclature BOM consolidée & Sémantique :** 84 composants synchronisés dans [`BOM.md`](BOM.md) et [`circuit_semantics.json`](circuit_semantics.json), sélection optimisée en Basic Parts JLCPCB (~48 $ économisés).
- [x] **Annotations fonctionnelles du schéma [review004 M1 / review005 I1] :** Cartouches d'instructions explicites ajoutés sur les pages 2 (`JP1` : CAN 120 Ω) et 3 (`JP2` : K-Line 500 Ω) documentant les modes CAR vs BENCH.

---

## Phase 2 : Placement PCB & Skill `pcb-placer`

### 2.1 Refonte & Implémentation du skill `pcb-placer` (v2.0)

#### Phase 0 : Fondations de Données & Extraction Géométrique Live
- [x] **Validation des schémas & Cohérence des données (`validate.py`) :**
  - Écrire et exécuter le validateur formel vérifiant la cohérence stricte entre `circuit_manifest.json` et `board_constraints.json`.
  - Contrôler l'alignement des 84 composants avec la BOM, les boîtiers IPC, les ancres de bordure fixes (`J1`, `J2`, `U1`), les 4 trous M2 et les keepouts.
- [x] **Extracteur géométrique EasyEDA (`export_geometry.py`) :**
  - Développer l'extraction live via l'API EasyEDA Pro : récupération de l'état actuel du PCB, des dimensions réelles des pads, de leurs offsets (dx, dy) à rotation 0°, et du graphe broche-à-broche de la netlist.
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

#### Phase 3 : Micro-Placement CP-SAT & Raffinement LNS *(Optionnel / Évolutions futures)*
> *Note : Le recuit simulé multi-départs combiné à la légalisation géométrique déterministe (Phase 2 & 4) a directement convergé vers un placement sans collision (0 mm², DRC = 0), rendant les solveurs CP-SAT/LNS superflus pour cette révision.*
- [x] **Légalisation géométrique finale :** Intégrée directement dans `simulated_annealing.py` pour éliminer tout chevauchement résiduel. *(Validé : 0 collision, DRC = 0)*
- [ ] **Solveur Exact de Clusters Rigides (`cpsat_cluster.py`) :** Module optionnel pour placement exact sous contraintes dures CP-SAT d'OR-Tools.
- [ ] **Raffineur Local LNS (`lns_refiner.py`) :** Module optionnel d'optimisation par fenêtres glissantes résolues par CP-SAT.

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
- [x] **Paire différentielle USB (`USB_D+` / `USB_D-`) :** Impédance contrôlée 90 Ω, skew < 2 mm, routage direct depuis `J2` à travers `U6`/`U7` vers GPIO19/20. *(Validé : 100% routé via FreeRouting, 0 Clearance Error)*
- [x] **Paire différentielle CAN (`CANH` / `CANL`) :** Impédance contrôlée 120 Ω, skew < 5 mm, routage symétrique à 45° entre `U2`, `JP1` et le bornier `J1`. *(Validé : 100% routé via FreeRouting, 0 Clearance Error)*
- [x] **Lignes numériques TWAI & UART :** Liaisons TWAI (`TWAI_TX`, `TWAI_RX`) et UART K-Line (`K_RX_IC`, `KLINE_RX`, `K_TX_IC`, `KLINE_TX` via résistances d'amortissement `R1`/`R2`). *(Validé : 100% routé via FreeRouting, 0 Clearance Error)*

### Rails d'alimentation de puissance
- [x] **Rails 12V d'entrée (`+12V`, `+12V_FUSED`, `+12V_PROT`) :** Pistes larges de 0.8 mm depuis le bornier d'entrée jusqu'au convertisseur Buck `U4`. *(Validé : 100% routé via FreeRouting)*
- [x] **Distribution des rails régulés :** Distribution à faible impédance du `+5V` (0.6 mm) vers `U5` et `U2`, puis du `3.3V` purifié (0.6 mm) via la perle de ferrite `FB1` vers l'ESP32 et les étages logiques. *(Validé : 100% routé via FreeRouting)*

### Plans de masse, CEM & Dissipation thermique
- [x] **Keepout RF d'antenne multicouche :** Définir sur toutes les couches (*All Layers*) la zone d'exclusion stricte (NO_WIRES, NO_FILLS, NO_POURS) sous et autour de l'antenne méandre 2.4 GHz de l'ESP32. *(Validé : 0 piste, 0 via sous l'antenne)*
- [x] **Règle de routage PCB - Retour de masse direct des TVS [review005 M4] :** Relier les broches de masse des diodes de protection (`D1`, `D5`, `U8`) au plan de référence avec via d'échappement direct (via de `D1` injecté avec garde > 0.28 mm). *(Validé)*
- [ ] **Plans de masse continus Top et Bottom (`GND`) & Skill `pcb-stitcher` :**
  - [x] Coulage des zones de cuivre pleines `POUR1` (TopLayer) et `POUR2` (BottomLayer).
  - [x] Création et documentation du skill autonome [`.agents/skills/pcb-stitcher/`](.agents/skills/pcb-stitcher/) (moteur agnostique, détection continue segment-segment, fanout automatique et arbre couvrant A* multi-couches).
  - [x] Pose des 34 vias de couture et raccordement de 100% des pastilles de masse (**0 Connection Error** au DRC).
  - [ ] **Résolution des 13 Clearance Errors résiduelles (Point d'arrêt / Reprise) :** Remplacer les 3 segments rectilignes de pontage d'îlots par les chemins d'évitement calculés par l'algorithme A* (`island_bridger.py`) pour éliminer les violations de dégagement.
- [ ] **Vias de couture (stitching) de renfort :** Maillage régulier de vias additionnels le long du contour de carte si nécessaire après élimination des erreurs DRC.

### Sérigraphie Finale & Clôture Matérielle (PCB)
- [ ] **Sérigraphie PCB des Cavaliers [review004 M1 / review005 I1] :** Texte compact d'aide à l'utilisateur sur les cavaliers (`JP1` : *« OPEN = CAR / SHUNT = BENCH »*, `JP2` : *« SHUNT = CAR / OPEN = BENCH HI-Z »*) sur la couche Top Silk Layer après finalisation des plans de masse.
- [ ] **Contrôle DRC physique strict post-routage :** Exécuter le DRC PCB sous EasyEDA Pro avec plans de masse coulés et certifier **0 erreur, 0 avertissement (DRC = 0 strict)**.
- [ ] **Inspection 3D finale :** Contrôle visuel 3D de l'assemblage complet (`images/3D.png`, `images/2D-TOP.png` et `images/2D-BOTTOM.png`), du contour de carte et des dégagements mécaniques des connecteurs `J1` et `J2`.
- [ ] **Étapes post-validation et clôture bloquante (Section 4 [AGENTS.md](AGENTS.md)) :**
  - Sauvegarde définitive du PCB (`eda.pcb_Document.save()`).
  - Contrôle ERC Schéma = 0 sous EasyEDA Pro.
  - Validation de synchronisation sémantique (`uv run python .agents/skills/stingy-schematics/scripts/sync_semantics.py check --bom BOM.md --semantics circuit_semantics.json`).
  - Capitalisation technique dans [`LEARNINGS.md`](LEARNINGS.md) avec le nouveau skill `pcb-stitcher`.
  - Export de l'archive projet `easyeda/OBD2.epro2`.
  - Demande des exports graphiques haute résolution (`Schematic.png`, `PCB.png`, `2D-TOP.png`, `2D-BOTTOM.png`, `3D.png`).
  - Accord explicite sur le message de commit avant tout commit/push Git.

---

## Conception du boîtier & Intégration Mécanique

- [ ] **Maintien mécanique du faisceau OBD-II :** Concevoir le serre-câble / passe-fil pour décharger mécaniquement les contraintes de traction sur le bornier à vis `J1`.
- [ ] **Accès connectique & interfaces :** Dégager les ouvertures pour le connecteur USB-C `J2`, le bouton Flash `SW1` et le guide de lumière de `LED1`.
- [ ] **Fixation carte :** Intégrer les 4 bossages de fixation M2 alignés avec les perçages du PCB.
- [ ] **Modélisation 3D (STEP / STL) :** Export et validation des tolérances d'assemblage pour impression 3D / usinage.

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
