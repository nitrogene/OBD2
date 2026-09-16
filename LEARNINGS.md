# Capitalisation Technique & Découvertes API EasyEDA Pro

Ce document consigne de manière datée les comportements, astuces, contournements et spécificités de l'API EasyEDA Pro non documentés (ou insuffisamment détaillés) dans le skill officiel `easyeda-api`.

---

## 1. Schématique & Saisie de Schéma

* **[2026-09-05] Schématique : Raccordement impératif des drapeaux de réseau (`NetFlag`) par des fils (`Wire`)**
  * **Comportement découvert :** Si un drapeau de réseau (`netflag`, ex. `power-5v` ou `ground-gnd`) est positionné aux coordonnées exactes d'une broche de composant sans segment de fil physique (`eda.sch_PrimitiveWire`), le compilateur de schéma d'EasyEDA considère la broche comme **flottante** (`[Warn] : Found some components Pins floating, suggest placing No Connect Flag...`)[cite: 3].
  * **Impact critique :** Lors de l'import Schéma → PCB (`Design > Update PCB`), la pastille PCB associée ne reçoit aucun net ou reçoit un net temporaire découplé (ex. `$1N14`), risquant de laisser des diviseurs de tension de contre-réaction (comme `VSENSE` sur un Buck) complètement ouverts[cite: 3].
  * **Règle à appliquer :** Toujours insérer au minimum un segment de fil (`eda.sch_PrimitiveWire.create([x1, y1, x2, y2], net)`) reliant explicitement la broche du composant au point de connexion du drapeau[cite: 3].

* **[2026-09-06] Schématique : Fusion automatique des fils (`Wire Merging`) et assignation de net**
  * **Fusion automatique de polylignes :** Dans le schéma EasyEDA Pro, dès que deux segments de fil (`sch_PrimitiveWire`) se touchent ou s'intersectent sur la grille, le compilateur les fusionne automatiquement en une seule entité polyline. Il faut veiller à ne pas faire transiter un fil d'alimentation brute (`+12V_FUSED`) à proximité immédiate d'un fil de sortie protégée (`+12V_PROT`) sous peine de court-circuiter le composant série (transistor de protection `Q1`)[cite: 3].
  * **API de modification de fil :** `await eda.sch_PrimitiveWire.modify(wireId, { net: 'NET_NAME' })` permet d'attribuer directement le nom de net électrique à une liaison filaire[cite: 3].
  * **Fonctions stubs de `sch_PrimitiveAttribute` :** Dans la version actuelle de l'API embarquée, `eda.sch_PrimitiveAttribute.createNetLabel()` et `create()` sont des stubs vides (`async createNetLabel(t,i,n){}`). Pour modifier un label existant, utiliser `eda.sch_PrimitiveAttribute.modify(attrId, { value: 'NET_NAME' })`[cite: 3].

* **[2026-09-06] Annotation textuelle du schéma (`sch_PrimitiveText`) & Système de coordonnées**
  * **API :** `eda.sch_PrimitiveText.create(x, y, text, angle, font, fontSize, color, bold, italic)`
    * Exemple : `await eda.sch_PrimitiveText.create(50, 480, "ALIMENTATION", 0, undefined, 9, "#003388", true, false)`[cite: 3]
  * **Repère et orientation du schéma (`documentType: 1`) :**
    * Format standard A4 : Largeur 1170, Hauteur 825[cite: 3].
    * **L'axe Y est orienté vers le HAUT** (`y = 0` en bas de page, `y = 825` en haut de page)[cite: 3].
    * Attention : inversé par rapport au PCB où l'origine et l'orientation peuvent varier selon le cadrage[cite: 3].
  * **Usage :** Permet d'insérer des titres et des annotations explicatives directement au-dessus des blocs de composants sans risque de court-circuit électrique (éléments purement graphiques)[cite: 3].

