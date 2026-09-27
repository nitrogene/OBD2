# Revue Technique : Audit de conformité constructeur du schéma P1 (alimentation, MCU, K-Line, outillage)

- **Nom du Reviewer / Agent :** Devin (audit externe, posture *tabula rasa*)
- **Date :** 2026-09-26
- **Périmètre audité :** Schéma électrique P1 (4 pages, exports PNG), `BOM.md`, `circuit_semantics.json`, `DATASHEETS.md`, `TODO.md`, skills `.agents/skills/`
- **Version / Référence examinée :** commit `f37f36d` (« refactor(sch): rapatriement découplage C1/C2 sur ESP32 et nettoyage boucle bootstrap Buck »)
- **Verdict global :** 🟠 Approuvé avec réserves

---

## Résumé Exécutif

L'architecture générale (protection d'entrée PPTC + TVS + P-MOS anti-inversion, Buck 12 V→5 V, LDO 3,3 V, TJA1051T/3 en VCC 5 V / VIO 3,3 V, L9637D en VCC 3,3 V, USB natif sur IO19/IO20, ADC1 sur GPIO1) est saine et cohérente avec le périmètre 12 V VL. Les points déjà inscrits dans `TODO.md` (Css absent sur `U4`, `C6` sous-dimensionné, calibre `F1`, pull-up `IO0`, fuite `D6`, marge TVS `D1`, `Q2`/Load-Dump, `D4`) ne sont pas répétés ici.

Cet audit ne retient que des écarts **non couverts** par `TODO.md`. Un écart bloquant est confirmé face à la datasheet TI : le condensateur de bootstrap `C5` vaut 1 µF alors que TI impose **0,1 µF** — et `DATASHEETS.md`, présenté comme « source de vérité », cite une plage erronée qui a légitimé ce choix. Deux corrections de correctifs sont également nécessaires : le repli GPIO36/37 proposé pour la ré-assignation TWAI est **physiquement impossible** sur un module N16R8, et la variante `-N16R8` plafonne à **65 °C ambiants**, ce qui est incompatible avec l'usage habitacle revendiqué. Enfin, la broche `VOUT` redondante de `U5` est laissée en l'air, la broche `EN` de `U4` n'a pas de seuil UVLO programmé et `review001.md` reste non dépouillée tout en contredisant `BOM.md`.

---

## Synthèse des Observations

| Réf | Criticité | Composants / Nets | Description synthétique |
| :--- | :--- | :--- | :--- |
| **B1** | 🔴 Bloquant | `C5` (`BOOT`/`PH` de `U4`) | Bootstrap à 1 µF alors que TI impose strictement 0,1 µF |
| **I1** | 🟠 Important | `U1` (`ESP32-S3-WROOM-1-N16R8`) | Repli GPIO36/37 du TODO impossible (PSRAM Octal) et doc HARDWARE fausse |
| **I2** | 🟠 Important | `U1`, thermique | Variante R8 limitée à 65 °C ambiants, incompatible habitacle |
| **I3** | 🟠 Important | `U5` pin 2 (`VOUT`) | Seconde broche de sortie/tab laissée non connectée (chemin thermique) |
| **I4** | 🟠 Important | `U4` pin 3 (`EN`) | Aucun pont UVLO programmé : pas de coupure propre au démarreur |
| **I5** | 🟠 Important | `R16`, net `K_LINE` | 1 kΩ : temps de montée et dissipation hors des critères annoncés |
| **M1** | 🟢 Mineur | `J2`, net `VBUS_5V` | Pas de réservoir VBUS côté connecteur USB-C |
| **M2** | 🟢 Mineur | `DATASHEETS.md`, `review/guidelines.md` | Citations datasheet non conformes (bootstrap, plage VCC du L9637D) |
| **M3** | 🟢 Mineur | `.agents/skills/` | Deux violations de la Règle 0 (désignateurs codés en dur) |
| **M4** | 🟢 Mineur | `review001.md`, `BOM.md` | Revue non dépouillée, en contradiction avec la synthèse BOM |
| **M5** | 🟢 Mineur | Fichier projet EasyEDA | Quatre noms de fichier projet différents dans la documentation |
| **M6** | 🟢 Mineur | `U3` pin 8 (`LI`) | `LI` à GND maintient le comparateur L actif en permanence |

