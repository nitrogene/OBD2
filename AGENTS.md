# Règles du projet : Scanner OBD-II ESP32

## 0. Modularité et Découplage des Skills & Outils
- **Interdiction du hardcoding de composants :** Les skills sous `.agents/skills/` et les scripts réutilisables ne doivent comporter **aucune référence en dur** à des composants spécifiques du projet (ex. `U4`, `R13`, `C14`, etc.), ni coordonnées physiques ou valeurs figées dans leur code source Python.
- **Principe du Moteur Agnostique :** Un skill est un moteur algorithmique pur et réutilisable (calculateur, placeur, solveur, auditeur). Il manipule des abstractions (règles de proximité CEM, découplage, modèles de boucle, critères DRC) et non les instances singulières d'un circuit donné.
- **Provenance des Données (Inputs) :** Les données d'entrée doivent être systématiquement injectées à l'exécution et provenir exclusivement de trois sources :
  1. *La documentation ou les fichiers de configuration du projet :* Fichiers dédiés versionnés dans le projet (ex. `floorplan.json`, `constraints.yaml`, `BOM.md`, ou extraction dynamique via l'API EasyEDA).
  2. *L'utilisateur :* Arguments passés en ligne de commande (`--config`, `--params`), options explicites ou prompts.
  3. *L'agent :* Synthèse dynamique générée par l'agent depuis la documentation et le schéma avant transmission sous forme de payload au skill.
- **Exécution Python obligatoire via `uv` :** Tout lancement de script ou de commande Python doit être impérativement exécuté via `uv` (ex. `uv run <script>.py` ou `uv run python -m ...`). L'appel direct à `python` sans `uv` est strictement proscrit.

## 1. Transparence et Sécurité
- **Explication obligatoire :** Avant tout script interactif sur le pont EasyEDA (`http://localhost:49620`), expliciter l'intention, le motif technique précis (composants/coordonnées) et l'action concrète.
- **Périmètre strict :** Modifications cantonnées au répertoire courant. Interdiction de toucher aux répertoires externes ou au skill `easyeda-api`. Nettoyer les scripts `.js`/`.mjs` temporaires avant validation.

## 2. Contraintes Techniques & API
- **Nets explicites :** Interdiction absolue des identifiants anonymes type `$1N...`.
- **Ajout de composants :** Ne jamais tenter d'instancier un composant par script en aveugle. Demander systématiquement à l'utilisateur de l'ajouter dans EasyEDA Pro en lui fournissant toutes les informations pertinentes (désignateur, valeur exacte, référence fabricant/LCSC et empreinte/package).
- **Pièges d'API :** Respecter rigoureusement les signatures de création (`pcb_PrimitiveVia` : perçage avant diamètre ; `pcb_PrimitiveLine` : coordonnées avant largeur). Consulter `./LEARNINGS.md`.
- **Cache WebGL :** Fermer et réouvrir le document PCB en cas de persistance visuelle des textes de pistes.

## 3. Méthodologie Séquentielle de Conception
1. **Schéma :** Complet, validé (ERC = 0), fils physiques obligatoires sur tous les `NetFlag` / `NetPort`.
2. **Mécanique :** Enveloppe, fixation M2 et connecteurs de bord (J1, J2) fixés avant routage.
3. **Floorplanning :** Blocs logiques, découplage à < 2 mm, espace RF dégagé (Keepout multicouche).
4. **Routage :** Paires différentielles USB/CAN -> Signaux critiques -> Rails d'alimentation.
5. **Plans de masse :** Remplissage (`rebuildCopperRegion`), vias de couture et micro-zones `NO_POURS`.
6. **Contrôles :** DRC PCB = 0, ERC Schéma = 0.

## 4. Étapes Post-Validation (Bloquantes)
1. Sauvegarder (`eda.pcb_Document.save()`).
2. Nettoyer les fichiers `.js` / `.mjs` temporaires.
3. Vérifier DRC = 0 et ERC = 0.
4. Valider la synchronisation de `circuit_semantics.json` face à `BOM.md` (`uv run python .agents/skills/stingy-schematics/scripts/sync_semantics.py check --bom BOM.md --semantics circuit_semantics.json`).
5. Mettre à jour `LEARNINGS.md` si découverte technique. Si la découverte constitue un calcul, un audit ou un automatisme réutilisable, proposer ou acter sa transformation en Skill autonome sous `.agents/skills/<nom>/`.
6. Exporter `ProPrj_OBD2-Scanner.epro2` via les skills easyeda-api.
7. Demander à l'utilisateur les exports graphiques haute résolution (`Schematic.png`, `PCB.png`, `3D.png`).
8. Commit et push **uniquement** après accord explicite sur le message de commit.

## 5. Dépouillement des Revues Techniques (`review/reviewXXX.md`)
- **Détection active :** Scanner le répertoire `review/` à la recherche de fichiers de revue `reviewXXX.md` (ou `review*.md`) non encore dépouillés :
  - Les revues doivent respecter le formalisme défini dans [`review/guidelines.md`](review/guidelines.md) (nom de l'agent/reviewer, date, version auditée, classification par ordre de criticité : Bloquant / Important / Mineur).
  1. **Analyse & Synthèse :** L'agent doit analyser le contenu du fichier de revue, trier les remarques par ordre de criticité (Bloquant / Important / Mineur) et identifier les impacts concrets sur le projet.
  2. **Arbitrage interactif :** Présenter une synthèse à l'utilisateur et échanger avec lui pour valider, amender ou écarter chaque point (faisabilité, encombrement, catalogue LCSC, choix d'architecture).
  3. **Intégration au TODO :** Après accord explicite de l'utilisateur, convertir les points retenus en cases à cocher actionnables (`- [ ] ...`) dans la section appropriée de la checklist de `TODO.md`.
  4. **Suppression du fichier traité :** Supprimer définitivement le fichier `reviewXXX.md` une fois l'intégration dans `TODO.md` actée afin de laisser le sas propre pour les revues suivantes.
- **Regard critique & vérification obligatoire :** Une revue ne doit jamais être prise pour argent comptant. L'agent doit impérativement confronter les remarques du reviewer à la réalité matérielle et documentaire du projet (schéma physique, fichiers sources, datasheets constructeurs).
  - *États obsolètes :* La revue peut se baser sur un commit antérieur, un document non synchronisé ou une image non à jour (composants déjà implantés, pistes déjà routées, erratum déjà corrigés).
  - *Collisions & doublons :* Vérifier systématiquement si une remarque entre en collision ou redéfinit des choix déjà arbitrés ou en cours de traitement dans `TODO.md`.
  - *Erreurs de référence :* Détecter les confusions de composants ou de variantes matérielles (ex. brochage et périphériques spécifiques à l'ESP32-S3 vs ESP32 classique).