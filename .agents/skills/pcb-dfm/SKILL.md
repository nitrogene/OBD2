---
name: pcb-dfm
description: "Moteur d'audit automatisé de fabricabilité DFM (Design for Manufacturing) et d'assemblage SMT pour EasyEDA Pro et JLCPCB. Vérifie les ponts de vernis épargne, les distances via-to-pad (solder wicking), la sérigraphie, les dégagements de cuivre, les perçages, l'espacement CMS et la cohérence BOM/CPL."
---

# Skill : PCB & SMT DFM Auditor pour EasyEDA Pro & JLCPCB

## 1. Vue d'Ensemble & Architecture

Le skill `pcb-dfm` est un moteur d'ingénierie et d'assurance qualité industrielle conçu pour automatiser les contrôles de fabricabilité (**DFM**) et d'assemblage automatisé (**SMT**) selon les capacités d'usine standard de **JLCPCB** (PCB 4 couches JLC2313, 1.6 mm, cuivre 1 oz).

Dans une chaîne de conception assistée par IA, le DRC natif d'EasyEDA Pro valide uniquement les contraintes électriques de connectivité (absence de court-circuit, isolation entre filets distincts). Cependant, il ne détecte pas les défauts physiques d'usine qui provoquent des rejets de fabrication ou des défauts d'assemblage critique :
- **Ponts de vernis épargne trop fins (*Solder Mask Bridge* < 0.10 mm) :** Décollement du vernis créant un *gang mask* et favorisant les ponts de soudure entre broches à pas fin (ex: USB-C, ESP32-S3, circuits intégrés).
- **Vias collés ou sur pastilles CMS (*Via to Pad* < 0.15 mm) :** Aspiration de la pâte à braser par capillarité dans le via lors de la refusion (*solder wicking*), créant des soudures sèches ou le redressement des composants (*tombstoning*).
- **Chevauchement sérigraphie / vernis (*Silkscreen to Pad / Hole*) :** Rognage automatique du texte par le fabricant (*auto-clipping*) ou encre isolante déposée sur le cuivre.
- **Dégagements inter-composants CMS :** Espace insuffisant pour les buses de placement automatique Pick & Place.
- **Cohérence BOM / CPL :** Incohérences entre nomenclature et implantation physique.

### Chaîne d'Exécution du Pipeline DFM :
```
[EasyEDA Pro PCB Actif]
       │
       ▼ (1) drc_bridge.py : Extraction instantanée des primitives (mils -> mm)
[Primitives Géométriques Normalisées]
       │
       ├─► (2) pcb_dfm_auditor.py : Ponts vernis, vias-to-pad, sérigraphie, bord de carte, perçages
       │
       └─► (3) smt_dfm_auditor.py : Espacement composants, marges convoyeur, repères optiques, BOM
               │
               ▼ (4) report_generator.py
[Rapport Markdown (documents/pcb/dfm_report.md) & JSON (documents/pcb/dfm_report.json)]
```

---

## 2. Conformité aux Règles du Projet (AGENTS.md)