---

## Détail des Observations & Recommandations

### 🔴 Remarques Bloquantes (Critiques)

#### B1. Condensateur de bootstrap `C5` hors spécification constructeur (1 µF au lieu de 0,1 µF)
- **Composants / Nets concernés :** `C5` (1 µF 50V X5R 0603, LCSC `C15849`) entre `U4` pin 1 (`BOOT`) et `U4` pin 8 (`PH`)
- **Constat technique :** La page 1 du schéma et `BOM.md` implantent `C5 = 1 µF`. Le référentiel interne `DATASHEETS.md` (§ U4, point 4) autorise « 0,1 µF à 1 µF ». Cette plage n'existe pas chez TI.
- **Justification & Risque :** Datasheet TPS54331 (SLVS839H) — Table 5-1, pin 1 : « *A 0.1-µF bootstrap capacitor **is required** between the BOOT and PH pins* » ; § 7.3.3 : « *requires a 0.1-µF ceramic capacitor* » ; § 8.2.2.8 : « *Every TPS54331 design requires a bootstrap capacitor... The bootstrap capacitor **must have a value of 0.1 µF*** ». Le régulateur intègre sa diode et son régulateur de recharge de bootstrap : la charge est fournie pendant le temps OFF, à courant limité. Avec 1 µF (10× la valeur spécifiée), l'énergie à transférer à chaque cycle est décuplée ; la tension BOOT-PH peut rester sous le seuil UVLO interne de 2,1 V, ce qui force le MOSFET high-side à s'ouvrir (« *the high-side MOSFET is forced to switch off until the capacitor is refreshed* »), en particulier au démarrage et à faible charge (Eco-mode, ESP32 en veille). Symptômes attendus : démarrage par hoquets, rail `+5V` non établi ou instable à l'enfichage OBD, sous-tension du rail `3.3V` et brownout ESP32-S3. Le composant est sur une broche vitale du seul convertisseur de la carte : l'écart est bloquant.
- **Solution recommandée :** Remplacer `C5` par un **100 nF 50 V X7R 0603**, référence `CC0603KRX7R9BB104`, LCSC **`C14663`** — **Basic Part** déjà utilisée sur la carte (`C1`, `C2`, `C3`, `C4`, `C10`, `C14`, `C15`) : aucun coût, aucune empreinte nouvelle. Corriger simultanément `DATASHEETS.md` (cf. M2) et `circuit_semantics.json` (`C5.constraints.value_farad = 1e-7`, diélectrique X7R).

---

### 🟠 Remarques Importantes (Robustesse & CEM)

#### I1. Correction du correctif TWAI : GPIO36/37 indisponibles sur `ESP32-S3-WROOM-1-N16R8`
- **Composants / Nets concernés :** `U1` pins 36 (`RXD0`) et 37 (`TXD0`), nets `TXD` / `RXD` vers `U2` pins 1 (`TXD`) et 4 (`RXD`) ; ligne `[I5]` de `TODO.md` ; `HARDWARE.md` lignes 273-274
- **Constat technique :** Trois incohérences se cumulent sur le même bus. (1) Le schéma page 4 câble bien `TXD`/`RXD` sur les broches **36/37 du module**, qui sont `RXD0`/`TXD0`, c'est-à-dire **GPIO44/GPIO43** — le constat de `TODO.md [I5]` est donc exact. (2) `HARDWARE.md` documente encore ces liaisons comme « IO37 (TXD) » et « IO36 (RXD) » : la documentation confond numéro de broche du module et numéro de GPIO, et reste fausse. (3) Le repli proposé par `TODO.md [I5]` — « *ou GPIO36/37* » — est **physiquement impossible** sur la variante achetée.
- **Justification :** Datasheet ESP32-S3-WROOM-1 (Table 3-1, note b, p.12) : « *For modules with Octal SPI PSRAM, i.e., modules embedded with ESP32-S3R8 or ESP32-S3R16V, pins **IO35, IO36, and IO37 are connected to the Octal SPI PSRAM and are not available for other uses***. » La `BOM.md` retient `ESP32-S3-WROOM-1-N16R8` (LCSC `C2913202`), donc PSRAM Octal : IO35/36/37 sont captifs, et le schéma les marque d'ailleurs correctement en *No Connect* (broches 28-30). Router TWAI sur GPIO36/37 rendrait la PSRAM inutilisable et le bus CAN non fonctionnel.
- **Solution recommandée :** Restreindre la cible de `[I5]` aux seuls GPIO libres et sans contrainte de strapping : **GPIO15/GPIO16** (pins 8/9, déjà non connectées) ou GPIO17/GPIO18 (pins 10/11) pour `TWAI_TX`/`TWAI_RX`, et supprimer la mention « GPIO36/37 » de `TODO.md`. Mettre `HARDWARE.md` (lignes 273-274) et `circuit_semantics.json` en cohérence en nommant les GPIO réels et non les numéros de broches du module.

