#!/usr/bin/env python3
"""
Patcher de contraintes Specctra DSN pour FreeRouting
===================================================
Skill: freerouting
Règle 0: Ce module est un moteur algorithmique purement agnostique.
Il ne contient aucun composant ni règle spécifique en dur.
Toutes les contraintes et classes de nets proviennent du fichier JSON passé en argument.
"""

import re
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logger = logging.getLogger("freerouting.dsn_patcher")


def parse_resolution(dsn_content: str) -> Tuple[str, float]:
    """Extrait l'unité et la résolution du fichier DSN.
    
    Exemple: (resolution mil 1000)
    Retourne: ('mil', 1000.0)
    """
    match = re.search(r'\(resolution\s+([a-zA-Z_]+)\s+([0-9.]+)\)', dsn_content)
    if match:
        unit = match.group(1).lower()
        res = float(match.group(2))
        return unit, res
    return "mil", 1000.0


def mm_to_dsn_units(mm: float, unit: str) -> float:
    """Convertit une dimension en millimètres vers l'unité de coordonnées du DSN.
    
    Pour EasyEDA Pro, avec `(resolution mil 1000)`:
    1 mm = 1 / 0.0254 = 39.37007874 mil.
    Les coordonnées et largeurs dans les règles sont exprimées en mil (ex: 10.05 mil = 0.255 mm).
    """
    if unit == "mil":
        return mm * (1000.0 / 25.4)
    elif unit in ("mm", "millimeter"):
        return mm
    elif unit in ("um", "micrometer"):
        return mm * 1000.0
    elif unit == "inch":
        return mm / 25.4
    else:
        # Par défaut, suppose mil
        return mm * (1000.0 / 25.4)


def strip_net_from_dsn(content: str, target_net: str) -> str:
    """Supprime proprement la déclaration (net ...) et (class ...) d'un réseau dans le DSN."""
    # 1. Supprimer (net target_net ...) avec parenthèses équilibrées
    pattern_net = r'\(net\s+' + re.escape(target_net) + r'[\s(]'
    while True:
        m = re.search(pattern_net, content)
        if not m:
            break
        start_idx = m.start()
        depth = 0
        end_idx = start_idx
        for i in range(start_idx, len(content)):
            if content[i] == '(':
                depth += 1
            elif content[i] == ')':
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break
        content = content[:start_idx] + content[end_idx:]

    # 2. Supprimer (class <any> 'target_net' ...) avec parenthèses équilibrées
    pattern_cls = r'\(class\s+[^\s()]+\s+\'' + re.escape(target_net) + r'\''
    while True:
        m = re.search(pattern_cls, content)
        if not m:
            break
        start_idx = m.start()
        depth = 0
        end_idx = start_idx
        for i in range(start_idx, len(content)):
            if content[i] == '(':
                depth += 1
            elif content[i] == ')':
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break
        content = content[:start_idx] + content[end_idx:]

    return content


def extract_nets(dsn_content: str) -> List[str]:
    """Extrait tous les noms de nets déclarés dans la section (network ...)."""
    # Net pattern: (net <net_name> ... )
    nets = []
    # Trouve la section network
    net_matches = re.finditer(r'\(net\s+([^\s()]+)', dsn_content)
    for m in net_matches:
        net_name = m.group(1)
        # Nettoyer d'éventuels guillemets
        net_name = net_name.strip("'\"")
        nets.append(net_name)
    return nets


