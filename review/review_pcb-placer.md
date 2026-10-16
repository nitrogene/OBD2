# Review technique — Skill `pcb-placer` v2.1.0

**Objet :** évaluation du skill d'auto-placement PCB pour EasyEDA Pro
**Périmètre :** agnosticité, fiabilité, gestion des contraintes CEM
**Méthode :** revue statique des 14 modules, vérification des constats par analyse de code (lignes exactes citées)
**Verdict global :** excellent noyau algorithmique (recuit incrémental + légalisation + scoring indépendant), mais dette d'agnosticité réelle, un bug bloquant, et un modèle CEM purement heuristique qui mérite une v2 physique.

---

## 1. Synthèse exécutive

| Axe | Note /10 | Commentaire |
|---|---|---|
| Architecture & séparation des responsabilités | 9 | Extraction / scoring / optimisation / légalisation / injection proprement découplées |
| Algorithme de placement (recuit O(N), multi-départs, légalisation) | 9 | Niveau outil industriel open-source ; mise à jour incrémentale de l'énergie bien faite |
| Conformité à la règle 0 « agnostique » | 3 | 6 fichiers contiennent des références projet codées en dur |
| Fiabilité (robustesse, certification) | 5 | Bug `Set` non importé, DRC non bloquant, géométrie de test divergente |
| Modèle CEM | 5 | Règles de distance + proxies HPWL corrects mais sans physique EM (pas de retour de masse, pas de PDN, pas de fréquence) |
| Tests & validation | 2 | Aucun test unitaire ; `validate.py` valide les données d'entrée mais pas le code |

---

## 2. Constats vérifiés (preuves en ligne)

### 2.1 Bug bloquant — P0

- **`render_svg.py` : `Set` utilisé mais jamais importé.** Ligne 185 : `colliding_des: Set[str] = set()` ; l'import ligne 11 est `from typing import Any, Dict, List, Optional, Tuple`. Le script plante avec `NameError` dès qu'une paire en collision existe. Rendu SVG = livrable principal de débogage du placement : c'est le bug le plus visible du skill.

### 2.2 Violations de la règle 0 « agnostique » — P1

| Fichier | Ligne | Référence codée en dur |
|---|---|---|
| `label_placer.py` | 809 | Boîte d'antenne RF `(75.5, 81.28, 8.5, 27.0)` rattachée à `U1` |
| `label_placer.py` | 906–907 | `des in ("J1", "J2")`, `des.startswith("LED") or des in ("D4", "D5")` |
| `placement_resolver.py` | 42, 96–97 | Table de tailles + inférence par motif de désignateur (`"U1"` → ESP32-S3, `"J2"` → USB-C) |
| `render_svg.py` | 185 | Boucle chaude `["U4", "C14", "C7", "D2", "L1"]` en dur |
| `score.py` | 460 | `power_ground_nets = {"GND", "+12V", "+5V", "3.3V"}` |
| `simulated_annealing.py` | 192 | Même ensemble de rails codé en dur (duplication, risque de dérive) |

**Conséquence :** le skill ne peut pas être réutilisé sur un autre projet sans modifier le code — exactement ce que la Règle 0 interdit et que `SKILL.md` proclame. Le formalisme de configuration (`circuit_manifest.json`) contient déjà les bonnes structures (`emc_class`, `placement_constraints`, `anchors`) : il faut finir la migration, pas inventer un nouveau formalisme.

### 2.3 Fiabilité — P1/P2

- **DRC non contraignant.** `apply_placement.py` et `auto_place.py` loggent `errorCount` mais **aucune branche conditionnelle** ne déclenche `exit`/`raise`/`return False` (vérifié). Un placement qui échoue le DRC est sauvegardé et rapporté comme succès. Une « certification DRC » qui ne bloque pas n'en est pas une.
- **Deux géométries de test divergentes pour les keepouts.** `audit_placement.py` teste le **centre** du composant ; `score.py` teste le **courtyard**. Un composant à cheval sur un keepout mais dont le centre est dehors passe l'audit et échoue le score — verdicts contradictoires pour la même carte.
- **`sync_schematic_to_pcb`** clique dans le DOM sur du texte de boutons multilingue : fragile face aux mises à jour d'EasyEDA. À documenter comme limitation assumie, et à encadrer d'un timeout + détection d'échec réelle.
- **Pas de tests.** `RectBox`, `legalize()`, `load_floorplan()` sont purs et testables sans EasyEDA — c'est de la dette gratuite.

