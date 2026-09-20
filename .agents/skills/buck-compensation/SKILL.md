---
name: buck-compensation
description: >-
  Outil de calcul, modélisation petit-signal et optimisation paramétrique du réseau de compensation
  Type II pour les régulateurs Buck de la famille TI TPS543xx (TPS54331, TPS54332, TPS54231, TPS54240).
  Permet d'évaluer la stabilité de boucle (Bode, Fco, Marge de phase, Marge de gain) et d'optimiser le
  triplet (Rz, Cz, Cp) sur catalogue standard (Basic Parts JLCPCB) lors de toute modification
  du régulateur, de l'inductance L1, du condensateur Cout ou de la consommation estimée.
compatibility: Python 3.8+
metadata:
  author: ODB2-Scanner-Dev
  version: "1.0.0"
---

# Skill : Buck Compensation (TI TPS543xx / TPS54331)

Ce skill fournit un environnement autonome de modélisation petit-signal et d'optimisation de boucle de compensation Type II pour le régulateur Buck **TPS54331** (ou dérivés TPS543xx / TPS542xx) du projet **Scanner OBD-II ESP32**.

Il évite tout aller-retour manuel vers l'outil TI WEBENCH lors des révisions du schéma ou du dimensionnement mécanique/thermique.

---

## 1. Contexte & Modèle Physique

La famille TPS54331 utilise une architecture **Peak Current-Mode Control** à fréquence fixe (570 kHz). La boucle externe de tension est régulée par un amplificateur d'erreur à transconductance relié à la broche `COMP` (broche 6).

### Constantes internes du TPS54331 (TI SLVS839H)
* **Tension de référence (Vref) :** `0.8 V`
* **Gain en tension DC de l'ampli d'erreur (VGGM) :** `800 V/V`
* **Impédance de sortie ampli d'erreur (ROA) :** `8.0 MΩ`
* **Transconductance ampli d'erreur (gm,EA = VGGM / ROA) :** `100 µS`
* **Transconductance de l'étage de puissance (gm,PS = gm,COMP) :** `12.0 A/V`
* **Fréquence de commutation (Fsw) :** `570 kHz`
* **Limite pratique recommandée pour la coupure (Fco,max) :** `25 kHz`

---

## 2. Topologie du Réseau de Compensation Type II

Le réseau est connecté entre la broche `COMP` et la masse (`GND`) :
1. **Branche série Zéro / Pôle bas :** Résistance Rz (`R11`) en série avec le condensateur Cz (`C9`).
   * Zéro de boucle : `fz1 = 1 / (2π · Rz · Cz)`
2. **Condensateur parallèle Haute Fréquence :** Condensateur Cp (`C13`) en parallèle de la branche Rz + Cz.
   * Pôle haute fréquence : `fp1 ≈ 1 / (2π · Rz · Cp)` (avec Cz >> Cp)
   * Rôle : filtrage des bruits de commutation (570 kHz) sur la broche haute impédance `COMP`.

---

## 3. Utilisation du Script d'Optimisation

Le script est situé dans `scripts/tps54331_compensation.py`.

### A. Calcul nominal (Équations fermées TI 16-28)
Calcul déterministe pour une fréquence de coupure Fco et une marge de phase cibles :
```bash
python .agents/skills/buck-compensation/scripts/tps54331_compensation.py
```
*Arguments optionnels :* `--vout 5.0 --cout 15e-6 --iomax 0.6 --fco 20e3 --pm 65.0`

### B. Évaluation précise d'un triplet existant (`--eval`)
Analyse petit-signal exacte par résolution de la fonction de transfert en boucle ouverte T(s) :
```bash
python .agents/skills/buck-compensation/scripts/tps54331_compensation.py --eval --rz 10000 --cz 3.3e-9 --cp 220e-12
```
*Résultats fournis :*
* Fréquence de coupure exacte Fco (gain = 0 dB)
* Marge de phase nominale Φm
* Marge de gain Gm
* Balayage de robustesse sur l'enveloppe complète (Io de 0.1 A à 1.0 A et Cout de 10 µF à 20 µF)

### C. Optimisation paramétrique sur le catalogue JLCPCB (`--optimize`)
Scanne les combinaisons de passifs standards disponibles en **Basic Parts** et classe les meilleures solutions par score de stabilité :
```bash
python .agents/skills/buck-compensation/scripts/tps54331_compensation.py --optimize
```

### D. Sortie formatée JSON pour intégration automatique par un agent (`--json`)
```bash
python .agents/skills/buck-compensation/scripts/tps54331_compensation.py --eval --rz 10000 --cz 3.3e-9 --cp 220e-12 --json
```

---

## 4. Règles de Déclenchement Automatique

L'agent doit ré-exécuter ce script dès que l'un des événements suivants survient :
1. Modification du condensateur de sortie `C8` (valeur nominale, technologie ou tension nominale modifiant le dérating DC-bias).
2. Modification de l'inductance de puissance `L1`.
3. Réévaluation de la consommation maximale du montage (ex. activation conjointe Wi-Fi + BLE + transceivers).
4. Détection d'un écart supérieur à **15%** entre les valeurs posées sur le schéma et le calcul optimal.
