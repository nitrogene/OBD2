# Capitalisation Technique & Guide des Pièges EasyEDA Pro

Ce document constitue la **base de connaissances techniques** et le **journal de retour d'expérience** du projet Scanner OBD-II ESP32. Il répertorie les subtilités, contournements et comportements non documentés d'EasyEDA Pro, ainsi que le protocole de capitalisation pour les futures découvertes.

---

## 1. Protocole de Gestion des Futures Découvertes

Pour maintenir un projet propre, modulaire et directement exploitable par les agents IA, toute nouvelle anomalie, astuce ou découverte technique doit suivre ce cycle de vie :

```
[Nouvelle Découverte / Erratum rencontré]
                    │
                    ▼
  1. Consignation dans LEARNINGS.md (Section 4 : Journal)
     • Date, contexte technique et description du symptôme
     • Cause racine identifiée
     • Solution éprouvée ou contournement
                    │
                    ▼
  2. Qualification & Ventilation :
     ├── S'il s'agit d'une Règle de Conception / Sécurité :
     │   └── Rapatrier la consigne impérative dans AGENTS.md
     ├── S'il s'agit d'un Algorithme / Calcul réutilisable :
     │   └── L'encapsuler dans un Skill dédié (.agents/skills/<nom>/)
     └── S'il s'agit d'un Piège d'API EasyEDA Pro :
         └── Mettre à jour la fiche réflexe correspondante en Section 2
                    │
                    ▼
  3. Allègement périodique :
     Dès qu'une connaissance est transformée en Skill ou en règle, résumer le journal
     pour éviter l'accumulation de code verbeux.
```

---

## 2. Fiches Réflexes : Pièges d'API EasyEDA Pro & Règles d'Or

### A. Schématique (`eda.sch_*`)

| Piège / Comportement | Cause & Risque | Règle & Solution Éprouvée |
| :--- | :--- | :--- |
| **Drapeau de réseau (`NetFlag`) sans fil physique** | Si un NetFlag est posé directement sur une pastille sans segment de fil, EasyEDA considère la broche comme **flottante** et génère un net orphelin au PCB (`$1N...`). | **Toujours insérer un fil physique (`sch_PrimitiveWire.create([x1, y1, x2, y2])`)** entre la broche et le drapeau. |
| **Avertissement "Multiple net names" sur fil** | Spécifier un nom de net sur un fil déjà relié à un NetFlag ou NetPort déclenche `[Warn] : Wire has multiple net names`. | **Omettre le nom de net** lors de `sch_PrimitiveWire.create(line)` si le fil touche un port/drapeau : la propagation est automatique. |
| **Stubs vides de `createNetLabel`** | `eda.sch_PrimitiveAttribute.createNetLabel()` est un stub vide dans le runtime actuel. | **Utiliser des NetPorts :** `eda.sch_PrimitiveComponent.createNetPort(...)`, qui connecte instantanément tout fil superposé. |
| **Instanciation de composants en script** | Passer un objet allégé `{ libraryUuid, uuid }` bloque avec timeout de 30s. | **Résoudre d'abord le Device complet** via `eda.lib_Device.search(...)` avant d'appeler `sch_PrimitiveComponent.create(devs[0], ...)`. |
| **Orientation de l'axe Y schématique** | Sur une feuille de schéma (`documentType: 1`), **l'axe Y est orienté vers le HAUT** (inversé par rapport au canvas PCB). | Vérifier les coordonnées : `y = 0` est en bas de page A4, `y = 825` est en haut. |
| **Énumération multi-feuilles (`sch_PrimitiveComponent.getAll`)** | `eda.sch_PrimitiveComponent.getAll(undefined, true)` peut omettre des composants si les feuilles associées n'ont pas encore été ouvertes dans l'éditeur (non chargées en mémoire). | **Itérer sur les feuilles via `eda.dmt_Schematic.getAllSchematicPagesInfo()`**, activer chaque onglet avec `eda.dmt_EditorControl.openDocument(page.uuid)`, puis exécuter `getAll()` feuille par feuille. |

### B. Layout PCB & Primitives (`eda.pcb_*`)