---

## 3. Plan de remédiation « agnostique »

### 3.1 État cible

Aucune chaîne de désignateur, aucune coordonnée, aucun rail d'alimentation dans le code. Tout transite par la configuration.

### 3.2 Extensions du schéma `circuit_manifest.json`

```jsonc
{
  "project_profile": {
    "power_nets": ["GND", "+12V", "+5V", "3.3V"],     // consommé par score.py & simulated_annealing.py
    "ground_nets": ["GND"]
  },
  "emc_model": {
    "reference_plane": "GND",
    "hot_loops": [                                       // remplace ["U4","C14","C7","D2","L1"] codé en dur
      {
        "id": "BUCK_HOT_LOOP",
        "net": "PH_BUCK",
        "return_net": "GND",                             // clé v2 : chemin de retour explicite
        "members": [
          {"ref": "U4", "pin": "2"}, {"ref": "C14", "pin": "1"},
          {"ref": "C7", "pin": "1"},  {"ref": "D2", "pin": "2"},
          {"ref": "L1", "pin": "1"}
        ],
        "target_max_inductance_nH": 15.0                  // remplace target_max_mm (voir §5.2)
      }
    ],
    "separation_rules": [
      {
        "id": "BUCK_VS_RF",
        "group_aggressor": {"cluster": "buck_5v"},
        "group_victim":  {"emc_class": "rf_antenna"},
        "coupling": "H_field",
        "frequency_mhz": [65, 260],                      // fondamental + harmonique dominante
        "min_distance_mm": 10.0,
        "weight": 5
      }
    ]
  },
  "components": {
    "U1": {
      "emc_class": "rf_transceiver",
      "package": "ESP32-S3",
      "antenna_keepout": {"dx_min_mm": -9.0, "dx_max_mm": 9.0,
                          "dy_min_mm": 6.45, "dy_max_mm": 12.75,
                          "extend_to_board_edge": true}
    },
    "J1": {"emc_class": "mechanical_connector", "edge_flush": "west"},
    "D4": {"emc_class": "esd_protection", "silkscreen_clearance_boost_mm": 0.30}
  }
}
```

### 3.3 Refactorings mécaniques (P1, effort faible, gain immédiat)

1. **`render_svg.py`** : ajouter `Set` à l'import `typing` ; lire `hot_loops` et la palette de couleurs depuis le manifeste (avec fallback neutre).
2. **`label_placer.py`** : remplacer `des in ("J1","J2")` par `emc_class == "mechanical_connector"` ; le keepout U1 par `antenna_keepout` du manifeste (la logique existe déjà dans `score.py::get_all_keepouts` — la réutiliser au lieu de dupliquer).
3. **`placement_resolver.py`** : supprimer `_infer_node_size` par motif de désignateur ; exiger les dimensions depuis `packages` du manifeste et rejeter en erreur explicite si absent (échec franc > inférence silencieuse fausse).
4. **`score.py` / `simulated_annealing.py`** : lire `power_nets` depuis `project_profile`, constante partagée dans `placement_constraints.py`.

---

## 4. Fiabilité : plan d'action

