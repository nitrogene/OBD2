#!/usr/bin/env python3
"""
Modélisation formelle des contraintes de placement pour le scanner OBD-II ESP32
================================================================================
Ce module définit l'ensemble des règles physiques, géométriques, CEM et thermiques
qui pilotent l'algorithme d'auto-placement et le validateur d'audit.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# =============================================================================
# Constantes de Conversion et Tolérances
# =============================================================================

MM_TO_MIL = 39.37007874
MIL_TO_MM = 0.0254

def mm_to_mil(mm: float) -> float:
    return mm * MM_TO_MIL

def mil_to_mm(mil: float) -> float:
    return mil * MIL_TO_MM


# =============================================================================
# Enveloppe Mécanique du PCB (Contour standard : 81.28 mm x 35.56 mm)
# =============================================================================

BOARD_WIDTH_MM = 81.28    # 3200 mil
BOARD_HEIGHT_MM = 35.56   # 1400 mil

BOARD_WIDTH_MIL = mm_to_mil(BOARD_WIDTH_MM)
BOARD_HEIGHT_MIL = mm_to_mil(BOARD_HEIGHT_MM)

# Marge de sécurité avec le bord de carte (Edge Clearance)
EDGE_CLEARANCE_MM = 1.0
EDGE_CLEARANCE_MIL = mm_to_mil(EDGE_CLEARANCE_MM)


# =============================================================================
# Contraintes de Distance Critique (Seuils d'Audit)
# =============================================================================

MAX_DECOUPLING_DISTANCE_MM = 2.0   # C1, C2, C11 à < 2 mm des broches VDD/GND
MAX_RESET_RC_DISTANCE_MM = 2.0     # C12, R15 à < 2 mm de la broche EN
MAX_ESD_DISTANCE_MM = 5.0          # U6, U7, U8, D5 à < 5 mm des connecteurs J1, J2
GRID_STEP_MIL = 25.0               # Pas de grille d'accrochage pour le placement


# =============================================================================
# Structures de Données pour les Contraintes
# =============================================================================

@dataclass
class AnchorConstraint:
    """Composant dont la position mécanique est imposée."""
    designator: str
    target_x_mil: float
    target_y_mil: float
    target_rotation: float
    fixed: bool = True
    description: str = ""


@dataclass
class ProximityRule:
    """Règle de distance maximale entre deux composants ou broches."""
    component: str
    reference_component: str
    max_distance_mm: float
    target_net: str
    description: str


@dataclass
class KeepoutZone:
    """Zone d'exclusion stricte multicouche (NO_WIRES, NO_POURS, NO_COMPONENTS)."""
    name: str
    x_min_mil: float
    x_max_mil: float
    y_min_mil: float
    y_max_mil: float
    description: str


# =============================================================================
# Répertoire des Contraintes du Projet Scanner OBD-II
# =============================================================================

# 1. Ancres Mécaniques Fixes
FIXED_ANCHORS: Dict[str, AnchorConstraint] = {
    # Connecteur OBD-II mâle 16 broches (J1) centré sur le bord Ouest
    "J1": AnchorConstraint(
        designator="J1",
        target_x_mil=1400.0,
        target_y_mil=-600.0,
        target_rotation=270.0,
        fixed=True,
        description="Connecteur OBD-II traversant 90° centré sur la face Ouest"
    ),
    # Port USB-C (J2) affleurant sur le bord Sud
    "J2": AnchorConstraint(
        designator="J2",
        target_x_mil=1600.0,
        target_y_mil=200.0,
        target_rotation=0.0,
        fixed=True,
        description="Prise USB-C horizontale CMS affleurante bord Sud"
    ),
    # Module ESP32-S3 (U1) sur le bord Est (antenne dégagée vers l'extérieur)
    "U1": AnchorConstraint(
        designator="U1",
        target_x_mil=2700.0,
        target_y_mil=700.0,
        target_rotation=0.0,
        fixed=True,
        description="SoC ESP32-S3 avec antenne PCB orientée vers le bord extérieur Est"
    )
}

# 2. Clusters Fonctionnels Hiérarchiques
FUNCTIONAL_CLUSTERS: Dict[str, List[str]] = {
    # Cluster 1 : Protections Entrée 12V (Ouest, immédiat sortie Pin 16 de J1)
    "POWER_PROTECTION": ["F1", "D1", "Q1", "Q2", "D3", "R5", "R7", "R14"],
    
    # Cluster 2 : Monitoring Batterie ADC (Ouest-Nord, à droite de J1)
    "BATTERY_SENSE": ["R12", "R13", "C10", "TP9"],
    
    # Cluster 3 : Protections & Transceivers OBD (Ouest-Centre)
    "OBD_TRANSCEIVERS": ["U8", "D5", "R16", "U2", "R8", "JP1", "C3", "C14", "TP7", "TP8", "U3", "R1", "R2", "C4", "TP2"],
    
    # Cluster 4 : Étage Buck 12V -> 5V (Centre-Nord, boucle compacte isolée)
    "BUCK_CONVERTER": ["U4", "C7", "C15", "D2", "L1", "C8", "C5", "R9", "R10", "R11", "C9", "C13", "TP4", "TP5"],
    
    # Cluster 5 : LDO 3.3V Faible Bruit (Centre)
    "LDO_REGULATOR": ["U5", "FB1", "C6", "TP6"],
    
    # Cluster 6 : Interface USB-C & Protections ESD (Sud-Centre)
    "USB_INTERFACE": ["U6", "U7", "R3", "R4", "D4", "TP1"],
    
    # Cluster 7 : MCU ESP32-S3, Découplage & Reset (Est)
    "MCU_CORE": ["C1", "C2", "C11", "C12", "R15", "SW1", "TP10", "TP11", "TP3"],
    
    # Cluster 8 : Indicateur d'état (Sud-Est)
    "STATUS_INDICATOR": ["LED1", "R6"]
}

