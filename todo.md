# Feuille de Route & Checklist Active (TODO)

Ce document constitue le plan d'action opérationnel du projet **Scanner OBD-II ESP32**.
Il recense les jalons majeurs validés et détaille les tâches restantes à accomplir.

---

## 🏁 Jalons Validés

- ✅ **Phase 1 : Schéma Électrique & Nomenclature (BOM)** : 85 composants validés (70 physiques + 15 mires TP), ERC = 0 strict, nomenclature optimisée en Basic Parts JLCPCB ([`documents/schema/bom.json`](documents/schema/bom.json), [`documents/schema/semantics.json`](documents/schema/semantics.json)).
- ✅ **Phase 2 : Auto-Placement PCB & Sérigraphie (`pcb-placer`)** : 84 composants et labels orientés sans collision, dégagements pastilles et courtyards IPC-7351 validés, rendu unique [`documents/pcb/placement.svg`](documents/pcb/placement.svg).
- ✅ **Phase 3.1 : Auto-Routage Headless (`freerouting`)** : 100% des connexions de signaux et rails d'alimentation routées (219/219), impédance différentielle USB/CAN respectée, isolation RF 2.4 GHz garantie.

---

## 1. Priorité Immédiate : Finalisation PCB & Plans de Masse (Clôture Phase 3)

### Actions issues de la revue du 2026-04-12 (Gemini 4 Argon (Medium))
<!-- Source : review\review001.md - Verdict : 🔴 Rejeté (corrections critiques nécessaires) -->

#### Correctifs Critiques (Bloquants)
- [x] **[BLOQUANT] Suppression de l'Étape 2b (Fanout préalable) et encerclement de 11 pastilles `GND` :** 1. **Rétablir l'Étape 2b** dans `synthesizer_pipeline.py` afin de poser les vias et micro-pistes de fanout `GND` avant l'export Specctra DSN, et convertir dans `dsn_patcher.py` les vias/micro-pistes `GND` de `(wiring ...)` en obstacles `(keepout ...)` dans `(structure ...)` avant de supprimer le net `GND` (Réseau `GND`, pastilles CMS `J2_1`, `e36`, `J2_4`, `e35`, `R3_2`, `C14_1`, `R20_1`, `C15_2`, `U2_8`, `D5_2`, `D6_1`, `LED1_2` (`synthesizer_pipeline.py` lignes 183-185, `dsn_patcher.py` lignes 62-81)).
- [x] **[BLOQUANT] Écrasement du Cycle 1 (`unrouted = 0`) par les Cycles 2 et 3 (`unrouted = 3`) :** 1. Dès que `report.unrouted_count == 0` et `report.violation_count == 0`, interrompre immédiatement la boucle de rétroaction à l'Étape 4 et mémoriser le meilleur cycle `(min unrouted, min violations)` (Réseaux `+5V` (`U1_2`, `L1_2`, `R16_2`) et `$1N305` (`Q2_1`, `R14_1`, `R13_1`) dans `synthesizer_pipeline.py` (lignes 234-265)).
- [x] **[BLOQUANT] Fallback aveugle à `40 mil` (`1.016 mm`) sur la taille des pads dans `fanout_stitcher.py` et `island_bridger.py` :** 1. Extraire les dimensions exactes de chaque pad dans `fanout_stitcher.py` et `island_bridger.py` en inspectant la structure retournée par `p.getState_PadShape()` (ou en parsant les dimensions exactes des padstacks depuis `work/autoroute.dsn`), et tenir compte de la rotation `p.getState_Rotation()` du pad (`D1_1` (`+12V_PROT`) vs via `e6431` (`GND`), `H3_1` (`+12V`) vs via `e6434` (`GND`) dans `fanout_stitcher.py` (lignes 67-68) et `island_bridger.py` (lignes 81-82)).
- [x] **[BLOQUANT] Artefacts de concurrence FreeRouting (`--threads 8` et `--passes 8`) :** Configurer FreeRouting avec `--passes 15` et `--threads 4` (ou `--threads 1` si déterminisme strict souhaité). Combiné à la conversion des vias `GND` en keepouts (`B1`), le temps de routage reste inférieur à **75 secondes** pour `0 violation` et `0 unrouted` (Routeur FreeRouting CLI (`synthesizer_pipeline.py` lignes 188-193)).

