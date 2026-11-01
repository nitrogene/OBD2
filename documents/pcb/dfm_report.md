# Rapport d'Audit Fabricabilité DFM & Assemblage SMT

- **Date de l'audit :** 2026-11-01 08:57:40
- **Verdict Global :** 🟠 Approuvé avec Réserves (Warnings DFM uniquement)
- **Fabricant cible :** JLCPCB (Stackup JLC2313)

---

## 1. Synthèse Métrologique

| Domaine | Statut | Danger (Bloquant) | Warning (Avertissement) | Info / Recommandation |
| :--- | :---: | :---: | :---: | :---: |
| **PCB DFM (Nu)** | ✅ CONFORME | 0 | 7 | 0 |
| **SMT DFM (Assemblage)** | ✅ CONFORME | 0 | 1 | 2 |

### Répartition de l'Assemblage :
- Composants CMS (Automated Pick & Place) : **78**
- Composants Traversants THT (Soudure manuelle / sélective) : **7** (H1, H2, H3, J1, J2, JP1, JP2)

---

## 2. 🟢 Zéro Anomalie Critique (0 Alerte DANGER)
Aucun risque de siphonnage d'étain destructeur, court-circuit ou violation dimensionnelle majeure.

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
| 8 | `SMT_DFM_FIDUCIALS_MISSING` | Seulement 0 repère(s) fiduciaire(s) détecté(s) sur le PCB (recommandé : au moins 3 repères optiques en L / triangle). Prévoir l'ajout de 3 pastilles circulaires 1.0 mm isolées ou des repères sur les bandes d'outillage. | 0 mm | 3 mm | (0.00, 0.00) mm |

## 4. Recommandations d'Actions Correctives Immédiates

- **Vernis épargne :** Ajuster l'expansion de masque à 0.02–0.03 mm sur les composants denses pour restaurer un barrage physique >= 0.10 mm.
- **Repères fiduciaires :** Prévoir 3 repères optiques de 1.0 mm sur le PCB ou confirmer la fourniture de bandes de rive techniques lors de la panélisation usine.