* **[2026-09-07] Schématique : Création programmatique de ports de réseau (`NetPort`)**
  * **Contournement des stubs `createNetLabel` :** L'API `eda.sch_PrimitiveAttribute.createNetLabel()` étant un stub vide dans le runtime EasyEDA Pro actuel, la création de ports de réseau via `eda.sch_PrimitiveComponent.createNetPort(direction, net, x, y, rotation, mirror)` est pleinement fonctionnelle et opérationnelle[cite: 3].
  * **Connexion au schéma :** Le port de réseau dispose d'une broche électrique interne (au point d'insertion selon la rotation) qui connecte immédiatement tout fil (`Wire`) superposé ou adjacent et propage le net dans le compilateur de netlist EasyEDA sans nécessiter d'intervention manuelle[cite: 3].

* **[2026-09-11] Schématique : Détection fine des avertissements ERC, broches non connectées et redondance de net**
  * **Extraction des messages ERC/DRC schématique :**
    * Lorsque `eda.sch_Drc.check(true, false, true)` retourne un résumé de type `[{ type: "warn", count: N }]`, appeler `await eda.sch_Drc.check(true, true, true)` avec `userInterface: true` ouvre le panneau de contrôle dans l'UI EasyEDA Pro[cite: 3].
    * Les messages détaillés du compilateur (`[Warn] : ...`, `[Error] : ...`) sont alors injectés dans le DOM de la fenêtre EasyEDA et peuvent être extraits via une requête DOM sur les nœuds textuels (`element.innerText.startsWith('[Warn]')`)[cite: 3].
  * **Marquage programmatique des broches non connectées (`noConnected`) :**
    * Les broches d'un composant laissées ouvertes (ex. `SBU1` et `SBU2` sur un connecteur USB-C 2.0) déclenchent l'avertissement ERC `Found some components Pins floating, suggest placing No Connect Flag`[cite: 3].
    * Pour marquer une broche en "No Connect" sans ajouter de symbole graphique, appeler :
      `await pin.toAsync().setState_NoConnected(true).done();`[cite: 3]
  * **Évitement de l'avertissement "multiple net names" sur les fils :**
    * Si un segment de fil (`sch_PrimitiveWire.create(line, net)`) reçoit explicitement un nom de net alors qu'il est raccordé à un drapeau (`NetFlag`, ex. `GND`) ou à un port (`NetPort`, ex. `VBUS_USB`), le compilateur de schéma détecte une redondance de source et émet l'avertissement :
      `[Warn] : Wire $1Nxxx has multiple net names: GND、GND`[cite: 3].
    * Pour les fils connectés à un `NetFlag` ou `NetPort`, il convient d'omettre le second argument de nom de net lors de l'appel à `eda.sch_PrimitiveWire.create(line)`[cite: 3]. La propagation électrique s'effectue automatiquement et proprement depuis le port ou drapeau sans aucune alerte[cite: 3].

* **[2026-09-14] Schématique : Instanciation programmatique de composants via la bibliothèque système**
  * **Résolution obligatoire de l'objet Device pour `sch_PrimitiveComponent.create()` :**
    * Passer directement un objet allégé `{ libraryUuid, uuid }` ou `{ libraryType, libraryUuid, uuid }` provoque un blocage indéfini ou un timeout (30 000 ms) dans EasyEDA Pro[cite: 3].
    * Pour instancier un composant sans blocage, il faut d'abord rechercher et récupérer l'objet `Device` complet résolu par le moteur interne :
      ```javascript
      const sysLib = await eda.lib_LibrariesList.getSystemLibraryUuid(); // '0819f05c4eef4c71ace90d822a990e87'
      const devs = await eda.lib_Device.search('FRC0805', undefined, sysLib);
      const comp = await eda.sch_PrimitiveComponent.create(devs[0], x, y, undefined, rotation, mirror, addIntoBom, addIntoPcb);
      await comp.toAsync().setState_Designator('R12').setState_Name('100k').done();
      ```[cite: 3]
    * Cette démarche fonctionne instantanément pour tous les passifs standard (`FRC0805`, `CL10B104KB8NNNC`, `Test-Point`, etc.)[cite: 3].

---

## 2. API PCB, Primitives & Routage