#### Améliorations de Robustesse & CEM (Importants)
- [x] **[IMPORTANT] Faux positif sur l'aire de boucle `PC_BUCK_HOT_LOOP` (`130.91 mm²`) dans `dsn_metrics.py` :** Dans `dsn_metrics.py`, calculer l'aire de boucle 3D physique avec retour par plan interne ($A = L_{\text{trace}} \times h_{\text{prepreg}}$ avec $h = 0.11\text{ mm}$ extrait du stackup de `constraints.json`) lorsque le PCB dispose d'un plan `GND` interne, ou limiter le polygone XY aux segments reliant directement les `target_pads` (Classe `SWITCHING_BUCK` (`$1N16`, `$1N19`) dans `dsn_metrics.py` (lignes 118-137)).
- [x] **[IMPORTANT] Affichage systématique d'un tableau récapitulatif en fin d'exécution du pipeline :** Ajouter une fonction `print_executive_summary(report_data, cycle_history, elapsed_s)` appelée systématiquement à la fin de `run_pipeline()` (Orchestrateur `.agents/skills/pcb-synthesizer/synthesizer_pipeline.py`).

#### Optimisations de Nomenclature & DFM (Mineurs)
- [x] **[MINEUR] Nettoyage de la double définition de `cmd_stitch` dans `synthesizer_pipeline.py` :** Lisibilité du code et maintien d'un paramétrage unique pour `fanout_stitcher.py` (`.agents/skills/pcb-synthesizer/synthesizer_pipeline.py` (lignes 327-351)).

### Actions issues de la revue du 2026-10-23 (Gemini 4 Argon (High))
<!-- Source : review\review001.md - Verdict : 🔴 Rejeté (corrections critiques nécessaires sur 5 bugs algorithmiques bloquants) -->

#### Correctifs Critiques (Bloquants)
- [x] **[BLOQUANT] Corruption syntaxique du bloc `(wiring ...)` et perte de protection des vias de fanout `GND` de l'Étape 2b :** Remplacer dans `dsn_patcher.py` la suppression aveugle de `(net GND ...)` et la regex `(wiring ...)` par une conservation stricte de `(net GND)` sans `(pins ...)` dans `(network ...)` et d'un bloc `(wiring ...)` valide contenant tous les `(wire ...)` et `(via ...)` marqués `(type protect)` (`.agents/skills/freerouting/dsn_patcher.py` (lignes 148-189 et 375-378), `.agents/skills/pcb-synthesizer/synthesizer_pipeline.py` (lignes 184-212), net `GND`, pastilles `C10_1`, `C11_2`, `R17_2` et vias `e5460`, `e5447`).
- [x] **[BLOQUANT] Chaîne JavaScript non interpolée dans `island_bridger.py` désactivant le pontage A* post-routage :** Injecter dynamiquement `target_net` via `json.dumps(target_net)` dans le script JavaScript de `fetch_layout_and_drc` au sein de `island_bridger.py` (`.agents/skills/pcb-stitcher/island_bridger.py` (lignes 38-97), net `GND`, pastilles et vias en erreur `Connection Error`).
- [x] **[BLOQUANT] Échec de `padstack_overrides` sur les fentes de blindage `e55`/`e56` du connecteur USB-C `J2` :** Étendre `apply_padstack_overrides` dans `dsn_patcher.py` et `constraints.json` pour supporter la surcharge ciblée par `pin_id` (`bdbad5cc7fc4f6ae55` et `bdbad5cc7fc4f6ae56`) avec création d'un padstack dédié (`.agents/skills/freerouting/dsn_patcher.py` (lignes 207-233), `documents/pcb/constraints.json` (lignes 104-109), connecteur `J2` (fentes `e55` / `bdbad5cc7fc4f6ae55` et `e56` / `bdbad5cc7fc4f6ae56`), net `VBUS_5V`).
- [x] **[BLOQUANT] Mutualisation de via sans segment de piste dans `fanout_stitcher.py` et absence d'échappement pour `H2_3` / `J2_4` / `e35` :** Exiger dans `fanout_stitcher.py` une connexion filaire explicite (`has_line`) pour considérer une pastille CMS comme échappée, tracer un segment direct lorsqu'un via voisin est mutualisé, et exécuter une passe `only_disconnected=True` à l'Étape 6 (`.agents/skills/pcb-stitcher/fanout_stitcher.py` (lignes 169 et 223-229), `.agents/skills/pcb-synthesizer/synthesizer_pipeline.py` (lignes 340-355), connecteurs `J2` (`J2_4`, `e35`) et `H2` (`H2_3`), net `GND`).
- [x] **[BLOQUANT] Faux positifs `NON ROUTÉ` dans `dsn_metrics.py` provoquant l'exécution systématique de 3 cycles complets :** Filtrer dans `dsn_metrics.py` les nets évalués contre la liste des nets réellement présents dans la section `(network ...)` de `board_raw.dsn` et synchroniser les noms de nets dans `constraints.json` (`.agents/skills/pcb-synthesizer/dsn_metrics.py` (lignes 186-205 et 305-320), `documents/pcb/constraints.json` (lignes 137, 165, 193), nets `+12V_FUSED`, `VBAT_OBD`, `PH_BUCK` (`$1N16`), `BOOT_BUCK` (`$1N19`), `K_RX_IC` (`$6N4`), `K_TX_IC` (`$6N3`), `IO0` (`$7N5`)).