#### I2. Plage de température ambiante de la variante `-N16R8` (65 °C) incompatible avec l'usage annoncé
- **Composants / Nets concernés :** `U1` — `ESP32-S3-WROOM-1-N16R8`, LCSC `C2913202`
- **Constat technique :** Aucun document du projet (`BOM.md`, `DATASHEETS.md`, `HARDWARE.md`) ne mentionne la limite thermique spécifique des variantes à PSRAM Octal, alors que `TODO.md [I3]` retient explicitement une température habitacle de **50-60 °C** comme hypothèse de dimensionnement du fusible `F1`.
- **Justification :** Datasheet ESP32-S3-WROOM-1, Table 1-1 et §1 : « *R8 and R16V series modules operate at **–40 ~ 65 °C** ambient temperature, and other module variants operate at –40 ~ 85 °C.* » La marge est donc nulle : un boîtier fermé, alimenté en permanence sur la prise OBD (souvent sous la planche de bord), avec l'auto-échauffement du LDO `U5` (cf. I3) et des salves Wi-Fi, dépasse aisément 65 °C ambiants internes. Au-delà, la fiabilité de la PSRAM Octal n'est plus garantie (erreurs mémoire silencieuses, redémarrages).
- **Solution recommandée :** Deux options, à arbitrer selon le besoin firmware réel en PSRAM : (a) basculer sur `ESP32-S3-WROOM-1-N16R2` ou `-N8R2` (PSRAM Quad, **–40 ~ 85 °C**, IO35/36/37 libérés — ce qui résout aussi I1 en dégageant trois GPIO) ; (b) conserver le N16R8 et **activer l'ECC PSRAM** en firmware, qui remonte la limite à 85 °C au prix de 1/16 de la capacité (même source, §1), en documentant cette exigence comme contrainte bloquante de build dans `TODO.md` Phase 5.

#### I3. Broche `VOUT` redondante de `U5` laissée non connectée (chemin thermique amputé)
- **Composants / Nets concernés :** `U5` (`LDL1117S33R`, SOT-223-4) pin 2 marquée *No Connect* sur le schéma page 1, pin 4 seule raccordée au net vers `FB1`
- **Constat technique :** Sur le boîtier SOT-223-4, les broches 2 et 4 sont le même potentiel `VOUT`, la large broche/tab étant le **drain thermique** du composant. Le schéma n'en câble qu'une : la synchronisation vers le PCB héritera d'une pastille de sortie isolée, sans obligation de cuivre ni de vias.
- **Justification :** Bilan thermique : `U5` abaisse 5 V → 3,3 V. Avec l'hypothèse projet de 300 à 500 mA (`HARDWARE.md` bloc 2, salves Wi-Fi), P = (5,0 − 3,3) × 0,35 ≈ **0,6 W** en moyenne et jusqu'à 0,85 W en crête. La datasheet LDL1117 (§6.1) impose PDMAX = (125 − Tamb)/RthJA : un SOT-223 dont le tab n'est pas soudé à une plage de cuivre présente un RthJA très dégradé (> 100 °C/W au lieu de ~50 °C/W avec plage), soit ΔT > 60 °C, donc TJ > 125 °C dès 60 °C ambiants → protection thermique 175 °C / auto-retry, coupures du rail `3.3V`. C'est aussi cohérent avec la tâche « vias thermiques sous le pad de `U5` » déjà listée en Phase 3.4, qui ne pourra pas s'appliquer si le net n'est pas présent.
- **Solution recommandée :** Raccorder explicitement `U5` pin 2 au même net que pin 4 sur le schéma (suppression du flag *No Connect*), afin que le PCB impose une plage de cuivre de sortie sur les deux pastilles, et conserver la matrice de vias thermiques prévue en Phase 3.4.

