# Scanner OBD-II ESP32

Projet de conception matérielle (schématique et PCB) et logicielle d'un scanner de diagnostic automobile OBD-II intelligent, communicant et sécurisé.

---

## 1. Objectifs du Projet

* **Diagnostic embarqué :** Lecture en temps réel des données moteur et des codes défauts (DTC) via la prise standard automobile OBD-II (16 broches).
* **Connectivité sans fil :** Module **ESP32-S3** assurant la liaison sans fil (Wi-Fi 2.4 GHz / BLE 5.0) vers une application mobile.
* **Support multi-protocoles :**
  * **Ligne K-Line (ISO 9141-2 / ISO 14230 KWP2000) :** Spécifiquement calibré pour les calculateurs Daewoo Kalos (2003) et véhicules similaires.
  * **Bus CAN (ISO 15765-4) :** Diagnostic haute vitesse et compatibilité avec les véhicules récents.
* **Alimentation robuste & sécurisée :**
  * Alimentation directe depuis le 12V batterie automobile.
  * Protections complètes : fusible réarmable PPTC `F1`, diode TVS `D1` (écrêtage 29.2V pour limite 30V), protection anti-inversion par MOSFETs `Q1`/`Q2` (avec Zener `D3` de grille).
  * Double étage d'alimentation : abaisseur à découpage Buck 12V → 5V à 570 kHz (`U4` / `L1`) suivi d'un régulateur linéaire LDO 3.3V ultra-propre (`U5` / `FB1`) pour l'ESP32 et la logique.
  * Alimentation autonome sur table via port USB-C protégée par diode anti-retour `D4`.

---

## 2. Architecture Fonctionnelle Globale

```
               PRISE DIAGNOSTIC OBD-II (16 BROCHES)
                │                  │               │
  Broche 16 (+12V Batterie)   Broches 6 & 14    Broche 7 (K-Line)
                │              (Bus CAN Diff)          │
                ▼                  │                   ▼
    ┌─────────────────────────┐    │       ┌───────────────────────┐
    │  1. PROTECTION 12V      │    │       │  6. TRANSCEIVER       │
    │  • Fusible PPTC F1      │    │       │     K-LINE (U3)       │
    │  • Diode TVS D1 (18V)   │    │       │  Traduction 12V ↔ 3.3V│
    │  • Anti-inversion Q1/Q2 │    │       └───────────┬───────────┘
    └───────────┬─────────────┘    │                   │ UART_RX / TX
                │ +12V_PROT        │                   │ (amortisseurs R1/R2)
                ▼                  ▼                   │
    ┌─────────────────────────┐  ┌────────────────┐    │
    │  2. BUCK 12V -> 5V      │  │ 5. TRANSCEIVER │    │
    │     (TPS54331 - 570kHz) │  │ CAN (TJA1051T) │    │
    │  • Inductance L1 (10µH) │  │ • Term. R8/JP1 │    │
    │  • Diode Schottky D2    │  │ • Adapt. VIO   │    │
    └───────────┬─────────────┘  └────────┬───────┘    │
                │ +5V                     │ TWAI_RX/TX │
                ├─────────────────────────┼────────────┤
                │                         │ (CAN)      │
                ▼                         │            │
    ┌─────────────────────────┐           │            │
    │  3. LDO 3.3V & FILTRE HF│           │            │
    │     (LDL1117S33R)       │           │            │
    │  • Filtrage HF (FB1)    │           │            │
    └───────────┬─────────────┘           │            │
                │ +3.3V Logique           │            │
                ▼                         ▼            ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  8. ESP32-S3-WROOM-1 (Wi-Fi/BLE) (U1)                        │
    │  • SoC double cœur 32 bits Xtensa LX7 (16 Mo Flash, 8 Mo PSRAM)│
    │  • LED d'état (LED1 / IO2), Découplage HF + Réservoir Bulk (C11)│
    │  • Monitoring tension batterie (R12/R13, C10 vers ADC1)      │
    │  • Circuit de reset sécurisé & bootloader (SW1, R15, C12)     │
    └──────────────────────────────┬───────────────────────────────┘
                                   │ USB_D+ / USB_D-
                                   ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  4. USB-C, ALIMENTATION BANC & ESD (J2, D4, U6, U7, R3, R4)  │
    └──────────────────────────────────────────────────────────────┘
```