- **Règle 1 (Modularité & Moteur Agnostique) :**
  - **Zéro composant en dur :** Aucune référence à un composant (`U4`, `R13`, `C8`), coordonnée physique ou net n'est codé dans les scripts Python.
  - **Injection par configuration :** Tous les seuils proviennent du fichier de règles déclaratif (`config/rules_jlcpcb.json`) et de la BOM injectée (`--bom`).
  - **Exécution stricte via `uv` :** Tout script Python du skill est exécuté impérativement via `uv run` (l'appel direct à `python` est proscrit).
- **Règle 2 (Sécurité & Contrôle du Pont EasyEDA) :**
  - Le pont local écoute sur le port 49620 en lecture géométrique pure.
- **Règle 6 (Typographie & Formules) :**
  - Zéro balisage LaTeX pour les composants ou valeurs (pas de `$10\,\text{k}\Omega$`, texte brut Markdown exclusivement : `10 kΩ`, `0.10 mm`, `3.3V`).

---

## 3. Composants du Skill

| Script | Rôle | Description |
| :--- | :--- | :--- |
| `config/rules_jlcpcb.json` | Spécification d'usine | Déclare les seuils dimensionnels JLCPCB standard (JLC2313, 4 couches, vernis vert). |
| `scripts/drc_bridge.py` | Connecteur EasyEDA | Extrait les primitives physiques (pads, vias, pistes, sérigraphie, contour) et convertit les mils en mm. |
| `scripts/pcb_dfm_auditor.py` | Moteur PCB DFM | Analyse géométrique du PCB nu (soldermask bridge, via-to-pad wicking, silkscreen clearances, perçages). |
| `scripts/smt_dfm_auditor.py` | Moteur SMT DFM | Analyse d'assemblage (espacement boîtiers CMS, marges convoyeur, fiducials, BOM vs CPL). |
| `scripts/report_generator.py` | Générateur de synthèse | Produit le bilan exécutif structuré en Markdown et JSON avec verdicts (🔴 Danger, 🟠 Warning, 🟢 Info). |
| `scripts/dfm_pipeline.py` | CLI & Orchestrateur | Point d'entrée principal pour automatisation CI/CD et boucle fermée dans `pcb-synthesizer`. |
| `scripts/export_fabrication.py` | Exportateur Production | Exporte automatiquement l'archive Gerber (ZIP), les centroïdes Pick & Place (CPL CSV) et la nomenclature (BOM CSV). |

---

## 4. Guide d'Utilisation CLI

Toutes les commandes doivent être exécutées via `uv run` depuis la racine du dépôt :

### Exécution Standard Complète (PCB + SMT + Rapports) :
```bash
uv run python .agents/skills/pcb-dfm/scripts/dfm_pipeline.py
```

### Audit PCB DFM Seul :
```bash
uv run python .agents/skills/pcb-dfm/scripts/dfm_pipeline.py --pcb-only
```

### Audit SMT Seul avec Spécification de la BOM :
```bash
uv run python .agents/skills/pcb-dfm/scripts/dfm_pipeline.py --smt-only --bom documents/schema/bom.json
```

### Mode Strict (Échec si Avertissements WARNING) :
```bash
uv run python .agents/skills/pcb-dfm/scripts/dfm_pipeline.py --strict
```

### Exportation Complète du Dossier de Fabrication (Gerber + CPL + BOM) :
```bash
uv run python .agents/skills/pcb-dfm/scripts/export_fabrication.py --output-dir documents/production --prefix OBD2
```

### Arguments de Ligne de Commande :
- `--config <chemin>` : Fichier JSON des règles d'usinage (défaut : `.agents/skills/pcb-dfm/config/rules_jlcpcb.json`).
- `--bom <chemin>` : Fichier de nomenclature (défaut : `documents/schema/bom.json`).
- `--output-json <chemin>` : Destination du rapport JSON (défaut : `documents/pcb/dfm_report.json`).
- `--output-md <chemin>` : Destination du rapport Markdown (défaut : `documents/pcb/dfm_report.md`).
- `--port <int>` : Port HTTP du pont local EasyEDA (défaut : `49620`).
- `--pcb-only` : Ignore l'audit SMT.
- `--smt-only` : Ignore l'audit PCB.
- `--strict` : Retourne un code d'erreur 1 si des avertissements non bloquants subsistent.

---

## 5. Synthèse des Règles Contrôlées

| Règle DFM / SMT | Seuil JLCPCB Standard | Seuil Danger | Impact Technique |
| :--- | :---: | :---: | :--- |
| **Pont de vernis épargne** | $\ge 0.10\,\text{mm}$ | $< 0.08\,\text{mm}$ | Décollement de vernis, pont de brasure à pas fin (*gang mask*). |
| **Proximité Via-to-Pad** | $\ge 0.15\,\text{mm}$ | $< 0.05\,\text{mm}$ | Siphonnage d'étain dans le perçage (*wicking*), soudure sèche. |
| **Sérigraphie sur pastille** | $\ge 0.15\,\text{mm}$ | Chevauchement | Encre isolante sur cuivre, rognage automatique (*clipping*). |
| **Épaisseur trait sérigraphie**| $\ge 0.15\,\text{mm}$ | $< 0.12\,\text{mm}$ | Texte illisible, bavure à l'impression. |
| **Cuivre au bord de carte** | $\ge 0.30\,\text{mm}$ | $< 0.20\,\text{mm}$ | Sectionnement de piste / via lors du dépyranage ou fraisage. |
| **Bague de cuivre (Annular Ring)**| $\ge 0.13\,\text{mm}$ | $< 0.10\,\text{mm}$ | Rupture électrique en cas de désalignement de perçage. |
| **Espacement boîtiers CMS** | $\ge 0.50\,\text{mm}$ | $< 0.25\,\text{mm}$ | Collision buse Pick & Place, interférence de refusion. |
| **Bord de convoyeur SMT** | $\ge 3.0\,\text{mm}$ | $< 1.5\,\text{mm}$ | Nécessite des bandes de rive d'outillage (*tooling rails*). |
| **Repères fiduciaires** | 3 optiques | 0 | Calage optique automatique de la machine d'insertion. |