| # | Action | Priorité | Effort |
|---|---|---|---|
| R1 | Corriger l'import `Set` dans `render_svg.py` | P0 | 1 ligne |
| R2 | DRC bloquant : `if err_count > 0: rollback/save=False + exit(2)` dans `apply_placement.py` et `auto_place.py` ; ajouter `--drc-tolerant` pour contourner explicitement | P1 | ~15 lignes |
| R3 | Unifier la géométrie de test : courtyards partout ; `audit_placement.py` doit réutiliser `get_component_courtyard_box` de `score.py` | P1 | ~30 lignes |
| R4 | Tests unitaires (pytest, sans EasyEDA) : `RectBox` (intersections, rotation 90°), `legalize()` (cas de pénétration artificiels), `load_floorplan()` (mm/mil, erreurs), `optimize_labels()` sur géométrie synthétique | P1 | 1 journée |
| R5 | Validation de schéma : pydantic ou jsonschema sur `circuit_manifest.json` / `board_constraints.json` avant tout solveur | P2 | 1/2 journée |
| R6 | Reproductibilité : journaliser `seed`, version du skill, hash des configs dans `placement_candidate.json` (le seed est fixé mais non tracé) | P2 | ~10 lignes |
| R7 | Transactionnalité pont : snapshot des positions avant `batch_move_components`, restauration en cas d'exception (le pont permet `get_components` avant/après) | P2 | ~40 lignes |
| R8 | Supprimer ou implémenter les contraintes **thermiques** promises par SKILL.md (au minimum : distance IC–cuivre dissipateur, thermal vias) | P2 | 1–2 jours |

---

## 5. Améliorer la gestion des contraintes CEM

C'est le cœur de la demande. Le modèle actuel est **topologique** : distances max, HPWL de nœuds, keepouts. C'est la bonne base (cohérent avec l'état de l'art industriel), mais quatre améliorations le feraient passer de « règles de bonne pratique automatisées » à « optimisation CEM quantitative ».

### 5.1 Contraintes CEM actuelles — inventaire honnête

| Mécanisme | Où | Nature | Limite |
|---|---|---|---|
| Proximité pad-à-pad (découplage, ESD, reset) | `score.py`, `simulated_annealing.py`, `audit_placement.py` | Heuristique distance | Sans fréquence ni impedance ; seuil unique |
| Compacité de boucle (HPWL des membres) | idem | Proxy HPWL | Ignore le chemin de retour : une boucle HPWL courte avec retour éloigné reste une grande boucle rayonnante |
| Keepouts d'antenne (dérivés des packages) | `score.py::get_all_keepouts` | Géométrique | Correct ; à généraliser (§3.3) |
| Séparation agresseur/victime | `score.py` | Distance au keepout[0] | Ne regarde que le premier keepout ; pas de décroissance avec fréquence |
| Rails électriquement exclus du HPWL | codé en dur | Filtre | Devient config (§3.2) |

### 5.2 Levier 1 — Physique des boucles : remplacer le HPWL par une inductance de boucle estimée

Le HPWL d'un ensemble de pads surestime ou sous-estime la vraie boucle. Une estimation d'inductance de boucle partielle est calculable **au placement**, sans routage :

```
L_loop ≈ μ0/2π · Σ_segments ℓ · [ ln(2ℓ/(w+h)) − 1 + ... ]   (formule de Rosa/Grover simplifiée)
```

Implémentation pragmatique : construire l'arbre de Steiner minimal (ou MST) des pads de la boucle sur le plan de référence, et surtout exiger `return_net` dans la contrainte : l'inductance de la boucle = inductance du chemin d'aller **plus** inductance du chemin de retour via le réseau `return_net`. Un condensateur de découplage placé loin de la broche d'un circuit intégré mais proche d'un via GND devient correctement pénalisé — ce que le HPWL pur ne voit pas.

**Gain :** la contrainte `target_max_mm` devient `target_max_inductance_nH` (typ. 5–20 nH pour une boucle de Buck). Alignement direct avec la pratique PDN.

### 5.3 Levier 2 — Sensibilité au chemin de retour (return-path awareness)

La cause n°1 d'échec CEM en placement est un retour de courant qui contourne une fente de plan. Le placement peut l'anticiper :

- Pour chaque net à signal rapide (`emc_class: "clock"` | `"switching_node"`), mesurer la distance du pad de source au **pad/via de référence le plus proche** (`reference_plane`). Pénaliser si > seuil (typ. 5 mm).
- Bonus : après routage, `export_dsn()` existe déjà — parse le DSN pour vérifier que chaque via de signal à fréquence élevée a un via de référence à < 3 mm. Fermer la boucle placement → routage → vérification.

### 5.4 Levier 3 — Efficacité de découplage : proxy d'impédance plutôt que distance seule

Le placement d'un condensateur de découplage est gouverné par l'**inductance de propagation** (spreading inductance), pas par la seule distance euclidienne. Proxy calculable au placement :

