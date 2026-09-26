# Référentiel Technique des Circuits Intégrés & Audit de Conformité (DATASHEETS)

Ce document constitue la **source de vérité technique** du projet **Scanner OBD-II ESP32**. Il synthétise les spécifications officielles des constructeurs (Espressif, NXP, STMicroelectronics, Texas Instruments, onsemi) issues des documents PDF archivés dans le répertoire [`datasheet/`](datasheet/), extrait les exigences rigoureuses d'implémentation électronique et de routage PCB, et audite la conformité point par point du circuit actuel.

---

## 1. Index des Fichiers Constructeurs Référencés

| Repère | Circuit Intégré | Fabricant | Rôle Fonctionnel | Fichier PDF Source Archivé |
| :--- | :--- | :--- | :--- | :--- |
| **`U1`** | **ESP32-S3-WROOM-1-N16R8** | Espressif Systems | SoC Dual-Core 240 MHz, Wi-Fi 2.4 GHz, BLE 5.0, USB natif, TWAI | [`datasheet/ESP32-S3-WROOM-1.pdf`](datasheet/ESP32-S3-WROOM-1.pdf) |
| **`U2`** | **TJA1051T/3/1J** | NXP Semiconductors | Transceiver CAN haute vitesse (5 Mbit/s) avec translation VIO 3.3V | [`datasheet/TJA1051T.pdf`](datasheet/TJA1051T.pdf) |
| **`U3`** | **E-L9637D013TR (L9637D)** | STMicroelectronics | Transceiver ligne K-Line ISO 9141 / KWP2000 bidirectionnel 12V | [`datasheet/E-L9637D013TR (L9637).pdf`](datasheet/E-L9637D013TR%20(L9637).pdf) |
| **`U4`** | **TPS54331DR** | Texas Instruments | Convertisseur Buck Step-Down 12V → 5V (3A, 570 kHz, Eco-mode) | [`datasheet/TPS54331.pdf`](datasheet/TPS54331.pdf) |
| **`U5`** | **LDL1117S33R** | STMicroelectronics | Régulateur linéaire LDO 5V → 3.3V faible bruit, PSRR 87 dB, 1.2A | [`datasheet/LDL1117S33R(DS_ldl1117).pdf`](datasheet/LDL1117S33R(DS_ldl1117).pdf) |
| **`U8`** | **NUP2105LT1G** | onsemi | Double diode TVS 24V différentielle protection transitoire bus CAN | [`datasheet/NUP2105L-D.PDF`](datasheet/NUP2105L-D.PDF) |
| **`U6`/`U7`** | **SESD05C** | Semiware | Diodes discrètes TVS 5V bidirectionnelles protection ESD USB D+/D- | Catalogue constructeur LCSC [`C720025`](BOM.md#L75-L76) |

---

## 2. Fiches Techniques Détaillées & Règles d'Implémentation

---

### U1 — SoC Wi-Fi & BLE : ESP32-S3-WROOM-1-N16R8

* **Fichier constructeur :** [`datasheet/ESP32-S3-WROOM-1.pdf`](datasheet/ESP32-S3-WROOM-1.pdf) (Espressif Systems)
* **Boîtier :** Module SMD 41 broches + Pad thermique central (25.5 × 18.0 mm).
* **Rôle électrique :** Traitement principal, protocole OBD-II, Wi-Fi 802.11 b/g/n, Bluetooth LE 5.0, contrôleur TWAI (CAN 2.0B), interface USB OTG native.

#### A. Spécifications & Limites Électriques
| Paramètre | Symbole | Min | Typique | Max | Unité | Remarques constructeur |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Tension d'alimentation** | VDD | 3.0 | 3.3 | 3.6 | V | Stabilité requise à ±5% sous fortes dynamiques de charge. |
| **Courant crête alimentation** | IDD_peak | 500 | — | — | mA | Exigence absolue lors des salves d'émission Wi-Fi TX. |
| **Limite absolue d'alimentation** | VDD_max | -0.3 | — | +3.6 | V | **Aucune tolérance 5V**. Risque de claquage irréversible. |
| **Tension sur les entrées GPIO** | VIO_in | -0.3 | — | VDD + 0.3 | V | Plafond strict à 3.60V (sous 3.3V). Diodes de clamp requises si risque. |
| **Seuil de reset (CHIP_PU / EN)** | VIL_EN / VIH_EN | — / 0.75 VDD | — | 0.25 VDD / — | V | Seuil haut d'activation à 2.475 V (pour VDD = 3.3V). |

#### B. Préconisations Constructeur — Schéma Électrique
1. **Temporisation Power-On-Reset (broche 3 - `EN`) :**
   * Pour éviter tout démarrage chaotique lors de la montée du rail 3.3V, la broche `EN` doit être maintenue au niveau bas jusqu'à ce que VDD atteigne 2.8V - 3.0V.
   * **Circuit RC externe obligatoire :** Résistance de pull-up R = 10 kΩ vers 3.3V et condensateur C = 1 µF vers GND (tau = 10 ms). Temps de montée de EN > 50 µs.
2. **Découplage d'Alimentation Local :**
   * Un condensateur réservoir Bulk d'au moins **10 µF** (faible ESR, céramique X5R/X7R de tension assignée >= 10V) doit être connecté directement entre la broche 2 (VDD) et la broche 1 (GND).
   * Un condensateur de découplage haute fréquence de **100 nF** en parallèle direct.
3. **Broches de Strapping & Boot :**
   * `GPIO0` (pin 27) : Doit être au niveau HAUT (High) au relâchement du reset pour démarrer depuis la Flash SPI. Doit pouvoir être tirée à la MASSE (Low) pour forcer le mode téléchargement ROM (Flash firmware de secours).
4. **Lignes USB D+ / D- :**
   * Connexion directe sur `IO20` (D+) et `IO19` (D-). L'ESP32-S3 intègre ses propres résistances de pull-up USB commutables par logiciel ; aucune pull-up externe ne doit être ajoutée sur D+ !

#### C. Préconisations Constructeur — Implantation & Routage PCB
* **Zone d'exclusion RF de l'antenne (Keepout / Clearance) :**
  * L'antenne méandre PCB intégrée doit être positionnée en débordement de carte ou affleurante en bordure.
  * **Interdiction stricte sur TOUTES les couches (All Layers) :** Aucun plan de masse (GND), aucune piste de signal, aucun plan d'alimentation, aucun composant métallique ne doit être présent sous l'antenne ni dans un rayon de **15 mm** autour de la zone rayonnante.
* **Pad thermique central (Ground EPAD - Pin 42) :**
  * Doit être solidement soudé au plan de masse de la carte hôte via une matrice de vias thermiques traversants (au moins 9 à 16 vias de perçage 0.3 mm) pour assurer l'évacuation thermique et la continuité de masse RF.
* **Réseau de Reset (`R15`, `C12`, `SW1`) :**
  * Doit être placé immédiatement contre la broche 3 (`EN`) (< 2 mm) pour éliminer toute boucle inductive susceptible de capter le champ électromagnétique 2.4 GHz de l'antenne voisine (risque de reset intempestif sous forte puissance radio TX).

#### D. Confrontation avec le Schéma Actuel
* [x] **Conforme :** Circuit RC de reset implémenté avec `R15` (10 kΩ) et `C12` (1 µF) sur la broche EN.
* [x] **Conforme :** Réservoir Bulk local `C11` (10 µF 25V 0805) et découplages `C1`, `C2` (100 nF) raccordés aux broches d'alimentation.
* [x] **Conforme :** Lignes USB D+/D- routées directement vers IO20/IO19 avec diodes ESD externes `U6`/`U7` sans pull-up parasite.
* [x] **Conforme :** Point de test `TP10` présent sur `IO0` et bouton poussoir `SW1` sur `EN` pour forcer le téléchargement et réinitialiser.

---

### U2 — Transceiver CAN Haute Vitesse : TJA1051T/3/1J

* **Fichier constructeur :** [`datasheet/TJA1051T.pdf`](datasheet/TJA1051T.pdf) (NXP Semiconductors)
* **Boîtier :** SOIC-8 (150 mil).
* **Rôle électrique :** Transceiver physique CAN haute vitesse ISO 11898-2:2016 et CAN FD (jusqu'à 5 Mbit/s) assurant l'interfaçage différentiel 5V du véhicule avec le domaine logique 3.3V de l'ESP32 via sa broche d'adaptation VIO.

#### A. Spécifications & Limites Électriques
| Paramètre | Symbole | Min | Typique | Max | Unité | Remarques constructeur |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Alimentation analogique** | VCC | 4.5 | 5.0 | 5.5 | V | **Obligatoirement 5V nominal**. Ne fonctionne pas sous 3.3V ! |
| **Alimentation I/O logique** | VIO | 2.8 | 3.3 | 5.5 | V | Relié au 3.3V pour adaptation directe aux GPIOs ESP32. |
| **Courant d'alimentation** | ICC | — | 45 | 70 | mA | En état dominant d'émission. |
| **Tension continue sur CANH / CANL** | VCANH/L | **-58.0** | — | **+58.0** | V | Tenue continue aux courts-circuits batterie / masse. |
| **Transitoires sur CANH / CANL** | V_transient | **-150** | — | **+100** | V | Selon normes automobiles ISO 7637-2 / 7637-3. |
| **Tension différentielle récessive** | Vdiff(r) | -500 | 0 | +50 | mV | CANH = 2.5V, CANL = 2.5V nominal. |
| **Tension différentielle dominante** | Vdiff(d) | 1.5 | 2.0 | 3.0 | V | CANH = 3.5V, CANL = 1.5V nominal. |

#### B. Préconisations Constructeur — Schéma Électrique
1. **Double Découplage HF Impératif :**
   * Broche 3 (VCC) : Condensateur céramique C >= 100 nF (qualifié 50V) vers GND pour fournir les fortes pointes d'injection de courant lors des transitions dominant/récessif.
   * Broche 5 (VIO) : Condensateur céramique C >= 100 nF vers GND pour filtrer la référence logique du comparateur RXD.
2. **Gestion de la Broche 8 (`S` - Silent Mode) :**
   * La broche 8 contrôle le mode silencieux. En interne, une résistance de pull-up la tire par défaut vers VIO (mode silencieux, émetteur désactivé).
   * **Règle impérative :** Pour un fonctionnement bidirectionnel normal (lecture et émission de requêtes OBD-II), la broche 8 doit être **fermement reliée à GND**.
3. **Terminaison de Ligne CAN Différentielle (120 Ω) :**
   * La spécification impose 120 Ω aux extrémités de la ligne. Sur prise OBD-II véhicule, la terminaison existe déjà dans le câblage du véhicule.
   * L'adjonction d'un cavalier (`JP1`) permettant de déconnecter la résistance `R8` (120 Ω) est la solution conforme recommandée : **JP1 OUVERT en voiture / FERMÉ sur banc de test**.

#### C. Préconisations Constructeur — Implantation & Routage PCB
* **Lignes différentielles CANH / CANL :**
  * Pistes à impédance différentielle contrôlée Zdiff = 120 Ω ± 10%.
  * Routage strictement symétrique, parallèle, de longueur identique (tolérance de désalignement / skew < 1 mm), avec angles à 45° ou arrondis.
* **Positionnement des Protections Transitoires :**
  * La diode de protection TVS (`U8` - NUP2105L) doit être implantée **au plus près immédiat du connecteur OBD-II `J1`** (< 5 mm). Les transitoires du faisceau doivent frapper la TVS avant d'atteindre le transceiver `U2`.
* **Proximité du Découplage :**
  * `C15` (sur Pin 3) et `C3` (sur Pin 5) doivent être implantés à moins de 2 mm des broches respectives avec liaison très courte au plan de masse.

#### D. Confrontation avec le Schéma Actuel
* [x] **Conforme :** VCC alimenté par le rail régulé +5V (Buck) avec découplage dédié `C15` (100 nF 50V).
* [x] **Conforme :** VIO alimenté par le rail 3.3V propre (LDO) avec découplage `C3` (100 nF 50V).
* [x] **Conforme :** Broche 8 (`S`) raccordée à GND.
* [x] **Conforme :** Cavalier `JP1` et résistance `R8` (120 Ω) conformes pour la gestion banc/voiture.
* [x] **Conforme :** Protection TVS `U8` (NUP2105L) raccordée sur CANH/CANL.

---

### U3 — Transceiver K-Line ISO 9141 : E-L9637D013TR (L9637D)

* **Fichier constructeur :** [`datasheet/E-L9637D013TR (L9637).pdf`](datasheet/E-L9637D013TR%20(L9637).pdf) (STMicroelectronics)
* **Boîtier :** SOIC-8.
* **Rôle électrique :** Transceiver spécifique assurant la transmission bidirectionnelle semi-duplex (Half-Duplex) sur la ligne mono-fil K-Line 12V (ISO 9141-2 et ISO 14230 KWP2000).

#### A. Spécifications & Limites Électriques
| Paramètre | Symbole | Min | Typique | Max | Unité | Remarques constructeur |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Tension d'alimentation batterie** | VS (Pin 7) | 4.5 | 12.0 | 36.0 | V | Fonctionnement nominal sous 12V habitacle. |
| **Alimentation logique** | VCC (Pin 8) | **3.0** | **3.3 / 5.0** | **7.0** | V | Plage de service logique (Table 5). 3.3V pleinement supporté. |
| **Limite absolue batterie VS** | VS_max | -24.0 | — | +40.0 | V | Protection intégrée contre l'inversion jusqu'à -24V. |
| **Transitoires batterie VS** | VS_transient | -100 | — | +100 | V | Impulsions transitoires ISO 7637-1. |
| **Limite absolue broche K (Pin 6)** | VK_max | -24.0 | — | VS + 0.3 | V | Borne supérieure plafonnée par VS (max 40V). |
| **Limite absolue entrées logiques TX** | VTX_max | -0.3 | — | VCC + 0.3 | V | Plafonnée par la tension logique VCC. |
| **Seuil de détection K-Line** | VK_th | 0.45 VS | 0.50 VS | 0.55 VS | V | Seuil comparateur proportionnel à la tension batterie. |
| **Coupure thermique interne** | TJ_sd | 150 | 175 | — | °C | Protection contre l'échauffement en court-circuit. |

#### B. Préconisations Constructeur — Schéma Électrique
1. **Brochage Exact & Identification des Broches (Attention aux méprises !) :**
   * **Pin 1 : `RX`** (Sortie logique vers MCU - Étage push-pull avec pull-up interne $R_{RX} \approx 10\,\text{k}\Omega$ vers $V_{CC}$ ; $V_{RXH} = V_{CC} - 0.1\,\text{V}$).
   * **Pin 2 : `LO`** (Loop Output - non utilisé, laisser ouvert).
   * **Pin 3 : `LI`** (Loop Input - non utilisé, à raccorder à GND).
   * **Pin 4 : `TX`** (Entrée logique de commande d'émission depuis le MCU).
   * **Pin 5 : `GND`** (Masse de référence).
   * **Pin 6 : `K`** (Ligne bidirectionnelle haute tension 12V vers prise OBD).
   * **Pin 7 : `VS`** (Alimentation haute tension batterie 12V).
   * **Pin 8 : `VCC`** (Alimentation logique du circuit interne).
2. **Conformité & Sécurité de l'Alimentation Logique VCC (Pin 8) :**
   * *Spécification ST officielle (Table 5 & 6) :* La plage de fonctionnement de $V_{CC}$ s'étend de **3.0 V à 7.0 V** (le minimum de 4.5V de la datasheet concerne uniquement la tension batterie $V_S$). Un fonctionnement sous $V_{CC} = 3.3\,\text{V}$ est donc 100% conforme.
   * *Structure interne de RX et danger du 5V :* La broche 1 (`RX`) possède une résistance de pull-up interne active reliée à $V_{CC}$ ($R_{RX} \approx 10\,\text{k}\Omega$). Elle n'est PAS un collecteur ouvert pur.
   * *Protection vitale de l'ESP32-S3 :* Les GPIOs de l'ESP32-S3 ne sont **pas tolérants 5V** (limite absolue à $3.6\,\text{V}$). Si $V_{CC}$ était alimenté en 5V, RX délivrerait ~4.9V dans le GPIO4, entraînant sa destruction immédiate.
   * *Décision de conception :* **VCC doit impérativement rester raccordé au rail `3.3V`** avec son condensateur de découplage de 100 nF (`C4`).
3. **Raccordement Sécurisé de VS (Pin 7) :**
   * Bien que `U3` tolère -24V sur VS, le raccorder en aval direct de la protection anti-inversion `Q1` et du fusible `F1` (rail `+12V_PROT`) protège le composant contre les transitoires violents et évite toute fuite.
4. **Résistance de Pull-Up Normalisée K-Line (`R16`) :**
   * La norme ISO 9141-2 impose une résistance de pull-up comprise entre 510 Ω et 1 kΩ vers le 12V pour charger la capacité parasite du faisceau (C <= 2 nF) avec un temps de montée tr < 2 µs.
   * R16 (1 kΩ) reliée à `+12V_PROT` dissipe en état dominant :
     P = V^2 / R = (14.4 V)^2 / 1000 Ω ≈ 0.207 W.
   * L'utilisation d'un boîtier **1206 (250 mW)** est strictement obligatoire.

#### C. Préconisations Constructeur — Implantation & Routage PCB
* **Protection TVS `D5` (`SMF24CA`) :**
  * Doit être placée à l'entrée immédiate de la broche 7 d'OBD-II avant la broche 6 de `U3`.
* **Dissipation thermique de `R16` :**
  * La résistance `R16` doit être dégagée des zones thermiquement sensibles (LDO, quartz, transceivers) et entourée de cuivre généreux pour évacuer ses ~210 mW lors des transferts K-Line soutenus.
* **Résistances d'amortissement série (`R1`, `R2`) :**
  * Placer `R1` (10 Ω sur RX) et `R2` (10 Ω sur TX) à mi-chemin entre `U3` et l'ESP32 pour amortir les réflexions et limiter les courants de fuite.

#### D. Confrontation avec le Schéma Actuel & Points d'Arbitrage (TODO 1.1)
* [x] **[CONFORME / SÉCURISÉ] Alimentation logique VCC (Pin 8) sous +3.3V :** VCC opère sous le rail 3.3V (plage autorisée 3.0V à 7.0V). Protège le GPIO4 de l'ESP32-S3 (non tolérant 5V) contre les ~4.9V qu'injecterait le pull-up interne actif de RX si VCC était relié au +5V.
* [ ] **[ACTION REQUISE - TODO 1.1] Sécuriser le net de la broche 7 (VS) :** Raccorder physiquement la broche 7 de `U3` au rail `+12V_PROT` (après `Q1`/`F1`) et rectifier la coquille documentaire dans [`HARDWARE.md`](HARDWARE.md) qui mentionnait `U3(3)`.
* [x] **Conforme :** Résistance normalisée `R16` (1 kΩ) qualifiée en boîtier 1206 (250 mW) sur `+12V_PROT`.
* [x] **Conforme :** Diode TVS `D5` (24V) présente sur la ligne physique K-Line.

---

### U4 — Régulateur Buck Step-Down : TPS54331DR

* **Fichier constructeur :** [`datasheet/TPS54331.pdf`](datasheet/TPS54331.pdf) (Texas Instruments)
* **Boîtier :** SOIC-8.
* **Rôle électrique :** Abaisseur de tension à découpage haute fréquence (570 kHz, 3A) convertissant le 12V automobile en +5V régulé pour alimenter le transceiver CAN et le régulateur LDO 3.3V avec un rendement supérieur à 85%.

#### A. Spécifications & Limites Électriques
| Paramètre | Symbole | Min | Typique | Max | Unité | Remarques constructeur |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Plage de tension d'entrée** | VIN | 3.5 | 12.0 | 28.0 | V | Plage d'exploitation recommandée. |
| **Tension de sortie** | VOUT | 0.8 | 5.0 | 25.0 | V | Ajustable par pont diviseur externe. |
| **Courant de sortie continu** | IOUT | — | — | 3.0 | A | Avec diode externe et inductance adaptées. |
| **Fréquence de découpage** | f_sw | 400 | 570 | 740 | kHz | Fixée en interne par oscillateur. |
| **Référence interne de tension** | Vref | 0.784 | **0.800** | 0.816 | V | Précision ±2% sur -40°C à +125°C. |
| **LIMITE ABSOLUE ENTRÉE VIN** | VIN_abs | **-0.3** | — | **+30.0** | V | **CRITIQUE : Claquage silicium au-delà de 30.0V !** |
| **Limite absolue broche Phase (PH)** | VPH_abs | -0.6 | — | 30.0 | V | Tolérance transitoire -1.0V pendant < 10 ns. |
| **Limite absolue broche BOOT** | VBOOT_abs | — | — | VPH + 8 | V | Pompe de charge interne. |
| **Transconductance ampli d'erreur** | gm | 70 | 92 | 115 | µA/V | Sortie sur broche COMP (Ro = 8.4 MΩ). |

#### B. Préconisations Constructeur — Schéma & Dimensionnement
1. **Protection Surtension d'Entrée Face au Plafond de 30.0 V :**
   * *Alerte majeure TI :* La tension maximale absolue admissible sur la broche 2 (`VIN`) est de **30.0 V**. En environnement automobile, lors des transitoires d'alternateur (*Load Dump*), la tension peut dépasser 40V à 60V.
   * *Exigence de serrage :* La diode TVS d'entrée `D1` doit impérativement brider la surtension résiduelle sous 30.0V.
   * *Arbitrage technique (TODO 1.1) :* La diode `SMBJ18A` actuelle bride à VCL = 29.2 V (marge de 0.8V). L'adoption préconisée d'une `SMBJ16A` (VRWM = 16 V, VCL = 26.0 V) dégage une marge de sécurité robuste de **4.0 V** sous le seuil destructeur.
2. **Condensateurs d'Entrée (CIN) :**
   * Condensateur de découplage HF céramique de **100 nF 50V X7R (`C14`)** obligatoirement placé directement sur la broche 2 (`VIN`).
   * Condensateur réservoir Bulk de **10 µF 50V X5R (`C7`)** pour fournir les impulsions de courant de hachage.
3. **Diode Schottky de Roue Libre (`D2`) :**
   * Doit être une diode Schottky ultra-rapide (faible VF < 0.5V), tenue en tension inverse >= 40 V et courant moyen assigné >= 3 A. La référence `SS34` (40V, 3A, boîtier SMA) est conforme aux préconisations TI.
4. **Condensateur de Bootstrap (`C5`) :**
   * Céramique de **0.1 µF à 1 µF** connecté entre `BOOT` (pin 1) et `PH` (pin 8). Un modèle 1 µF 50V X5R (`C15849`) est implémenté.
5. **Inductance de Puissance (`L1`) :**
   * Valeur nominale calculée : 10 µH pour un ripple de courant compris entre 20% et 40%.
   * Courant de saturation : Isat >= 3.0 A. Le composant blindé `YNR6045-100M` (Isat = 3.6 A) garantit qu'aucune saturation magnétique n'intervient.
6. **Pont Diviseur de Feedback (`R9`, `R10`) :**
   * VOUT = 0.800 V * (1 + R9 / R10) = 0.8 * (1 + 10 kΩ / 1.91 kΩ) = 4.988 V ≈ 5.0 V.
   * Conforme à ±0.24% de la consigne nominale.
7. **Réseau de Compensation Type II (`COMP` - Pin 6) :**
   * Triplet dimensionné : R11 = 10 kΩ, C9 = 3.3 nF (zéro stabilisateur fz ≈ 4.8 kHz annulant le pôle de charge), complété par C13 = 220 pF (pôle HF de réjection du bruit de découpage fp ≈ 77 kHz).
   * Modélisation validée via le skill `buck-compensation` : **Marge de phase = 66.3°**, marge de gain > 20 dB (stabilité inconditionnelle).

#### C. Préconisations Constructeur — Implantation & Routage PCB (Section 10 Datasheet TI)
* **Boucle de Courant Critique Haute Fréquence (di/dt) :**
  * La maille formée par `C14` / `C7` (VIN) → Broche 2 (`VIN`) → Broche 8 (`PH`) → Diode `D2` → Masse GND de `C14` / `C7` doit présenter **une surface minimale absolue**.
  * Toute inductance parasite sur cette maille génère des surtensions inductives (V = L * di/dt) et du bruit électromagnétique rayonné.
* **Nœud de Commutation PH :**
  * La piste reliant la broche 8, la diode `D2` et l'inductance `L1` doit être courte et large, mais confinée géométriquement pour limiter le couplage capacitif (dv/dt).
* **Isolement Strict du Nœud Sensible COMP / VSENSE :**
  * Les pistes et composants du réseau de compensation (`R11`, `C9`, `C13`) et du pont diviseur (`R9`, `R10`) doivent être situés **à l'opposé strict de la broche PH** et protégés par un plan de masse.
  * Interdiction absolue de faire transiter les pistes de commutation ou de bootstrap sous les pistes de feedback.

#### D. Confrontation avec le Schéma Actuel & Points d'Arbitrage
* [x] **Conforme :** Triplet de compensation de boucle (10 kΩ / 3.3 nF / 220 pF) validé pour f_sw = 570 kHz avec marge de phase de 66.3°.
* [x] **Conforme :** Inductance blindée 10 µH (3.6A) et diode Schottky SS34 (40V 3A).
* [x] **Conforme :** Filtrage d'entrée avec céramique 100 nF (`C14`) au plus près de VIN et 10 µF (`C7`).
* [x] **Conforme :** Capacité de sortie optimisée en Basic Parts (2 × 10 µF 50V `C8` // `C16`) divisant par deux l'ESR.
* [ ] **[POINT D'ARBITRAGE - TODO 1.1] Optimisation TVS D1 :** Évaluer la bascule de `SMBJ18A` vers `SMBJ16A` pour porter la marge de protection à 4.0V sous les 30.0V de limite absolue.

---

### U5 — Régulateur LDO Faible Bruit : LDL1117S33R

* **Fichier constructeur :** [`datasheet/LDL1117S33R(DS_ldl1117).pdf`](datasheet/LDL1117S33R(DS_ldl1117).pdf) (STMicroelectronics)
* **Boîtier :** SOT-223.
* **Rôle électrique :** Régulateur linéaire Low Dropout (LDO) abaissant le rail +5V (Buck) vers le rail 3.3V logique avec une réjection d'alimentation remarquable (PSRR 87 dB @ 120 Hz, > 60 dB @ 100 kHz) éliminant l'ondulation résiduelle 570 kHz pour purifier l'alimentation du SoC ESP32 et de son émetteur-récepteur radio 2.4 GHz.

#### A. Spécifications & Limites Électriques
| Paramètre | Symbole | Min | Typique | Max | Unité | Remarques constructeur |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Tension d'entrée d'exploitation** | VIN | 2.5 | 5.0 | 18.0 | V | Alimenté ici par le rail +5V régulé. |
| **Tension de sortie fixe** | VOUT | 3.234 | **3.300** | 3.366 | V | Précision ±2% sur -40°C à +125°C. |
| **Courant de sortie maximal** | IOUT | **1.2** | — | — | A | Capacité en courant largement dimensionnée. |
| **Tension de chute (Dropout)** | Vdrop | — | 350 | 600 | mV | À pleine charge 1.2A (< 150 mV à 500 mA). |
| **Tension d'entrée maximale absolue** | VIN_abs | -0.3 | — | +20.0 | V | Marge totale face aux 5V d'entrée. |
| **Courant de repos (Quiescent)** | Iq | — | 250 | 500 | µA | Très faible consommation au repos. |
| **Réjection de mode commun (PSRR)** | PSRR | 75 | 87 | — | dB | À 120 Hz (garantit une tension ultra-silencieuse). |

#### B. Préconisations Constructeur — Stabilité de Boucle & Capacités
1. **Condensateur d'Entrée (CIN) :**
   * Recommandation ST : CIN >= 1 µF céramique X5R/X7R placé à proximité de la broche 3 (`VIN`). Ce rôle est parfaitement assuré par le rail +5V et les capacités de sortie Buck `C8`/`C16` (20 µF).
2. **Condensateur de Sortie (COUT) — Règle de Stabilité Inconditionnelle :**
   * *Avertissement constructeur ST :* Le régulateur `LDL1117` intègre une boucle interne rapide qui exige un condensateur de sortie COUT >= 4.7 µF avec une résistance série équivalente (ESR) comprise entre 10 mΩ et 2 Ω pour garantir sa marge de phase.
   * *Audit de notre circuit :*
     * Dans notre schéma actuel, `C6` (immédiatement en sortie de U5 sur le net `3.3V_PRE`) a une valeur de **1 µF** (`C15849`).
     * Le condensateur réservoir Bulk `C11` (**10 µF**) se situe juste après la perle de ferrite `FB1` sur le net `3.3V`.
     * **Préconisation d'amélioration :** Porter `C6` à **4.7 µF** ou **10 µF 50V 1206 (`C13585` - Basic Part)** directement sur `3.3V_PRE` avant `FB1` sécurise à 100% la marge de phase intrinsèque du LDO selon la courbe de stabilité de la datasheet ST.

#### C. Préconisations Constructeur — Implantation & Thermique
* **Bilan Thermique :**
  * Sous consommation nominale (ESP32 en écoute + transceivers ≈ 150 mA) :
    Pdiss = (5.0 V - 3.3 V) * 0.15 A = 0.255 W.
  * Lors d'une rafale Wi-Fi prolongée (I = 450 mA) :
    Pdiss = (5.0 V - 3.3 V) * 0.45 A = 0.765 W.
* **Règles de Layout SOT-223 :**
  * Le Tab central du boîtier SOT-223 est relié en interne à la broche 2 (`VOUT`).
  * Il doit être étendu sur le PCB par une zone de cuivre de dissipation thermique d'au moins **100 à 150 mm²** reliée à la couche Bottom par des vias thermiques pour maintenir l'échauffement sous ΔT < 30°C dans le boîtier fermé du scanner.

#### D. Confrontation avec le Schéma Actuel
* [x] **Conforme :** Tension d'entrée 5V et différentiel de 1.7V assurant un fonctionnement très au-dessus du dropout (350 mV).
* [x] **Conforme :** Perle de ferrite `FB1` (120 Ω @ 100 MHz) associée pour créer un filtre en Pi avec découplages.
* [!] **Point d'attention (Stabilité) :** Remplacer ou compléter `C6` (1 µF) par une capacité >= 4.7 µF (ex. 10 µF `C13585` Basic Part) avant `FB1` pour respecter scrupuleusement la préconisation constructeur ST.

---

### U8 — Réseau Double TVS Bus CAN : NUP2105LT1G

* **Fichier constructeur :** [`datasheet/NUP2105L-D.PDF`](datasheet/NUP2105L-D.PDF) (onsemi)
* **Boîtier :** SOT-23 (Pin 1: CANH, Pin 2: CANL, Pin 3: GND).
* **Rôle électrique :** Protection antistatique (ESD) et absorption des surtensions transitoires différentielles et de mode commun sur le bus CAN automobile selon les normes IEC 61000-4-2 et ISO 7637-3.

#### A. Spécifications & Limites Électriques
| Paramètre | Symbole | Min | Typique | Max | Unité | Remarques constructeur |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Tension inverse de maintien** | VRWM | — | — | **24.0** | V | Reste transparent sous excursions CAN et 24V. |
| **Tension d'avalanche (Breakdown)** | VBR | 26.2 | 27.5 | 32.0 | V | À IT = 1.0 mA. |
| **Puissance crête impulsionnelle** | Ppk | **350** | — | — | W | Onde standard 8/20 µs. |
| **Tension de serrage crête** | VC | — | 35.0 | 44.0 | V | À IPP = 8.0 A (8/20 µs). |
| **Capacité parasite de jonction** | Cj | — | **15** | **30** | pF | À VR = 0 V, f = 1 MHz. |
| **Tenue décharge ESD (Contact)** | VESD_contact | ±30 | — | — | kV | Norme IEC 61000-4-2 (standard = 8 kV). |
| **Tenue décharge ESD (Air)** | VESD_air | ±30 | — | — | kV | Norme IEC 61000-4-2 (standard = 15 kV). |

#### B. Préconisations Constructeur — Implantation & Routage PCB
* **Implantation Frontière Immédiate :**
  * Le composant `U8` doit être placé **au plus près des broches 6 et 14 du connecteur OBD-II `J1`** (< 5 mm).
  * Les pistes différentielles `CANH` et `CANL` doivent impérativement **traverser les pastilles 1 et 2 de `U8`** avant de se diriger vers le transceiver `U2` et la terminaison `R8`. Aucun tronçon en antenne (stub) n'est toléré.
* **Inductance Parasite de Masse :**
  * La broche 3 (GND) doit être connectée au plan de masse de référence par une piste large et un via dédié immédiat. Toute inductance parasite sur le retour de masse réduit l'efficacité d'écrêtage face aux fronts raides (< 1 ns) d'une décharge ESD.

#### C. Confrontation avec le Schéma Actuel
* [x] **Conforme :** Broche 1 reliée à CANH, Broche 2 reliée à CANL, Broche 3 reliée à GND.
* [x] **Conforme :** Capacité parasite de 15 pF parfaitement compatible avec le débit de 500 kbps / 1 Mbps du diagnostic automobile.

---

### U6 / U7 — Diodes ESD USB : SESD05C

* **Référence constructeur :** `SESD05C` (Semiware) / LCSC [`C720025`](BOM.md#L75-L76).
* **Boîtier :** SOD-323 (composant discret 2 broches).
* **Rôle électrique :** Diodes TVS bidirectionnelles assurant la protection antistatique (ESD) des lignes de données USB Full-Speed `USB_D+` et `USB_D-`.
* **Spécifications clés :**
  * Tension de maintien : VRWM = 5.0 V.
  * Capacité parasite ultra-faible : Cj < 3 pF (garantit l'absence de distorsion des fronts rapides de la communication USB).
  * Tenue ESD : ±15 kV au contact selon IEC 61000-4-2.
* **Règles d'implantation :**
  * Implantées au contact direct des pastilles A6/B6 (`D+`) et A7/B7 (`D-`) de la prise USB-C `J2`.

---

## 3. Matrice de Synthèse & Audit de Conformité aux Préconisations

| IC | Préconisation Constructeur | Implémentation Scanner OBD-II | Statut Audit | Action Requise / Échéance |
| :--- | :--- | :--- | :---: | :--- |
| **`U1`** (ESP32-S3) | Temporisation RC Power-On sur EN (tau >= 10 ms) | R15 = 10 kΩ, C12 = 1 µF (tau = 10 ms) | **CONFORME** | Aucune. |
| **`U1`** (ESP32-S3) | Courant alimentation >= 500 mA crête | LDO U5 calibré à 1.2 A max continu | **CONFORME** | Aucune. |
| **`U1`** (ESP32-S3) | Réservoir Bulk local >= 10 µF aux pins 1-2 | C11 = 10 µF 25V 0805 (< 2 mm) | **CONFORME** | Aucune. |
| **`U1`** (ESP32-S3) | Exclusion de cuivre sous antenne (All Layers) | Keepout multicouche 15 mm prévu | **CONFORME** | À valider au Floorplanning (Phase 2). |
| **`U2`** (TJA1051T) | Alimentation analogique VCC = 5.0 V nominal | Rail régulé +5V (Buck) avec C15 = 100 nF | **CONFORME** | Aucune. |
| **`U2`** (TJA1051T) | Adaptation I/O VIO = 3.3 V pour MCU 3.3V | Rail 3.3V (LDO) avec C3 = 100 nF | **CONFORME** | Aucune. |
| **`U2`** (TJA1051T) | Broche 8 (`S`) tirée à GND pour mode actif | Raccordée en direct au net GND | **CONFORME** | Aucune. |
| **`U2`** (TJA1051T) | Protection transitoire différentielle CAN | Double TVS U8 (NUP2105L 24V) | **CONFORME** | Aucune. |
| **`U3`** (L9637D) | Alimentation logique VCC entre 3.0V et 7.0V | Raccordé au rail régulé 3.3V (C4 = 100 nF) | **CONFORME** | Aucune (VCC = 3.3V protège le GPIO4 de l'ESP32-S3 non tolérant 5V). |
| **`U3`** (L9637D) | **Alimentation batterie VS sur rail sécurisé** | **Mention erronée U3(3) dans doc** | **ACTION REQUISE** | **[TODO 1.1] Relier Pin 7 à `+12V_PROT`.** |
| **`U3`** (L9637D) | Pull-up normalisée ISO 9141-2 (1 kΩ) | R16 = 1 kΩ en boîtier 1206 (250 mW) | **CONFORME** | Aucune. |
| **`U4`** (TPS54331) | **Plafond absolu d'entrée VIN <= 30.0 V** | TVS D1 VCL = 29.2 V (marge 0.8V) | **ATTENTION** | **[TODO 1.1] Évaluer TVS SMBJ16A.** |
| **`U4`** (TPS54331) | Découplage HF direct sur pin 2 (`VIN`) | C14 = 100 nF 50V X7R (< 1.5 mm) | **CONFORME** | Aucune. |
| **`U4`** (TPS54331) | Diode Schottky >= 40 V, >= 3 A | Diode SS34 (40V, 3A, SMA) | **CONFORME** | Aucune. |
| **`U4`** (TPS54331) | Stabilité Type II (f_c ≈ 20 kHz, marge > 60°) | R11 = 10 k, C9 = 3.3 n, C13 = 220 p (marge 66.3°) | **CONFORME** | Modélisé & validé par skill buck. |
| **`U5`** (LDL1117) | Capacité de sortie COUT >= 4.7 µF pour stabilité | C6 = 1 µF sur 3.3V_PRE + C11 = 10 µF | **ATTENTION** | **Passer C6 à 10 µF Basic Part.** |
| **`U8`** (NUP2105L) | Placement frontière direct sur connecteur | U8 à < 5 mm de J1 (pistes traversantes) | **CONFORME** | Règle fixée pour Phase 2. |

---

## 4. Synthèse Opérationnelle pour l'Implantation PCB (Phases 2 & 3)

1. **Priorité 1 — Boucle Buck U4 (SW / PH) :** Implanter `C14`, `C7`, `U4`, `D2` et `L1` en cluster ultra-compact à l'Ouest. Eloigner formellement le réseau COMP (`R11`, `C9`, `C13`) de la broche 8 (PH).
2. **Priorité 2 — Frontière d'Entrée & ESD :** Les composants de clamp (`D1`, `D5`, `U8`, `U6`, `U7`) doivent intercepter physiquement les signaux directement au ras des broches des connecteurs (`J1` OBD-II et `J2` USB-C) avant toute entrée dans les transceivers ou le microcontrôleur.
3. **Priorité 3 — Zone Radio ESP32 :** Maintenir la zone d'exclusion RF absolue sous l'antenne méandre, implanter `C11` (10 µF) et le réseau de reset `C12`/`R15` au plus près des broches 1, 2 et 3.
4. **Priorité 4 — Dissipation Thermique :** Prévoir des surfaces de cuivre généreuses et des réseaux de vias thermiques pour le P-MOS `Q1` (60V), le LDO `U5` (SOT-223), la résistance de pull-up K-Line `R16` (1206) et le pad central de l'ESP32 `U1`.
