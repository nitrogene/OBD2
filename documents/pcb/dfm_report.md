# Rapport d'Audit Fabricabilité DFM & Assemblage SMT

- **Date de l'audit :** 2026-10-27 08:57:41
- **Verdict Global :** 🔴 Rejet DFM : Anomalies Critiques Détectées
- **Fabricant cible :** JLCPCB (Stackup JLC2313)

---

## 1. Synthèse Métrologique

| Domaine | Statut | Danger (Bloquant) | Warning (Avertissement) | Info / Recommandation |
| :--- | :---: | :---: | :---: | :---: |
| **PCB DFM (Nu)** | ❌ NON CONFORME | 56 | 66 | 0 |
| **SMT DFM (Assemblage)** | ✅ CONFORME | 0 | 1 | 5 |

### Répartition de l'Assemblage :
- Composants CMS (Automated Pick & Place) : **78**
- Composants Traversants THT (Soudure manuelle / sélective) : **7** (H1, H2, H3, J1, J2, JP1, JP2)

---

## 2. 🔴 Anomalies Critiques (DANGER - À corriger avant commande)

| # | Catégorie | Description Technique | Valeur | Seuil | Coordonnées (X, Y) |
| :---: | :--- | :--- | :---: | :---: | :---: |
| 1 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '1' et '2' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (71.26, 26.53) mm |
| 2 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '2' et '3' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (69.99, 26.53) mm |
| 3 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '3' et '4' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (68.72, 26.53) mm |
| 4 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '4' et '5' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (67.45, 26.53) mm |
| 5 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '5' et '6' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (66.18, 26.53) mm |
| 6 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '6' et '7' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (64.91, 26.53) mm |
| 7 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '7' et '8' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (63.64, 26.53) mm |
| 8 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '8' et '9' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (62.37, 26.53) mm |
| 9 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '9' et '10' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (61.10, 26.53) mm |
| 10 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '10' et '11' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (59.83, 26.53) mm |
| 11 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '11' et '12' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (58.56, 26.53) mm |
| 12 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '12' et '13' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (57.29, 26.53) mm |
| 13 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '13' et '14' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (56.02, 26.53) mm |
| 14 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '27' et '28' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (56.02, 9.03) mm |
| 15 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '28' et '29' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (57.29, 9.03) mm |
| 16 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '29' et '30' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (58.56, 9.03) mm |
| 17 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '30' et '31' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (59.83, 9.03) mm |
| 18 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '31' et '32' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (61.10, 9.03) mm |
| 19 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '32' et '33' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (62.37, 9.03) mm |
| 20 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '33' et '34' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (63.64, 9.03) mm |
| 21 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '34' et '35' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (64.91, 9.03) mm |
| 22 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '35' et '36' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (66.18, 9.03) mm |
| 23 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '36' et '37' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (67.45, 9.03) mm |
| 24 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '37' et '38' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (68.72, 9.03) mm |
| 25 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '38' et '39' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (69.99, 9.03) mm |
| 26 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '39' et '40' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (71.26, 9.03) mm |
| 27 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '5' et '6' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (30.10, 5.90) mm |
| 28 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '6' et '7' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (30.10, 7.17) mm |
| 29 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '7' et '8' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (30.10, 8.44) mm |
| 30 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '4' et '3' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (24.90, 5.90) mm |
| 31 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '3' et '2' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (24.90, 7.17) mm |
| 32 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '2' et '1' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (24.90, 8.44) mm |
| 33 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '5' et '6' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (41.08, 14.40) mm |
| 34 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '6' et '7' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (41.08, 13.13) mm |
| 35 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '7' et '8' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (41.08, 11.86) mm |
| 36 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '4' et '3' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (46.28, 14.40) mm |
| 37 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '3' et '2' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (46.28, 13.13) mm |
| 38 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (-0.102 mm < 0.10 mm) entre pastilles '2' et '1' (layer 1). Risque d'arrachement de vernis / gang mask. | -0.102 mm | 0.1 mm | (46.28, 11.86) mm |
| 39 | `PCB_DFM_VIA_IN_PAD` | Via chevauche directement la pastille CMS '2' (distance bord = -0.114 mm). Risque majeur de siphonnage de brasure. | -0.114 mm | 0.0 mm | (72.53, 29.95) mm |
| 40 | `PCB_DFM_VIA_IN_PAD` | Via chevauche directement la pastille CMS '2' (distance bord = -0.325 mm). Risque majeur de siphonnage de brasure. | -0.325 mm | 0.0 mm | (70.10, 28.45) mm |
| 41 | `PCB_DFM_VIA_IN_PAD` | Via chevauche directement la pastille CMS '2' (distance bord = -0.114 mm). Risque majeur de siphonnage de brasure. | -0.114 mm | 0.0 mm | (65.59, 27.89) mm |
| 42 | `PCB_DFM_VIA_IN_PAD` | Via chevauche directement la pastille CMS '1' (distance bord = -0.114 mm). Risque majeur de siphonnage de brasure. | -0.114 mm | 0.0 mm | (37.98, 17.91) mm |
| 43 | `PCB_DFM_VIA_IN_PAD` | Via chevauche directement la pastille CMS '1' (distance bord = -0.528 mm). Risque majeur de siphonnage de brasure. | -0.528 mm | 0.0 mm | (34.29, 16.73) mm |
| 44 | `PCB_DFM_VIA_IN_PAD` | Via chevauche directement la pastille CMS '2' (distance bord = -0.114 mm). Risque majeur de siphonnage de brasure. | -0.114 mm | 0.0 mm | (36.18, 9.39) mm |
| 45 | `PCB_DFM_VIA_IN_PAD` | Via chevauche directement la pastille CMS '2' (distance bord = -0.165 mm). Risque majeur de siphonnage de brasure. | -0.165 mm | 0.0 mm | (19.54, 18.05) mm |
| 46 | `PCB_DFM_VIA_IN_PAD` | Via chevauche directement la pastille CMS '2' (distance bord = -0.353 mm). Risque majeur de siphonnage de brasure. | -0.353 mm | 0.0 mm | (43.58, 26.86) mm |
| 47 | `PCB_DFM_VIA_IN_PAD` | Via chevauche directement la pastille CMS '2' (distance bord = -0.020 mm). Risque majeur de siphonnage de brasure. | -0.02 mm | 0.0 mm | (19.36, 6.37) mm |
| 48 | `PCB_DFM_VIA_IN_PAD` | Via chevauche directement la pastille CMS '1' (distance bord = -0.033 mm). Risque majeur de siphonnage de brasure. | -0.033 mm | 0.0 mm | (22.41, 19.70) mm |
| 49 | `PCB_DFM_VIA_IN_PAD` | Via chevauche directement la pastille CMS '2' (distance bord = -0.353 mm). Risque majeur de siphonnage de brasure. | -0.353 mm | 0.0 mm | (36.39, 27.45) mm |
| 50 | `PCB_DFM_VIA_IN_PAD` | Via chevauche directement la pastille CMS '41' (distance bord = -0.114 mm). Risque majeur de siphonnage de brasure. | -0.114 mm | 0.0 mm | (63.22, 18.83) mm |
| 51 | `PCB_DFM_VIA_TO_PAD_PROXIMITY` | Via trop proche de la pastille CMS '41' (0.018 mm < 0.15 mm). Insérer un col de piste dog-bone >= 0.15 mm. | 0.018 mm | 0.15 mm | (64.18, 18.65) mm |
| 52 | `PCB_DFM_VIA_IN_PAD` | Via chevauche directement la pastille CMS '41' (distance bord = -0.114 mm). Risque majeur de siphonnage de brasure. | -0.114 mm | 0.0 mm | (64.18, 18.65) mm |
| 53 | `PCB_DFM_VIA_IN_PAD` | Via chevauche directement la pastille CMS '5' (distance bord = -0.565 mm). Risque majeur de siphonnage de brasure. | -0.565 mm | 0.0 mm | (41.71, 15.04) mm |
| 54 | `PCB_DFM_VIA_IN_PAD` | Via chevauche directement la pastille CMS '4' (distance bord = -0.052 mm). Risque majeur de siphonnage de brasure. | -0.052 mm | 0.0 mm | (45.47, 15.85) mm |
| 55 | `PCB_DFM_VIA_TO_PAD_PROXIMITY` | Via trop proche de la pastille CMS '5' (0.007 mm < 0.15 mm). Insérer un col de piste dog-bone >= 0.15 mm. | 0.007 mm | 0.15 mm | (39.80, 26.01) mm |
| 56 | `PCB_DFM_VIA_IN_PAD` | Via chevauche directement la pastille CMS '2' (distance bord = -0.065 mm). Risque majeur de siphonnage de brasure. | -0.065 mm | 0.0 mm | (38.46, 11.88) mm |