| Piège / Comportement | Cause & Risque | Règle & Solution Éprouvée |
| :--- | :--- | :--- |
| **Signature de `pcb_PrimitiveVia.create` (CRITIQUE)** | La signature est `(net, x, y, holeDiameter, diameter)`. Inverser perçage et diamètre extérieur crée un via aberrant et bloque le DRC. | **Le diamètre de perçage précède toujours le diamètre extérieur.** Standard JLCPCB : `hole = 12 mil` (~0.3 mm), `diameter = 24 mil` (~0.6 mm). |
| **Signature de `pcb_PrimitiveLine.create` (CRITIQUE)** | La signature est `(net, layer, startX, startY, endX, endY, width)`. Placer la largeur avant les coordonnées décale tout. | **Les coordonnées précèdent toujours la largeur de piste.** |
| **Unités runtime** | Les coordonnées de l'API PCB sont exprimées en **mils** (1 mil = 0.0254 mm, 1 mm = 39.3701 mil). | Toujours convertir explicitement avec `mm_to_mil()` et `mil_to_mm()`. |
| **Identifiants de couches (Layers)** | Les couches sont référencées par des entiers : `1` = Top Layer, `2` = Bottom Layer, `11` = Board Outline, `12` = Multi-layer. | Utiliser les constantes numériques entières ou l'énumération `EPCB_LayerId`. |
| **Déplacement / Relocalisation d'un via** | Modifier in-place les coordonnées d'un via existant ne recalcule pas le masque d'isolement du cuivre lors du remplissage. | **Supprimer l'ancien via** (`delete([oldId])`), **créer le nouveau via**, puis exécuter `rebuildCopperRegion()`. |
| **Chanfreinage paires différentielles** | Les angles à 90° créent des ruptures d'impédance et du rayonnement EMI (critique pour USB 480 Mbps et CAN 500 kbps). | **Systématiser les angles à 45°** (Δx = Δy = 25 mil pour une piste de 10 mil). |

### C. Plans de Cuivre, DRC & Cache WebGL

| Piège / Comportement | Cause & Risque | Règle & Solution Éprouvée |
| :--- | :--- | :--- |
| **Persistance des anciens textes de pistes (Cache WebGL)** | Après modification de net via l'API, le texte imprimé sur la piste WebGL affiche toujours l'ancien nom tant que l'onglet reste ouvert. | **Fermer et réouvrir le document PCB** : `save()`, `closeDocument(tabId)`, puis `openDocument(pcbUuid)`. |
| **Micro-intrusions de cuivre entre pads CMS** | Le remplissage de plan de masse peut créer des langues de cuivre parasites entre les pastilles rapprochées (0603/0805). | Poser une micro-zone d'exclusion locale `NO_POURS` (`ruleType: [7]`) entre les pastilles via `pcb_PrimitiveRegion.create()`. |
| **Keepout multicouche antenne RF** | L'antenne ESP32-S3 exige un vide total de cuivre sous et autour du méandre 2.4 GHz sur toutes les couches. | Créer une région sur la couche `12` (`MULTI`) avec `ruleType: [5, 6, 7]` (`NO_WIRES`, `NO_FILLS`, `NO_POURS`). |
| **Vérification de continuité du plan de masse** | Après `rebuildCopperRegion()`, s'assurer que le plan n'a pas été saucissonné en îlots isolés. | Vérifier via `pcb_PrimitivePoured.getAll()` que `pouredCount == 2` (1 région Top, 1 région Bottom). |

---

## 3. Répertoire des Compétences Outillées (Skills Dérivés)

Les connaissances théoriques et algorithmiques issues de ce document ont été structurées en compétences autonomes sous `.agents/skills/` :

1. **⚡ [Skill `buck-compensation`](.agents/skills/buck-compensation/SKILL.md) :**
   - *Origine :* Modélisation petit-signal de l'étage Buck TI TPS54331 (gain ampli d'erreur, compensation Type II Rz, Cz, Cp, dérating DC-bias des céramiques X5R).
   - *Capacité :* Calcul instantané de la marge de phase, fréquence de coupure Fco, marge de gain et sélection des Basic Parts JLCPCB.
2. **🔌 [Skill `easyeda-api`](.agents/skills/easyeda-api/SKILL.md) :**
   - *Origine :* Spécifications officielles et architecture du pont Node.js (port 49620).
   - *Capacité :* Communication WebSocket/HTTP bidirectionnelle avec l'API interne EasyEDA Pro.