* **[2026-09-03] Extraction de la nomenclature (BOM) et des empreintes depuis le PCB**
  * **Subtilité de lecture des valeurs :** `getState_Name()` ou `getState_Designator()` ne renvoient que le préfixe/désignateur du composant (`R1`, `C1`). La valeur réelle du composant (`10k`, `100nF`) ainsi que le part number LCSC se trouvent dans le dictionnaire `getState_OtherProperty()?.Value` ou `props.Device`[cite: 3].
  * **Récupération de l'empreinte :** L'objet empreinte est accessible via `c.getState_Footprint()`. Pour résoudre le nom lisible de l'empreinte, il faut appeler `eda.lib_Footprint.get(fpInfo.uuid, fpInfo.libraryUuid)`[cite: 3].

  ```javascript
  const ids = await eda.pcb_PrimitiveComponent.getAllPrimitiveId();
  const components = await eda.pcb_PrimitiveComponent.get(ids);

  const results = [];
  for (const c of components) {
    const fpInfo = c.getState_Footprint?.() || c.footprint;
    let fpName = '';
    if (fpInfo?.uuid && fpInfo?.libraryUuid) {
      const fp = await eda.lib_Footprint.get(fpInfo.uuid, fpInfo.libraryUuid);
      fpName = fp?.name || fp || '';
    }

    const props = c.getState_OtherProperty?.() || {};
    results.push({
      designator: c.getState_Designator?.() || c.designator,
      value: props.Value || props.Device || '',
      footprint: fpName
    });
  }
  return results;
  ```[cite: 3]

* **[2026-09-03] Géométrie des pastilles (Pads) et unités de mesure**
  * **Unités runtime :** Les coordonnées de l'API PCB (`center.x`, `center.y`, `width`, `height`) sont exprimées en **mils** (1 mil = 0.0254 mm)[cite: 3].
  * **Lien composant - pastille :** L'identifiant `primitiveId` d'une pastille commence systématiquement par le `primitiveId` du composant parent (`pad.primitiveId.startsWith(comp.primitiveId)`)[cite: 3].
  * **Dimensions :** `pad.pad[1]` correspond à la largeur et `pad.pad[2]` à la hauteur en mils. `pad.pad[0]` indique la forme (`"RECT"`, `"OVAL"`, etc.)[cite: 3].

  ```javascript
  const targetNets = ['+12V', '+12V_PROT'];
  const compIds = await eda.pcb_PrimitiveComponent.getAllPrimitiveId();
  const comps = await eda.pcb_PrimitiveComponent.get(compIds);
  const compMap = new Map();
  for (const c of comps) {
    compMap.set(c.getState_PrimitiveId(), c.getState_Designator());
  }

  const padGeometry = [];
  for (const net of targetNets) {
    const prims = await eda.pcb_Net.getAllPrimitivesByNet(net);
    for (const p of prims) {
      padGeometry.push({
        designator: compMap.get(p.parentId) || p.parentId,
        padNumber: p.num,
        net: p.net,
        x: Math.round(p.center.x * 10) / 10,
        y: Math.round(p.center.y * 10) / 10,
        width_mil: Math.round((p.topWidth || 0) * 10 * 10) / 10,
        height_mil: Math.round((p.topHeight || 0) * 10 * 10) / 10,
        shape: p.topType
      });
    }
  }
  return padGeometry;
  ```[cite: 3]

* **[2026-09-03] Identifiants numériques des couches (Layers) & Tracé de lignes**
  * **Identifiants runtime :** Dans le contexte navigateur EasyEDA Pro, les couches sont référencées par des entiers :
    * `1` = `Top Layer` (cuivre supérieur)
    * `2` = `Bottom Layer` (cuivre inférieur)
    * `11` = `Board Outline` (contour de carte)[cite: 3]
  * **API de tracé :** `eda.pcb_PrimitiveLine.create(net, layer, startX, startY, endX, endY, lineWidth, primitiveLock)`[cite: 3]
  * **API de via :** `eda.pcb_PrimitiveVia.create(net, x, y, holeDiameter, diameter)` (standard JLCPCB : perçage 12 mil ≈ 0.3 mm, diamètre 24 mil ≈ 0.6 mm)[cite: 3].