## 3. 🟠 Avertissements DFM (WARNING - Tolérances limites)

| # | Catégorie | Observation | Mesure | Seuil Standard | Coordonnées |
| :---: | :--- | :--- | :---: | :---: | :---: |
| 1 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (0.099 mm < 0.10 mm) entre pastilles 'B8' et 'A5' (layer 1). Risque d'arrachement de vernis / gang mask. | 0.099 mm | 0.1 mm | (39.14, 6.28) mm |
| 2 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (0.099 mm < 0.10 mm) entre pastilles 'A5' et 'B7' (layer 1). Risque d'arrachement de vernis / gang mask. | 0.099 mm | 0.1 mm | (39.64, 6.28) mm |
| 3 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (0.099 mm < 0.10 mm) entre pastilles 'B7' et 'A6' (layer 1). Risque d'arrachement de vernis / gang mask. | 0.099 mm | 0.1 mm | (40.14, 6.28) mm |
| 4 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (0.096 mm < 0.10 mm) entre pastilles 'A6' et 'A7' (layer 1). Risque d'arrachement de vernis / gang mask. | 0.096 mm | 0.1 mm | (40.64, 6.28) mm |
| 5 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (0.099 mm < 0.10 mm) entre pastilles 'A7' et 'B6' (layer 1). Risque d'arrachement de vernis / gang mask. | 0.099 mm | 0.1 mm | (41.14, 6.28) mm |
| 6 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (0.099 mm < 0.10 mm) entre pastilles 'B6' et 'A8' (layer 1). Risque d'arrachement de vernis / gang mask. | 0.099 mm | 0.1 mm | (41.64, 6.28) mm |
| 7 | `PCB_DFM_SOLDERMASK_BRIDGE` | Pont de vernis épargne insuffisant (0.099 mm < 0.10 mm) entre pastilles 'A8' et 'B5' (layer 1). Risque d'arrachement de vernis / gang mask. | 0.099 mm | 0.1 mm | (42.14, 6.28) mm |
| 8 | `PCB_DFM_VIA_TO_PAD_PROXIMITY` | Via trop proche de la pastille CMS '1' (0.086 mm < 0.15 mm). Insérer un col de piste dog-bone >= 0.15 mm. | 0.086 mm | 0.15 mm | (22.17, 12.98) mm |
| 9 | `PCB_DFM_VIA_TO_PAD_PROXIMITY` | Via trop proche de la pastille CMS '1' (0.142 mm < 0.15 mm). Insérer un col de piste dog-bone >= 0.15 mm. | 0.142 mm | 0.15 mm | (20.57, 17.04) mm |
| 10 | `PCB_DFM_VIA_TO_PAD_PROXIMITY` | Via trop proche de la pastille CMS '1' (0.126 mm < 0.15 mm). Insérer un col de piste dog-bone >= 0.15 mm. | 0.126 mm | 0.15 mm | (19.03, 3.94) mm |
| 11 | `PCB_DFM_VIA_TO_PAD_PROXIMITY` | Via trop proche de la pastille CMS '1' (0.123 mm < 0.15 mm). Insérer un col de piste dog-bone >= 0.15 mm. | 0.123 mm | 0.15 mm | (32.81, 14.62) mm |
| 12 | `PCB_DFM_VIA_TO_PAD_PROXIMITY` | Via trop proche de la pastille CMS '1' (0.129 mm < 0.15 mm). Insérer un col de piste dog-bone >= 0.15 mm. | 0.129 mm | 0.15 mm | (61.32, 28.65) mm |
| 13 | `PCB_DFM_VIA_TO_PAD_PROXIMITY` | Via trop proche de la pastille CMS '7' (0.098 mm < 0.15 mm). Insérer un col de piste dog-bone >= 0.15 mm. | 0.098 mm | 0.15 mm | (28.93, 8.37) mm |
| 14 | `PCB_DFM_VIA_TO_PAD_PROXIMITY` | Via trop proche de la pastille CMS '1' (0.099 mm < 0.15 mm). Insérer un col de piste dog-bone >= 0.15 mm. | 0.099 mm | 0.15 mm | (34.60, 20.90) mm |
| 15 | `PCB_DFM_VIA_TO_PAD_PROXIMITY` | Via trop proche de la pastille CMS '6' (0.091 mm < 0.15 mm). Insérer un col de piste dog-bone >= 0.15 mm. | 0.091 mm | 0.15 mm | (38.32, 23.83) mm |
| 16 | `PCB_DFM_VIA_TO_PAD_PROXIMITY` | Via trop proche de la pastille CMS '5' (0.089 mm < 0.15 mm). Insérer un col de piste dog-bone >= 0.15 mm. | 0.089 mm | 0.15 mm | (38.32, 23.83) mm |
| 17 | `PCB_DFM_VIA_TO_PAD_PROXIMITY` | Via trop proche de la pastille CMS '3' (0.113 mm < 0.15 mm). Insérer un col de piste dog-bone >= 0.15 mm. | 0.113 mm | 0.15 mm | (53.85, 7.78) mm |
| 18 | `PCB_DFM_SILKSCREEN_STROKE` | Trait de sérigraphie trop fin pour le texte '+' (0.150 mm < 0.15 mm). Augmenter à >= 0.18 mm pour un rendu net. | 0.1499 mm | 0.15 mm | (20.33, 31.50) mm |
| 19 | `PCB_DFM_SILKSCREEN_TO_PAD` | Texte de sérigraphie '+' trop proche de la pastille '2' (0.039 mm < 0.15 mm). Risque d'auto-clipping ou de bavure. | 0.039 mm | 0.15 mm | (20.33, 31.50) mm |
| 20 | `PCB_DFM_SILKSCREEN_STROKE` | Trait de sérigraphie trop fin pour le texte '-' (0.150 mm < 0.15 mm). Augmenter à >= 0.18 mm pour un rendu net. | 0.1499 mm | 0.15 mm | (22.87, 31.50) mm |
| 21 | `PCB_DFM_SILKSCREEN_STROKE` | Trait de sérigraphie trop fin pour le texte 'STATUS' (0.150 mm < 0.15 mm). Augmenter à >= 0.18 mm pour un rendu net. | 0.1499 mm | 0.15 mm | (68.73, 7.03) mm |
| 22 | `PCB_DFM_SILKSCREEN_STROKE` | Trait de sérigraphie trop fin pour le texte 'SCANNER: POWER OUT' (0.150 mm < 0.15 mm). Augmenter à >= 0.18 mm pour un rendu net. | 0.1499 mm | 0.15 mm | (19.05, 26.67) mm |
| 23 | `PCB_DFM_SILKSCREEN_STROKE` | Trait de sérigraphie trop fin pour le texte '+12V' (0.150 mm < 0.15 mm). Augmenter à >= 0.18 mm pour un rendu net. | 0.1499 mm | 0.15 mm | (18.73, 29.50) mm |
| 24 | `PCB_DFM_SILKSCREEN_STROKE` | Trait de sérigraphie trop fin pour le texte 'GND' (0.150 mm < 0.15 mm). Augmenter à >= 0.18 mm pour un rendu net. | 0.1499 mm | 0.15 mm | (21.27, 29.50) mm |
| 25 | `PCB_DFM_SILKSCREEN_STROKE` | Trait de sérigraphie trop fin pour le texte '+12V' (0.150 mm < 0.15 mm). Augmenter à >= 0.18 mm pour un rendu net. | 0.1499 mm | 0.15 mm | (7.00, 23.39) mm |
| ... | ... | *(et 42 autres avertissements similaires)* | ... | ... | ... |

## 4. Recommandations d'Actions Correctives Immédiates

- **Vernis épargne :** Ajuster l'expansion de masque à 0.02–0.03 mm sur les composants denses pour restaurer un barrage physique >= 0.10 mm.
- **Vias collés aux pastilles :** Insérer un col de piste dog-bone >= 0.15 mm ou certifier le tenting 100% pour stopper l'aspiration d'étain.
- **Sérigraphie :** Éloigner les textes à >= 0.15 mm des pastilles et configurer une épaisseur de trait >= 0.18 mm.
- **Repères fiduciaires :** Prévoir 3 repères optiques de 1.0 mm sur le PCB ou confirmer la fourniture de bandes de rive techniques lors de la panélisation usine.