#### I4. Broche `EN` de `U4` flottante : aucun seuil UVLO programmé pour le régime démarreur
- **Composants / Nets concernés :** `U4` pin 3 (`EN`), net `+12V_PROT`
- **Constat technique :** La broche `EN` est marquée *No Connect* sur le schéma page 1. Le fonctionnement est correct (la source de courant interne valide le composant), mais aucun seuil d'entrée n'est défini.
- **Justification :** Datasheet TPS54331, Table 5-1 pin 3 : « *Float this pin to enable. **Programming the input undervoltage lockout with two resistors is recommended***. » et §7.3.4. Sans pont, le seul seuil actif est l'UVLO interne à **3,5 V** : lors d'un démarrage moteur (chute de la batterie VL à 6-8 V, ISO 7637-2 pulse 4), le Buck continue de commuter en limite de rapport cyclique 100 %, le rail `+5V` s'effondre progressivement, `U5` entre en *dropout* et l'ESP32-S3 subit un brownout non maîtrisé pendant toute la phase de crank, avec risque de corruption de la NVS en cas d'écriture en cours.
- **Solution recommandée :** Implanter le pont UVLO préconisé par TI entre `+12V_PROT`, `EN` et `GND` : `Ren1 = (VSTART − VSTOP)/3 µA`, `Ren2 = VEN / ((VSTART − VEN)/Ren1 + 1 µA)` avec VEN = 1,25 V. Pour VSTART ≈ 8,8 V / VSTOP ≈ 7,3 V (hystérésis 1,5 V), retenir **Ren1 = 510 kΩ 0805** et **Ren2 = 91 kΩ 0805** (`0805W8F...`, *Basic Parts* de la même série que `R5`/`R12`), valeurs à re-vérifier une fois le seuil arbitré. L'arbitrage porte sur le compromis : seuil haut = coupure nette et redémarrage propre après crank ; seuil bas (VSTART ≈ 6,5 V) = maintien de session au prix d'un fonctionnement en limite.

#### I5. Pull-up K-Line `R16` de 1 kΩ : critères de temps de montée et de dissipation non tenus
- **Composants / Nets concernés :** `R16` (1 kΩ 1206, LCSC `C4410`), net `K_LINE` entre `+12V_PROT` et `U3` pin 6 (`K`)
- **Constat technique :** `HARDWARE.md` (ligne 395) fixe lui-même le critère : « *tr < 2 µs malgré la capacité parasite du faisceau habitacle (pouvant atteindre 2 nF)* ». Avec R = 1 kΩ et C = 2 nF, tr(10-90 %) = 2,2·R·C = **4,4 µs**, soit plus du double du critère annoncé. Le respect de tr < 2 µs impose R ≤ 455 Ω. Par ailleurs `circuit_semantics.json` verrouille `R16` (`substitutability: locked`) sur une dissipation crête de 207 mW dans un boîtier 1206 de 250 mW, soit **83 % du nominal**, alors que la ligne K est dominante (tirée à la masse) pendant la majeure partie d'une trame et que le dérating d'une couche épaisse 1206 débute typiquement à 70 °C — dans un habitacle à 60 °C, la marge réelle est quasi nulle.
- **Justification :** La datasheet L9637D caractérise l'ensemble de ses temps de transition (tr/tf, tON/tOFF, fmax 50 kHz) sous la condition explicite **RKO = 510 Ω, CK ≤ 1,3 nF** (Table 5, notes de test), qui est aussi la valeur historique des testeurs ISO 9141-2. À 1 kΩ, le circuit sort des conditions de caractérisation du constructeur, ce qui fragilise l'initialisation 5 baud (ISO 9141-2 §5) et le *fast-init* KWP2000 sur les faisceaux les plus capacitifs.
- **Solution recommandée :** Passer la pull-up à ~510 Ω en conservant la *Basic Part* déjà qualifiée : implanter **deux résistances 1 kΩ 1206 (`1206W4F1001T5E`, LCSC `C4410`) en parallèle** (`R16` + `R17`), soit 500 Ω avec 207 mW dissipés **par résistance** (2 × 250 mW disponibles). tr devient 2,2 µs à 2 nF et 1,4 µs à 1,3 nF. Mettre à jour `circuit_semantics.json` (rôle `kline_pullup_iso9141` porté sur une paire) et le calcul de `HARDWARE.md`.