```
Z_eff(f) ≈ 2πf · (L_via + L_trace + L_spread)  avec L_spread ≈ f(geometry pad, nb vias, plan)
```

Le score CEM actuel (`f_proximity_cem`) devient une pénalité d'impédance cible : `|Z_target(f) − Z_estimé(f)|`. Même modèle grossier (±30 %), il classe correctement « capa 0402 collée à la broche avec 2 vias » vs « capa 1206 éloignée à 1 via » — le classement, pas la valeur absolue, est ce qui guide l'optimiseur.

### 5.5 Levier 4 — Contraintes fréquentielles et décroissance spatiale

La séparation agresseur/victime dépend du mécanisme et de la fréquence :

- Champ H quasi-statique (boucles di/dt) : chute ~1/r³ → pénalité `w/(r³·f²)`
- Champ E / couplage capacitif (nœuds dv/dt) : ~1/r²
- Conduite (partage d'impédance commune) : pénalité sur la longueur commune estimée, pas sur la distance

Ajouter `coupling: "H_field" | "E_field" | "conducted"` et `frequency_mhz` dans le DSL (§3.2) rend le moteur de séparation honnête physiquement sans nécessiter de solveur de champ.

### 5.6 Levier 5 — Boucle fermée simulation ↔ mesure (feuille de route)

Alignement sur l'état de l'art : le placement ne se certifie pas en distance, il se certifie en émission.

1. **Court terme (dans le skill)** : export DSN → mesure post-routage des aires de boucle réelles et de la longueur de retour → ré-injection comme poids ajustés dans `simulated_annealing` (co-optimisation placement-routage, itérative).
2. **Moyen terme** : hook de solveur externe (HyperLynx, openEMS, ou champ proche) sur `placement_candidate.json` ; le score indépendant `score.py` est déjà la bonne porte d'entrée — il suffit d'ajouter un backend `FieldSolverBackend` à côté des métriques actuelles.
3. **Validation** : scan champ proche en pré-conformité, hotspots reportés comme nouvelles `keepout_zones` dynamiques dans le manifeste — la boucle d'amélioration continue existe alors de bout en bout.

### 5.7 Pondération multicritère

Passer d'un score scalaire figé à un **front de Pareto** traçable : `f_prox`, `f_loop`, `f_sep` vs surface/HPWL. `weighted_total_score` existe déjà ; le faire varier selon un profil projet (`"profile": "automotive_emc_strict" | "consumer" | "cost_first"`) rend le skill réutilisable sans retoucher les poids en dur.

---

## 6. Priorisation consolidée

| Rang | Livrable | Effort estimé | Impact |
|---|---|---|---|
| 1 | Fix `Set` + DRC bloquant (R1, R2) | 0.5 j | Fiabilité perçue immédiate |
| 2 | Migration agnostique complète (§3.3) | 1–2 j | Réutilisabilité — cœur de la charte |
| 3 | Unification courtyard + tests unitaires (R3, R4) | 1–2 j | Confiance dans les verdicts |
| 4 | DSL CEM v2 : return_net, coupling, fréquence (§5.2–5.5) | 3–5 j | Saut qualitatif du modèle CEM |
| 5 | Boucle DSN post-routage (§5.6-1) | 2–3 j | Certification réelle |
| 6 | Backend solveur de champ + Pareto (§5.6-2, §5.7) | 5–10 j | Différenciation état de l'art |

---

## 7. Verdict

Un **noyau algorithmique de qualité professionnelle** — recuit incrémental, légalisation déterministe, évaluateur indépendant, multi-départs — grevé par une dette d'agnosticité concentrée et remboursable, un bug bloquant trivial, et un modèle CEM volontairement simple qui doit maintenant évoluer vers la physique (inductance de boucle, chemin de retour, impédance de découplage) si le skill veut prétendre à l'optimisation CEM plutôt qu'à l'automatisation de règles de bonnes pratiques.

Les leviers §5.2–5.5 sont tous calculables au placement, sans solveur EM, et s'intègrent dans l'architecture existante (nouvelles métriques dans `score.py`, nouveaux termes d'énergie dans `simulated_annealing.py`).