class DsnPatcher:
    """Moteur de patching de contraintes sur un fichier Specctra DSN."""

    def __init__(self, constraints: Dict[str, Any]):
        self.constraints = constraints
        self.net_classes_cfg = constraints.get("net_classes", {})
        self.default_class_cfg = self.net_classes_cfg.get("DEFAULT", {})
        self.padstack_overrides = constraints.get("padstack_overrides", {})
        self.keepout_zones = constraints.get("keepout_zones", [])
        self.plane_nets = set(constraints.get("plane_nets", []))

    def resolve_net_rule(self, net_name: str) -> Dict[str, Any]:
        """Associe un net à sa règle correspondante dans constraints.json."""
        # 1. Recherche dans les classes spécifiques
        for class_name, cfg in self.net_classes_cfg.items():
            if class_name == "DEFAULT":
                continue
            nets_in_class = cfg.get("nets", [])
            if net_name in nets_in_class:
                return {
                    "class_name": class_name,
                    "track_width_mm": cfg.get("track_width_mm", self.default_class_cfg.get("track_width_mm", 0.254)),
                    "clearance_mm": cfg.get("clearance_mm", self.default_class_cfg.get("clearance_mm", 0.20)),
                    "via_drill_mm": cfg.get("via_drill_mm", self.default_class_cfg.get("via_drill_mm", 0.3)),
                    "via_diameter_mm": cfg.get("via_diameter_mm", self.default_class_cfg.get("via_diameter_mm", 0.6)),
                }

        # 2. Règle par défaut
        return {
            "class_name": "DEFAULT",
            "track_width_mm": self.default_class_cfg.get("track_width_mm", 0.254),
            "clearance_mm": self.default_class_cfg.get("clearance_mm", 0.20),
            "via_drill_mm": self.default_class_cfg.get("via_drill_mm", 0.3),
            "via_diameter_mm": self.default_class_cfg.get("via_diameter_mm", 0.6),
        }

    def patch(self, dsn_content: str, incremental: bool = False, ignore_plane_nets: bool = True) -> str:
        """Applique l'injection de règles et padstacks sur le contenu DSN."""
        unit, resolution = parse_resolution(dsn_content)
        logger.info(f"Unité DSN détectée: {unit} (résolution: {resolution})")

        # Extraction dynamique de toutes les couches de cuivre définies dans le DSN
        all_layers = re.findall(r'\(layer\s+([A-Za-z0-9_]+)\b', dsn_content)
        if not all_layers:
            all_layers = ["TopLayer", "BottomLayer"]

        # 0a. Configuration des plans d'alimentation/masse internes (type power) dans (structure ...)
        stackup_layers = self.constraints.get("board", {}).get("stackup", {}).get("layers", [])
        for lay in stackup_layers:
            if lay.get("type") == "plane":
                lname = lay.get("name")
                default_net = lay.get("default_net")
                prop_str = f'\n    (property (net_name "{default_net}"))' if default_net else ''
                pattern_lay = re.compile(rf'\(layer\s+{re.escape(lname)}\s*\(type\s+signal\)\s*\)', re.IGNORECASE)
                dsn_content, n_mod = pattern_lay.subn(f'(layer {lname}\n    (type power){prop_str}\n  )', dsn_content)
                if n_mod > 0:
                    logger.info(f"Couche interne configurée en plan (type power, net={default_net}) : {lname}")

        # 0b. Exclusion des réseaux de plans du routage filaire (laissé aux plans de masse/cuivre)
        if ignore_plane_nets and self.plane_nets:
            for p_net in sorted(self.plane_nets):
                dsn_content = strip_net_from_dsn(dsn_content, p_net)
                logger.info(f"Net de plan exclu du routage filaire (laissé aux plans de cuivre) : {p_net}")

        # 1. Identifier tous les types de vias nécessaires
        via_types: Dict[str, float] = {}  # {via_id: diameter_dsn_units}
        via_types["via0"] = mm_to_dsn_units(0.61, unit)  # Via par défaut EasyEDA (24 mil)

        for c_name, c_cfg in self.net_classes_cfg.items():
            dia_mm = c_cfg.get("via_diameter_mm")
            if dia_mm:
                via_id = f"via_dia{int(round(dia_mm * 100)):03d}"
                if abs(dia_mm - 0.60) < 0.05:
                    dia_units = mm_to_dsn_units(0.61, unit)
                else:
                    dia_units = mm_to_dsn_units(dia_mm, unit)
                via_types[via_id] = dia_units

        # 2. Injecter les nouveaux padstacks de vias dans (library ...) sur toutes les couches
        padstack_insertions = []
        for via_id, dia_units in via_types.items():
            if via_id == "via0":
                continue  # Déjà présent
            if f"(padstack {via_id}" not in dsn_content:
                shapes_str = "\n".join([f"      (shape(circle {ln} {dia_units:.2f}))" for ln in all_layers])
                padstack_str = (
                    f"    (padstack {via_id}\n"
                    f"{shapes_str}\n"
                    f"    )"
                )
                padstack_insertions.append(padstack_str)

        if padstack_insertions:
            library_match = re.search(r'\(library\b', dsn_content)
            if library_match:
                insert_pos = library_match.end()
                joined_padstacks = "\n" + "\n".join(padstack_insertions)
                dsn_content = dsn_content[:insert_pos] + joined_padstacks + dsn_content[insert_pos:]

        # 2b. Appliquer les surcharges de padstacks configurées sur toutes les couches
        for pad_id, p_cfg in self.padstack_overrides.items():
            ovr_dia_mm = p_cfg.get("diameter_mm")
            if ovr_dia_mm:
                ovr_units = mm_to_dsn_units(ovr_dia_mm, unit)
                pattern_pad = re.compile(
                    rf'\(padstack\s+{re.escape(pad_id)}\s*(?:\(shape\([^)]+\)\)\s*)+\)',
                    re.MULTILINE
                )
                shapes_ovr = "\n".join([f"      (shape(circle {ln} {ovr_units:.2f} 0 0))" for ln in all_layers])
                replacement = f"(padstack {pad_id}\n{shapes_ovr}\n    )"
                dsn_content, n_subs = pattern_pad.subn(replacement, dsn_content)
                if n_subs > 0:
                    logger.info(f"Surcharge padstack appliquée : {pad_id} -> diamètre {ovr_dia_mm} mm ({ovr_units:.2f} {unit})")

        # 3. Mettre à jour la déclaration (via ...) et les règles globales dans (structure ...)
        all_via_ids = list(via_types.keys())
        via_declaration = " ".join(all_via_ids)
        dsn_content = re.sub(
            r'\(via\s+[^)]+\)',
            f'(via {via_declaration})',
            dsn_content,
            count=1,
        )

        default_clear_units = mm_to_dsn_units(self.default_class_cfg.get("clearance_mm", 0.20), unit)
        default_width_units = mm_to_dsn_units(self.default_class_cfg.get("track_width_mm", 0.254), unit)
        structure_rules = (
            f"    (rule(clear {default_clear_units:.2f}))\n"
            f"    (rule(clear {default_clear_units:.2f} (type default_smd)))\n"
            f"    (rule(clear {default_clear_units:.2f} (type smd_smd)))\n"
            f"    (rule(clear {default_clear_units:.2f} (type via_via)))\n"
            f"    (rule(clear {default_clear_units:.2f} (type via_wire)))\n"
            f"    (rule(clear {default_clear_units:.2f} (type wire_wire)))\n"
            f"    (rule(width {default_width_units:.2f}))"
        )
        dsn_content = re.sub(
            r'\(rule\(clear\s+[0-9.]+\)\)\s*'
            r'\(rule\(clear\s+[0-9.]+\s*\(type default_smd\)\)\)\s*'
            r'\(rule\(clear\s+[0-9.]+\s*\(type smd_smd\)\)\)\s*'
            r'\(rule\(width\s+[0-9.]+\)\)',
            structure_rules,
            dsn_content,
            count=1,
        )

        # 3c. Injection des zones d'exclusion (keepouts) configurées dans (structure ...)
        if self.keepout_zones:
            keepout_dsn_blocks = []
            for kz in self.keepout_zones:
                rules = kz.get("rules", ["no_wires"])
                if "no_wires" not in rules:
                    # Ne pas restreindre le routage si la zone n'interdit que les composants (ex: zone d'enfichage mécanique)
                    continue

                kz_name = kz.get("id") or kz.get("name", "KEEPOUT")
                rect_mm = kz.get("rect_mm", {})
                if not rect_mm:
                    continue
                x1 = mm_to_dsn_units(rect_mm.get("x_min", 0.0), unit)
                y1 = mm_to_dsn_units(rect_mm.get("y_min", 0.0), unit)
                x2 = mm_to_dsn_units(rect_mm.get("x_max", 0.0), unit)
                y2 = mm_to_dsn_units(rect_mm.get("y_max", 0.0), unit)

                layer_req = kz.get("layer", "all").lower()
                target_layers = all_layers if layer_req in ("all", "multi") else [kz.get("layer")]

                for t_layer in target_layers:
                    keepout_dsn_blocks.append(
                        f"    (keepout {t_layer}\n"
                        f"      (rect {t_layer} {x1:.2f} {y1:.2f} {x2:.2f} {y2:.2f})\n"
                        f"    )"
                    )
                logger.info(
                    f"Keepout injecté : {kz_name} sur {target_layers} -> "
                    f"[{rect_mm.get('x_min')}..{rect_mm.get('x_max')}, {rect_mm.get('y_min')}..{rect_mm.get('y_max')}] mm"
                )

            if keepout_dsn_blocks:
                all_ko_str = "\n".join(keepout_dsn_blocks) + "\n"
                dsn_content = dsn_content.replace("(boundary", all_ko_str + "    (boundary", 1)

        # 4. Patch des classes de nets dans (network ...)
        # Analyse des blocs (class ...) existants
        # Format EasyEDA:
        # (class <NetName> '<NetName>'
        #   (circuit
        #     (use_via via0)
        #   )
        #   (rule
        #     (width 10)
        #     (clearance 4.02)
        #   )
        # )
        class_block_regex = re.compile(
            r'\(class\s+([^\s()]+)\s+\'([^\']*)\'\s*'
            r'\(circuit\s*\(use_via\s+([^\s()]+)\)\s*\)\s*'
            r'\(rule\s*\(width\s+([0-9.]+)\)\s*\(clearance\s+([0-9.]+)\)\s*\)\s*\)',
            re.MULTILINE | re.DOTALL,
        )

        stats_by_class: Dict[str, int] = {}

        def replace_class(m: re.Match) -> str:
            cls_id = m.group(1)
            net_name = m.group(2)
            rule = self.resolve_net_rule(net_name)

            class_name = rule["class_name"]
            stats_by_class[class_name] = stats_by_class.get(class_name, 0) + 1

            width_units = mm_to_dsn_units(rule["track_width_mm"], unit)
            clearance_units = mm_to_dsn_units(rule["clearance_mm"], unit)
            via_dia_mm = rule["via_diameter_mm"]
            via_id = f"via_dia{int(round(via_dia_mm * 100)):03d}" if via_dia_mm else "via0"

            return (
                f"(class {cls_id} '{net_name}'\n"
                f"      (circuit \n"
                f"        (use_via {via_id})\n"
                f"      )\n"
                f"      (rule \n"
                f"        (width {width_units:.2f})\n"
                f"        (clearance {clearance_units:.2f})\n"
                f"      )\n"
                f"    )"
            )

        dsn_content = class_block_regex.sub(replace_class, dsn_content)

        # Log des statistiques d'application
        logger.info("Règles appliquées par classe de nets :")
        for c_name, count in sorted(stats_by_class.items()):
            c_cfg = self.net_classes_cfg.get(c_name, self.default_class_cfg)
            w_mm = c_cfg.get("track_width_mm", 0.254)
            cl_mm = c_cfg.get("clearance_mm", 0.20)
            logger.info(
                f"  - {c_name:<16} : {count:2d} nets | "
                f"Piste: {w_mm:.3f} mm ({mm_to_dsn_units(w_mm, unit):.1f} {unit}) | "
                f"Isolement: {cl_mm:.3f} mm ({mm_to_dsn_units(cl_mm, unit):.1f} {unit})"
            )

        # 5. Gestion des pistes existantes
        if incremental:
            # Si des pistes existent dans (wiring ...), marquer chaque (wire ...) avec (type protect)
            def protect_wire(m: re.Match) -> str:
                wire_body = m.group(1)
                if "(type " not in wire_body:
                    return f"(wire {wire_body} (type protect))"
                return m.group(0)

            dsn_content = re.sub(
                r'\(wire\s+([^()]+(?:\([^()]*\)[^()]*)*)\)',
                protect_wire,
                dsn_content,
            )
            logger.info("Mode incrémental activé : pistes pré-existantes protégées (type protect).")
        else:
            # Mode non-incrémental (à blanc) : purger toute section (wiring ...) résiduelle pour une carte 100% propre
            dsn_content = re.sub(r'\(wiring\b.*?\n\s*\)', '', dsn_content, flags=re.DOTALL)

        return dsn_content