---

### 🟢 Remarques Mineures (Optimisation & DFM)

#### M1. Absence de condensateur réservoir sur `VBUS` côté connecteur USB-C
- **Composants / Nets concernés :** `J2` pins A4/B9 et B4/A9 (`VBUS`), net `VBUS_5V`, `TP1`
- **Constat & Proposition :** Le net `VBUS_5V` ne porte que `TP1` et les anodes de `D4` ; le premier réservoir (`C8`/`C16`) se trouve **derrière** la diode, sur le rail `+5V`. La spécification USB 2.0 (§7.2.4.1) demande un découplage local de l'ordre de 1 à 10 µF sur VBUS côté périphérique pour encaisser l'inrush à l'enfichage et l'ondulation des salves Wi-Fi (~500 mA à travers une `BAT54CW`). Ajouter un **10 µF 50 V X5R 1206** (`CL31A106KBHNNNE`, LCSC `C13585`, *Basic Part* déjà au catalogue du projet) entre `VBUS_5V` et `GND`, à moins de 5 mm de `J2`.
- **Gain attendu :** Stabilité du 5 V en alimentation banc, réduction des rebonds d'enfichage et du bruit conduit vers le PC hôte ; composant sans surcoût (bobine déjà chargée).

#### M2. Citations de datasheet non conformes dans les documents de référence
- **Composants / Nets concernés :** `DATASHEETS.md` (§ U4 point 4), `review/guidelines.md` (§2.5), `TODO.md` ligne 14
- **Constat & Proposition :** Deux citations présentées comme constructeur ne figurent pas dans les datasheets archivées. (1) « *Bootstrap : céramique de 0,1 µF à 1 µF* » : TI n'énonce qu'une valeur unique et impérative de 0,1 µF (cf. B1) — c'est cette phrase qui a validé l'écart bloquant. (2) « *La plage de tension de service logique VCC s'étend de 3,0 V à 7,0 V (Tables 5 & 6)* » pour le L9637D : la datasheet ST (Doc ID 1765 Rev 8) ne donne qu'un *absolute maximum* de −0,3 à +7 V (Table 3) et la note 1 de la Table 5 précise « *Specs are tested at 5 V only. Compliance on Vcc full range is guaranteed by design* ». **Le choix de VCC = 3,3 V n'est pas remis en cause** (il est bien imposé par la non-tolérance 5 V des GPIO et par VTXhigh min = 2,5 V ≤ 3,3 V) : seule la référence documentaire doit être corrigée pour rester traçable.
- **Gain attendu :** Un référentiel dont chaque assertion est vérifiable ligne à ligne dans les PDF archivés ; suppression du mécanisme qui a laissé passer B1.

#### M3. Deux violations résiduelles de la Règle 0 (`AGENTS.md`) dans les skills
- **Composants / Nets concernés :** `.agents/skills/buck-compensation/scripts/tps54331_compensation.py` (ligne 376), `.agents/skills/pcb-placer/easyeda_client.py` (ligne 173)
- **Constat & Proposition :** Le premier script imprime en dur le désignateur du projet : `print("=== Calcul du Reseau de Compensation Type II - TPS54331 (U4) ===")`. Le second contient un exemple avec désignateur et coordonnées figées (`{"designator": "C1", "x": 1200.0, "y": 800.0, ...}`). Le reste de l'audit des cinq skills est conforme (aucune autre référence en dur détectée). Paramétrer le désignateur via un argument CLI optionnel (`--designator`, défaut vide) et neutraliser l'exemple de la docstring (`<REF>`, coordonnées symboliques).
- **Gain attendu :** Conformité stricte à la Règle 0 et réutilisabilité des skills sur un autre projet sans édition du code.