# 3. Règles de Proximité Stricte
PROXIMITY_RULES: List[ProximityRule] = [
    # Découplage VDD ESP32
    ProximityRule("C1", "U1", MAX_DECOUPLING_DISTANCE_MM, "3.3V", "Condensateur découplage HF C1 < 2mm pin 2"),
    ProximityRule("C2", "U1", MAX_DECOUPLING_DISTANCE_MM, "3.3V", "Condensateur découplage HF C2 < 2mm pin 2"),
    ProximityRule("C11", "U1", MAX_DECOUPLING_DISTANCE_MM, "3.3V", "Condensateur réservoir Bulk C11 < 2mm pins 1/2"),
    
    # Reset & Filtrage EN
    ProximityRule("C12", "U1", MAX_RESET_RC_DISTANCE_MM, "ESP_EN", "Condensateur RC Reset C12 < 2mm pin 3"),
    ProximityRule("R15", "U1", MAX_RESET_RC_DISTANCE_MM, "ESP_EN", "Résistance pull-up EN R15 < 2mm pin 3"),
    
    # Protections ESD / TVS
    ProximityRule("U8", "J1", MAX_ESD_DISTANCE_MM, "CANH", "TVS double CAN U8 < 5mm broches OBD"),
    ProximityRule("D5", "J1", MAX_ESD_DISTANCE_MM, "K_LINE", "TVS K-Line D5 < 5mm broche OBD"),
    ProximityRule("U6", "J2", MAX_ESD_DISTANCE_MM, "USB_D+", "ESD USB D+ U6 au contact du connecteur J2"),
    ProximityRule("U7", "J2", MAX_ESD_DISTANCE_MM, "USB_D-", "ESD USB D- U7 au contact du connecteur J2"),
    
    # Découplage Transceivers
    ProximityRule("C3", "U2", MAX_DECOUPLING_DISTANCE_MM, "3.3V", "Découplage VIO U2 < 2mm"),
    ProximityRule("C14", "U2", MAX_DECOUPLING_DISTANCE_MM, "+5V", "Découplage VCC U2 < 2mm"),
    ProximityRule("C4", "U3", MAX_DECOUPLING_DISTANCE_MM, "3.3V", "Découplage VCC U3 < 2mm"),
    
    # Découplage Buck
    ProximityRule("C7", "U4", MAX_DECOUPLING_DISTANCE_MM, "+12V_PROT", "Condensateur entrée Buck C7 collé à VIN"),
    ProximityRule("C15", "U4", MAX_DECOUPLING_DISTANCE_MM, "+12V_PROT", "Condensateur HF Buck C15 collé à VIN")
]

# 4. Zones d'Exclusion Stricte (Keepouts)
KEEPOUT_ZONES: List[KeepoutZone] = [
    # Zone d'antenne RF ESP32-S3 (Bord extérieur Est)
    KeepoutZone(
        name="RF_ANTENNA_KEEPOUT",
        x_min_mil=2900.0,
        x_max_mil=3200.0,
        y_min_mil=300.0,
        y_max_mil=1100.0,
        description="Zone d'exclusion totale multicouche sous l'antenne méandre 2.4 GHz"
    )
]


def print_constraints_summary():
    """Affiche un résumé clair des contraintes enregistrées."""
    print("=" * 70)
    print(" RÉPERTOIRE DES CONTRAINTES DE CONCEPTION (PCB PLACER)")
    print("=" * 70)
    print(f"Dimensions de la carte : {BOARD_WIDTH_MM:.2f} mm x {BOARD_HEIGHT_MM:.2f} mm ({BOARD_WIDTH_MIL:.0f} x {BOARD_HEIGHT_MIL:.0f} mil)")
    print(f"Marge bord de carte    : {EDGE_CLEARANCE_MM:.1f} mm ({EDGE_CLEARANCE_MIL:.0f} mil)")
    print(f"Seuil découplage       : < {MAX_DECOUPLING_DISTANCE_MM:.1f} mm")
    print(f"Seuil Reset EN         : < {MAX_RESET_RC_DISTANCE_MM:.1f} mm")
    print(f"Seuil TVS/ESD          : < {MAX_ESD_DISTANCE_MM:.1f} mm")
    print(f"Nombre d'ancres fixes  : {len(FIXED_ANCHORS)}")
    print(f"Nombre de clusters     : {len(FUNCTIONAL_CLUSTERS)} ({sum(len(c) for c in FUNCTIONAL_CLUSTERS.values())} composants)")
    print(f"Nombre de règles prox. : {len(PROXIMITY_RULES)}")
    print(f"Zones d'exclusion      : {len(KEEPOUT_ZONES)}")
    print("=" * 70)


if __name__ == "__main__":
    print_constraints_summary()
