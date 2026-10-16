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

- [ ] **Résolution des 13 Clearance Errors résiduelles (Point d'arrêt / Reprise) :**
  - Remplacer les 3 segments rectilignes de pontage d'îlots par les chemins d'évitement calculés par l'algorithme A* du skill [`.agents/skills/pcb-stitcher/`](.agents/skills/pcb-stitcher/SKILL.md) (`island_bridger.py`) pour éliminer les violations de dégagement face aux pistes actives.
- [ ] **Vias de couture (stitching) de renfort :**
  - Ajouter un maillage régulier de vias de masse le long du contour de carte après élimination des erreurs DRC.
- [ ] **Sérigraphie PCB des Cavaliers [review004 M1 / review005 I1] :**
  - Ajouter les sérigraphies d'aide à l'utilisateur sur la couche Top Silk :
    - `JP1` : *« OPEN = CAR / SHUNT = BENCH »*
    - `JP2` : *« SHUNT = CAR / OPEN = BENCH HI-Z »*
- [ ] **Contrôle DRC physique strict post-routage :**
  - Exécuter le DRC sous EasyEDA Pro avec plans de masse coulés et certifier **DRC = 0 erreur, 0 avertissement**.
- [ ] **Inspection 3D finale :**
  - Contrôle visuel 3D de l'assemblage complet (`documents/pcb/3d.png`, `documents/pcb/2d-top.png`, `documents/pcb/2d-bottom.png`), du contour de carte et des dégagements mécaniques des connecteurs `J1` et `J2`.
- [ ] **Étapes post-validation et clôture bloquante (Règle 5 d'[`agents.md`](agents.md)) :**
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
- [ ] **[FONDAMENTAL] Nouveau Skill Orchestrateur `pcb-synthesizer` :**
  - Créer le skill `.agents/skills/pcb-synthesizer/` orchestrant la chaîne fermée en une commande autonome.
  - Chaîner de manière transactionnelle : `pcb-placer` -> `apply_placement` -> `freerouting` -> `audit post-routage DSN` -> `pcb-stitcher`.
  - Implémenter l'analyseur métrologique DSN/SES post-routage : extraction des pistes réelles de boucles et des vias de retour.
  - Implémenter la rétroaction itérative (max 3 cycles) : resserrement automatique des contraintes locales si une boucle dépasse sa cible.
  - Valider l'exécution de bout en bout avec rapport de synthèse complet et certification DRC = 0.
