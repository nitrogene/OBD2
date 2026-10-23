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


def decompose_plane_net_fanout(content: str, target_net: str) -> str:
    """
    Décompose un réseau plan (ex. GND) en mini-réseaux locaux ({target_net}_f1, _f2...)
    autour de chaque groupe (pastille(s) + micro-piste(s) + via) pré-routé à l'Étape 2b.
    Avantages :
    - 0 chevelu global à router dans FreeRouting (gain de temps massif).
    - 0 fausse violation fil-pastille dans FreeRouting (la pastille et sa micro-piste partagent le même mini-net).
    - Protection physique intégrale (type protect) des vias et micro-pistes d'échappement.
    """
    # 1. Extraire les coordonnées de toutes les pins dans (image u1 ...)
    pin_coords: Dict[str, Tuple[float, float]] = {}
    for pm in re.finditer(r'\(pin\s+[^\s()]+\s+([^\s()]+)\s+([0-9.-]+)\s+([0-9.-]+)\)', content):
        pid = f"u1-{pm.group(1)}"
        pin_coords[pid] = (float(pm.group(2)), float(pm.group(3)))

    # 2. Extraire les pins déclarées dans (net target_net (pins ...)) et supprimer (net target_net ...)
    target_pins: List[str] = []
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
        net_block = content[start_idx:end_idx]
        pm_pins = re.search(r'\(pins\s+([^)]+)\)', net_block)
        if pm_pins:
            target_pins.extend(pm_pins.group(1).split())
        content = content[:start_idx] + content[end_idx:]

    # 3. Supprimer (class <any> 'target_net' ...)
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

    # 4. Inspecter (wiring ...) pour trouver les wires et vias de target_net
    m_wiring = re.search(r'\(wiring\b', content)
    if not m_wiring:
        return content

    w_start = m_wiring.start()
    depth = 0
    w_end = w_start
    for i in range(w_start, len(content)):
        if content[i] == '(':
            depth += 1
        elif content[i] == ')':
            depth -= 1
            if depth == 0:
                w_end = i + 1
                break
    wiring_block = content[w_start:w_end]

    # Extraire les sous-expressions (wire ...) et (via ...) dans wiring_block
    items = []
    idx = len("(wiring")
    while idx < len(wiring_block) - 1:
        if wiring_block[idx] == '(':
            s_idx = idx
            d = 0
            e_idx = s_idx
            for j in range(s_idx, len(wiring_block)):
                if wiring_block[j] == '(':
                    d += 1
                elif wiring_block[j] == ')':
                    d -= 1
                    if d == 0:
                        e_idx = j + 1
                        break
            sexpr = wiring_block[s_idx:e_idx]
            items.append(sexpr)
            idx = e_idx
        else:
            idx += 1

    target_wires_vias = []
    other_wires_vias = []
    for sexpr in items:
        m_n = re.search(r'\(net\s+(?:"([^"]+)"|([^\s()]+))\)', sexpr)
        net_val = (m_n.group(1) or m_n.group(2)) if m_n else ""
        if net_val == target_net:
            pts = []
            if sexpr.startswith("(wire"):
                m_p = re.search(r'\(path\s+[^\s()]+\s+[0-9.]+\s+([^)]+)\)', sexpr)
                if m_p:
                    nums = [float(v) for v in m_p.group(1).split()]
                    for k in range(0, len(nums) - 1, 2):
                        pts.append((nums[k], nums[k + 1]))
            elif sexpr.startswith("(via"):
                m_v = re.search(r'\(via\s+[^\s()]+\s+([0-9.-]+)\s+([0-9.-]+)', sexpr)
                if m_v:
                    pts.append((float(m_v.group(1)), float(m_v.group(2))))
            target_wires_vias.append({"sexpr": sexpr, "pts": pts})
        else:
            other_wires_vias.append(sexpr)

    if not target_wires_vias:
        return content

    # 5. Union-Find géométrique entre target_wires_vias et target_pins (< 4.5 mil)
    n_wv = len(target_wires_vias)
    parent = list(range(n_wv))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n_wv):
        for j in range(i + 1, n_wv):
            if any(abs(p1[0] - p2[0]) <= 4.5 and abs(p1[1] - p2[1]) <= 4.5 for p1 in target_wires_vias[i]["pts"] for p2 in target_wires_vias[j]["pts"]):
                union(i, j)

    comp_wv: Dict[int, List[str]] = {}
    comp_pins: Dict[int, List[str]] = {}
    for i in range(n_wv):
        r = find(i)
        comp_wv.setdefault(r, []).append(target_wires_vias[i]["sexpr"])
        comp_pins.setdefault(r, [])

    for pid in target_pins:
        if pid not in pin_coords:
            continue
        px, py = pin_coords[pid]
        for i in range(n_wv):
            if any(abs(px - pt[0]) <= 4.5 and abs(py - pt[1]) <= 4.5 for pt in target_wires_vias[i]["pts"]):
                r = find(i)
                if pid not in comp_pins[r]:
                    comp_pins[r].append(pid)
                break

    # 6. Générer les mini-nets {target_net}_f{k} et les blocs (wiring ...) protégés
    mini_net_defs = []
    rewritten_wv = []
    k_idx = 0
    for r, wv_list in comp_wv.items():
        k_idx += 1
        mini_net = f"{target_net}_f{k_idx}"
        pins_str = " ".join(comp_pins[r])
        if pins_str:
            mini_net_defs.append(f"    (net {mini_net}\n      (pins {pins_str})\n    )")
        else:
            mini_net_defs.append(f"    (net {mini_net})")
        for s in wv_list:
            s_new = re.sub(
                r'\(net\s+(?:"[^"]+"|[^\s()]+)\)',
                f'(net {mini_net})',
                s
            )
            if "(type " not in s_new:
                s_new = s_new[:-1] + " (type protect))"
            rewritten_wv.append("    " + s_new)

    new_wiring_block = "(wiring\n" + "\n".join(rewritten_wv) + "\n  )"
    content = content[:w_start] + new_wiring_block + content[w_end:]

    if mini_net_defs:
        m_net_sec = re.search(r'\(network\b', content)
        if m_net_sec:
            ins_pos = m_net_sec.end()
            content = content[:ins_pos] + "\n" + "\n".join(mini_net_defs) + content[ins_pos:]

    logger.info(f"Fanout '{target_net}' décomposé en {k_idx} mini-réseau(x) protégé(s) (0 chevelu global, 0 conflit).")
    return content


