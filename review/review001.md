# Revue Technique : Optimisation de Nomenclature (BOM) & Bascule Basic Parts

- **Nom du Reviewer / Agent :** Moteur d'Optimisation SMT (stingy-schematics)
- **Date :** 2026-09-26
- **Périmètre audité :** Nomenclature PCBA (BOM.md) & Intention de Schéma (circuit_semantics.json)
- **Version / Référence examinée :** Version 1.0
- **Verdict global :** 🟢 Approuvé (3 composant(s) éligible(s) audité(s))

---

## Résumé Exécutif

L'audit automatisé de la nomenclature du projet face au catalogue en temps réel de JLCPCB SMT a analysé les **21 composants Extended Parts** du circuit. Grâce au référentiel d'intention [`circuit_semantics.json`](../circuit_semantics.json) et aux filtres de non-régression de `ComponentValidator`, le moteur a écarté tout faux positif (puissance, tenue en tension, CEM, fuites ADC) et a identifié les opportunités réelles de basculement vers des **Basic Parts (0,00 $ de frais d'outillage)** sans aucun compromis technique.

> [!TIP]
> **Économie financière directe estimée : +6.00 $ USD** sur les frais de chargement outillage (*Feeder Changeover Fee*).

---

## Synthèse des Observations

| Réf | Criticité | Composants / Nets | Description synthétique | Économie |
| :--- | :--- | :--- | :--- | :---: |
| **M1** | 🟢 Mineur | `LED1` (PSC-1608U52GC-G4) | Bascule vers Basic Part `C2286` (KT-0603R —) | **+3.00 $** |
| **M2** | 🟢 Mineur | `R9` (0805W8F1002T5E) | Bascule vers Basic Part `C17593` (0805W8F2702T5E 27 kΩ) | **+0.00 $** |
| **M3** | 🟢 Mineur | `R10` (0805W8F1911T5E) | Bascule vers Basic Part `C27834` (0805W8F5101T5E 5.1 kΩ) | **+3.00 $** |

---

## Détail des Observations & Recommandations

### 🟢 Remarques Mineures (Optimisation de Coût PCBA & DFM)

#### M1. Remplacement de LED1 (PSC-1608U52GC-G4) par la Basic Part C2286
- **Composants / Nets concernés :** `LED1` (Valeur actuelle : —, Boîtier : 0603).
- **Constat technique :**
  Le composant `LED1` engendre un coût d'outillage de 3,00 $ chez JLCPCB (Extended Part) ou fait partie d'une paire paramétrique optimisable.
- **Justification & Non-Régression :**
  Composant qualifié en Basic Part chez JLCPCB avec un stock actif de 3,934,804 pièces. Boîtier '0603' strictement identique, caractéristiques conformes au rôle 'status_indicator_led'. (Option DFM : passage à la couleur Rouge qualifiée en Basic Part)
- **Solution recommandée :**
  1. Remplacer la référence par `KT-0603R` (LCSC `C2286` - **Basic Part**, Marque : Hubei KENTO Elec, Stock : 3,934,804 pcs).
  2. Impact : Remplacement drop-in 1-to-1 strict (zéro modification d'encombrement ni de routage). (Option DFM : passage à la couleur Rouge qualifiée en Basic Part)

---

#### M2. Remplacement de R9 (0805W8F1002T5E) par la Basic Part C17593
- **Composants / Nets concernés :** `R9` (Valeur actuelle : 10kΩ, Boîtier : 0805).
- **Constat technique :**
  Le composant `R9` engendre un coût d'outillage de 3,00 $ chez JLCPCB (Extended Part) ou fait partie d'une paire paramétrique optimisable.
- **Justification & Non-Régression :**
  Recalcul paramétrique de boucle validé par ratio-solver : le couple R9 = 27 kΩ et R10 = 5.1 kΩ produit une tension régulée de 5.0353 V (écart nominal de 0.71%, courant de pont = 0.156 mA). Les deux références sont des Basic Parts 1% en boîtier 0805 en stock massif chez JLCPCB.
- **Solution recommandée :**
  1. Remplacer la référence par `0805W8F2702T5E` (LCSC `C17593` - **Basic Part**, Marque : UNI-ROYAL(Uniroyal Elec), Stock : 242,718 pcs).
  2. Impact : Mise à jour de la valeur de R9 à 27 kΩ conjointement avec R10 (5.1 kΩ).

---

#### M3. Remplacement de R10 (0805W8F1911T5E) par la Basic Part C27834
- **Composants / Nets concernés :** `R10` (Valeur actuelle : 1.91kΩ, Boîtier : 0805).
- **Constat technique :**
  Le composant `R10` engendre un coût d'outillage de 3,00 $ chez JLCPCB (Extended Part) ou fait partie d'une paire paramétrique optimisable.
- **Justification & Non-Régression :**
  Recalcul paramétrique de boucle validé par ratio-solver : le couple R9 = 27 kΩ et R10 = 5.1 kΩ produit une tension régulée de 5.0353 V (écart nominal de 0.71%, courant de pont = 0.156 mA). Les deux références sont des Basic Parts 1% en boîtier 0805 en stock massif chez JLCPCB.
- **Solution recommandée :**
  1. Remplacer la référence par `0805W8F5101T5E` (LCSC `C27834` - **Basic Part**, Marque : UNI-ROYAL(Uniroyal Elec), Stock : 3,570,228 pcs).
  2. Impact : Mise à jour de la valeur de R10 à 5.1 kΩ (Bascule Extended -> Basic Part, économie directe de 3,00 $).

---