3. **📐 [Skill `pcb-placer`](.agents/skills/pcb-placer/SKILL.md) :**
   - *Origine :* Règles d'agencement physique (ancres mécaniques J1/J2/U1, découplage < 2 mm, boucle Buck compacte, exclusion RF).
   - *Capacité :* Solveur d'auto-placement en une passe pour les 60 composants, audit géométrique pad-à-pad et injection directe avec contrôle DRC.
4. **🔍 [Skill `review`](.agents/skills/review/SKILL.md) :**
   - *Origine :* Méthodologie d'audit critique de schéma (Axe 1 à 6), formalisation des guidelines et règles de dépouillement d'AGENTS.md.
   - *Capacité :* Outil CLI agnostique de génération de templates, validation formelle de conformité des rapports face aux guidelines, et dépouillement/triage automatique vers `TODO.md` avec détection de collisions.
5. **💰 [Skill `stingy-schematics`](.agents/skills/stingy-schematics/SKILL.md) :**
   - *Origine :* Problématique des frais de configuration outillage SMT chez JLCPCB (3,00 $ par composant Extended) et nécessité de formaliser l'intention de schéma.
   - *Capacité :* Moteur d'audit et de réduction des coûts de nomenclature, exploitant `circuit_semantics.json` pour basculer des pièces Extended en Basic Parts sans dégrader les signaux ni violer les marges de sécurité, avec outil de synchronisation continue (`sync_semantics.py`).

---

## 4. Journal Historique des Retours d'Expérience

* **[2026-09-03 / 2026-09-06] Primitives & Routage de base :**
  - Identification de l'unité universelle `mil` et du lien hiérarchique `pad.primitiveId.startsWith(comp.primitiveId)`.
  - Mise au point du diagnostic DRC verbeux (`eda.pcb_Drc.check(true, false, true)`).
* **[2026-09-07 / 2026-09-11] Topologies critiques & CEM :**
  - Découplage HF transceivers (via -> pastille condensateur -> broche IC).
  - Échappement des broches USB-C à pas fin (0.8 mm) et routage différentiel 45°.
  - Matrice thermique de dissipation sous le pad central 41 de l'ESP32-S3.
* **[2026-09-19] Modélisation de régulation & Stabilité :**
  - Validation du triplet de compensation TPS54331 (R11 = 10 kΩ, C9 = 3.3 nF, C13 = 220 pF) garantissant une marge de phase de 61.7° à 68.8°.
* **[2026-09-20] Dépouillement des revues & Esprit critique :**
  - Mise en évidence des confusions de variantes matérielles chez les reviewers (différences de brochage ADC entre ESP32 classique et ESP32-S3).
  - Nécessité d'un pull-up fort de 1 kΩ vers le 12V sur la ligne K-Line pour la Daewoo Kalos (ISO 9141-2).
  - Création du moteur d'auto-placement par contraintes `pcb-placer`.
