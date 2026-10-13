---
name: pcb-stitcher
description: "Moteur d'auto-stitching, d'échappement par vias et de pontage multi-couches d'îlots de cuivre pour EasyEDA Pro. Résout la continuité des plans de masse (GND) et rails d'alimentation en respectant les contraintes DRC et CEM."
---

# Skill : PCB Stitcher pour EasyEDA Pro

## 1. Vue d'Ensemble & Architecture

Le skill `pcb-stitcher` est un moteur algorithmique d'automatisation de la continuité électrique des plans de cuivre (masse de référence `GND`, rails d'alimentation ou plans thermiques) conçu pour EasyEDA Pro.

Après un auto-routage des signaux (par exemple via FreeRouting) et la génération des zones de cuivre (`rebuildCopperRegion`), deux problèmes physiques récurrents surviennent :
1. **Pastilles CMS isolées :** Des pastilles de masse en face supérieure (ou inférieure) ne disposent pas d'un via d'échappement vers le plan de masse opposé.
2. **Îlots de cuivre déconnectés :** Des pistes de signaux traversantes découpent les plans de cuivre en presqu'îles ou îlots flottants (`Connection Error` au contrôle DRC).

### Chaîne d'Exécution du Pipeline :
```
[EasyEDA Pro PCB (Pours Rebuilt)]
       │
       ▼ (1) fanout_stitcher.py : Détection des pastilles CMS sans via & injection des vias d'échappement
[Pours Rebuilt + DRC Audit]
       │
       ▼ (2) island_bridger.py : Routage A* 3D multi-couches des îlots isolés vers le plan de référence
[Pours Rebuilt]
       │
       ▼ (3) stitcher_pipeline.py : Validation finale DRC = 0 strict
```

---

## 2. Conformité aux Règles du Projet (agents.md)

- **Règle 1 (Modularité & Moteur Agnostique) :**
  - **Zéro composant en dur :** Aucune référence à un composant (`U4`, `R13`, `C7`, etc.), aucune coordonnée physique ni net spécifique n'est codé dans les scripts.
  - **Provenance des Données :** Tous les paramètres (nom du net, largeur de piste, isolement, dimensions des vias) proviennent exclusivement des arguments en ligne de commande (`--net`, `--clearance-mm`, `--via-drill-mm`, etc.) ou de la topologie physique lue dynamiquement via l'API EasyEDA Pro.
  - **Exécution stricte via `uv` :** Tout script Python du skill est exécuté impérativement via `uv run python <script>.py`.
- **Règle 1 (Transparence et Sécurité) :**
  - Toute modification injectée dans le document PCB via le pont EasyEDA (`http://localhost:49620`) est explicitée au préalable (nombre de vias, coordonnées des segments).

---

## 3. Composants du Skill

| Script | Rôle | Description |
| :--- | :--- | :--- |
| `geometry.py` | Moteur géométrique agnostique | Fournit le calcul continu des distances segment-segment, segment-point, détection des collisions face aux pistes, pastilles et vias, et respect des keepouts et contours de carte. |
| `fanout_stitcher.py` | Solveur de vias d'échappement | Identifie les pastilles CMS du net cible nécessitant un via, échantillonne radialement les spots sans collision et trace la micro-piste de raccordement. |
| `island_bridger.py` | Routeur A* multi-couches | Identifie les îlots déconnectés (via le DRC), calcule les trajectoires A* 3D avec transitions de vias et contrôle continu de dégagement, et injecte les passerelles. |
| `stitcher_pipeline.py` | Orchestrateur maître | Coordonne la séquence complète (Fanout $\to$ Recalcul des plans $\to$ Audit DRC $\to$ Pontage A* $\to$ Contrôle final DRC = 0). |

---

## 4. Utilisation en Ligne de Commande

### Pipeline Complet Unifié (Recommandé)
```bash
# Exécution du pipeline complet avec application directe dans le PCB :
uv run python .agents/skills/pcb-stitcher/stitcher_pipeline.py --net GND --clearance-mm 0.23 --track-width-mm 0.30 --via-drill-mm 0.30 --via-diameter-mm 0.60 --apply

# Simulation préalable (Dry-Run sans modification du PCB) :
uv run python .agents/skills/pcb-stitcher/stitcher_pipeline.py --net GND --clearance-mm 0.23
```

### Options du Pipeline :
- `--net <str>` : Nom du net cible (défaut : `GND`).
- `--clearance-mm <float>` : Marge d'isolement minimale garantie face à tous les obstacles (défaut : `0.23` mm / 9.0 mil pour satisfaire le DRC standard JLCPCB de 0.20 mm).
- `--track-width-mm <float>` : Largeur des micro-pistes d'échappement et passerelles (défaut : `0.30` mm / 12 mil).
- `--via-drill-mm <float>` : Diamètre de perçage des vias de couture (défaut : `0.30` mm / 12 mil).
- `--via-diameter-mm <float>` : Diamètre extérieur de couronne des vias (défaut : `0.60` mm / 24 mil).
- `--grid-step-mil <float>` : Pas de la grille de discrétisation pour l'algorithme A* (défaut : `5.0` mil).
- `--port <int>` : Port HTTP du pont local EasyEDA Pro (défaut : `49620`).
- `--apply` : Applique les primitives (vias, lignes) et déclenche la reconstruction des plans dans EasyEDA Pro.

---

## 5. Algorithme de Routage A* 3D

L'algorithme A* d'`island_bridger.py` garantit :
- **Transitions de couches intelligentes :** Une transition TopLayer $\leftrightarrow$ BottomLayer n'est autorisée qu'aux coordonnées où un via complet respecte la règle de dégagement sur toutes les couches conductrices.
- **Pénalité de via :** Un surcoût est appliqué aux transitions de vias afin de privilégier les tracés restant sur le plan de cuivre le plus direct.
- **Vérification de dégagement continu :** Chaque segment reliant deux nœuds de la grille est vérifié analytiquement (distance segment-segment) pour empêcher tout chevauchement en diagonale ou coupure de coin de pastille.
- **Lissage colinéaire :** Le chemin en grille est automatiquement fusionné en segments rectilignes et diagonaux conformes aux standards de CAO électronique.
