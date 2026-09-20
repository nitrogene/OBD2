---
name: pcb-placer
description: >-
  Moteur d'auto-placement par contraintes géométriques, CEM et thermiques pour EasyEDA Pro.
  Permet d'extraire les composants du schéma ou PCB, de calculer les coordonnées optimales
  en respectant les contraintes strictes (ancres mécaniques, découplage < 2mm, boucle Buck compacte,
  keepout RF, protections ESD/TVS), d'auditer les distances et d'injecter le placement en une passe
  via le pont local EasyEDA.
compatibility: Python 3.8+, Node.js 18+, EasyEDA Pro desktop avec run-api-gateway
metadata:
  author: ODB2-Scanner-Dev
  version: "1.0.0"
---

# Skill : PCB Placer (Moteur d'Auto-Placement par Contraintes)

Ce skill fournit un environnement autonome de calcul géométrique, de modélisation de contraintes physiques et d'injection en une passe pour l'agencement du circuit imprimé sous **EasyEDA Pro**.

Il s'appuie sur le skill [easyeda-api](../easyeda-api/SKILL.md) et son pont local (port 49620).

---

## 1. Architecture des Modules

```
.agents/skills/pcb-placer/
├── SKILL.md                 # Documentation et guide d'utilisation
├── easyeda_client.py        # Client Python de communication avec EasyEDA Pro
├── placement_constraints.py # Définition formelle des règles, ancres et clusters
├── auto_place.py            # Solveur géométrique d'auto-placement en une passe
└── audit_placement.py       # Auditeur géométrique des distances critiques (DRC pré-injection)
```

---

## 2. Utilisation Rapide

### A. Vérifier la connexion avec EasyEDA Pro
```bash
python .agents/skills/pcb-placer/easyeda_client.py
```

### B. Auditer le placement actuel du PCB
```bash
python .agents/skills/pcb-placer/audit_placement.py
```
Vérifie :
* Découplage HF `C1`, `C2` et Bulk `C11` à **< 2.0 mm** des broches 1/2 de l'ESP32.
* Filtre Reset `C12`, `R15` à **< 2.0 mm** de la broche 3 (`EN`).
* Proximité des TVS `U8` et `D5` avec les broches du connecteur OBD `J1`.
* Absence de tout élément sous la zone d'exclusion d'antenne RF 2.4 GHz.

### C. Calculer et appliquer l'auto-placement en une passe
```bash
# Simulation sans injection (dry-run)
python .agents/skills/pcb-placer/auto_place.py --dry-run

# Injection réelle dans EasyEDA Pro
python .agents/skills/pcb-placer/auto_place.py --apply
```