* **[2026-09-26] Découplage Sémantique Schéma & Skill Review :**
  - Réfutation de la fausse recommandation VCC 5V sur L9637D (L9637D possède une pull-up interne active sur RX vers VCC, qui détruirait l'ESP32 non 5V-tolerant sous 5V).
  - Détection de l'absence de diviseur sur la grille du 2N7002 (Vgs max ±20V dépassé sous Load Dump 29.2V) et du court-circuit de masse/Silent mode sur TJA1051T.
  - Création du skill autonome `.agents/skills/review/` pour standardiser l'audit, la validation et le dépouillement vers `TODO.md`.
  - **Création du référentiel sémantique `circuit_semantics.json` :** Les fichiers de CAO propriétaires (EasyEDA, KiCad) stockent la géométrie et les nets, mais pas l'intention d'ingénierie (rôle, tolérance critique, politique de substituabilité). La création de `circuit_semantics.json` comble ce vide et sert de socle pour l'optimisation des coûts (`stingy-schematics`), l'audit automatique et l'auto-placement.
* **[2026-09-27] Audit Critique, Pièges Schématiques & Conformité Normative :**
  - **Topologie LDO & Perle de Ferrite (LDL1117) :** Le condensateur de régulation et de stabilité de boucle $C_{OUT} \ge 4.7\,\mu\text{F}$ (`C6` = 10 µF) doit impérativement être branché en dérivation directement sur la sortie $V_{OUT}$ (`3.3V_PRE`) en amont de la perle de ferrite `FB1`. Insérer une perle inductive entre le LDO et son condensateur primaire déphase la contre-réaction interne et induit un risque critique d'oscillation HF.
  - **Piège des primitives graphiques EasyEDA (`LINE`) :** Un segment de fil traversant accidentellement le corps d'un composant passif (ex. `C7`) relie ses deux pastilles dans la netlist sans avertissement visuel évident, provoquant un court-circuit franc entre le rail d'alimentation et la masse. Nécessité d'auditer la continuité et l'intégrité des primitives géométriques.
  - **Alimentation explicite du Buck TPS54331 :** Vérification formelle du raccordement du NetPort `+12V_PROT` sur l'étage de découplage d'entrée (`C14`, `C7`) et sur la broche 2 (`VIN`).
  - **Formalisation du Référentiel Normatif :** Intégration d'une matrice d'évaluation de la conformité par conception (*Design Compliance Assessment*) couvrant les 8 normes cibles automobiles (SAE J1962, ISO 11898-2, ISO 9141-2, ISO 14230, ISO 15765-4, ISO 7637-2, ISO 16750-2, ISO 10605).
* **[2026-09-28] Méthodologie TODO & Attribution des désignateurs de composants :**
  - **Désignateurs anticipés proscrits dans le TODO :** Figer prématurément un identifiant (ex. `R18`, `R21`, `C18`, `TP12`) dans une tâche de la feuille de route avant son implémentation effective est une source majeure d'incohérences. Dès que l'ordre de traitement des tâches change ou qu'une priorité est inversée (ex. ajout des résistances UVLO `R19`/`R20` avant la pull-up `IO0`), des trous ou des collisions de désignateurs apparaissent.
  - **Règle méthodologique :** Une tâche du `TODO.md` ou une observation de revue doit caractériser le composant uniquement de manière générique et fonctionnelle (rôle, valeur, tolérance, boîtier, contraintes, référence catalogue Basic Part). L'attribution du désignateur officiel ne se fait qu'au moment précis de l'intégration effective dans le schéma, en prenant le prochain numéro séquentiel libre dans la nomenclature (BOM).
* **[2026-09-28] Transceiver K-Line L9637D & Protection TVS Buck :**
  - **Piège de revue sur l'entrée L-Line `LI` (L9637D broche 8) :** `LI` n'est pas une entrée logique 3.3V mais une entrée analogique haute tension dont le seuil de basculement est proportionnel à la tension batterie ($V_{th} = 0.5 \times V_S \approx 6\,\text{V}$). La raccorder à 3.3V l'aurait forcée en permanence à l'état actif/dominant ($3.3\,\text{V} < 0.45 \times V_S$) avec injection de courant inverse via son pull-up interne vers $V_S$. La ponter directement sur la broche 7 adjacente (`VS` / `+12V_PROT`) verrouille le comparateur au repos inactif, garantit une consommation nulle ($0\,\mu\text{A}$) et immunise l'étage contre les parasites CEM sans traverser la carte.
  - **Optimisation de la marge de protection Buck (TVS `D1`) :** Remplacement de `SMBJ18A` ($V_{CL} = 29.2\,\text{V}$) par `SMBJ16A` ($V_{CL} = 26.0\,\text{V}$) : dégage une marge de sécurité robuste de **4.0 V** (au lieu de 0.8 V) sous le plafond destructeur de 30.0 V du TPS54331, tout en restant transparente sous alternateur VL ($V_{RWM} = 16.0\,\text{V} > 14.8\,\text{V}$).
* **[2026-09-29] Mesure ADC Batterie & Piège du Courant de Fuite des Diodes de Clamp :**
  - **Sensibilité thermique des ponts diviseurs ADC à haute impédance :** Sur un pont diviseur $R_{12} = 100\,\text{k}\Omega$ / $R_{13} = 12\,\text{k}\Omega$ de ratio $k = R_{13}/(R_{12}+R_{13}) \approx 1/9.33$, tout courant de fuite inverse $I_R$ injecté par une diode de clamp connectée au rail 3.3V produit une tension d'erreur $\Delta V_{SENSE} = I_R \times (R_{12} \parallel R_{13})$. Rapportée à la tension batterie estimée par le firmware, l'erreur devient strictement indépendante de $R_{13}$ :
    $$\Delta V_{BAT} = \frac{\Delta V_{SENSE}}{k} = I_R \times R_{12} = I_R \times 100\,\text{k}\Omega$$
  - **Piège des diodes Schottky (`BAT54WS`) :** À température ambiante ($25^\circ\text{C}$), la fuite d'une Schottky reste faible (~0.2 µA, soit 20 mV d'erreur). Mais en habitacle automobile exposé au soleil ($70^\circ\text{C}$ à $85^\circ\text{C}$), $I_R$ grimpe exponentiellement entre 5 µA et 10 µA, provoquant une surestimation dramatique de **+0.5 V à +1.0 V** sur la tension batterie mesurée, rendant impossible le diagnostic de charge/décharge (la différence entre une batterie pleine à 12.6V et déchargée à 11.9V n'étant que de 0.7V).
  - **Détection des confusions dans les revues techniques (`BAV99` vs `BAV199`) :** La revue M4 préconisait indifféremment `BAV199` ou `BAV99` pour une fuite « < 5 nA à chaud ». L'audit rigoureux des datasheets montre que la `BAV99` est une diode rapide standard dont la fuite atteint $30\,\mu\text{A}$ à $150^\circ\text{C}$ (~1 µA à $85^\circ\text{C}$, soit 100 mV d'erreur résiduelle). Seule la **`BAV199`** est une véritable diode silicium planar ultra-faible fuite (typique **3 pA** à $25^\circ\text{C}$, $< 100\,\text{pA}$ à $85^\circ\text{C}$, garantie $< 5\,\text{nA}$ à $75\,\text{V}$), réduisant l'erreur à $\Delta V_{BAT} < 0.01\,\text{mV}$ (< 0.001 LSB de l'ADC).
  - **Topologie Rail-to-Rail SOT-23 :** En adoptant le boîtier double diode SOT-23, le nœud `VBAT_SENSE` est raccordé sur le point milieu (broche 3), la broche 1 à la masse `GND` écrête les sonneries inductives négatives sous $-0.65\,\text{V}$, et la broche 2 au rail `3.3V` écrête les surtensions transitoires au-delà de $3.95\,\text{V}$.
  - **Dimensionnement thermique de la terminaison CAN face aux défauts véhicule :** En fonctionnement normal sur véhicule (prise OBD-II), le cavalier `JP1` reste ouvert car le bus possède déjà ses deux terminaisons de 120 Ω aux extrémités du faisceau. En revanche, sur banc d'essai ou en cas d'insertion accidentelle du shunt sur le véhicule, un court-circuit franc d'une ligne différentielle vers le rail batterie (+12V à +14.4V) génère une puissance crête $P = V^2 / R \approx 1.2\,\text{W}$ à $1.7\,\text{W}$. Alors qu'un boîtier 0805 est limité à 125 mW, le passage en boîtier 1206 (*Basic Part* `C17909`, 250 mW) double la puissance nominale continue admissible, offre une surface de contact thermique bien plus généreuse (3.2 × 1.6 mm) pour évacuer les calories vers les plans de cuivre PCB et renforce l'inertie thermique face aux surcharges transitoires.
  - **Méthodologie Schéma / Documentation :** La source de vérité absolue d'un composant reste sa concrétisation dans le schéma CAO (`easyeda/OBD2.epro2`). Les modifications de nomenclature (`BOM.md`), de sémantique (`circuit_semantics.json`) et d'architecture (`HARDWARE.md`) ne doivent être appliquées qu'après validation effective du schéma physique par l'ingénieur.
* **[2026-09-30] Règle d'or du séquencement documentaire (Post-résolution exclusive) :**
  - **Interdiction formelle d'anticipation :** Toute modification des fichiers de documentation (`BOM.md`, `circuit_semantics.json`, `HARDWARE.md`, `floorplan.json`) et tout cochage de tâche dans `TODO.md` (`- [x]`) sont formellement proscrits tant que l'action n'a pas été réellement implémentée et validée par l'utilisateur.
  - **Flux de travail impératif :**
    1. L'agent analyse le besoin, explicite la solution technique et fournit les consignes pas à pas (composants, désignateurs, valeurs, boîtiers, nets, coordonnées de placement).
    2. L'utilisateur réalise l'opération dans EasyEDA Pro et confirme sa validation.
    3. L'agent procède *alors seulement* à la mise à jour documentaire, synchronise la BOM / sémantique, et coche la tâche dans `TODO.md`.