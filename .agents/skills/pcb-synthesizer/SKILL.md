---
name: pcb-synthesizer
description: "Moteur de synthèse PCB en boucle fermée (Co-design Placement -> Routage -> Métrologie CEM -> Couture de masse). Orchestre la chaîne complète EasyEDA Pro, FreeRouting et PCB Stitcher avec rétroaction adaptative et certification DRC = 0."
---

# Skill : PCB Synthesizer (Synthèse en Boucle Fermée Placement-Routage-CEM)

## 1. Vue d'Ensemble & Vision

Le skill `pcb-synthesizer` est l'orchestrateur de haut niveau unifiant la conception de circuits imprimés sous **EasyEDA Pro** en une chaîne fermée entièrement transactionnelle et automatisée :

```
             ┌─────────────────────────────────────────────────────────────┐
             │                     PCB SYNTHESIZER                         │
             │           (Orchestrateur en Boucle Fermée)                  │
             └──────────────────────────────┬──────────────────────────────┘
                                            │
                                            ▼ (1)
             ┌─────────────────────────────────────────────────────────────┐
             │                         PCB-PLACER                          │
             │  Placement Stochastique & Recuit Simulé Physique CEM v2     │
             │  (0 Collision, Keepouts RF, Ancres, Énergie H 1/r³, E 1/r²) │
             └──────────────────────────────┬──────────────────────────────┘
                                            │
                                            ▼ (2)
             ┌─────────────────────────────────────────────────────────────┐
             │                       APPLY PLACEMENT                       │
             │  Injection par Lot EasyEDA Pro avec Snapshot Rollback       │
             └──────────────────────────────┬──────────────────────────────┘
                                            │
                                            ▼ (3)
             ┌─────────────────────────────────────────────────────────────┐
             │                         FREEROUTING                         │
             │  Export DSN -> Patching des NetClasses -> FreeRouting CLI   │
             │  -> Import SES dans EasyEDA Pro                             │
             └──────────────────────────────┬──────────────────────────────┘
                                            │
                                            ▼ (4)
             ┌─────────────────────────────────────────────────────────────┐
             │                         DSN METRICS                         │
             │  Analyseur Métrologique Réel Post-Routage                   │
             │  - Aire réelle de boucle polygonale (Shoelace)              │
             │  - Inductance fermée sur plan GND (Grover/Rosa/Paul)        │
             │  - Skew des paires différentielles                          │
             └──────────────────────────────┬──────────────────────────────┘
                                            │
                       [Conforme ?] ────────┼──────── [Non Conforme]
                            │               │                │
                           OUI              │               NON (Cycle < 3)
                            │               │                │
                            ▼               │                ▼ (Rétroaction)
             ┌──────────────────────────────┴─┐   ┌───────────────────────────┐
             │          PCB-STITCHER          │   │ Resserrement Adaptatif    │
             │  Vias d'échappement GND        │   │ des Contraintes Locales   │
             │  + Pontage d'îlots A* 3D       │   │ et Re-bouclage vers (1)   │
             │  + Reconstruction des Plans    │   └───────────────────────────┘
             └──────────────┬─────────────────┘
                            │
                            ▼ (5)
             ┌─────────────────────────────────────────────────────────────┐
             │                     CERTIFICATION DRC = 0                   │
             │            Rapport de Synthèse Physique Final               │
             └─────────────────────────────────────────────────────────────┘
```

---

## 2. Conformité aux Règles du Projet (AGENTS.md)

- **Règle 1 (Modularité & Moteurs Agnostiques) :**
  - **Zéro composant en dur :** Aucun composant, net ou coordonnée n'est figé dans le code. Toutes les règles sont injectées via `--manifest` (`manifest.json`) et `--config` (`constraints.json`).
  - **Exécution stricte via `uv` :** Toute commande Python doit être lancée via `uv run python ...`.
- **Règle 2 (Sécurité & Contrôle du Pont EasyEDA) :**
  - Sauvegardes atomiques, vérification de connectivité HTTP sur le port 49620 et rollback en cas d'erreur.
- **Règle 5 (Clôture & Post-Validation) :**
  - Contrôle DRC = 0 et ERC = 0 bloquant avant certification.

---

## 3. Composants du Skill

| Fichier | Rôle | Description |
| :--- | :--- | :--- |
| `SKILL.md` | Spécification | Documentation d'architecture et manuel d'utilisation CLI. |
| `dsn_metrics.py` | Métrologie post-routage | Parseur Specctra DSN/SES extrayant les tracés réels des pistes, calculant l'aire de boucle réelle et l'inductance de boucle fermée. |
| `synthesizer_pipeline.py` | Orchestrateur maître | Moteur de coordination exécutant la boucle fermée avec rétroaction itérative (max 3 cycles) et certification finale. |
| `tests/test_dsn_metrics.py` | Banc de tests | Tests unitaires automatisés pour l'analyse métrologique des fichiers DSN/SES. |

---

## 4. Utilisation en Ligne de Commande

### A. Synthèse Complète en Boucle Fermée (Recommandé)
```bash
uv run python .agents/skills/pcb-synthesizer/synthesizer_pipeline.py \
  --manifest documents/pcb/manifest.json \
  --board documents/pcb/constraints.json \
  --max-cycles 3 \
  --passes 10 \
  --apply
```

### B. Métrologie Post-Routage Seule (`dsn_metrics.py`)
```bash
uv run python .agents/skills/pcb-synthesizer/dsn_metrics.py \
  --dsn .agents/skills/freerouting/.cache/board.dsn \
  --manifest documents/pcb/manifest.json \
  --board documents/pcb/constraints.json
```

### C. Mode Simulation (Dry-Run sans altération EasyEDA)
```bash
uv run python .agents/skills/pcb-synthesizer/synthesizer_pipeline.py \
  --manifest documents/pcb/manifest.json \
  --board documents/pcb/constraints.json \
  --dry-run
```
