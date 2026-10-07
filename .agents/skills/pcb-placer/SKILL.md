---
name: pcb-placer
description: >-
  Moteur d'auto-placement agnostique par contraintes géométriques, CEM et thermiques pour EasyEDA Pro.
  Prend en entrée obligatoire un fichier formel de configuration (--config floorplan.json),
  estime et suggère les dimensions minimales du PCB selon les normes IPC-7351,
  vérifie les contraintes (ancres mécaniques, découplage, boucles critiques, keepouts),
  audite les distances et injecte le placement en une passe via le pont local EasyEDA.
compatibility: Python 3.8+, Node.js 18+, uv, EasyEDA Pro desktop avec run-api-gateway
metadata:
  author: OBD2-Scanner-Dev
  version: "2.1.0"
---

# Skill : PCB Placer (Moteur d'Auto-Placement & Dimensionnement Agnostique)

Ce skill fournit un **moteur algorithmique pur** de calcul géométrique, d'estimation dimensionnelle, de contrôle de contraintes CEM/thermiques et d'injection en une passe pour l'agencement de circuits imprimés sous **EasyEDA Pro**.

Conformément à la règle `## 0.` d'`AGENTS.md`, ce skill est **totalement agnostique** : il ne contient aucune référence en dur à des composants, empreintes ou coordonnées physiques spécifiques. Toutes les données doivent lui être transmises via un fichier de configuration formel (`--config <fichier.json>`) ou une nomenclature (`--bom <BOM.md>`).

Il s'appuie sur le skill [easyeda-api](../easyeda-api/SKILL.md) et son pont local (port 49620).

---

## 1. Architecture des Modules

```
.agents/skills/pcb-placer/
├── SKILL.md                 # Documentation et guide d'utilisation
├── easyeda_client.py        # Client Python de communication avec EasyEDA Pro
├── validate.py              # Contrôleur d'intégrité et de cohérence des données d'entrée
├── score.py                 # Évaluateur objectif multicritère (HPWL, collisions, CEM, thermie)
├── simulated_annealing.py   # Moteur de recuit simulé multi-départs & légalisation géométrique
├── apply_placement.py       # Actionneur d'injection par lot & certification DRC
├── render_svg.py            # Générateur de visualisations vectorielles SVG
├── size_estimator.py        # Moteur d'estimation et suggestion dimensionnelle (IPC-7351)
├── auto_place.py            # Moteur d'auto-placement et d'injection en une passe
└── audit_placement.py       # Auditeur géométrique des distances critiques CEM et du contour
```

---

## 2. Utilisation Rapide (via `uv run`)

> [!IMPORTANT]
> Conformément aux règles du projet, tous les scripts Python doivent être exécutés via `uv run`, et l'argument `--config` (ou `--bom`) est **obligatoire**.

### A. Estimer et Suggérer les Dimensions Idéales du PCB (`size_estimator.py`)
Avant de figer un contour ou pour évaluer la faisabilité de routage d'une carte :
```bash
# Estimation depuis le floorplan et comparaison avec le contour actuel
uv run .agents/skills/pcb-placer/size_estimator.py --config floorplan.json

# Estimation en spécifiant un empilement 4 couches
uv run .agents/skills/pcb-placer/size_estimator.py --config floorplan.json --layers 4

# Estimation directe depuis la nomenclature BOM
uv run .agents/skills/pcb-placer/size_estimator.py --bom BOM.md --layers 2

# Via auto_place.py
uv run .agents/skills/pcb-placer/auto_place.py --config floorplan.json --suggest-size
```

#### Modèle Mathématique de Dimensionnement
Le calcul s'appuie sur les surfaces de sécurité d'implantation (*Courtyards* normalisés **IPC-7351B**) :
$$S_{\text{PCB}} = \frac{\sum S_{\text{composants}} + S_{\text{Keepouts}}}{\eta_{\text{routage}}}$$

