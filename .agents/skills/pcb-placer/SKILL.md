---
name: pcb-placer
description: >-
  Moteur d'auto-placement agnostique par contraintes géométriques, CEM et thermiques pour EasyEDA Pro.
  Prend en entrée obligatoire un fichier formel de configuration (--config floorplan.json),
  vérifie les contraintes (ancres mécaniques, découplage, boucles critiques, keepouts),
  audite les distances et injecte le placement en une passe via le pont local EasyEDA.
compatibility: Python 3.8+, Node.js 18+, uv, EasyEDA Pro desktop avec run-api-gateway
metadata:
  author: ODB2-Scanner-Dev
  version: "2.0.0"
---

# Skill : PCB Placer (Moteur d'Auto-Placement Agnostique par Contraintes)

Ce skill fournit un **moteur algorithmique pur** de calcul géométrique, de contrôle de contraintes CEM/thermiques et d'injection en une passe pour l'agencement de circuits imprimés sous **EasyEDA Pro**.

Conformément à la règle `## 0.` d'`AGENTS.md`, ce skill est **totalement agnostique** : il ne contient aucune référence en dur à des composants, empreintes ou coordonnées physiques. Toutes les données doivent lui être transmises via un fichier de configuration formel (`--config <fichier.json>`).

Il s'appuie sur le skill [easyeda-api](../easyeda-api/SKILL.md) et son pont local (port 49620).

---

## 1. Architecture des Modules

```
.agents/skills/pcb-placer/
├── SKILL.md                 # Documentation et guide d'utilisation
├── easyeda_client.py        # Client Python de communication avec EasyEDA Pro
├── placement_constraints.py # Schéma de données agnostique et parseur (load_floorplan)
├── auto_place.py            # Moteur d'auto-placement (prend obligatoirement --config)
├── apply_placement.py       # Actionneur d'injection et sauvegarde (prend --config)
└── audit_placement.py       # Auditeur géométrique des distances critiques (prend --config)
```

---

## 2. Utilisation Rapide (via `uv run`)

> [!IMPORTANT]
> Conformément aux règles du projet, tous les scripts Python doivent être exécutés via `uv run`, et l'argument `--config` est **obligatoire**.

### A. Vérifier la connexion avec EasyEDA Pro
```bash
uv run .agents/skills/pcb-placer/easyeda_client.py
```

### B. Auditer le placement actuel du PCB contre un fichier de configuration
```bash
uv run .agents/skills/pcb-placer/audit_placement.py --config floorplan.json
```
Vérifie :
* Positionnement des ancres mécaniques fixes (ex: connecteurs de bord, SoC).
* Respect des seuils de découplage HF (< 2.0 mm) et des mailles de boucle.
* Proximité des protections transitoires et diodes ESD face aux connecteurs.
* Respect strict des zones d'exclusion (Keepouts RF, etc.).

### C. Calculer et appliquer l'auto-placement en une passe
```bash
# Simulation sans injection (dry-run d'affichage du plan)
uv run .agents/skills/pcb-placer/auto_place.py --config floorplan.json

# Injection réelle dans EasyEDA Pro + contrôle DRC + sauvegarde
uv run .agents/skills/pcb-placer/auto_place.py --config floorplan.json --apply

# Injection avec audit de conformité immédiat
uv run .agents/skills/pcb-placer/auto_place.py --config floorplan.json --apply --audit
```