def patch_dsn_file(
    input_dsn: Path,
    config_path: Path,
    output_dsn: Path,
    incremental: bool = False,
    ignore_plane_nets: bool = True,
) -> Path:
    """Lit un fichier DSN, injecte les contraintes et écrit le fichier DSN corrigé."""
    if not input_dsn.exists():
        raise FileNotFoundError(f"Fichier DSN source introuvable : {input_dsn}")
    if not config_path.exists():
        raise FileNotFoundError(f"Fichier de configuration introuvable : {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        constraints = json.load(f)

    with open(input_dsn, "r", encoding="utf-8") as f:
        dsn_content = f.read()

    patcher = DsnPatcher(constraints)
    patched_content = patcher.patch(dsn_content, incremental=incremental, ignore_plane_nets=ignore_plane_nets)

    output_dsn.parent.mkdir(parents=True, exist_ok=True)
    with open(output_dsn, "w", encoding="utf-8") as f:
        f.write(patched_content)

    logger.info(f"Fichier DSN patché généré avec succès : {output_dsn}")
    return output_dsn


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="[dsn_patcher] %(message)s")
    parser = argparse.ArgumentParser(description="Patcher de contraintes Specctra DSN pour FreeRouting")
    default_config = Path("documents/pcb/constraints.json") if Path("documents/pcb/constraints.json").exists() else (Path("board_constraints.json") if Path("board_constraints.json").exists() else None)
    parser.add_argument("--dsn", type=Path, required=True, help="Chemin vers le fichier DSN brut")
    parser.add_argument("--config", type=Path, default=default_config, required=(default_config is None), help="Chemin vers constraints.json (défaut: documents/pcb/constraints.json)")
    parser.add_argument("--out", type=Path, required=True, help="Chemin vers le fichier DSN corrigé de sortie")
    parser.add_argument("--incremental", action="store_true", help="Fixe les pistes pré-existantes")
    parser.add_argument("--route-all-nets", action="store_true", help="Force le routage filaire de tous les nets y compris les plans de masse")
    args = parser.parse_args()

    patch_dsn_file(
        args.dsn,
        args.config,
        args.out,
        incremental=args.incremental,
        ignore_plane_nets=not args.route_all_nets,
    )
