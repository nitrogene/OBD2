# Spécification Technique : Skill `pcb-placer` (Placement PCB & CEM v2.0)

Ce document constitue la référence d'architecture, de modélisation mathématique et de feuille de route pour la refonte complète du skill `.agents/skills/pcb-placer/`. Il synthétise les recommandations du document [`review/README_placement_CEM.md`](review/README_placement_CEM.md) et les adapte aux contraintes strictes du projet (Règles `AGENTS.md`).

---

## Sommaire

1. [Vision & Principes Directeurs](#1-vision--principes-directeurs)
2. [Architecture des Données & Schémas v2.0](#2-architecture-des-données--schémas-v20)
   - 2.1 Répartition des responsabilités
   - 2.2 `circuit_manifest.json` (Vérité Schéma & CEM)
   - 2.3 `board_constraints.json` (Vérité Mécanique & Boîtier)
   - 2.4 `netlist_geometry.json` (Extraction Géométrique Live)
   - 2.5 `placement.json` (Livrable d'Agencement)
3. [Modèle Mathématique & Évaluateur Indépendant (`score.py`)](#3-modèle-mathématique--évaluateur-indépendant-scorepy)
   - 3.1 Contraintes dures vs Contraintes molles
   - 3.2 Termes du score normalisé
   - 3.3 Visualisation & Rapport SVG
4. [Architecture Algorithmique en Trois Étages](#4-architecture-algorithmique-en-trois-étages)
   - 4.1 Étage A : Micro-placement exact par CP-SAT (OR-Tools)
   - 4.2 Étage B : Placement global par Recuit Simulé multi-départs
   - 4.3 Étage C : Raffinement local par fenêtres LNS (CP-SAT)
   - 4.4 Légalisation et alignement sur grille finale
   - 4.5 Modélisation et gestion de la rotation
5. [Intégration avec EasyEDA Pro](#5-intégration-avec-easyeda-pro)
6. [Feuille de Route & Jalons d'Implémentation](#6-feuille-de-route--jalons-dimplémentation)
7. [Matrice de Conformité aux Règles du Projet (`AGENTS.md`)](#7-matrice-de-conformité-aux-règles-du-projet-agentsmd)

---

## 1. Vision & Principes Directeurs

Le skill `pcb-placer` a pour mission de calculer un agencement physique 2D optimal des composants d'un circuit imprimé, conciliant **contraintes mécaniques**, **intégrité du signal**, **immunité CEM** et **industrialisation SMT**.

### Principes Clés

1. **Séparation Découplée Schéma / Mécanique / Moteur :**
   * Le schéma ne connaît pas la boîte.
   * La boîte ne connaît pas les transistors.
   * Le moteur algorithmique ne contient **aucun composant, dimension ou coordonnée en dur** (Règle 0 `AGENTS.md`).
2. **Découplage Solveur / Évaluateur (`score.py`) :**
   * L'évaluation de la qualité d'un placement est un module totalement indépendant de l'algorithme d'optimisation.
   * Permet de benchmarker le placement manuel existant comme « référence à battre », de tester différents optimiseurs sur une base objective, et de détecter les régressions.
3. **Unité et Repère Uniques :**
   * Bannissement du mélange `mil` / `mm` : **l'unité interne unique est le millimètre (`mm`)**.
   * Repère cartésien explicite : origine en bas à gauche (`bottom_left`), axe Y vers le haut (`up`), angles en degrés trigonométriques anti-horaires (`ccw_degrees`).
4. **Zéro Perte d'Information :**
   * L'ancien `floorplan.json` cesse d'être une double source de vérité fragile. Les coordonnées physiques sont persistées dans EasyEDA Pro (`easyeda/OBD2.epro2`), la mécanique dans `board_constraints.json`, la sémantique dans `circuit_manifest.json`.

```
 circuit_manifest.json ──┐
 board_constraints.json ─┼─► validate.py ─► Modèle Interne Normalisé (mm)
 netlist_geometry.json ──┘        │            (Pads réels, nets, courtyards)
                                  ▼
        Étage A : Micro-placement des clusters rigides (CP-SAT exact)
                                  ▼
        Étage B : Placement global macro (Recuit Simulé multi-départs)
                                  ▼
        Étage C : Raffinement local par fenêtres (LNS / CP-SAT)
                                  ▼
        Évaluateur de score (score.py) ──► placement.json + visualiseur SVG
                                  ▼
               Injection validée dans EasyEDA Pro (DRC = 0)
```

---

## 2. Architecture des Données & Schémas v2.0

### 2.1 Répartition des responsabilités

| Fichier | Nature & Rôle | Mainteneur | Versionné Git ? |
| :--- | :--- | :--- | :--- |
| `circuit_manifest.json` | **Vérité Schéma & CEM** : Blocs fonctionnels, rôles sémantiques, classes CEM, contraintes CEM (`proximity`, `loop`, `net_compact`), packages et cotes 3D. | Architecte / Agent | **OUI** (Source de vérité) |
| `board_constraints.json` | **Vérité Mécanique** : Gabarit physique, 4 vis M2 avec dégagements, ancres de bordure (`J1`, `J2`), zones interdites (keepouts), règles de séparation, NetClasses. | Architecte / Agent | **OUI** (Source de vérité) |
| `netlist_geometry.json` | **Export Géométrique Live** : Empreintes réelles extraites du canevas EasyEDA Pro (dimensions exactes des pads, courtyards, connectivité broche-à-broche). | Moteur (généré) | Non (ou cache transitoire) |
| `placement.json` | **Livrable d'Implantation** : Coordonnées calculées `(X, Y, rotation, face)` + rapport de score pour injection ou contrôle. | Moteur (produit) | Optionnel / Rapport |

---

### 2.2 `circuit_manifest.json` (Vérité Schéma & CEM)

Ce fichier étend l'ancien `circuit_semantics.json` en y intégrant formellement les boîtiers (`packages`) et les contraintes géométriques CEM sous forme structurée.

#### A. Dictionnaire des Packages (`packages`)
Définit les dimensions enveloppes et la marge d'implantation normalisée (IPC-7351B) :

```json
{
  "schema_version": "2.0",
  "project": "OBD2-Scanner-ESP32",
  "packages": {
    "0603": {
      "width_mm": 1.6, "length_mm": 0.8, "height_mm": 0.5,
      "courtyard_margin_mm": 0.25,
      "description": "CMS passif standard 0603"
    },
    "0805": {
      "width_mm": 2.0, "length_mm": 1.25, "height_mm": 0.6,
      "courtyard_margin_mm": 0.25
    },
    "SOIC-8": {
      "width_mm": 4.9, "length_mm": 3.9, "height_mm": 1.75,
      "courtyard_margin_mm": 0.5
    },
    "MODULE_ESP32_S3": {
      "width_mm": 18.0, "length_mm": 25.5, "height_mm": 3.2,
      "courtyard_margin_mm": 0.5
    }
  }
}
```

#### B. Typage des Composants (`components`)
Chaque composant reçoit ses métadonnées de placement :

```json
"C7": {
  "block": "buck_5v",
  "role": "bulk_input_reservoir",
  "package": "1206",
  "value": "10uF",
  "placement": {
    "allowed_rotations": [0, 90, 180, 270],
    "side": "top",
    "emc_class": "neutral",
    "priority": 2
  }
}
```

* `allowed_rotations` : `[0, 180]` pour les pièces polarisées, `[0, 90, 180, 270]` pour les passifs non polarisés, `[rot_fixe]` pour les ancres.
* `emc_class` : `aggressor` (générateur de bruit), `victim` (signal sensible), ou `neutral`.
* `priority` : Ordre d'agencement dans l'étage A (1: IC maître, 2: découplage immédiat, 3: passifs annexes, 4: points de test).

#### C. Liste Unifiée des Contraintes (`placement_constraints`)
Remplace les anciens mappings hétérogènes par une typologie formelle avec distinction **dur (`hard: true`) / mou (`hard: false`)** et **poids de pénalité (1 à 10)** :

```json
"placement_constraints": [
  {
    "id": "PC_C14_VIN",
    "type": "proximity",
    "subject": { "ref": "C14", "pin": "1" },
    "target":  { "ref": "U4",  "pin": "2" },
    "metric": "pad_to_pad",
    "max_mm": 3.0,
    "hard": true,
    "weight": 10,
    "rationale": "Découplage HF entrée Buck < 3 mm de VIN"
  },
  {
    "id": "PC_BUCK_HOT_LOOP",
    "type": "loop",
    "members": [
      { "ref": "C14", "pin": "1" }, { "ref": "C7", "pin": "1" },
      { "ref": "U4", "pin": "2" },  { "ref": "U4", "pin": "8" },
      { "ref": "D2", "pin": "K" },  { "ref": "U4", "pin": "7" }
    ],
    "metric": "bbox_half_perimeter",
    "target_max_mm": 25.0,
    "hard": false,
    "weight": 8,
    "rationale": "Boucle chaude de découpage di/dt minimale"
  },
  {
    "id": "PC_PH_NODE_COMPACT",
    "type": "net_compact",
    "net": "PH_BUCK",
    "metric": "bbox_half_perimeter",
    "target_max_mm": 12.0,
    "hard": false,
    "weight": 6,
    "rationale": "Nœud de commutation PH haute fréquence compact pour limiter le rayonnement"
  },
  {
    "id": "PC_SW1_EDGE",
    "type": "edge_access",
    "subject": { "ref": "SW1" },
    "edge": "north",
    "max_distance_to_edge_mm": 5.0,
    "hard": false,
    "weight": 2,
    "rationale": "Accessibilité mécanique du bouton Reset"
  }
]
```

#### D. Définition des Micro-Clusters Rigides (`rigid_groups`)
Spécifie les ensembles de composants intimement liés qui doivent être résolus ensemble à l'étage A puis déplacés comme un bloc indéformable à l'étage B :

```json
"rigid_groups": [
  {
    "id": "G_BUCK_CORE",
    "anchor_component": "U4",
    "members": ["U4", "C5", "C7", "C14", "D2", "C17", "R11", "C9", "C13"],
    "layout": "solve"
  },
  {
    "id": "G_ESP32_CORE",
    "anchor_component": "U1",
    "members": ["U1", "C1", "C2", "C11", "C12", "R15"],
    "layout": "solve"
  }
]
```

---

### 2.3 `board_constraints.json` (Vérité Mécanique & Boîtier)

Ne contient **que** ce qui est dicté par la carte nue, les fixations et le boîtier extérieur.

```json
{
  "schema_version": "2.0",
  "project": "Scanner OBD-II ESP32",
  "frame": {
    "unit": "mm",
    "origin": "bottom_left",
    "y_axis": "up",
    "rotation": "ccw_degrees",
    "internal_resolution_mm": 0.05,
    "final_snap_mm": 0.635
  },
  "board": {
    "outline_polygon_mm": [
      [0.0, 0.0],
      [81.28, 0.0],
      [81.28, 35.56],
      [0.0, 35.56]
    ],
    "width_mm": 81.28,
    "height_mm": 35.56,
    "layers": 2,
    "edge_clearance_mm": 1.0,
    "mounting_holes": [
      { "id": "MH1", "x_mm": 3.5, "y_mm": 3.5,   "drill_mm": 2.2, "pad_mm": 4.5, "head_clearance_mm": 4.5, "net": "GND" },
      { "id": "MH2", "x_mm": 3.5, "y_mm": 32.06, "drill_mm": 2.2, "pad_mm": 4.5, "head_clearance_mm": 4.5, "net": "GND" },
      { "id": "MH3", "x_mm": 77.78, "y_mm": 3.5,   "drill_mm": 2.2, "pad_mm": 4.5, "head_clearance_mm": 4.5, "net": "GND" },
      { "id": "MH4", "x_mm": 77.78, "y_mm": 32.06, "drill_mm": 2.2, "pad_mm": 4.5, "head_clearance_mm": 4.5, "net": "GND" }
    ]
  },
  "anchors": {
    "J1": {
      "x_mm": 8.89, "y_mm": 17.78, "rot_deg": 270,
      "fixed": true,
      "ref_point": "courtyard_center",
      "edge_flush": "west",
      "overhang_mm": 0.0,
      "description": "Bornier OBD 5 contacts affleurant bord Ouest"
    },
    "J2": {
      "x_mm": 40.64, "y_mm": 3.81, "rot_deg": 0,
      "fixed": true,
      "ref_point": "courtyard_center",
      "edge_flush": "south",
      "overhang_mm": 0.0,
      "description": "Prise USB-C affleurante bord Sud"
    },
    "U1": {
      "x_mm": 64.77, "y_mm": 17.78, "rot_deg": 0,
      "fixed": true,
      "ref_point": "courtyard_center",
      "description": "Module ESP32-S3 orienté Est"
    }
  },
  "keepout_zones": [
    {
      "name": "RF_ANTENNA_KEEPOUT",
      "rect_mm": { "x_min": 73.66, "x_max": 81.28, "y_min": 7.62, "y_max": 27.94 },
      "applies_to": "all_except",
      "exempt_refs": ["U1"],
      "layers": ["top", "bottom", "internal"],
      "forbid": ["components", "copper", "vias"],
      "description": "Exclusion RF sous antenne méandre ESP32"
    }
  ],
  "separation_rules": [
    {
      "id": "SEP_BUCK_ANTENNA",
      "group_a": { "cluster": "buck_5v" },
      "group_b": { "zone": "RF_ANTENNA_KEEPOUT" },
      "min_distance_mm": 15.0,
      "hard": false,
      "weight": 6,
      "rationale": "Découpage Buck 570 kHz éloigné de l'antenne radio 2.4 GHz"
    },
    {
      "id": "SEP_AGGRESSOR_VICTIM",
      "group_a": { "emc_class": "aggressor" },
      "group_b": { "emc_class": "victim" },
      "min_distance_mm": 8.0,
      "hard": false,
      "weight": 5,
      "rationale": "Isolation des bus sensibles (USB, CAN) des commutations de puissance"
    }
  ],
  "net_classes": {
    "POWER_12V":        { "track_width_mm": 0.8, "clearance_mm": 0.25, "emc_class": "power_raw" },
    "POWER_REGULATED":  { "track_width_mm": 0.6, "clearance_mm": 0.20, "emc_class": "power_clean" },
    "SWITCHING_BUCK":   { "track_width_mm": 0.8, "clearance_mm": 0.30, "emc_class": "aggressor" },
    "DIFF_USB":         { "track_width_mm": 0.3, "clearance_mm": 0.20, "diff_pair": true, "diff_z_ohm": 90.0, "emc_class": "victim" },
    "DIFF_CAN":         { "track_width_mm": 0.3, "clearance_mm": 0.25, "diff_pair": true, "diff_z_ohm": 120.0, "emc_class": "victim" },
    "SIGNAL_CRITICAL":  { "track_width_mm": 0.254, "clearance_mm": 0.20, "emc_class": "signal" },
    "DEFAULT":          { "track_width_mm": 0.254, "clearance_mm": 0.20, "emc_class": "neutral" }
  }
}
```

---

### 2.4 `netlist_geometry.json` (Extraction Géométrique Live)

Ce fichier est **généré automatiquement** par extraction directe depuis EasyEDA Pro via le skill `easyeda-api`. Il constitue la référence absolue des dimensions réelles des pastilles et de la connectivité broche-à-broche :

```json
{
  "generated_at": "2026-10-04T10:00:00Z",
  "components": {
    "U4": {
      "footprint": "SOIC-8",
      "courtyard": { "width_mm": 5.9, "height_mm": 4.9, "center_offset_mm": [0.0, 0.0] },
      "pads": [
        { "number": "1", "name": "BOOT", "x_mm": -1.905, "y_mm": -2.7, "width_mm": 0.6, "height_mm": 1.5, "net": "BOOT_BUCK" },
        { "number": "2", "name": "VIN",  "x_mm": -0.635, "y_mm": -2.7, "width_mm": 0.6, "height_mm": 1.5, "net": "+12V_PROT" },
        { "number": "8", "name": "PH",   "x_mm": -1.905, "y_mm":  2.7, "width_mm": 0.6, "height_mm": 1.5, "net": "PH_BUCK" }
      ]
    }
  },
  "nets": {
    "PH_BUCK": [["U4", "8"], ["D2", "K"], ["L1", "1"], ["C5", "2"], ["TP12", "1"]],
    "BOOT_BUCK": [["U4", "1"], ["C5", "1"], ["TP13", "1"]]
  }
}
```

*Toutes les coordonnées relatives des broches sont données à rotation 0° par rapport au centre du courtyard.*

---

## 3. Modèle Mathématique & Évaluateur Indépendant (`score.py`)

### 3.1 Contraintes Dures vs Contraintes Molles

* **Contraintes Dures (Hard Constraints) :**
  * Doivent être impérativement satisfaites ($Violation = 0$). Une solution présentant une seule violation dure est **rejetée et déclarée non livrable**.
  * Types : Hors-carte, chevauchement de courtyards, intrusion en zone keepout (hors exemption), violation des têtes de vis M2, composants ancres verrouillés, contraintes `proximity` marquées `hard: true`.
* **Contraintes Molles (Soft Objectives) :**
  * Contribuent à la fonction de coût à minimiser.
  * Chaque terme $f_j$ est **adimensionné et normalisé** (valeur typique entre 0 et 1) par rapport à une échelle physique de référence avant pondération.

### 3.2 Formules Normalisées de la Fonction de Coût

La fonction objectif globale s'écrit :

$$\text{Score} = \sum_{j} w_j \cdot f_j(\mathbf{x})$$

Pendant les phases stochastiques (Recuit), la fonction d'évaluation intègre les pénalités dures avec un multiplicateur $\lambda$ croissant :

$$C_{\text{recherche}}(\mathbf{x}) = \text{Score} + \lambda \sum_{k} \text{ViolationHard}_k + \mu \cdot \text{SurfaceOverlap}$$

#### Détail des Termes Normalisés ($f_j$) :

1. **Longueur de Câblage Globale (HPWL Normalisé) :**
   $$f_{\text{wire}} = \frac{\sum_{n \in \text{Nets}} \text{HPWL}(n)}{\text{Demi-périmètre de carte}}$$
   *Mesure la somme des demi-périmètres des boîtes englobantes des pastilles de chaque signal (hors plans d'alimentation et GND).*
2. **Proximité CEM Pad-à-Pad :**
   $$f_{\text{prox}, i} = \max\left(0, \frac{d_{\text{pad-pad}} - d_{\text{max}}}{d_{\text{max}}}\right)$$
3. **Compacité de Boucle à Fort di/dt (Buck Hot Loop) :**
   $$f_{\text{loop}} = \frac{\text{HPWL}(\text{Broches de la boucle})}{L_{\text{cible}}}$$
4. **Compacité d'un Nœud Rayonnant (PH_BUCK) :**
   $$f_{\text{net}} = \frac{\text{HPWL}(\text{Nœud})}{L_{\text{seuil}}}$$
5. **Séparation CEM Agressor / Victim :**
   $$f_{\text{sep}} = \max\left(0, \frac{D_{\text{requis}} - \text{dist}(\text{Groupe}_A, \text{Groupe}_B)}{D_{\text{requis}}}\right)$$
6. **Accessibilité Bord de Carte (SW1, LED1, Cavaliers) :**
   $$f_{\text{edge}} = \frac{\text{dist}(\text{Composant}, \text{Bord Cible})}{D_{\text{max\_bord}}}$$

---

### 3.3 Visualisation & Rapport SVG (`score.py`)

Le script `score.py` est totalement découplé des solveurs. Il produit :
1. Un **bilan chiffré console** détaillant chaque terme de score, le statut des contraintes dures et la comparaison face au placement de référence (baseline).
2. Un **rendu graphique vectoriel SVG** généré automatiquement :
   * Contour du PCB et trous de vis M2 (zones vertes autorisées).
   * Boîtes d'encombrement des composants (rectangles de courtyards colorés par bloc fonctionnel).
   * Zones d'exclusion (hachures rouges).
   * Lignes élastiques reliant les broches associées (vecteurs de force de proximité et boucles).
   * Surlignage immédiat des éventuels chevauchements en rouge clignotant.

---

## 4. Architecture Algorithmique en Trois Étages

L'optimisation globale d'un placement PCB avec contraintes de non-chevauchement (problème NP-difficile disjonctif) est résolue par une cascade à 3 étages combinant programmation par contraintes et métaheuristique stochastique :

```
                  ┌────────────────────────────────────────────────────────┐
                  │ Étage A : Micro-Placement Exact par Micro-Cluster      │
                  │ Algorithme : CP-SAT (Google OR-Tools)                  │
                  │ Périmètre  : 4 à 8 composants par groupe (U4, U1...)   │
                  │ Résultat   : Formes rigides locales optimales          │
                  └──────────────────────────┬─────────────────────────────┘
                                             ▼
                  ┌────────────────────────────────────────────────────────┐
                  │ Étage B : Placement Macro Global                       │
                  │ Algorithme : Recuit Simulé Multi-Départs               │
                  │ Périmètre  : Carte complète (Groupes + Pièces libres)  │
                  │ Résultat   : Équilibre global des forces & CEM         │
                  └──────────────────────────┬─────────────────────────────┘
                                             ▼
                  ┌────────────────────────────────────────────────────────┐
                  │ Étage C : Raffinement Local LNS (Large Neighborhood)   │
                  │ Algorithme : CP-SAT sur fenêtres glissantes (8-15 pcs) │
                  │ Condition  : Acceptation stricte si score.py s'améliore│
                  └──────────────────────────┬─────────────────────────────┘
                                             ▼
                  ┌────────────────────────────────────────────────────────┐
                  │ Légalisation & Snap Grille Finale (0.635 mm / 25 mil)  │
                  └────────────────────────────────────────────────────────┘
```

### 4.1 Étage A : Micro-placement exact par CP-SAT

* Pour chaque groupe déclaré dans `rigid_groups` (ex: `U4` Buck + composants périphériques `C7`, `C14`, `D2`, `L1`, `C5`, `R11`, `C9`, `C13`) :
  * Modélisation mathématique discrète sur grille fine (résolution $0.05\text{ mm}$).
  * Contrainte `NoOverlap2D` stricte sur les boîtes d'encombrement des courtyards.
  * Minimisation exacte de la boucle chaude et des distances de découplage pad-à-pad.
  * Résolution garantie à l'optimum en moins de 2 secondes.
  * Le micro-cluster résultant est figé en un **macro-composant rigide** doté d'une boîte englobante composite et d'offsets relatifs fixes.

### 4.2 Étage B : Placement global par Recuit Simulé

* **Entités mobiles :** Macro-composants rigides (Étage A) + composants individuels libres.
* **Entités fixes (Obstacles) :** Ancres mécaniques `J1`, `J2`, trous de vis M2, zones keepout.
* **Multi-Départs Parallèles :** 16 à 64 graines aléatoires exécutées en parallèle. Un des départs est initialisé avec la disposition courante du PCB afin de **garantir mathématiquement de ne jamais faire pire que l'existant**.
* **Opérateurs de Voisinage (Moves) :**
  1. *Translation gaussienne :* $\sigma$ proportionnel à la température $T$.
  2. *Swap :* Échange de position entre deux composants de gabarits compatibles.
  3. *Rotation :* Sélection d'un angle parmi `allowed_rotations`.
  4. *Attraction barycentrique :* Déplacement orienté vers la médiane des broches connectées.
  5. *Rotation de macro-cluster :* Rotation collective d'un bloc rigide entier.
* **Refroidissement & Réchauffage :** Schéma de refroidissement adaptatif avec 2 à 3 réchauffages (*reheating*) depuis la meilleure solution trouvée.

### 4.3 Étage C : Raffinement local LNS (Large Neighborhood Search)

* Parcours des zones de congestion ou des points chauds identifiés par `score.py`.
* Sélection d'une fenêtre de 8 à 15 composants libres ; gel de l'ensemble du reste du PCB.
* Résolution exacte par CP-SAT sur cette fenêtre avec un timeout de 5 à 10 secondes.
* **Garde-fou strict :** La solution n'est injectée que si `score.py` confirme une amélioration du score global, éliminant tout risque de régression.

### 4.4 Modélisation et Gestion de la Rotation

La rotation physique modifie l'empreinte au sol et la position spatiale des broches :
* **Dans le Recuit Simulé :**
  Pour un angle $\theta \in \{0^\circ, 90^\circ, 180^\circ, 270^\circ\}$ :
  $$\begin{pmatrix} X_{\text{pad}} \\ Y_{\text{pad}} \end{pmatrix} = \begin{pmatrix} X_{\text{centre}} \\ Y_{\text{centre}} \end{pmatrix} + \begin{pmatrix} \cos\theta & -\sin\theta \\ \sin\theta & \cos\theta \end{pmatrix} \begin{pmatrix} dx_0 \\ dy_0 \end{pmatrix}$$
  Les dimensions du courtyard sont permutées ($W \leftrightarrow H$) à $90^\circ$ et $270^\circ$.
* **Dans CP-SAT :**
  Chaque composant à orientation variable est représenté par des variables booléennes alternatives $b_r \in \{0, 1\}$ avec $\sum_r b_r = 1$ (`ExactlyOne`). Les intervalles spatiaux associés dans `NoOverlap2D` s'activent conditionnellement selon l'orientation choisie.

---

## 5. Intégration avec EasyEDA Pro

Le skill respecte scrupuleusement les règles de communication avec l'environnement EasyEDA Pro :

1. **Phase 1 : Extraction Géométrique Live**
   * Exécution d'un script via le pont local WebSocket/HTTP (`http://localhost:49620`).
   * Récupération exhaustive des composants instanciés, des contours réels des pastilles et des nets.
   * Génération du fichier `netlist_geometry.json`.
2. **Phase 2 : Optimisation Headless**
   * L'ensemble des calculs (CP-SAT, Recuit, LNS, Score) s'exécute en pur Python dans l'environnement local via `uv run`.
   * Zéro blocage de l'interface graphique EasyEDA Pro pendant les calculs.
3. **Phase 3 : Prévisualisation & Validation Humaine**
   * Affichage du rapport de score comparatif (Avant vs Après).
   * Génération de la vue vectorielle SVG pour inspection visuelle immédiate.
4. **Phase 4 : Injection Atomique & Certification**
   * Déplacement en lot via l'API `eda.pcb_PrimitiveComponent.modify()`.
   * Lancement du DRC physique natif EasyEDA Pro (`eda.pcb_Drc.run()`).
   * Validation de l'objectif bloquant : **DRC = 0 erreur**.
   * Sauvegarde du document PCB (`eda.pcb_Document.save()`).

---

## 6. Feuille de Route & Jalons d'Implémentation

Le déploiement du nouveau skill `pcb-placer` s'articule en 5 phases séquentielles indépendantes et testables :

```
 Phase 0 : Schémas JSON v2.0, Validateur formel (validate.py) & Export netlist_geometry.py
           │
           ▼
 Phase 1 : Évaluateur indépendant (score.py) & Rendu SVG
           Mesure du placement manuel actuel (Score de référence)
           │
           ▼
 Phase 2 : Moteur de Recuit Simulé Global (Étage B)
           Validation de l'auto-placement sans violation dure
           │
           ▼
 Phase 3 : Micro-placement CP-SAT (Étage A) & Raffinement LNS (Étage C)
           Gain mesuré face au recuit seul
           │
           ▼
 Phase 4 : Pipeline d'injection EasyEDA Pro, boucle DRC = 0 & Calibration des poids
```

| Phase | Objectif | Livrables Concrets | Critère de Succès |
| :--- | :--- | :--- | :--- |
| **Phase 0** | Fondations des données v2.0 | • Schémas JSON validés (`circuit_manifest.json`, `board_constraints.json`).<br>• Script `validate.py`.<br>• Extracteur `export_geometry.py`. | `validate.py` valide les fichiers à 100%, extraction des 84 composants et 250 pads réussie. |
| **Phase 1** | Évaluateur de score & Baseline | • Script `score.py`.<br>• Générateur de visualisation `render_svg.py`.<br>• Rapport de score du placement actuel. | Calcul du score de référence de la carte actuelle, 0 faux positif dans l'audit. |
| **Phase 2** | Solveur Global (Recuit) | • Moteur `simulated_annealing.py`.<br>• Multi-départs parallélisés.<br>• Gestion des rotations et blocs rigides. | Score inférieur à la baseline manuelle, 0 violation dure, 0 chevauchement. |
| **Phase 3** | Précision CP-SAT & LNS | • Solveur `cpsat_cluster.py` (Étage A).<br>• Module LNS `lns_refiner.py` (Étage C). | Réduction mesurable de l'aire de boucle Buck et du découplage face à la Phase 2. |
| **Phase 4** | Intégration EasyEDA & Finition | • Actionneur `apply_placement.py`.<br>• Commande CLI unifiée `auto_place.py`.<br>• Documentation finale `SKILL.md`. | Injection complète en 1 clic dans EasyEDA Pro, DRC = 0, document PCB sauvegardé. |

---

## 7. Matrice de Conformité aux Règles du Projet (`AGENTS.md`)

| Règle `AGENTS.md` | Exigence | Implémentation dans `pcb-placer` |
| :--- | :--- | :--- |
| **Règle 0** | **Modularité et Découplage** : Zéro composant en dur (`U4`, `R13`), code purement agnostique. | Le solveur ne manipule que des abstractions (`Component`, `Courtyard`, `Constraint`, `Net`). Toutes les données proviennent exclusivement des fichiers JSON de configuration. |
| **Règle 0** | **Exécution Python obligatoire via `uv`** | Toutes les invocations d'outils et de scripts sont systématiquement préfixées par `uv run python ...`. |
| **Règle 1** | **Transparence et Sécurité** | Explication claire des intentions et des modifications avant toute interaction avec le pont EasyEDA (`http://localhost:49620`). |
| **Règle 2** | **Interdiction d'instancier des composants à l'aveugle** | Le placer ne crée aucun composant ; il déplace et oriente exclusivement les composants importés depuis le schéma. |
| **Règle 3** | **Méthodologie séquentielle** | Respect rigoureux du séquencement : Schéma validé $\rightarrow$ Trous M2 et contour $\rightarrow$ Placement des ancres $\rightarrow$ Auto-placement relaxé $\rightarrow$ DRC = 0. |
| **Règle 4** | **Étapes Post-Validation** | DRC = 0 obligatoire, sauvegarde via `eda.pcb_Document.save()`, synchronisation de la sémantique et nettoyage des scripts temporaires. |
| **Règle 6** | **Pas d'anticipation documentaire** | Les documents du projet ne sont mis à jour qu'après validation effective et mesurée du résultat. |
| **Règle 7** | **Typographie Markdown backticks** | Formatage systématique des composants, connecteurs et grandeurs en texte brut avec code en ligne (`J1`, `U1`, `C1`, `3.3V`, `60 Ω`), sans LaTeX mathématique en ligne. |

---

*Document de référence prêt pour revue et validation par l'utilisateur.*