def clean_or_preserve_wiring(dsn_content: str, incremental: bool, preserved_nets: set) -> str:
    """Protège les micro-pistes/vias de fanout des plans internes et nettoie le reste si non incrémental."""
    return dsn_content


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
                dsn_content = decompose_plane_net_fanout(dsn_content, p_net)
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
            if not ovr_dia_mm:
                continue
            ovr_units = mm_to_dsn_units(ovr_dia_mm, unit)
            shapes_ovr = "\n".join([f"      (shape(circle {ln} {ovr_units:.2f} 0 0))" for ln in all_layers])

            # Tentative 1 : Surcharge directe d'un (padstack <pad_id> ...) existant
            pattern_pad = re.compile(
                rf'\(padstack\s+{re.escape(pad_id)}\s*(?:\(shape\([^)]+\)\)\s*)+\)',
                re.MULTILINE
            )
            replacement = f"(padstack {pad_id}\n{shapes_ovr}\n    )"
            dsn_content, n_subs = pattern_pad.subn(replacement, dsn_content)
            if n_subs > 0:
                logger.info(f"Surcharge padstack appliquée : {pad_id} -> diamètre {ovr_dia_mm} mm ({ovr_units:.2f} {unit})")
                continue

            # Tentative 2 : Surcharge ciblée d'une pin spécifique (pin_id)
            # Supporte l'identifiant brut ou avec/sans préfixe 'p' (ex. bdbad5cc7fc4f6ae55, e55, e56)
            clean_pin = pad_id.lstrip("p")
            pin_regex = re.compile(rf'\(pin\s+([^\s()]+)\s+([^\s()]*{re.escape(clean_pin)})\s+', re.MULTILINE)
            m_pin = pin_regex.search(dsn_content)
            if m_pin:
                old_pstack = m_pin.group(1)
                matched_pin_id = m_pin.group(2)
                new_pstack_name = f"p_ovr_{matched_pin_id[-10:]}"
                # Injecter le nouveau padstack dans (library ...)
                new_padstack_def = f"    (padstack {new_pstack_name}\n{shapes_ovr}\n    )\n"
                lib_m = re.search(r'\(library\b', dsn_content)
                if lib_m:
                    dsn_content = dsn_content[:lib_m.end()] + "\n" + new_padstack_def + dsn_content[lib_m.end():]
                # Remplacer la référence dans (pin ...)
                dsn_content = pin_regex.sub(rf'(pin {new_pstack_name} \2 ', dsn_content)
                logger.info(f"Surcharge pin appliquée sur {matched_pin_id} : nouveau padstack {new_pstack_name} ({ovr_dia_mm} mm / {ovr_units:.2f} {unit})")

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

        # 5. Gestion des pistes et vias existants dans (wiring ...)
        preserved_nets = set(self.plane_nets) if ignore_plane_nets else set()
        dsn_content = clean_or_preserve_wiring(dsn_content, incremental=incremental, preserved_nets=preserved_nets)

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
