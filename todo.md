# Feuille de Route & Checklist Active (TODO)

Ce document constitue le plan d'action opérationnel du projet **Scanner OBD-II ESP32**.
Il recense les jalons majeurs validés et détaille les tâches restantes à accomplir.

---

## 🏁 Jalons Validés

- ✅ **Phase 1 : Schéma Électrique & Nomenclature (BOM)** : 84 composants validés, ERC = 0 strict, nomenclature optimisée en Basic Parts JLCPCB ([`documents/schema/bom.json`](documents/schema/bom.json), [`documents/schema/semantics.json`](documents/schema/semantics.json)).
- ✅ **Phase 2 : Auto-Placement PCB & Sérigraphie (`pcb-placer`)** : 84 composants et labels orientés sans collision, dégagements pastilles et courtyards IPC-7351 validés, rendu unique [`documents/pcb/placement.svg`](documents/pcb/placement.svg).
- ✅ **Phase 3.1 : Auto-Routage Headless (`freerouting`)** : 100% des connexions de signaux et rails d'alimentation routées (219/219), impédance différentielle USB/CAN respectée, isolation RF 2.4 GHz garantie.

---

## 1. Priorité Immédiate : Finalisation PCB & Plans de Masse (Clôture Phase 3)

- [ ] **Résolution des 13 Clearance Errors résiduelles (Point d'arrêt / Reprise) :**
  - Remplacer les 3 segments rectilignes de pontage d'îlots par les chemins d'évitement calculés par l'algorithme A* du skill [`.agents/skills/pcb-stitcher/`](.agents/skills/pcb-stitcher/SKILL.md) (`island_bridger.py`) pour éliminer les violations de dégagement face aux pistes actives.
- [ ] **Vias de couture (stitching) de renfort :**
  - Ajouter un maillage régulier de vias de masse le long du contour de carte après élimination des erreurs DRC.
- [ ] **Sérigraphie PCB des Cavaliers [review004 M1 / review005 I1] :**
  - Ajouter les sérigraphies d'aide à l'utilisateur sur la couche Top Silk :
    - `JP1` : *« OPEN = CAR / SHUNT = BENCH »*
    - `JP2` : *« SHUNT = CAR / OPEN = BENCH HI-Z »*
- [ ] **Contrôle DRC physique strict post-routage :**
  - Exécuter le DRC sous EasyEDA Pro avec plans de masse coulés et certifier **DRC = 0 erreur, 0 avertissement**.
- [ ] **Inspection 3D finale :**
  - Contrôle visuel 3D de l'assemblage complet (`documents/pcb/3d.png`, `documents/pcb/2d-top.png`, `documents/pcb/2d-bottom.png`), du contour de carte et des dégagements mécaniques des connecteurs `J1` et `J2`.
- [ ] **Étapes post-validation et clôture bloquante (Règle 5 d'[`agents.md`](agents.md)) :**
  - Sauvegarde définitive du PCB (`eda.pcb_Document.save()`).
  - Contrôle ERC Schéma = 0 sous EasyEDA Pro.
  - Validation de synchronisation sémantique (`uv run python .agents/skills/stingy-schematics/scripts/sync_semantics.py check`).
  - Capitalisation technique dans [`learnings.md`](learnings.md).
  - Export de l'archive projet [`documents/easyeda/OBD2.epro2`](documents/easyeda/OBD2.epro2).
  - Demande des exports graphiques haute résolution à l'utilisateur.
  - Accord explicite sur le message de commit avant tout commit/push Git.

---

## 2. Dossier de Fabrication (JLCPCB)

- [ ] **Génération des fichiers Gerber & Drill :** Standard 2 couches JLCPCB.
- [ ] **Export BOM SMT :** Nomenclature consolidée au format JLCPCB SMT ([`documents/schema/bom.json`](documents/schema/bom.json)).
- [ ] **Export Pick & Place (CPL) :** Fichier de centroïdes pour l'assemblage CMS automatisé.

---

## 3. Conception du Boîtier & Intégration Mécanique

- [ ] **Maintien mécanique du faisceau OBD-II :** Concevoir le serre-câble / passe-fil pour décharger mécaniquement les contraintes de traction sur le bornier à vis `J1`.
- [ ] **Accès connectique & interfaces :** Dégager les ouvertures pour le connecteur USB-C `J2`, le bouton Flash `SW1` et le guide de lumière de `LED1`.
- [ ] **Fixation carte :** Intégrer les 4 bossages de fixation M2 alignés avec les perçages du PCB.
- [ ] **Modélisation 3D (STEP / STL) :** Export et validation des tolérances d'assemblage pour impression 3D / usinage.

---

## 4. Transition Firmware & Dépôt Logiciel Dédié

Le développement du firmware est déporté dans un dépôt Git dédié (`obd2-esp32-firmware`).
L'ensemble des spécifications et le guide d'amorçage sont consignés dans [`documents/software.md`](documents/software.md).

- [x] **Rédaction du cahier des charges & document d'amorçage ([`documents/software.md`](documents/software.md)) :**
  - Mappage exhaustif des GPIOs et adaptation 3.3V.
  - Spécifications métrologiques ADC1 et formule de conversion $V_{BAT}$.
  - Spécifications protocolaires TWAI/CAN (ISO 15765-4 / ISO-TP) et K-Line (ISO 9141-2 / Fast-Init / GM-Daewoo Kalos).
  - Spécifications du simulateur d'ECU et console CLI de test sur banc.
  - Architecture FreeRTOS recommandée et arborescence cible du futur projet.
- [ ] **Initialisation du dépôt dédié `obd2-esp32-firmware` :**
  - Créer le dépôt Git distant.
  - Initialiser le projet avec [`documents/software.md`](documents/software.md) comme socle contractuel.
  - Configurer `sdkconfig.defaults` (TWAI, USB CDC, BLE 5.0, Flash 16 Mo, PSRAM 2 Mo).
