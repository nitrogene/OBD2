---
name: freerouting
description: "Moteur d'auto-routage headless agnostique intégrant FreeRouting CLI et EasyEDA Pro. Gère le bootstrap portable JRE 25, l'export/import Specctra DSN/SES, l'injection de classes de nets et contraintes géométriques/CEM, et le monitoring des passes d'optimisation."
---

# Skill : FreeRouting Headless pour EasyEDA Pro

## 1. Vue d'Ensemble & Architecture

Le skill `freerouting` fournit une suite logicielle autonome et portable permettant d'effectuer le routage automatique d'un circuit imprimé conçu sous EasyEDA Pro à l'aide du moteur open-source **FreeRouting v2.4.1** exécuté en ligne de commande.

### Chaîne d'Exécution du Pipeline :
```
[EasyEDA Pro PCB]
       │
       ▼ (1) dsn_exporter.py : Exportation Specctra DSN via l'API EasyEDA Pro
[board_raw.dsn]
       │
       ▼ (2) dsn_patcher.py : Injection des contraintes depuis --config (largeurs, isolements, vias)
[board_patched.dsn]
       │
       ▼ (3) router.py : Exécution headless CLI FreeRouting (OpenJDK Temurin JRE 25)
[board_routed.ses]
       │
       ▼ (4) ses_importer.py : Réimportation de la session SES dans EasyEDA Pro
[EasyEDA Pro PCB Routé]
```

---

## 2. Conformité aux Règles du Projet (AGENTS.md)

- **Règle 0 (Modularité & Moteur Agnostique) :**
  - **Zéro composant en dur :** Aucune référence à un composant (`U4`, `R13`, etc.), aucune coordonnée physique ni net spécifique n'est codé dans les scripts.
  - **Origine des données :** Toutes les règles (classes de nets, largeurs de pistes, dégagements, diamètres de vias) proviennent exclusivement du fichier de configuration formel passé en argument (`--config <fichier.json>`).
  - **Exécution stricte via `uv` :** Tout script Python du skill doit être exécuté impérativement via `uv run python <script>.py`.
- **Règle 1 (Transparence et Sécurité) :**
  - Toute interaction avec le pont local EasyEDA (`http://localhost:49620`) doit être explicitée avant exécution (intention, motif technique, action concrète).

---

## 3. Composants du Skill

| Script | Rôle | Description |
| :--- | :--- | :--- |
| `jre_manager.py` | Gestionnaire d'environnement | Télécharge et déballe automatiquement dans `.cache/runtime/` l'environnement portable OpenJDK Temurin JRE 25 et le JAR FreeRouting v2.4.1 si non présents. |
| `dsn_exporter.py` | Exportateur DSN | Interroge l'API EasyEDA Pro (`eda.pcb_ManufactureData.getDsnFile`) pour exporter en direct le layout au format Specctra DSN. |
| `dsn_patcher.py` | Patcher de contraintes | Parse le DSN Specctra, convertit les dimensions millimétriques en unités DSN (mil), injecte les padstacks de vias personnalisés et met à jour les règles des classes de nets selon le fichier JSON. |
| `router.py` | Exécuteur headless | Pilote FreeRouting en ligne de commande, analyse la progression en temps réel (fanout, passes d'autoroutage, optimisation) et produit le fichier de session `.ses`. |
| `ses_importer.py` | Importateur SES | Injecte le fichier `.ses` dans le document PCB actif via `eda.pcb_Document.importAutoRouteSesFile`. |
| `freerouting_pipeline.py` | Orchestrateur maître | Coordonne les étapes 1 à 4 dans un pipeline unifié avec gestion des erreurs et métriques récapitulatives. |

---

## 4. Utilisation en Ligne de Commande

### Pipeline Complet Unifié (Recommandé)
```bash
# Routage complet depuis EasyEDA Pro avec réimport automatique
uv run python .agents/skills/freerouting/freerouting_pipeline.py --config board_constraints.json --passes 10

# Routage en mode incrémental (préserve les pistes déjà routées)
uv run python .agents/skills/freerouting/freerouting_pipeline.py --config board_constraints.json --incremental

# Génération du fichier SES sans réimport dans le PCB (simulation / analyse)
uv run python .agents/skills/freerouting/freerouting_pipeline.py --config board_constraints.json --no-import
```

### Options du Pipeline :
- `--config <path>` : **(Obligatoire)** Fichier JSON contenant les règles de conception et classes de nets.
- `--dsn <path>` : Fichier DSN source (optionnel ; si omis, exporté directement depuis EasyEDA Pro).
- `--passes <int>` : Nombre maximal de passes d'autoroutage (défaut : `10`).
- `--threads <int>` : Nombre de threads pour le moteur (défaut : `1` pour garantir l'absence de violations d'isolement lors de l'optimisation).
- `--strategy <str>` : Stratégie de mise à jour (`greedy`, `global`, `hybrid` ; défaut : `hybrid`).
- `--incremental` : Protège les pistes pré-existantes dans le DSN (`type protect`).
- `--no-import` : Exécute le routage et produit le `.ses` sans l'injecter dans EasyEDA Pro.
- `--save` : Sauvegarde automatiquement le document PCB après l'importation.

### Utilisation Modulaire des Scripts

#### 1. Vérification / Installation de l'environnement JRE :
```bash
uv run python .agents/skills/freerouting/jre_manager.py --check
```

#### 2. Exportation seule du DSN :
```bash
uv run python .agents/skills/freerouting/dsn_exporter.py --out .agents/skills/freerouting/.cache/board.dsn
```

#### 3. Patching seul des contraintes :
```bash
uv run python .agents/skills/freerouting/dsn_patcher.py --dsn input.dsn --config board_constraints.json --out patched.dsn
```

#### 4. Exécution seule du moteur de routage :
```bash
uv run python .agents/skills/freerouting/router.py --dsn patched.dsn --ses output.ses --passes 10 --threads 1
```

#### 5. Importation seule du fichier SES :
```bash
uv run python .agents/skills/freerouting/ses_importer.py --ses output.ses
```

---

## 5. Spécification du Fichier de Contraintes (`--config`)

Le moteur `dsn_patcher.py` attend une section `net_classes` structurée comme suit :

```json
{
  "net_classes": {
    "POWER_12V": {
      "nets": ["+12V", "+12V_FUSED", "+12V_PROT", "VBAT_OBD"],
      "track_width_mm": 0.8,
      "clearance_mm": 0.25,
      "via_drill_mm": 0.4,
      "via_diameter_mm": 0.8
    },
    "POWER_REGULATED": {
      "nets": ["+5V", "VBUS_5V", "3.3V", "3.3V_PRE"],
      "track_width_mm": 0.6,
      "clearance_mm": 0.20,
      "via_drill_mm": 0.4,
      "via_diameter_mm": 0.8
    },
    "DIFF_USB": {
      "nets": ["USB_D+", "USB_D-"],
      "track_width_mm": 0.30,
      "clearance_mm": 0.20
    },
    "DEFAULT": {
      "track_width_mm": 0.254,
      "clearance_mm": 0.20,
      "via_drill_mm": 0.3,
      "via_diameter_mm": 0.6
    }
  }
}
```

Tous les signaux présents sur le PCB qui ne sont pas explicitement listés dans une classe spécifique adoptent automatiquement les contraintes définies dans la classe `DEFAULT`.
