---
name: ratio-solver
description: Moteur d'optimisation mathématique et de calcul de couples de résistances pour ponts diviseurs, références de régulateurs (Buck/Boost/LDO), atténuateurs ADC et étages d'ampli-op.
---

# Skill : ratio-solver

Moteur algorithmique universel et agnostique (Règle 0) conçu pour résoudre le problème d'optimisation de couples de résistances $(R_1, R_2)$ selon les séries normalisées (E12, E24, E96, E192) ou à partir d'un catalogue restreint de composants disponibles (ex. *Basic Parts* JLCPCB).

---

## 1. Principes & Équations Modélisées

### A. Mode Régulateur (`regulator`)
Utilisé pour déterminer le pont de feedback de convertisseurs Buck (ex. TPS54331), Boost ou régulateurs linéaires LDO :
$$V_{out} = V_{ref} \times \left(1 + \frac{R_1}{R_2}\right)$$
* $R_1$ : Résistance supérieure (connectée entre la sortie $V_{out}$ et la broche de feedback $FB$).
* $R_2$ : Résistance inférieure (connectée entre la broche $FB$ et la masse $GND$).
* Ratio théorique : $\frac{R_1}{R_2} = \frac{V_{out} - V_{ref}}{V_{ref}}$.
* Courant de repos du pont : $I_{div} = \frac{V_{out}}{R_1 + R_2}$.

### B. Mode Diviseur / Atténuateur ADC (`divider`)
Utilisé pour adapter une tension élevée (ex. rail 12V automobile) vers la dynamique d'entrée d'un convertisseur analogique-numérique (ex. ADC1 ESP32, $V_{adc} \le 1.3\,\text{V}$ à $3.1\,\text{V}$) :
$$V_{out} = V_{in} \times \frac{R_2}{R_1 + R_2}$$
* $R_1$ : Résistance supérieure (entrée $V_{in}$ vers nœud de mesure).
* $R_2$ : Résistance inférieure (nœud de mesure vers $GND$).
* Impédance équivalente de Thévenin : $R_{th} = \frac{R_1 \times R_2}{R_1 + R_2}$ *(critique pour le temps de charge de l'échantillonneur-bloqueur de l'ADC)*.

---

## 2. Guide d'Utilisation CLI

Le solveur s'exécute toujours via `uv run` :

### Exemple 1 : Pont de Feedback Buck 5.0V ($V_{ref} = 0.8\,\text{V}$) sous E96
```powershell
uv run python .agents/skills/ratio-solver/scripts/ratio_solver.py regulator --target-vout 5.0 --vref 0.8 --series E96
```

### Exemple 2 : Pont sous série E24 (Tolérance 5% ou 1% standard)
```powershell
uv run python .agents/skills/ratio-solver/scripts/ratio_solver.py regulator --target-vout 5.0 --vref 0.8 --series E24 --max-error 0.5
```

### Exemple 3 : Atténuateur ADC (12V -> 1.285V pour batterie)
```powershell
uv run python .agents/skills/ratio-solver/scripts/ratio_solver.py divider --vin 12.0 --target-vout 1.2857 --series E96 --max-rth 20000
```

### Exemple 4 : Utilisation avec un catalogue restreint (ex. Basic Parts JLCPCB)
```powershell
uv run python .agents/skills/ratio-solver/scripts/ratio_solver.py regulator --target-vout 5.0 --vref 0.8 --pool-file available_resistors.json --json
```

---

## 3. Paramètres de Filtrage & Contraintes

| Paramètre | Description | Défaut |
| :--- | :--- | :--- |
| `--max-error` | Erreur relative maximale admissible en % sur la tension cible | `0.5%` |
| `--min-current` | Courant minimal traversant le pont (évite les trop fortes impédances sensibles au bruit) | `50 µA` |
| `--max-current` | Courant maximal traversant le pont (limite la consommation de repos à vide) | `2 mA` |
| `--max-rth` | Résistance de Thévenin maximale en Ohms (mode `divider` pour respect d'impédance source ADC) | Illimité |
| `--top-n` | Nombre maximal de combinaisons candidates retournées | `5` |
| `--json` | Sortie structurée au format JSON pour consommation programmatique par un autre skill | Désactivé |
