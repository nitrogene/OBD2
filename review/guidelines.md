# Guide du Reviewer — Scanner OBD-II ESP32

Bienvenue ! Ce document définit les consignes, exigences techniques et standards de rédaction destinés à tout **reviewer** (modèle d'IA ou ingénieur humain) intervenant sur le projet **Scanner OBD-II ESP32**.

L'objectif d'une revue est d'apporter un regard critique et rigoureux sur le schéma électrique, le layout PCB, le routage, la conformité automobile/CEM, la nomenclature (BOM) ou le firmware, afin de garantir un matériel fiable, sécurisé et fabricable au meilleur coût.

---

## 1. Format & Convention de Nommage

### Nom du fichier
Déposez votre revue dans le dossier `review/` sous la forme :
`review/reviewXXX.md` *(ex. `review001.md`, `review_schema_01.md`, `review_pcb_02.md`)*.

> [!NOTE]
> **Cycle de vie :** Une fois votre fichier de revue déposé, l'équipe projet (l'utilisateur et l'agent de développement) analysera vos remarques, arbitrera chaque point, intégrera les actions retenues dans `TODO.md`, puis **supprimera** votre fichier `reviewXXX.md` pour signifier qu'il a été intégralement traité et laisser le sas propre pour les revues suivantes.

### En-tête obligatoire (Métadonnées)
Toute revue **doit impérativement débuter** par ce bloc de métadonnées pour assurer la traçabilité :

```markdown
# Revue Technique : [Titre court et explicite]

- **Nom du Reviewer / Agent :** [Ex. Claude 3.7 Sonnet, GPT-4o, Expert Hardware, etc.]
- **Date :** [AAAA-MM-JJ ou JJ/MM/AAAA]
- **Périmètre audité :** [Schéma électrique P1 / PCB Layout / Routage / BOM / Architecture / Firmware]
- **Version / Référence examinée :** [Commit Git hash ou version des documents/images audités]
- **Verdict global :** [🟢 Approuvé / 🟠 Approuvé avec réserves / 🔴 Rejeté (corrections critiques nécessaires)]
```

---

## 2. Contexte Matériel & Pièges à Éviter (À Lire Avant d'Auditer)

Pour éviter les fausses alertes et les remarques hors sujet, vous **devez impérativement** intégrer les contraintes fondamentales du projet :

1. **Périmètre véhicule : 12V VL exclusivement**
   - Le scanner est conçu pour les véhicules légers de tourisme (batterie 12.6V, alternateur 14.4V, transitoires modérés).
   - **Ne pas sur-spécifier** pour des réseaux 24V poids-lourds (le choix du régulateur Buck TPS54331 30V protégé par TVS SMBJ18A et P-MOSFET 60V est validé et dimensionné pour ce périmètre).

2. **MCU Cible : ESP32-S3 (≠ ESP32 classique)**
   - Le microcontrôleur est un **ESP32-S3-WROOM-1**.
   - *Attention au brochage :* Les canaux ADC compatibles avec le Wi-Fi actif sont situés sur **ADC1 (GPIO1 à GPIO10)**, contrairement à l'ESP32 classique.
   - *USB :* L'ESP32-S3 intègre un contrôleur USB OTG natif sur les broches GPIO19 (D-) et GPIO20 (D+).

3. **Contraintes de fabrication & Coûts JLCPCB**
   - PCB standard **2 couches** (plans de masse massifs Top et Bottom avec vias de couture).
   - **Priorité absolue aux *Basic Parts* JLCPCB :** Toute modification de composant passif ou actif doit privilégier les pièces de base du catalogue LCSC/JLCPCB pour éviter les frais d'outillage additionnels (*Extended part changeover fee*).

4. **Consulter l'état d'avancement réel**
   - Avant de lever une alerte, parcourez brièvement [`TODO.md`](../TODO.md), [`HARDWARE.md`](../HARDWARE.md) et [`BOM.md`](../BOM.md).
   - De nombreuses remarques antérieures sont déjà traitées ou arbitrées (ex. cavalier JP1 sur terminaison CAN, diode de clamp D6, condensateur C13 sur broche COMP, etc.).

---

## 3. Classification Obligatoire par Ordre de Criticité

Vos remarques doivent être rigoureusement hiérarchisées en 3 niveaux :

### 🔴 1. Bloquant / Critique (*High / Critical*)
*Ce qui empêche le circuit de fonctionner ou risque de le détruire.*
- Risque de destruction de composant, surtension, surintensité, inversion de polarité non protégée.
- Dépassement des valeurs limites absolues (*Absolute Maximum Ratings* : $V_{DS}$, $V_{GS}$, $V_{IN}$, dissipation thermique $T_J$).
- Court-circuit franc, violation bloquante ERC/DRC, broche vitale laissée en l'air (Reset, Boot, Alimentation).
- Impossibilité physique d'établir la communication (lignes CAN inversées, niveaux K-Line non conformes ISO 9141).

### 🟠 2. Important (*Medium*)
*Ce qui altère la robustesse, la CEM ou la fiabilité en environnement automobile.*
- Découplage insuffisant ou condensateurs placés trop loin (> 2 mm des broches d'alimentation).
- Mauvaise gestion des boucles critiques de commutation (Buck : boucle SW - L1 - D2 - Cout trop large générant du rayonnement EMI).
- Immunité aux parasites insuffisante (broche EN sans filtre RC, transitoires ESD non dérivées au connecteur OBD).
- Marge de régulation limite (dropout LDO, compensation de boucle avec marge de phase < 45°).
- Diode anti-retour manquante entre alimentation USB et alimentation véhicule.

### 🟢 3. Mineur / Suggestion (*Low / Info*)
*Ce qui optimise le coût, la fabricabilité ou l'ergonomie.*
- Optimisation de nomenclature (BOM) : remplacement d'une pièce *Extended* par une *Basic Part* équivalente.
- Clarté de la sérigraphie (repères de polarité, identification des cavaliers ex. `JP1: Shunt=Bench / Open=Car`).
- Visibilité des voyants (ajustement de résistance LED) ou accessibilité des points de test (`TP1` à `TP11`).
- Lisibilité et propreté du schéma ou de la documentation.

---

## 4. Ce qu'on Attend d'une Remarque bien Rédigée

Pour que votre retour soit directement actionnable, chaque remarque doit contenir :

1. **Précision chirurgicale :**
   - Citez les **désignateurs exacts** (`U4`, `R12`, `C10`, `TP9`).
   - Nommez les **nets exacts** (`+12V_PROT`, `CANH`, `ESP_EN`, `VBAT_SENSE`).
   - Indiquez le **numéro et nom de broche** (`pin 2 VIN de U4`).

2. **Démonstration technique (Pourquoi ?) :**
   - Ne vous limitez pas à un simple constat subjectif.
   - Appuyez votre analyse sur un **calcul**, une **formule**, un **extrait de datasheet constructeur** ou une **norme** (ISO 11898-2, ISO 9141-2, ISO 7637-2).

3. **Solution concrète clé en main (Comment corriger ?) :**
   - Proposez une solution précise : valeur, tolérance, boîtier/empreinte (0603, 0805, SOT-23...), référence fabricant exacte et **code LCSC**.
   - Précisez si votre proposition correspond à une *Basic Part* JLCPCB.

---

## 5. Modèle Type de Revue (`reviewXXX.md`)

Copiez et complétez le template ci-dessous dans votre fichier `review/reviewXXX.md` :

```markdown
# Revue Technique : [Titre court de votre audit]

- **Nom du Reviewer / Agent :** [Votre nom / modèle d'IA]
- **Date :** [AAAA-MM-JJ]
- **Périmètre audité :** [Schéma P1 / PCB Layout / BOM / Routage]
- **Version / Référence examinée :** [Commit Git ou référence du document]
- **Verdict global :** [🟢 Approuvé / 🟠 Approuvé avec réserves / 🔴 Rejeté]

---

## Résumé Exécutif
[Synthèse de 3 à 5 lignes sur l'état général du design, sa conformité et les priorités identifiées.]

---

## Synthèse des Observations

| Réf | Criticité | Composants / Nets | Description synthétique |
| :--- | :--- | :--- | :--- |
| **B1** | 🔴 Bloquant | `...` | ... |
| **I1** | 🟠 Important | `...` | ... |
| **M1** | 🟢 Mineur | `...` | ... |

---

## Détail des Observations & Recommandations

### 🔴 Remarques Bloquantes (Critiques)

#### B1. [Titre explicite de l'anomalie]
- **Composants / Nets concernés :** `...` (ex. `U4` pin 2, net `+12V_PROT`)
- **Constat technique :** [Description précise du problème constaté]
- **Justification & Risque :** [Référence datasheet, calcul ou norme expliquant le risque matériel]
- **Solution recommandée :** [Action concrète : référence fabricant, valeur, boîtier, code LCSC]

---

### 🟠 Remarques Importantes (Robustesse & CEM)

#### I1. [Titre de la recommandation]
- **Composants / Nets concernés :** `...`
- **Constat technique :** [Description]
- **Justification :** [Impact sur l'immunité CEM, robustesse véhicule, intégrité signal]
- **Solution recommandée :** [Composant, routage ou filtre préconisé]

---

### 🟢 Remarques Mineures (Optimisation & DFM)

#### M1. [Titre de l'optimisation]
- **Composants / Nets concernés :** `...`
- **Constat & Proposition :** [Ex. bascule vers une Basic Part, sérigraphie, etc.]
- **Gain attendu :** [Réduction de coût, clarté visuelle, accessibilité]
```