* **[2026-09-05] Portée des namespaces API & Document actif**
  * `eda.sch_*` échoue (`获取所有器件的图元ID失败`) si le document actif affiché dans EasyEDA n'est pas une feuille de schéma (`documentType !== 1`)[cite: 3].
  * `eda.pcb_*` échoue si le document actif n'est pas un circuit imprimé (`documentType !== 3`)[cite: 3].
  * **Bonne pratique :** Avant d'exécuter des requêtes sur un domaine, basculer activement le document via :
    ```javascript
    await eda.dmt_EditorControl.openDocument(targetDocumentUuid);
    await new Promise(r => setTimeout(r, 600));
    ```[cite: 3]

* **[2026-09-05] Comportement de `eda.pcb_Document.importChanges()`**
  * L'appel programmatique `await eda.pcb_Document.importChanges(schUuid)` renvoie `false` lorsque des boîtes de dialogue interactives de confirmation de changements (liste des composants ajoutés/supprimés et nets modifiés) sont requises par la version desktop d'EasyEDA Pro[cite: 3].
  * Pour une synchronisation fiable de nouveaux composants, privilégier l'action utilisateur via **Conception > Mettre à jour le PCB** (*Design > Update PCB*)[cite: 3].

* **[2026-09-05] Manipulation 2D des composants PCB (Position & Rotation)**
  * **API directe :** `eda.pcb_PrimitiveComponent.modify(primitiveId, { x, y, rotation })`[cite: 3]
    * *Note :* Privilégier cette méthode à l'approche `c.toAsync()`, car `get([id])` retourne un tableau, ce qui peut causer des erreurs de type si non déstructuré[cite: 3].
  * **Repère d'orientation des pastilles (composants passifs à 2 broches ex. 0805, 0603, SMA) :**
    * `0°` : Horizontal standard — Pastille 1 à gauche, Pastille 2 à droite[cite: 3].
    * `90°` : Vertical — Pastille 1 en bas, Pastille 2 en haut[cite: 3].
    * `180°` : Horizontal inversé — Pastille 1 à droite, Pastille 2 à gauche[cite: 3].
    * `270°` : Vertical inversé — Pastille 1 en haut, Pastille 2 en bas[cite: 3].