---

## 3. Visuels du Projet

### Schéma Électronique
![Schéma ODB2 Scanner](./images/Schematic.png)

### Circuit Imprimé (PCB)
![PCB ODB2 Scanner](./images/PCB.png)

### Modélisation 3D
![3D ODB2 Scanner](./images/3D.png)

---

## 4. État Actuel (work in progress) & Prochaine Étape

* **Schématique :** Validé à 100% sous EasyEDA Pro (feuille `P1`, 58 composants, ERC strict = 0).
* **Placement PCB :** Placement 2D validé pour l'ensemble des composants avec connecteur OBD-II `J1` coudé à 90°, prise USB-C `J2` affleurante et contour de carte ajusté (81.28 × 35.56 mm).
* **Prochaine étape immédiate :** Traiter les derniers points de revue (arbitrage des valeurs du pont diviseur batterie `R12`/`R13`, protections ESD sur les lignes OBD) puis synchroniser la netlist Schéma → PCB pour engager le routage des pistes.

---

## 5. Guide de Navigation du Dépôt

L'ensemble de la documentation technique et opérationnelle est structuré dans les documents dédiés suivants :

| Document | Description |
| :--- | :--- |
| 📋 **[TODO.md](TODO.md)** | **Feuille de route active & checklist complète** : suivi détaillé des 8 phases de conception (mécanique, schéma, floorplanning, routage, plans de masse, contrôles, fabrication). |
| 📦 **[BOM.md](BOM.md)** | **Nomenclature complète des 58 composants** : références fabricants, codes LCSC, boîtiers d'empreinte et sélection des pièces de base JLCPCB (*Basic Parts*). |
| 🔬 **[HARDWARE.md](HARDWARE.md)** | **Architecture matérielle & anatomie détaillée** : guide pédagogique des 11 blocs, calculs théoriques (Buck, LDO, pont diviseur, Zener), table complète des nets et répertoire des 11 points de test (`TP1` à `TP11`). |
| 🤖 **[AUTOMATION.md](AUTOMATION.md)** | **Automatisation IA via EasyEDA Pro** : architecture du pont Node.js, extension `.eext`, configuration des hooks de cycle de vie Antigravity et règles de routage IA. |
| 💡 **[LEARNINGS.md](LEARNINGS.md)** | **Capitalisation technique** : journal d'apprentissage, spécificités d'API EasyEDA Pro, formats d'unités et pièges évités. |
| 📜 **[AGENTS.md](AGENTS.md)** | **Règles de gouvernance IA** : consignes méthodologiques strictes, sécurité du pont et protocole de dépouillement des revues. |
| 📥 **[REVIEW.md](REVIEW.md)** | **Sas d'entrée pour revues techniques** : fichier réceptacle pour coller une revue (schéma, PCB, firmware) avant arbitrage avec l'utilisateur et transfert vers `TODO.md`. |
| 📁 **`ODB2-Scanner.eprj2`** | **Fichier projet natif EasyEDA Pro v2** : contient le schéma schématique `P1` et la carte de circuit imprimé `PCB1`. |

---

## 6. Démarrage Rapide

1. **Ouvrir le projet :** Lancer EasyEDA Pro (version bureau ou web) et ouvrir le fichier `ODB2-Scanner.eprj2`.
2. **Contrôle d'intégrité :**
   - Schéma : Menu `Design` → `Check ERC` (doit retourner 0 erreur, 0 avertissement).
   - PCB : Menu `Design` → `Check DRC` (doit retourner 0 erreur).
3. **Pilotage IA :** Démarrer le pont local via le skill EasyEDA pour activer la manipulation automatisée (voir [AUTOMATION.md](AUTOMATION.md)).