- **Taux d'efficacité surfacique ($\eta_{\text{routage}}$) :**
  - **2 couches :** $\eta \approx 30\,\%\text{ à }35\,\%$ (*Packing factor* 2.8× à 3.3×) pour préserver un plan de masse GND continu.
  - **4 couches :** $\eta \approx 50\,\%\text{ à }60\,\%$ (*Packing factor* 1.7× à 2.0×) grâce aux plans internes d'alimentation/masse.
- **Résultats fournis :**
  1. *Gabarit Minimal :* Routage très compact et dense.
  2. *Gabarit Recommandé (Nominal) :* Équilibre optimal entre CEM, continuité de masse et fabrication JLCPCB standard.
  3. *Gabarit Confortable :* Disposition aérée avec découplage thermique maximal.

---

### B. Vérifier la Connexion avec EasyEDA Pro (`easyeda_client.py`)
```bash
uv run .agents/skills/pcb-placer/easyeda_client.py
```
Affiche le statut de connexion au pont, le projet actif, le nom de la carte PCB, le nombre de composants, de nets, de primitives de pistes et le contour mécanique (Layer 11).

---

### C. Auditer le Placement Physique & les Règles CEM (`audit_placement.py`)
```bash
uv run .agents/skills/pcb-placer/audit_placement.py --config floorplan.json
```
Vérifie rigoureusement 24 règles de conception physique :
* **Contour mécanique :** Présence et conformité dimensionnelle du gabarit sur le Layer 11 (`BOARD_OUTLINE`).
* **Marge de bord :** Respect de l'*Edge Clearance* (>= 1.0 mm) pour tous les composants non-ancres.
* **Ancres fixes :** Position exacte des connecteurs (`J1`, `J2`) et du SoC (`U1`).
* **Proximité CEM :** Découplage HF (< 2.0 mm), filtres Reset (< 2.0 mm), protections ESD/TVS (< 5.0 mm).
* **Zones interdites :** Absence totale de composants dans le Keepout RF d'antenne méandre 2.4 GHz.

---

### D. Appliquer l'Auto-Placement en une Passe (`auto_place.py`)
```bash
# 1. Simulation sans injection (dry-run d'affichage des coordonnées et de la grille)
uv run .agents/skills/pcb-placer/auto_place.py --config floorplan.json

# 2. Injection réelle dans EasyEDA Pro + création automatique du contour si absent + DRC + sauvegarde
uv run .agents/skills/pcb-placer/auto_place.py --config floorplan.json --apply

# 3. Injection complète suivie de l'audit de certification immédiat
uv run .agents/skills/pcb-placer/auto_place.py --config floorplan.json --apply --audit

# 4. Synchronisation automatique depuis le schéma (importChanges) avant injection et audit
uv run .agents/skills/pcb-placer/auto_place.py --config floorplan.json --sync --apply --audit
```

---

### E. Résoudre le Placement Global par Recuit Simulé (`simulated_annealing.py`)
Génère une solution optimisée sans collision via un recuit simulé multi-départs parallélisé suivi d'une passe de légalisation géométrique déterministe :
```bash
# Lancement standard (16 graines, départ baseline inclus, export candidate JSON et SVG)
uv run .agents/skills/pcb-placer/simulated_annealing.py \
  --manifest circuit_manifest.json \
  --constraints board_constraints.json \
  --output placement_candidate.json \
  --svg images/placement_optimised.svg

# Résolution haute performance (multi-graines étendu)
uv run .agents/skills/pcb-placer/simulated_annealing.py \
  --manifest circuit_manifest.json \
  --constraints board_constraints.json \
  --seeds 32 \
  --steps 30000 \
  --output placement_candidate.json
```

---

### F. Injecter le Placement & Certifier le DRC (`apply_placement.py`)
Applique en une seule transaction par lot les coordonnées d'un fichier de placement dans EasyEDA Pro et lance la certification DRC :
```bash
# Simulation sans altération du PCB
uv run .agents/skills/pcb-placer/apply_placement.py --placement placement_candidate.json --dry-run

# Injection par lot, contrôle DRC natif et sauvegarde automatique
uv run .agents/skills/pcb-placer/apply_placement.py --placement placement_candidate.json
```