#### M4. `review001.md` non dépouillée et en contradiction avec `BOM.md`
- **Composants / Nets concernés :** `review/review001.md`, `BOM.md` §2.B, `LED1`, `R9`, `R10`
- **Constat & Proposition :** `review001.md` (verdict 🟢) propose trois bascules Basic Parts (`LED1` → `C2286`, `R9` → 27 kΩ `C17593`, `R10` → 5,1 kΩ `C27834`, Vout = 5,0353 V) ; aucune n'apparaît dans `TODO.md` et la BOM conserve `LED1` (`C22371297`, Extended), `R9` = 10 kΩ et `R10` = 1,91 kΩ (Extended). Or `BOM.md` §2.B affirme que « *toutes les opportunités d'optimisation directe vers le catalogue Basic Parts sont désormais intégralement concrétisées* », ce qui est faux tant que `R10` et `LED1` restent Extended. Procéder à l'arbitrage de `review001.md` selon `AGENTS.md` §5 (intégration dans `TODO.md` puis suppression du fichier), ou, si les points sont écartés, corriger la formulation de `BOM.md` §2.B.
- **Gain attendu :** Sas de revue propre, cohérence du discours BOM, et jusqu'à 6 $ de frais de bobine économisés par série si les bascules sont retenues.

#### M5. Nom du fichier projet EasyEDA incohérent entre quatre documents
- **Composants / Nets concernés :** `README.md` (lignes 176 et 196), `AUTOMATION.md` (lignes 65 et 125), `AGENTS.md` §4.6, arborescence `easyeda/`
- **Constat & Proposition :** Quatre désignations coexistent : `OBD2.eprj2`, `OBD2-Scanner.eprj2`, `ProPrj_OBD2-Scanner.epro2` et le fichier réellement versionné `easyeda/OBD2.epro2`. L'extension `.eprj2` n'existe pas. Aligner l'ensemble de la documentation sur le nom et le chemin réels du fichier versionné.
- **Gain attendu :** Instructions d'ouverture du projet exécutables sans tâtonnement par un nouvel arrivant ou un agent.

#### M6. Entrée `LI` de `U3` tirée à GND : comparateur L maintenu actif
- **Composants / Nets concernés :** `U3` pin 8 (`LI`) → `GND`, `U3` pin 2 (`LO`) en *No Connect*
- **Constat & Proposition :** Le raccordement à GND supprime bien le flottement (objectif de `TODO.md [M3]`), mais place `LI` en état bas : datasheet L9637D Table 5, `VLIlow` (−24 V à 0,45·VS) donne « *LO output status LOW* », c'est-à-dire l'étage de sortie de la ligne L activé en permanence. `LO` étant non connectée, il n'y a aucun courant ni risque, seul le comparateur reste sollicité. Préférer le raccordement de `LI` à `VCC` (rail `3.3V`) qui place la fonction L à l'état inactif/récessif, conformément à l'usage d'une entrée non utilisée.
- **Gain attendu :** État logique inactif sans ambiguïté sur une fonction non utilisée, consommation de repos minimale.

---

## Périmètre non couvert par cette revue

- **Layout / routage PCB :** non audité. `README.md` signale une synchronisation schéma → PCB non finalisée (`U8`, `D5`) et `TODO.md` §2.1 la liste comme tâche ouverte ; toute remarque de placement serait prématurée.
- **ERC/DRC :** non exécutables hors EasyEDA Pro. Les affirmations « ERC = 0 / DRC = 0 » de `BOM.md` et `README.md` n'ont pas pu être vérifiées et restent à confirmer par l'outil natif.
- **Contrôles automatisés exécutés :** `sync_semantics.py check` (67/67 composants, 100 % conforme) et `schematic_auditor.py` (3 observations, toutes déjà présentes dans `TODO.md`).