#### Améliorations de Robustesse & CEM (Importants)
- [x] **[IMPORTANT] Métrologie `PC_BUCK_HOT_LOOP` aveugle (`0.00 mm²` / `0.00 nH`) dans `dsn_metrics.py` :** Extraire dans `dsn_metrics.py` les coordonnées réelles des pins des `members` de la boucle depuis le fichier `.dsn` (ou les nets connectés à ces pins dans `(network ...)`) et invalider toute boucle ayant moins de 3 points (`.agents/skills/pcb-synthesizer/dsn_metrics.py` (lignes 221-269), `documents/pcb/manifest.json` (lignes 190-244), composants `U4`, `C14`, `C7`, `D2`, nets `+12V_PROT`, `PH_BUCK` (`$1N16`), `GND`).
- [x] **[IMPORTANT] Rétroaction adaptative ignorant le skew différentiel et dégradant globalement les `courtyard_margin_mm` :** Prendre en compte les violations `diff_pairs` dans `tighten_manifest_constraints` et interrompre immédiatement la boucle `max_cycles` si aucune contrainte du manifeste n'a été modifiée (`.agents/skills/pcb-synthesizer/synthesizer_pipeline.py` (lignes 116-146 et 261-272), paires différentielles `DIFF_USB` (`USB_D+`, `USB_D-`) et `DIFF_CAN` (`CANH`, `CANL`)).
- [x] **[IMPORTANT] Violations résiduelles d'agnosticisme (`AGENTS.md` Règle 1), de typographie LaTeX (Règle 6) et d'API EasyEDA :** Purger les valeurs par défaut `"GND"` en dur dans `synthesizer_pipeline.py`, corriger les accesseurs JS dans `freerouting_pipeline.py` et `easyeda_client.py`, et remplacer le LaTeX dans `SKILL.md` (`.agents/skills/pcb-synthesizer/synthesizer_pipeline.py` (lignes 186, 285), `.agents/skills/pcb-synthesizer/SKILL.md` (lignes 21, 30), `.agents/skills/pcb-placer/easyeda_client.py` (lignes 618-619), `.agents/skills/freerouting/freerouting_pipeline.py` (lignes 63-75)).

