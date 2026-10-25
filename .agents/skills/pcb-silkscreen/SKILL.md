---
name: pcb-silkscreen
description: "Moteur déclaratif et agnostique de génération et d'injection de sérigraphie additionnelle (marquage fonctionnel, repérage des broches, consignes de cavaliers, cartouche) pour EasyEDA Pro."
---

# Skill : PCB Silkscreen pour EasyEDA Pro

## 1. Vue d'Ensemble & Architecture

Le skill `pcb-silkscreen` est un moteur algorithmique d'automatisation de la sérigraphie fonctionnelle et documentaire pour EasyEDA Pro.
Il complète le placement des désignateurs natifs (`R1`, `C1`, `U1`...) en positionnant de manière paramétrique et répétable les textes explicatifs sur les couches **Top Silkscreen** (`TopSilkLayer`, couche 3) et **Bottom Silkscreen** (`BottomSilkLayer`, couche 4).

### Entrées et Flux de Données :
```text
[documents/pcb/silkscreen.json] ──┐
[documents/pcb/silkscreen.schema.json] ──┼──► apply_silkscreen.py ──► EasyEDA Pro API (http://localhost:49620)
[EasyEDA Pro PCB (Pads & BBox)] ──┘             │
                                                ▼
                                    .cache/silkscreen_state.json (Idempotence)
```

---

## 2. Conformité aux Règles du Projet (AGENTS.md)

- **Règle 1 (Agnosticisme Pur & Zéro Composant en Dur) :**
  - Le code Python sous `.agents/skills/pcb-silkscreen/` ne contient aucun désignateur (`J1`, `H1`), coordonnée XY, ni libellé en dur.
  - L'intégralité du contenu et des cibles provient obligatoirement du fichier déclaratif `--config documents/pcb/silkscreen.json`.
  - Exécution exclusive via `uv run` (`uv run python .agents/skills/pcb-silkscreen/apply_silkscreen.py`).
- **Règle 2 (Sécurité & Idempotence) :**
  - **Idempotence garantie :** Le moteur purge au préalable toutes les primitives créées lors des exécutions antérieures via son registre d'état (`.cache/silkscreen_state.json`), évitant tout texte fantôme ou superposition lors des modifications de `silkscreen.json`.
  - **Non-destructif :** Les désignateurs natifs de composants ne sont jamais altérés.
- **Règle 6 (Typographie) :**
  - Aucun formatage LaTeX dans les libellés de composants ou les textes de sérigraphie.

---

## 3. Types d'Annotations Supportés

1. **`pin_labels` (Repérage de broches) :**
   - Ancrage automatique en regard de chaque pastille (`Pad`) du composant cible (`J1`, `H1`, etc.).
   - Prise en compte de l'orientation et de la rotation du composant.
2. **`component_legends` (Légendes de composants) :**
   - Centrage automatique relatif au courtyard du composant (`above`, `below`, `left`, `right`).
   - Idéal pour les consignes de cavaliers (`JP1`, `JP2`) ou statuts de LEDs (`LED1`).
3. **`title_blocks` (Cartouches et blocs documentaires) :**
   - Ancrage relatif aux coins du PCB (`bottom_right`, `top_left`, etc.) calculé dynamiquement depuis le contour de carte (`BoardOutline`).
