# Règles du projet : Scanner OBD-II ESP32

## 1. Transparence et Sécurité
- **Explication obligatoire :** Avant tout script interactif sur le pont EasyEDA (`http://localhost:49620`), expliciter l'intention, le motif technique précis (composants/coordonnées) et l'action concrète.
- **Périmètre strict :** Modifications cantonnées à `D:\Dev\ODB`. Interdiction de toucher aux répertoires externes ou au skill `easyeda-api`. Nettoyer les scripts `.js`/`.mjs` temporaires avant validation.

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
4. Mettre à jour `LEARNINGS.md` si découverte technique.
5. Exporter `ProPrj_ODB2-Scanner.epro2` via les skills easyeda-api.
6. Demander à l'utilisateur les exports graphiques haute résolution (`Schematic.png`, `PCB.png`, `3D.png`).
7. Commit et push **uniquement** après accord explicite sur le message de commit.