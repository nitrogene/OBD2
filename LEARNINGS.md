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

### B. Layout PCB & Primitives (`eda.pcb_*`)

| Piège / Comportement | Cause & Risque | Règle & Solution Éprouvée |
| :--- | :--- | :--- |
| **Signature de `pcb_PrimitiveVia.create` (CRITIQUE)** | La signature est `(net, x, y, holeDiameter, diameter)`. Inverser perçage et diamètre extérieur crée un via aberrant et bloque le DRC. | **Le diamètre de perçage précède toujours le diamètre extérieur.** Standard JLCPCB : `hole = 12 mil` (~0.3 mm), `diameter = 24 mil` (~0.6 mm). |
| **Signature de `pcb_PrimitiveLine.create` (CRITIQUE)** | La signature est `(net, layer, startX, startY, endX, endY, width)`. Placer la largeur avant les coordonnées décale tout. | **Les coordonnées précèdent toujours la largeur de piste.** |
| **Unités runtime** | Les coordonnées de l'API PCB sont exprimées en **mils** (1 mil = 0.0254 mm, 1 mm = 39.3701 mil). | Toujours convertir explicitement avec `mm_to_mil()` et `mil_to_mm()`. |
| **Identifiants de couches (Layers)** | Les couches sont référencées par des entiers : `1` = Top Layer, `2` = Bottom Layer, `11` = Board Outline, `12` = Multi-layer. | Utiliser les constantes numériques entières ou l'énumération `EPCB_LayerId`. |
| **Déplacement / Relocalisation d'un via** | Modifier in-place les coordonnées d'un via existant ne recalcule pas le masque d'isolement du cuivre lors du remplissage. | **Supprimer l'ancien via** (`delete([oldId])`), **créer le nouveau via**, puis exécuter `rebuildCopperRegion()`. |
| **Chanfreinage paires différentielles** | Les angles à 90° créent des ruptures d'impédance et du rayonnement EMI (critique pour USB 480 Mbps et CAN 500 kbps). | **Systématiser les angles à 45°** ($\Delta x = \Delta y = 25\text{ mil}$ pour une piste de 10 mil). |

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
   - *Origine :* Modélisation petit-signal de l'étage Buck TI TPS54331 (gain ampli d'erreur, compensation Type II $R_z, C_z, C_p$, dérating DC-bias des céramiques X5R).
   - *Capacité :* Calcul instantané de la marge de phase, fréquence de coupure $F_{co}$, marge de gain et sélection des Basic Parts JLCPCB.
2. **🔌 [Skill `easyeda-api`](.agents/skills/easyeda-api/SKILL.md) :**
   - *Origine :* Spécifications officielles et architecture du pont Node.js (port 49620).
   - *Capacité :* Communication WebSocket/HTTP bidirectionnelle avec l'API interne EasyEDA Pro.
3. **📐 [Skill `pcb-placer`](.agents/skills/pcb-placer/SKILL.md) :**
   - *Origine :* Règles d'agencement physique (ancres mécaniques J1/J2/U1, découplage < 2 mm, boucle Buck compacte, exclusion RF).
   - *Capacité :* Solveur d'auto-placement en une passe pour les 60 composants, audit géométrique pad-à-pad et injection directe avec contrôle DRC.

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
  - Validation du triplet de compensation TPS54331 ($R_{11} = 10\text{ k}\Omega, C_9 = 3.3\text{ nF}, C_{13} = 220\text{ pF}$) garantissant une marge de phase de $61.7^\circ$ à $68.8^\circ$.
* **[2026-09-20] Dépouillement des revues & Esprit critique :**
  - Mise en évidence des confusions de variantes matérielles chez les reviewers (différences de brochage ADC entre ESP32 classique et ESP32-S3).
  - Nécessité d'un pull-up fort de $1\text{ k}\Omega$ vers le 12V sur la ligne K-Line pour la Daewoo Kalos (ISO 9141-2).
  - Création du moteur d'auto-placement par contraintes `pcb-placer`.