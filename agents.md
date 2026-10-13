# Règles du projet : Scanner OBD-II ESP32

## 1. Modularité & Moteurs Agnostiques
- **Zéro composant en dur :** Les skills sous `.agents/skills/` sont des moteurs algorithmiques purs. Aucune référence à un composant (`U4`, `R13`), coordonnée ou valeur figée dans leur code Python. Les données sont obligatoirement injectées à l'exécution via la configuration (`documents/pcb/constraints.json`, `documents/schema/bom.json`) ou des arguments CLI (`--config`).
- **Exécution Python exclusive via `uv` :** Tout script ou commande Python doit impérativement être lancé via `uv run` (ex. `uv run <script>.py`). L'appel direct à `python` est proscrit.

## 2. Sécurité & Contrôle du Pont EasyEDA
- **Transparence :** Expliciter l'intention et les paramètres techniques avant tout appel au pont local (`http://localhost:49620`). Modifications cantonnées au projet local (nettoyer les scripts `.js`/`.mjs` temporaires).
- **Composants physiques :** Ne jamais instancier de composant par script en aveugle. Demander à l'utilisateur de l'ajouter dans EasyEDA Pro en fournissant désignateur, valeur, boîtier et code LCSC.
- **Règles d'API :** Nets explicites obligatoires (aucun `$1N...`). Respecter l'ordre des arguments d'API (vias : perçage avant diamètre ; lignes : coordonnées avant largeur).
- **Limites d'autonomie :** Max 3 essais consécutifs pour corriger une violation DRC/ERC récurrente. En cas d'impasse géométrique (conflit répétitif), cesser les modifications à l'aveugle, sauvegarder l'état propre et rendre la main à l'utilisateur.

## 3. Conception & Séquencement Documentaire
- **Séquence matérielle :** Schéma (ERC = 0, fils physiques sur NetPorts) -> Mécanique (ancres, M2, connecteurs J1/J2) -> Floorplanning (découplage < 2 mm, keepout RF) -> Routage différentiel & puissance -> Plans de masse & vias de couture -> Contrôles (DRC = 0, ERC = 0).
- **Zéro anticipation documentaire :** La mise à jour des documents (`bom.json`, `semantics.json`, `hardware.md`, `constraints.json`, `manifest.json`) et le cochage dans `todo.md` (`- [x]`) se font **strictement après** validation de l'action dans EasyEDA Pro par l'utilisateur.
- **Désignateurs dynamiques :** Ne jamais figer de désignateur à l'avance dans `todo.md` ou lors d'une revue. Décrire les composants par leur fonction et assigner le prochain numéro libre dans la BOM au moment de l'implémentation.

## 4. Sas de Revue Technique (`review/`)
- Scanner `review/review*.md`, trier par criticité (Bloquant / Important / Mineur), arbitrer avec l'utilisateur, convertir les points validés dans `todo.md` et supprimer le fichier traité.
- Regard critique obligatoire : confronter chaque remarque au schéma réel et aux datasheets constructeurs (détecter obsolescences, doublons et fausses pistes).

## 5. Étapes Post-Validation & Clôture (Bloquantes)
1. Sauvegarder dans EasyEDA (`eda.pcb_Document.save()`) et nettoyer les fichiers temporaires.
2. Certifier DRC = 0 et ERC = 0.
3. Valider la synchronisation sémantique (`uv run python .agents/skills/stingy-schematics/scripts/sync_semantics.py check`).
4. Régénérer `documents/pcb/placement.svg` à chaque modification ou recalcul de placement via `pcb-placer`.
5. Exporter `documents/easyeda/OBD2.epro2` et demander les exports PNG haute résolution à l'utilisateur.
6. Commit et push **uniquement** après accord textuel explicite de l'utilisateur sur le message de commit.

## 6. Typographie & Formules
- **Pas de LaTeX pour les composants ou valeurs :** Proscription formelle de `$J_1$`, `$R_{16}$`, `$10\,\text{k}\Omega$`. Utiliser impérativement le texte brut avec code Markdown : `J1`, `R16`, `10 kΩ`, `3.3V`.
- Le balisage `$ ... $` est exclusivement réservé aux équations mathématiques complexes (ex. calcul de boucle ou de filtre).