* **[2026-09-06] Contrôle DRC programmatique**
  * **API :** `await eda.pcb_Drc.check()`[cite: 3]
  * **Comportement :** Renvoie un booléen immédiat :
    * `true` : Aucun conflit DRC détecté (règles de dégagement, chevauchements et continuité respectées)[cite: 3].
    * `false` : Présence de violations DRC (ex. discordance de nom de net entre pastille et piste, ou distance d'isolement insuffisante)[cite: 3].

* **[2026-09-06] Diagnostic approfondi des violations DRC (`includeVerboseError`)**
  * **API :** `await eda.pcb_Drc.check(true, false, true)`[cite: 3]
  * **Fonctionnement :** Le troisième paramètre `includeVerboseError = true` retourne la liste exhaustive des violations catégorisées (Clearance Error, Connection Error, Netlist Error) avec tous les détails géométriques :
    * Types et identifiants des objets incriminés (`obj1`, `obj2`, `objs`)[cite: 3].
    * Coordonnées précises du conflit (`pos: { x, y }`)[cite: 3].
    * Distances mesurées vs règles d'isolement requises (`minDistance`, `shouldBe`)[cite: 3].
  * **Utilité :** Permet à l'agent d'identifier et corriger précisément au mil près les violations d'isolement (ex. distance piste-pastille) sans intervention humaine[cite: 3].

* **[2026-09-06] Réaffectation directe du réseau d'une pastille (`Pad Net`)**
  * **API directe :** `await eda.pcb_PrimitivePad.modify(primitiveId, { net: 'NOUVEAU_NET' })`[cite: 3]
  * **Contexte :** Permet de réconcilier ou forcer l'attribution de réseau sur une pastille PCB sans devoir refaire un import complet du schéma lorsque des incohérences mineures de synchronisation bloquent le DRC[cite: 3].

* **[2026-09-06] Suppression ciblée de pistes (`PrimitiveLine`)**
  * **API :** `await eda.pcb_PrimitiveLine.delete([primitiveId1, primitiveId2, ...])`[cite: 3]
  * **Fonctionnement :** Supprime immédiatement les segments de ligne spécifiés par leur identifiant primitif (`primitiveId`), facilitant les ajustements de tracé et le ré-routage propre[cite: 3].

* **[2026-09-07] PCB : Invalidation de l'arbre de connectivité cuivre lors des modifications in-place (`modify` vs `create`)**
  * **Problème découvert :** Modifier directement l'attribut `net` de pistes ou vias existants via `eda.pcb_PrimitiveLine.modify(id, { net })` ou `eda.pcb_PrimitiveVia.modify(id, { net })` met à jour la propriété dans la base de données, mais le moteur de calcul DRC ne reconstruit pas toujours le graphe de continuité cuivre. Il en résulte de fausses alertes d'isolement DRC ("Track to Via distance is 0mm, should be >= 0.176mm") entre des éléments portant pourtant le même nom de net[cite: 3].
  * **Solution robuste :** Pour réassigner un tracé existant vers un nouveau net, supprimer les primitives incriminées (`pcb_PrimitiveLine.delete()`, `pcb_PrimitiveVia.delete()`) et les recréer avec `create(net, ...)` garantit leur insertion immédiate dans l'arbre spatial du nouveau réseau, assurant un DRC à 0 erreur d'isolement[cite: 3].

* **[2026-09-11] Sous-tâche 4.6.2 : Signature de `pcb_PrimitiveVia.create` et règles de routage Type-C**
  * **Ordre des paramètres de `eda.pcb_PrimitiveVia.create` (CRITIQUE) :**
    * La signature exacte est `create(net, x, y, holeDiameter, diameter, viaType, ...)` : le diamètre de perçage (`holeDiameter`) précède le diamètre extérieur du via (`diameter`). Inverser ces deux arguments crée un via avec un perçage plus grand que le diamètre de pastille et déclenche l'erreur DRC `Via Size / viaSize: The outer diameter of the via hole of {obj} is X, which should be 0.5mm ~ 10mm`[cite: 3].
  * **Règles d'échappement des connecteurs USB-C traversants (16 broches) :**
    * L'écartement entre broches d'une même rangée (pas de 1.0 mm, pastille de 0.8 mm) laisse moins de 8 mil de jeu, interdisant le passage d'une piste entre deux broches voisines sous la règle Safe Spacing standard (10 mil / 0.254 mm)[cite: 3].
    * Les broches de la rangée A doivent s'échapper vers le nord (vers le bord de carte) et les broches de la rangée B vers le sud[cite: 3].
    * Les pattes de fixation mécaniques de blindage (ex. `J2_0`) sont volumineuses (70.9 × 39.4 mil) : pour passer au nord sans violer la règle de bordure (`Board Outline to Track >= 0.3 mm`), la piste doit adopter une largeur fine (ex. 5 mil) calée sur la ligne médiane libre (`y ≈ 35 mil`)[cite: 3].
  * **Vigilance sur le bus d'alimentation Layer 2 :**
    * La distribution 3.3V descend sur Layer 2 le long du méridien `x = 3050` (piste de 24 mil). Tout saut ou via vers Layer 2 dans le bloc ouest doit impérativement respecter `x >= 3075 mil` pour ne pas couper ce rail d'alimentation[cite: 3].

* **[2026-09-11] Sous-tâches 4.6.3 : Découplage HF des transceivers, signature `pcb_PrimitiveLine.create` et relocalisation de vias**
  * **Signature exacte de `eda.pcb_PrimitiveLine.create` (CRITIQUE) :**
    * La signature est `create(net, layer, startX, startY, endX, endY, width, primitiveLock)`. Les coordonnées `startX, startY, endX, endY` précèdent la largeur de piste (`width`). Placer la largeur en 3e position décale tous les arguments et projette la piste hors de la carte ou à des coordonnées erronées[cite: 3].
  * **Relocalisation d'un via (`pcb_PrimitiveVia`) vs modification directe :**
    * L'appel `via.toAsync().setState_X().setState_Y().done()` sur un via existant met à jour ses coordonnées d'affichage mais ne recalcule pas correctement le masque d'isolement lors de `rebuildCopperRegion()`, laissant subsister une fausse erreur DRC d'isolement (`Copper Region(Filled) to Via`)[cite: 3].
    * Le motif fiable pour déplacer un via consiste à supprimer l'ancien via (`await eda.pcb_PrimitiveVia.delete([oldId])`) puis à instancier un nouveau via (`await eda.pcb_PrimitiveVia.create(net, x, y, hole, diameter, false)`), suivi de `rebuildCopperRegion()`[cite: 3].
  * **Topologie de découplage transceivers (CAN U2 & K-Line U3) :**
    * Pour un découplage HF efficace (suppression des transitoires di/dt), le condensateur céramique 100 nF (0603) doit être situé à moins de 2 mm de la broche d'alimentation de l'IC[cite: 3].
    * La topologie de routage optimale est : `Arrivée d'alimentation (Via) -> Pastille 1 Condensateur -> Broche IC`. Cette configuration garantit que le condensateur amortit le bruit haute fréquence avant l'entrée dans le CI tout en éliminant les stubs inductifs[cite: 3].

* **[2026-09-11] Sous-tâches 4.6.5 & 4.6.6 : Chanfreinage à 45° du bus CAN et intégrité du plan de masse**
  * **Méthodes d'accès aux coordonnées des pastilles (`pcb_PrimitivePad`) :**
    * Les coordonnées d'une pastille s'obtiennent par `await pad.getState_X()` et `await pad.getState_Y()` (et le numéro par `await pad.getState_PadNumber()`). La méthode `getState_Center()` n'existe pas sur la classe `pcb_PrimitivePad`[cite: 3].
  * **Adoucissement des angles (Chanfreinage 45°) sur paires différentielles :**
    * Les angles droits (90°) introduisent des ruptures d'impédance caractéristique et augmentent la capacité parasite locale aux coudes de routage, favorisant les réflexions et le rayonnement EMI lors de fronts raides (cas typique du bus CAN 500 kbps / 1 Mbps)[cite: 3].
    * L'insertion d'un biseau à 45° ($\Delta x = \Delta y = 25\text{ mil}$ pour une piste de 10 mil) adoucit la transition tout en conservant une marge de dégagement (`Safe Spacing`) très confortable vis-à-vis des vias de masse et pistes voisines (> 18 mil effectifs vs 6 mil mini requis)[cite: 3].
  * **Vérification de continuité du cuivre coulé (`pcb_PrimitivePoured`) :**
    * Après reconstruction des plans (`rebuildCopperRegion()`), le nombre de régions continues se vérifie via `await eda.pcb_PrimitivePoured.getAll()`. Deux régions actives (`pouredCount = 2`) confirment qu'il y a exactement un plan de masse unifié sur Top Layer et un sur Bottom Layer, sans îlot flottant ou isolé[cite: 3].

---

## 3. Plans de Cuivre, DRC & Intégrité

* **[2026-09-08] Contour de carte (`pcb_PrimitivePolyline`) et règles de dégagement**
  * **Lecture de la géométrie du contour :** Le contour de carte (Board Outline) est stocké sous la forme d'un objet `eda.pcb_PrimitivePolyline` sur la couche 11 (`EPCB_LayerId.BOARD_OUTLINE`)[cite: 3].
  * Sa géométrie est accessible via la méthode `poly.getState_Polygon()`, qui renvoie un descripteur géométrique standard, par exemple `["R", x, y, width, height, 0, 0]` pour un contour rectangulaire[cite: 3].
  * **Règle DRC de bordure :** La règle `Board Outline to Track` impose une distance d'isolement stricte de **0.300 mm (11.8 mil)**. Tout tracé ou via doit impérativement respecter cette marge par rapport aux 4 arêtes du contour[cite: 3].

* **[2026-09-11] Création d'une zone d'exclusion / Keepout multicouche (`pcb_PrimitiveRegion`)**
  * **API :** `eda.pcb_PrimitiveRegion.create(layer, complexPolygon, ruleType, regionName, lineWidth, primitiveLock)`[cite: 3]
  * **Couche multicouche (`EPCB_LayerId.MULTI`) :** Pour appliquer une zone d'exclusion sur toutes les couches (Top, Bottom, couches internes), utiliser l'identifiant de couche `12` (`EPCB_LayerId.MULTI`)[cite: 3].
  * **Géométrie rectangulaire :** Le polygone rectangulaire est instancié par `eda.pcb_MathPolygon.createPolygon(['R', x, y, width, height, rotation, cornerRadius])`[cite: 3].
  * **Combinaison des règles d'exclusion (`ruleType`) :**
    * `EPCB_PrimitiveRegionRuleType.NO_WIRES` (`5`) : Interdiction formelle de passage de pistes de cuivre[cite: 3].
    * `EPCB_PrimitiveRegionRuleType.NO_FILLS` (`6`) : Interdiction des remplissages de cuivre (`Solid Fill`)[cite: 3].
    * `EPCB_PrimitiveRegionRuleType.NO_POURS` (`7`) : Interdiction d'incursion des plans de masse ou de puissance (`Copper Pour`)[cite: 3].

* **[2026-09-11] Plans de masse (`pcb_PrimitivePour`), régénération et vias de couture (Stitching Vias)**
  * **Création des plans de masse :**
    * `eda.pcb_PrimitivePour.create(net, layer, complexPolygon, pourFillMethod, preserveSilos, pourName, pourPriority, lineWidth, primitiveLock)`[cite: 3]
    * Pour couvrir l'ensemble du contour de carte, utiliser le polygone rectangulaire : `eda.pcb_MathPolygon.createPolygon(['R', 1850, 50, 2600, 1250, 0, 0])`[cite: 3]
  * **Calcul et régénération du remplissage cuivre :**
    * Après création ou déplacement d'éléments, appeler impérativement `await pour.rebuildCopperRegion()` pour recalculer les zones de remplissage et les freins thermiques[cite: 3].
  * **Matrice thermique pour boîtier QFN/LGA (ESP32 pad 41) :**
    * Pour les modules dotés d'un pad thermique composite divisé en sous-pastilles, disposer une matrice de vias de masse 12/24 mil interconnectée par un quadrillage de pistes de cuivre sur les deux couches garantit une dissipation thermique optimale et une continuité électrique parfaite[cite: 3].

* **[2026-09-11] Normalisation Schéma ↔ PCB des noms de net et micro-zones d'exclusion (`NO_POURS`)**
  * **Micro-zones d'exclusion (`NO_POURS`) contre les langues de cuivre intempestives :**
    * Lors de la régénération d'un plan de masse, le moteur de remplissage peut créer des langues de cuivre s'infiltrant dans les fentes étroites entre les pastilles CMS (ex. entre les pads 1 et 2 d'un boîtier 0603 ou 0805), causant des violations d'isolement au mil près[cite: 3].
    * La création d'une micro-zone d'exclusion locale sur la couche cuivre concernée (`eda.pcb_PrimitiveRegion.create(layer, polygon, [7], name)`) avec `ruleType: [7]` (`NO_POURS`) bloque net l'intrusion du plan de masse sans impacter les pistes[cite: 3].

---

## 4. Rendu Graphique, Exports & Cache WebGL

* **[2026-09-03] Capture haute fidélité du canvas PCB / Schéma (Blob vers Base64)**
  * `eda.pcb_Document.zoomToBoardOutline()` permet de cadrer parfaitement la vue sur le contour de carte avant export[cite: 3].
  * `eda.dmt_EditorControl.getCurrentRenderedAreaImage(tabId)` renvoie un objet `Blob` inaccessible directement depuis l'extérieur du navigateur[cite: 3].
  * **Astuce :** Utiliser un `FileReader` dans le code exécuté dans le navigateur pour convertir le `Blob` en chaîne `Base64`, puis l'écrire sur le disque côté système hôte (PowerShell / Node.js)[cite: 3].

* **[2026-09-05] Exportation automatisée du projet EasyEDA (`.epro2`)**
  * **API :** `eda.sys_FileManager.getProjectFile(fileName, password, fileType)`[cite: 3]
  * **Fonctionnement :** Renvoie un objet standard Web `File` (Blob) converti en Base64 pour écriture disque via le pont WebSocket/HTTP[cite: 3].

* **[2026-09-05] Exportation haute résolution du schéma (`PNG`)**
  * **API :** `eda.dmt_EditorControl.zoomToAllPrimitives()` puis `eda.dmt_EditorControl.getCurrentRenderedAreaImage(doc.tabId)`[cite: 3]

* **[2026-09-06] Robustesse des scripts d'exportation (Node.js vs PowerShell)**
  * Lors du transfert de gros volumes de données Base64 (ex. captures PNG haute résolution `getCurrentRenderedAreaImage`), les variables PowerShell `$base64` peuvent être interpolées et vidées si incluses par inadvertance dans des blocs `@"..."@`[cite: 3].
  * L'exécution via un script Node.js exécuté via `node -e` ou un fichier scratch (`fetch('http://localhost:49620/execute')` et `Buffer.from(base64, 'base64')`) est plus robuste et gère directement les promesses JavaScript[cite: 3].

* **[2026-09-06] Rafraîchissement du rendu visuel des textes de pistes sur le canvas PCB (Cache WebGL)**
  * **Problème découvert :** Modifier la propriété `net` d'une piste via l'API met bien à jour la base de données interne, mais le texte imprimé le long de la piste dans le canvas WebGL continue d'afficher l'ancien nom de net (ex. `$1N15` au lieu de `+12V_PROT`)[cite: 3].
  * **Cause technique :** Le moteur graphique d'EasyEDA Pro met en cache les textures de rendu des textes vectoriels tant que l'onglet du document reste ouvert[cite: 3].
  * **Solution programmatique éprouvée :**
    ```javascript
    // 1. Sauvegarder les modifications dans la base du document
    await eda.pcb_Document.save();
    await new Promise(r => setTimeout(r, 400));

    // 2. Fermer l'onglet actif
    const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
    await eda.dmt_EditorControl.closeDocument(doc.tabId);
    await new Promise(r => setTimeout(r, 600));

    // 3. Réouvrir le document
    await eda.dmt_EditorControl.openDocument(pcbUuid);
    await new Promise(r => setTimeout(r, 1000));
    ```[cite: 3]

* **[2026-09-07] Exportation d'images haute résolution contrôlée via le contexte Canvas 2D**
  * **Spécificités runtime :** `eda.sch_ManufactureData.getPngFile()` n'est pas exposé dans tous les environnements desktop et `getExportDocumentFile()` requiert une validation modale bloquante[cite: 3].
  * **Méthode d'export exacte :** Utiliser `eda.dmt_EditorControl.getCurrentRenderedAreaImage(doc.tabId)` pour obtenir le flux graphique brut rendu, puis projeter l'image dans un élément `<canvas>` dimensionné aux résolutions requises (ex. `2274 × 1236 px` pour le schéma, `1137 × 642 px` pour le PCB) avec `imageSmoothingQuality = 'high'` avant l'encodage PNG Base64[cite: 3].

* **[2026-09-09] Limite de résolution de la capture d'écran API (`getCurrentRenderedAreaImage`) vs Export UI natif**
  * **Problème identifié :** L'API `eda.dmt_EditorControl.getCurrentRenderedAreaImage()` capture uniquement le viewport du navigateur (environ 1631 × 618 px). Pour une feuille de schéma complète (format A4), les textes des composants ne mesurent que 3 à 4 pixels[cite: 3].
  * **Solution retenue :** L'export d'images haute définition pour la documentation (`images/Schematic.png` et `images/PCB.png`) est confié à l'utilisateur via le menu natif de l'interface EasyEDA Pro (**Fichier > Exporter > Image / PDF** à 300 DPI ou largeur 4096 px), garantissant une netteté vectorielle irréprochable[cite: 3].