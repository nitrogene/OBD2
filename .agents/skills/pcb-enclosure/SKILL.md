---
name: pcb-enclosure
description: Moteur paramétrique agnostique de génération de boîtier mécanique 3D (STEP & STL) pour fabrication additive FDM, résine SLA et SLS Nylon JLCPCB.
---

# Skill : pcb-enclosure

Moteur de modélisation mécanique 3D paramétrique, agnostique et automatisé pour boîtiers électroniques.
Il s'appuie sur le noyau géométrique industriel **OpenCASCADE (OCCT)** via la bibliothèque Python `build123d`, garantissant une exécution 100% headless en ligne de commande et l'export direct de fichiers solides **STEP standards (ISO 10303 AP214)** et de maillages **STL haute résolution** directement commandables chez JLCPCB 3D Printing.

---

## 1. Principes d'Ingénierie & Conformité AGENTS.md

- **Règle 1 (Zéro composant en dur) :** Le moteur ne contient aucun composant, dimension ou cote figée. Toutes les grandeurs proviennent exclusivement des fichiers formels injectés :
  - [`documents/pcb/constraints.json`](../../../documents/pcb/constraints.json) : contour du PCB ($W, H$), perçages de fixation (`mounting_holes`).
  - [`documents/pcb/enclosure.json`](../../../documents/pcb/enclosure.json) : épaisseurs de paroi, jeux d'ajustement, bossages, découpes d'interface et serre-câble.
- **Règle 1 (Exécution exclusive via `uv`) :** Tous les scripts s'exécutent via `uv run --with build123d python ...`.
- **Règle 6 (Typographie stricte) :** Aucun balisage LaTeX pour les dimensions ou tolérances physiques.

---

## 2. Architecture Géométrique Générée

Le moteur génère automatiquement trois pièces mécaniques complémentaires :

```
             ┌──────────────────────────────────────────────┐
             │               COQUILLE HAUTE                 │  (Top Shell)
             │   - Perçages pour vis M2 (têtes fraisées)    │
             │   - Évidements pour bouton Flash & LED       │
             │   - Rainure d'emboîtement (joint à lèvre)    │
             └──────────────┬───────────────────────────────┘
                            │ Plan de joint
             ┌──────────────┴───────────────────────────────┐
             │                  CARTE PCB                   │  (Positionnée sur bossages)
             └──────────────┬───────────────────────────────┘
                            │
             ┌──────────────┴───────────────────────────────┐
             │               COQUILLE BASSE                 │  (Bottom Shell)
             │   - 4 colonnettes avec puits inserts M2      │
             │   - Berceau pour câble faisceau OBD-II       │
             │   - Lèvre d'emboîtement périphérique         │
             │   - Bride serre-câble 2 vis (enclosure_clamp)│
             └──────────────────────────────────────────────┘
```

### 1. Coquille basse (`enclosure_bottom`)
- Fond d'épaisseur nominale $T$ avec congés extérieurs $R$.
- 4 colonnettes de surélévation alignées sur les perçages de fixation du PCB avec puits pré-calibrés pour inserts thermofusibles en laiton M2.
- Évidement inférieur pour passage de câble et dégagement des soudures traversantes en face arrière.
- Berceau de serrage pour le câble OBD-II avec 2 puits filetés pour la bride.
- Lèvre d'emboîtement périphérique assurant un alignement sans jeu et une étanchéité aux poussières.

### 2. Coquille haute (`enclosure_top`)
- Toit d'épaisseur nominale $T$ avec rainure d'emboîtement complémentaire.
- 4 puits de vis traversants pour vis M2 avec lamage pour noyer les têtes de vis sous la surface.
- Demi-ouverture supérieure pour le connecteur USB-C sur le plan de joint.
- Perçage d'accès au bouton-poussoir Flash/Boot (permettant l'actionnement par stylet ou poussoir souple).
- Conduit de lumière pour la LED de statut.

### 3. Bride serre-câble (`enclosure_clamp`)
- Bride rigide à 2 vis M2 venant comprimer la gaine extérieure du câble OBD-II dans son berceau.
- Décharge mécanique totale : aucune contrainte de traction ou de torsion n'est transmise aux pastilles du connecteur J1 du PCB.

---

## 3. Utilisation en Ligne de Commande (CLI)

```bash
# Génération complète des pièces STEP et STL pour le projet OBD-II
uv run --with build123d python .agents/skills/pcb-enclosure/scripts/enclosure_generator.py \
    --constraints documents/pcb/constraints.json \
    --enclosure documents/pcb/enclosure.json \
    --output-dir documents/enclosure

# Exécution des tests unitaires géométriques
uv run --with build123d python .agents/skills/pcb-enclosure/tests/test_enclosure.py
```

---

## 4. Fichiers Produits dans `documents/enclosure/`

| Fichier | Format | Description | Destination |
| :--- | :--- | :--- | :--- |
| `enclosure_bottom.step` | STEP AP214 | Coquille inférieure solide | Archive CAO / JLCPCB 3D |
| `enclosure_bottom.stl` | STL (binaire) | Maillage fin coquille inférieure | Trancheur 3D / JLCPCB 3D |
| `enclosure_top.step` | STEP AP214 | Coquille supérieure solide | Archive CAO / JLCPCB 3D |
| `enclosure_top.stl` | STL (binaire) | Maillage fin coquille supérieure | Trancheur 3D / JLCPCB 3D |
| `enclosure_clamp.step` | STEP AP214 | Bride de serrage câble solide | Archive CAO / JLCPCB 3D |
| `enclosure_clamp.stl` | STL (binaire) | Maillage fin bride de serrage | Trancheur 3D / JLCPCB 3D |
| `enclosure_assembly.step` | STEP AP214 | Assemblage complet fermé | Contrôle CAO et tolérances |
