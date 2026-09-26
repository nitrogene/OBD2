---
name: stingy-schematics
description: Moteur d'optimisation SMT et gardien sémantique de schéma. Analyse la BOM et circuit_semantics.json pour proposer de remplacer des composants Extended par des Basic Parts JLCPCB (économie de 3,00 $ par composant) sans compromis de qualité ni de sécurité, avec génération automatique de rapports de revue.
---

# Skill : stingy-schematics

Moteur algorithmique et économique d'optimisation de nomenclature PCBA pour l'assemblage chez **JLCPCB**.

---

## 1. Pourquoi ce Skill ?

Chez JLCPCB, les composants CMS sont classés en deux catégories :
* **Basic Parts :** Chargés en permanence sur les dévidoirs des machines Pick & Place. **Frais d'outillage = 0,00 $**.
* **Extended Parts :** Nécessitent un chargement manuel de bobine. **Frais de chargement = 3,00 $ par référence unique**.

Sur une petite série de 5 cartes prototypes, remplacer 5 à 10 composants Extended par des Basic Parts fait économiser **15,00 $ à 30,00 $ nets** sur la facture d'assemblage, sans rien changer au fonctionnement du circuit.

---

## 2. Principes & Règles d'Or de Non-Régression

`stingy-schematics` s'interdit formellement de dégrader la qualité des signaux ou les marges de sécurité du matériel :

1. **Intention de Schéma (`circuit_semantics.json`) :**
   Le moteur ne travaille jamais à l'aveugle. Il lit impérativement le contrat sémantique pour connaître le rôle de chaque pièce et sa politique de substitution (`locked`, `direct_1to1`, `ratio_pair_recalc`, `topology_expansion_ok`).
2. **Garde-fous Physiques Inviolables :**
   * **Condensateurs :** $V_{rated\_new} \ge V_{rated\_old}$. Diélectrique $\ge$ ($C0G/NP0 > X7R > X5R$). Exclusion absolue des diélectriques instables Y5V/Z5U.
   * **Résistances :** Tolérance $Tol_{new} \le Tol_{old}$ (une résistance 1% reste à $\le 1\%$). Puissance $P_{new} \ge P_{old}$.
   * **Diodes :** $V_R \ge V_{R\_old}$, $I_F \ge I_{F\_old}$. Conservation stricte de la technologie de jonction (une diode Schottky reste une Schottky).
   * **Nœuds Sacrés :** Verrouillage strict des lignes normalisées (ex. 5.1 kΩ 1% sur USB-C CC1/CC2, pull-up 1206 1k 250mW sur K-Line).

---

## 3. Architecture & Outils Embarqués

Le skill comprend deux outils agnostiques conformes à la Règle 0 (AGENTS.md) :

```
.agents/skills/stingy-schematics/
├── SKILL.md
└── scripts/
    ├── jlcpcb_api.py       # Client HTTP d'interrogation en temps réel du catalogue JLCPCB SMT
    ├── sync_semantics.py   # Gardien d'intégrité entre BOM.md et circuit_semantics.json
    └── stingy.py           # Moteur principal d'optimisation et générateur de reviewXXX.md
```

### A. Gardien Sémantique (`sync_semantics.py`)
Contrôle l'alignement parfait entre la nomenclature et le contrat d'intention :
```powershell
# Contrôle de cohérence (DRC sémantique)
uv run python .agents/skills/stingy-schematics/scripts/sync_semantics.py check --bom BOM.md --semantics circuit_semantics.json

# Génération assistée d'ébauches pour les nouveaux composants
uv run python .agents/skills/stingy-schematics/scripts/sync_semantics.py scaffold --bom BOM.md --semantics circuit_semantics.json
```

### B. Moteur d'Optimisation SMT (`stingy.py`)
Scanne les composants Extended éligibles, interroge en direct JLCPCB, résout les recalculs de ratios via `ratio-solver` et génère un rapport de revue formel dans `review/` :
```powershell
uv run python .agents/skills/stingy-schematics/scripts/stingy.py --bom BOM.md --semantics circuit_semantics.json
```

---

## 4. Intégration dans le Workflow de Conception

1. **Exécution de l'optimiseur :** `stingy.py` génère le prochain fichier `review/reviewXXX.md`.
2. **Validation formelle :** Le rapport est validé par le skill `review` :
   ```powershell
   uv run python .agents/skills/review/scripts/review_tool.py validate review/reviewXXX.md
   ```
3. **Arbitrage avec l'ingénieur :** Revue interactive des propositions chiffrées.
4. **Dépouillement vers TODO :** Les modifications retenues sont injectées dans `TODO.md` puis le fichier `reviewXXX.md` est supprimé.
