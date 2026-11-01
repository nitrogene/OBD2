# Rapport d'Audit Fabricabilité DFM & Assemblage SMT

- **Date de l'audit :** 2026-10-31 22:17:52
- **Verdict Global :** 🟠 Approuvé avec Réserves (Warnings DFM uniquement)
- **Fabricant cible :** JLCPCB (Stackup JLC2313)

---

## 1. Synthèse Métrologique

| Domaine | Statut | Danger (Bloquant) | Warning (Avertissement) | Info / Recommandation |
| :--- | :---: | :---: | :---: | :---: |
| **PCB DFM (Nu)** | ✅ CONFORME | 0 | 0 | 0 |
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
| 1 | `SMT_DFM_FIDUCIALS_MISSING` | Seulement 0 repère(s) fiduciaire(s) détecté(s) sur le PCB (recommandé : au moins 3 repères optiques en L / triangle). Prévoir l'ajout de 3 pastilles circulaires 1.0 mm isolées ou des repères sur les bandes d'outillage. | 0 mm | 3 mm | (0.00, 0.00) mm |

## 4. Recommandations d'Actions Correctives Immédiates

- **Repères fiduciaires :** Prévoir 3 repères optiques de 1.0 mm sur le PCB ou confirmer la fourniture de bandes de rive techniques lors de la panélisation usine.