#### Optimisations de Nomenclature & DFM (Mineurs)
- [x] **[MINEUR] Réduction du temps d'autoroutage sous la barre des `90 s` par cycle :** Abaisser `max_passes` de `20` à `8` dans `synthesizer_pipeline.py` (et/ou ajouter `+5V` dans `plane_nets` pour l'échapper par vias vers `Inner2` dès l'Étape 2b) réduira le temps d'un cycle complet (Placement + Fanout + FreeRouting + Plans + DRC) de `228 s` à moins de `75 s` tout en allégeant la densité de pistes sur `TopLayer` (`.agents/skills/pcb-synthesizer/synthesizer_pipeline.py` (ligne 209), `documents/pcb/constraints.json` (ligne 134), net `+5V`).



- [x] **Résolution des 13 Clearance Errors résiduelles (Point d'arrêt / Reprise) :**
  - Remplacer les 3 segments rectilignes de pontage d'îlots par les chemins d'évitement calculés par l'algorithme A* du skill [`.agents/skills/pcb-stitcher/`](.agents/skills/pcb-stitcher/SKILL.md) (`island_bridger.py`) pour éliminer les violations de dégagement face aux pistes actives.
- [x] **Vias de couture (stitching) de renfort :**
  - Ajouter un maillage régulier de vias de masse le long du contour de carte après élimination des erreurs DRC.
- [ ] **Sérigraphie PCB des Cavaliers [review004 M1 / review005 I1] :**
  - Ajouter les sérigraphies d'aide à l'utilisateur sur la couche Top Silk :
    - `JP1` : *« OPEN = CAR / SHUNT = BENCH »*
    - `JP2` : *« SHUNT = CAR / OPEN = BENCH HI-Z »*
- [x] **Contrôle DRC physique strict post-routage :**
  - Exécuter le DRC sous EasyEDA Pro avec plans de masse coulés et certifier **DRC = 0 erreur, 0 avertissement**.
- [x] **Inspection 3D finale :**
  - Contrôle visuel 3D de l'assemblage complet (`documents/pcb/3d.png`, `documents/pcb/2d-top.png`, `documents/pcb/2d-bottom.png`), du contour de carte et des dégagements mécaniques des connecteurs `J1` et `J2`.
- [x] **Étapes post-validation et clôture bloquante (Règle 5 d'[`agents.md`](agents.md)) :**
  - Sauvegarde définitive du PCB (`eda.pcb_Document.save()`).
  - Contrôle ERC Schéma = 0 sous EasyEDA Pro.
  - Validation de synchronisation sémantique (`uv run python .agents/skills/stingy-schematics/scripts/sync_semantics.py check`).
  - Capitalisation technique dans [`learnings.md`](learnings.md).
  - Export de l'archive projet [`documents/easyeda/OBD2.epro2`](documents/easyeda/OBD2.epro2).
  - Demande des exports graphiques haute résolution à l'utilisateur.
  - Accord explicite sur le message de commit avant tout commit/push Git.

---

## 2. Dossier de Fabrication (JLCPCB)

- [ ] **Génération des fichiers Gerber & Drill :** Standard 2 couches JLCPCB.
- [ ] **Export BOM SMT :** Nomenclature consolidée au format JLCPCB SMT ([`documents/schema/bom.json`](documents/schema/bom.json)).
- [ ] **Export Pick & Place (CPL) :** Fichier de centroïdes pour l'assemblage CMS automatisé.

---

## 3. Conception du Boîtier & Intégration Mécanique

- [ ] **Maintien mécanique du faisceau OBD-II :** Concevoir le serre-câble / passe-fil pour décharger mécaniquement les contraintes de traction sur le connecteur `J1` (JST-XH 5P coudé).
- [ ] **Accès connectique & interfaces :** Dégager les ouvertures pour le connecteur USB-C `J2`, le bouton Flash `SW1` et le guide de lumière de `LED1`.
- [ ] **Fixation carte :** Intégrer les 4 bossages de fixation M2 alignés avec les perçages du PCB.
- [ ] **Modélisation 3D (STEP / STL) :** Export et validation des tolérances d'assemblage pour impression 3D / usinage.

---

## 4. Transition Firmware & Dépôt Logiciel Dédié

### Actions issues de la revue du 2026-10-12 (Kimi Chat (Moonshot AI) — méthodologie Tabula Rasa & Preuve Matérielle Exclusive)
<!-- Source : review\review007_schema_electrique.md - Verdict : 🟢 **Approuvé avec réserves** — Aucune modification de schéma matériel requise. 3 remarques Importantes de cohérence spécification/firmware et 8 remarques Mineures d'alignement documentaire. -->

#### Améliorations de Robustesse & CEM (Importants)
- [x] **[IMPORTANT] Cible de veille < 1 mA inatteignable avec le schéma actuel :** (a) Réaligner la cible firmware dans `TODO.md` et `documents/software.md` sur « plancher de veille ~8 à 15 mA » avec calcul d'autonomie associé ; (b) rectifier dans `HARDWARE.md` la mention « < 25 µA » en précisant qu'elle ne concerne que le diviseur UVLO ; (c) si une veille < 1 mA devenait un impératif absolu futur, prévoir un interrupteur High-Side commandé par GPIO sur le rail 5V de `U2` (`U2` (TJA1051T/3), `U3` (L9637D), `U5` (LDL1117), rail `+5V`, rail `3.3V`).
- [x] **[IMPORTANT] Signature « USB seule » de VBAT_SENSE erronée et rétro-alimentation K-Line :** (a) Corriger le seuil de détection firmware USB-seule à `VBAT_SENSE < 0.3 V` (tension batterie équivalente < 2.8 V) ; (b) expliciter dans `HARDWARE.md` la règle de câblage sur banc : toujours relier le 12V et la masse avant les lignes de bus ; (c) documenter l'interdiction du câblage partiel sans masse/12V (`R12`, `R13`, `D6`, net `VBAT_SENSE`, `U3` pin 7 (VS), `J1`).
- [x] **[IMPORTANT] Incohérence de référence pour D5 : SMF24A vs SMF24CA :** Aligner `README.md` (§1.3 et §4) sur la référence réelle `SMF24A` (unidirectionnelle, 200 W crête) en reprenant la justification physique de `HARDWARE.md` (`D5` (TVS K-Line), net `K_LINE`).

#### Optimisations de Nomenclature & DFM (Mineurs)
- [x] **[MINEUR] Capacité PSRAM de l'ESP32-S3 dans README :** Exactitude technique des spécifications pour le développement firmware (`U1` (`ESP32-S3-WROOM-1-N16R2`)).
- [x] **[MINEUR] Alignement diélectrique C0G vs X7R pour C13 :** Cohérence stricte entre la nomenclature BOM et la documentation matérielle (`C13` (220 pF, compensation Buck pin COMP)).
- [x] **[MINEUR] Décompte des composants dans les en-têtes documentaires :** Élimination des écarts résiduels de décompte dans les fichiers markdown (Documentation générale (`README.md`, `BOM.md`)).
- [x] **[MINEUR] Justification constructeur pour le condensateur bootstrap C5 :** Rigueur métrologique et traçabilité constructeur irréprochable (`C5` (100 nF, broches BOOT-PH de `U4`)).
- [x] **[MINEUR] Précision physique sur l'écrêtage ISO 7637-2 pulse 1 (−100 V) :** Fidélité physique de la documentation d'homologation automobile (`D1` (`SMBJ16A`), `Q1` (`CJ2309A`)).
- [x] **[MINEUR] Rectification du libellé de D4 dans le synoptique Mermaid :** Exactitude du schéma synoptique (`D4` (`B5819W SL`, SOD-123)).
- [x] **[MINEUR] Normalisation de la tenue ESD de U8 :** Conformité aux termes exacts de la datasheet onsemi (`U8` (`NUP2105LT1G`)).
- [x] **[MINEUR] Mesure de validation sur banc pour la chaîne VBUS → D4 → U5 :** Confirmation expérimentale de l'absence de brownout en mode flash/banc USB (`D4`, `U5`, points de test `TP1` (VBUS) et `TP6` (3.3V)).



Le développement du firmware est déporté dans un dépôt Git dédié (`obd2-esp32-firmware`).
L'ensemble des spécifications et le guide d'amorçage sont consignés dans [`documents/software.md`](documents/software.md).

- [x] **Rédaction du cahier des charges & document d'amorçage ([`documents/software.md`](documents/software.md)) :**
  - Mappage exhaustif des GPIOs et adaptation 3.3V.
  - Spécifications métrologiques ADC1 et formule de conversion $V_{BAT}$.
  - Spécifications protocolaires TWAI/CAN (ISO 15765-4 / ISO-TP) et K-Line (ISO 9141-2 / Fast-Init / GM-Daewoo Kalos).
  - Spécifications du simulateur d'ECU et console CLI de test sur banc.
  - Architecture FreeRTOS recommandée et arborescence cible du futur projet.
- [ ] **Initialisation du dépôt dédié `obd2-esp32-firmware` :**
  - Créer le dépôt Git distant.
  - Initialiser le projet avec [`documents/software.md`](documents/software.md) comme socle contractuel.
  - Configurer `sdkconfig.defaults` (TWAI, USB CDC, BLE 5.0, Flash 16 Mo, PSRAM 2 Mo).

---

## 5. Outillage & Fiabilisation du Skill `pcb-placer`

<!-- Source : review/review_pcb-placer.md - Audit technique du skill d'auto-placement PCB v2.1.0 -->

### Correctifs & Fiabilisation Algorithmique
- [x] **[BLOQUANT] Correction du bug d'import dans `render_svg.py` :**
  - Ajouter `Set` dans l'import `from typing import ...` de [`render_svg.py`](.agents/skills/pcb-placer/render_svg.py) pour sécuriser l'évaluation de types au runtime.
- [x] **[IMPORTANT] Remise en conformité Règle 0 (« Zéro composant en dur ») :**
  - Remplacer les désignateurs en dur (`U1`, `J1`, `J2`, `D4`, `D5`) par des classes sémantiques issues du manifeste [`manifest.json`](documents/pcb/manifest.json) (`emc_class: "mechanical_connector"`, `"rf_transceiver"`).
  - Dériver la boucle chaude Buck dynamiquement depuis le manifeste au lieu de la liste figée `["U4", "C14", "C7", "D2", "L1"]` dans [`render_svg.py`](.agents/skills/pcb-placer/render_svg.py).
  - Injecter `power_ground_nets` via la configuration globale au lieu des ensembles figés dans [`score.py`](.agents/skills/pcb-placer/score.py) et [`simulated_annealing.py`](.agents/skills/pcb-placer/simulated_annealing.py).
  - Supprimer l'inférence par motif de désignateur dans [`placement_resolver.py`](.agents/skills/pcb-placer/placement_resolver.py) au profit d'une lecture stricte des dimensions IPC.
- [x] **[IMPORTANT] Sécurisation DRC & Unification Géométrique des Keepouts :**
  - Rendre le DRC EasyEDA bloquant dans [`apply_placement.py`](.agents/skills/pcb-placer/apply_placement.py) (rollback / code de sortie d'erreur si violations).
  - Aligner [`audit_placement.py`](.agents/skills/pcb-placer/audit_placement.py) sur [`score.py`](.agents/skills/pcb-placer/score.py) en testant le courtyard complet face aux keepouts (et non le seul centre du composant).
### Évolution vers le Moteur CEM v2 & Modélisation Physique
- [x] **[FONDAMENTAL] Banc de Tests Unitaires Algorithmiques (Pytest) :**
  - Mettre en place la suite de tests automatisés dans `.agents/skills/pcb-placer/tests/` (exécutable via `uv run pytest`).
  - Tester les primitives géométriques `RectBox` : intersections, aires de chevauchement, rotations (0°, 90°, 180°, 270°), calculs de courtyards IPC.
  - Tester le légalisateur déterministe `legalize()` : résolution de chevauchements artificiels, non-déplacement des ancres, respect des marges.
  - Tester les calculs géométriques d'aires de boucles (formule du lacet de Gauss / Shoelace).
- [x] **[FONDAMENTAL] DSL Sémantique CEM v2 & Contraintes Physiques :**
  - Étendre le schéma des contraintes de boucle (`loop`) dans [`manifest.json`](documents/pcb/manifest.json) et [`constraints.json`](documents/pcb/constraints.json) : déclaration obligatoire du réseau de retour (`return_net: "GND"`), seuil d'aire maximale ($S_{loop}$ en mm²) et inductance cible ($L_{loop}$ en nH).
  - Étendre les règles de séparation (`separation_rules`) : ajout du mécanisme de couplage (`coupling: "H_field" | "E_field"`), fréquence caractéristique (`frequency_mhz`) et atténuation angulaire relative.
  - Déclarer les contraintes de proximité au plan de référence (`return_path_proximity`) pour les signaux à commutation rapide (nœud PH Buck, horloges, bus CAN).
- [x] **[FONDAMENTAL] Évaluation Physique & Modélisation Quantitative ([`score.py`](.agents/skills/pcb-placer/score.py)) :**
  - Remplacer l'heuristique HPWL par l'aire polygonale réelle (Shoelace) et l'inductance de boucle fermée aller-retour (formule de Rosa/Grover).
  - Remplacer le hack de séparation 1D en X par une évaluation 2D isotrope inter-clusters avec fonctions de décroissance physiques ($1/r^3$ pour champ H, $1/r^2$ pour champ E).
  - Remplacer les seuils de distance euclidienne de découplage par une pénalité d'inductance parasite équivalente ($L_{par} \propto d$).
- [x] **[FONDAMENTAL] Optimisation Énergétique dans le Recuit Simulé ([`simulated_annealing.py`](.agents/skills/pcb-placer/simulated_annealing.py)) :**
  - Intégrer les nouvelles énergies physiques (aire de boucle fermée, inductance, décroissance de champ 2D) dans la fonction de coût du recuit.
  - Maintenir un calcul incrémental $\Delta E$ rapide pour préserver les performances de convergence du solveur.
- [x] **[FONDAMENTAL] Validation & Benchmark Physique sur le PCB OBD-II :**
  - Comparer quantitativement le layout avant / après modèle CEM v2 (réduction de l'aire de boucle chaude Buck, isolation Buck-ADC, etc.).
  - Certifier la non-régression DRC (DRC = 0) et l'intégrité globale du placement.

### Synthèse en Boucle Fermée (Co-Design Placement-Routage-CEM)
- [x] **[FONDAMENTAL] Nouveau Skill Orchestrateur `pcb-synthesizer` :**
  - [x] Créer le skill [`.agents/skills/pcb-synthesizer/`](.agents/skills/pcb-synthesizer/) et son [`SKILL.md`](.agents/skills/pcb-synthesizer/SKILL.md) orchestrant la chaîne fermée en une commande autonome.
  - [x] Implémenter l'analyseur métrologique post-routage Specctra SES/DSN ([`dsn_metrics.py`](.agents/skills/pcb-synthesizer/dsn_metrics.py)) : extraction des tracés réels, aire polygonale Shoelace, inductance de boucle fermée et skew des paires différentielles.
  - [x] Implémenter le banc de tests unitaires ([`test_dsn_metrics.py`](.agents/skills/pcb-synthesizer/tests/test_dsn_metrics.py)).
  - [x] Implémenter l'orchestrateur maître transactionnel ([`synthesizer_pipeline.py`](.agents/skills/pcb-synthesizer/synthesizer_pipeline.py)) avec rétroaction adaptative (max 3 cycles) : `pcb-placer` -> `apply_placement` -> `freerouting` -> `dsn_metrics` -> `pcb-stitcher`.
  - [x] Valider l'exécution de bout en bout de la chaîne avec rapport de synthèse complet et certification DRC = 0.
