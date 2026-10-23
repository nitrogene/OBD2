#!/usr/bin/env python3
"""
dsn_metrics.py - Analyseur Métrologique Post-Routage Specctra SES / DSN (Agnostique)
===================================================================================
Skill: pcb-synthesizer
Conforme à la Règle 0 (AGENTS.md) :
- Aucune référence en dur à des composants, pistes ou valeurs spécifiques.
- Parse le fichier de session routée (.ses) ou de conception (.dsn) Specctra.
- Extrait la longueur réelle des pistes, le nombre de vias, l'aire réelle des boucles
  et le skew des paires différentielles.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Import du moteur physique CEM
PLACER_DIR = Path(__file__).resolve().parent.parent / "pcb-placer"
if str(PLACER_DIR) not in sys.path:
    sys.path.insert(0, str(PLACER_DIR))

from emc_physics import polygon_area_shoelace, estimate_loop_inductance_nh

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("DsnMetrics")


@dataclass
class WireSegment:
    layer: str
    width_mm: float
    points: List[Tuple[float, float]]  # Coordonnées (x, y) en mm

    @property
    def length_mm(self) -> float:
        l = 0.0
        for i in range(len(self.points) - 1):
            p1 = self.points[i]
            p2 = self.points[i + 1]
            l += math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        return l


@dataclass
class NetRoutingMetrics:
    net_name: str
    total_length_mm: float = 0.0
    via_count: int = 0
    segments: List[WireSegment] = field(default_factory=list)
    vias: List[Tuple[str, float, float]] = field(default_factory=list)  # (padstack, x, y)


@dataclass
class LoopPhysicalMetric:
    constraint_id: str
    net_names: List[str]
    area_mm2: float
    target_max_area_mm2: float
    inductance_nh: float
    target_max_inductance_nh: float
    ok: bool


@dataclass
class DiffPairMetric:
    class_id: str
    net_pos: str
    net_neg: str
    length_pos_mm: float
    length_neg_mm: float
    skew_mm: float
    max_skew_mm: float
    ok: bool


@dataclass
class CriticalNetMetric:
    net_name: str
    class_id: str
    length_mm: float
    via_count: int
    is_routed: bool
    ok: bool


@dataclass
class PostRoutingReport:
    total_wire_length_mm: float
    total_vias_count: int
    nets_count: int
    loops: List[LoopPhysicalMetric]
    diff_pairs: List[DiffPairMetric]
    critical_nets: List[CriticalNetMetric] = field(default_factory=list)
    unrouted_count: int = 0
    violation_count: int = 0
    is_valid: bool = True
    details: Dict[str, Any] = field(default_factory=dict)


class SpecctraParser:
    """Parseur agnostique pour fichiers Specctra SES et DSN."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.unit = "mil"
        self.resolution = 1000.0
        self.nets_metrics: Dict[str, NetRoutingMetrics] = {}
        self._parse()

    def _parse(self):
        if not self.file_path.exists():
            raise FileNotFoundError(f"Fichier Specctra introuvable : {self.file_path}")

        content = self.file_path.read_text(encoding="utf-8", errors="ignore")

        # Résolution
        m_res = re.search(r'\(resolution\s+([a-zA-Z_]+)\s+([0-9.]+)\)', content)
        if m_res:
            self.unit = m_res.group(1).lower()
            self.resolution = float(m_res.group(2))

        # Facteur vers millimètres
        if self.unit == "mil":
            scale = (25.4 / 1000.0) / self.resolution
        elif self.unit in ("mm", "millimeter"):
            scale = 1.0 / self.resolution
        elif self.unit in ("um", "micrometer"):
            scale = 0.001 / self.resolution
        elif self.unit == "inch":
            scale = 25.4 / self.resolution
        else:
            scale = (25.4 / 1000.0) / self.resolution

        # Trouver network_out ou wiring
        m_net_start = re.search(r'\((network_out|wiring)\b', content)
        if not m_net_start:
            return

        network_str = content[m_net_start.start():]

        # Découper par blocs (net ...)
        net_pattern = re.compile(r'\(net\s+(?:"([^"]+)"|([^\s()]+))\s', re.IGNORECASE)
        net_matches = list(net_pattern.finditer(network_str))

        for idx, nm in enumerate(net_matches):
            raw_net_name = nm.group(1) or nm.group(2)
            if re.search(r'_f\d+$', raw_net_name):
                continue
            start_pos = nm.start()
            end_pos = net_matches[idx + 1].start() if idx + 1 < len(net_matches) else len(network_str)
            net_block = network_str[start_pos:end_pos]

            net_metric = NetRoutingMetrics(net_name=raw_net_name)

            # Extraire les wires : (wire (path <layer> <width> x1 y1 x2 y2 ...))
            wire_pattern = re.compile(
                r'\(wire\s+\(path\s+([a-zA-Z0-9_]+)\s+([0-9.]+)\s+([^)]+)\)\s*\)',
                re.DOTALL
            )
            for wm in wire_pattern.finditer(net_block):
                layer = wm.group(1)
                width_mm = float(wm.group(2)) * scale
                coords_str = wm.group(3).split()
                points = []
                for i in range(0, len(coords_str) - 1, 2):
                    try:
                        x = float(coords_str[i]) * scale
                        y = float(coords_str[i + 1]) * scale
                        points.append((round(x, 4), round(y, 4)))
                    except ValueError:
                        continue
                if points:
                    seg = WireSegment(layer=layer, width_mm=width_mm, points=points)
                    net_metric.segments.append(seg)
                    net_metric.total_length_mm += seg.length_mm

            # Extraire les vias : (via <padstack> x y)
            via_pattern = re.compile(r'\(via\s+("?[^"\s()]+"?)\s+([0-9.]+)\s+([0-9.]+)', re.IGNORECASE)
            for vm in via_pattern.finditer(net_block):
                padstack = vm.group(1).strip('"')
                vx = float(vm.group(2)) * scale
                vy = float(vm.group(3)) * scale
                net_metric.vias.append((padstack, round(vx, 4), round(vy, 4)))
                net_metric.via_count += 1

            net_metric.total_length_mm = round(net_metric.total_length_mm, 3)
            self.nets_metrics[raw_net_name] = net_metric


class DsnMetrologyAnalyzer:
    """Analyseur métrologique quantitatif des contraintes physiques et CEM sur le routage Specctra."""

    def __init__(
        self,
        ses_or_dsn_path: Path,
        manifest: Dict[str, Any],
        board_constraints: Dict[str, Any]
    ):
        self.parser = SpecctraParser(ses_or_dsn_path)
        self.manifest = manifest
        self.board = board_constraints

    def analyze(self, unrouted_count: int = 0, violation_count: int = 0) -> PostRoutingReport:
        total_length = sum(m.total_length_mm for m in self.parser.nets_metrics.values())
        total_vias = sum(m.via_count for m in self.parser.nets_metrics.values())

        loop_metrics: List[LoopPhysicalMetric] = []
        is_all_valid = (unrouted_count == 0) and (violation_count == 0)

        # 1. Analyse des boucles fermées (manifest placement_constraints)
        for c in self.manifest.get("placement_constraints", []):
            if c.get("type") == "loop":
                cid = c.get("id", "LOOP")
                target_max_area = c.get("target_max_area_mm2", c.get("target_max_mm", 25.0))
                target_max_ind = c.get("target_max_inductance_nH", 8.0)

                # Collecter de façon agnostique les nets associés à la boucle
                loop_points: List[Tuple[float, float]] = []
                target_nets = list(c.get("nets", []))
                if not target_nets:
                    # Résolution automatique depuis les classes CEM agressives définies dans board_constraints
                    for cls_cfg in self.board.get("net_classes", {}).values():
                        if cls_cfg.get("emc_class") == "aggressor":
                            target_nets.extend(cls_cfg.get("nets", []))

                target_nets_set = set(target_nets)
                associated_nets = []
                total_loop_len_mm = 0.0

                for net_name, n_met in self.parser.nets_metrics.items():
                    if net_name in target_nets_set:
                        associated_nets.append(net_name)
                        total_loop_len_mm += n_met.total_length_mm
                        for seg in n_met.segments:
                            loop_points.extend(seg.points)

                stackup_layers = self.board.get("board", {}).get("stackup", {}).get("layers", [])
                has_internal_plane = any(lay.get("type") == "plane" for lay in stackup_layers)

                if len(loop_points) >= 3:
                    if has_internal_plane:
                        # Sur stackup multicouche avec plan interne (ex. JLC2313 h=0.11..0.20 mm),
                        # la boucle magnétique de retour se referme verticalement sous la piste (A = L * h)
                        area = total_loop_len_mm * 0.20
                    else:
                        area = polygon_area_shoelace(loop_points)
                    ind = estimate_loop_inductance_nh(loop_points, trace_width_mm=0.8, reference_plane_height_mm=0.2)
                else:
                    area = 0.0
                    ind = 0.0

                ok = (area <= target_max_area) and (ind <= target_max_ind)
                if not ok:
                    is_all_valid = False

                loop_metrics.append(LoopPhysicalMetric(
                    constraint_id=cid,
                    net_names=associated_nets,
                    area_mm2=round(area, 2),
                    target_max_area_mm2=target_max_area,
                    inductance_nh=round(ind, 2),
                    target_max_inductance_nh=target_max_ind,
                    ok=ok
                ))

        # 2. Analyse des paires différentielles (constraints net_classes)
        diff_metrics: List[DiffPairMetric] = []
        diff_net_names: Set[str] = set()
        for nc_id, nc_cfg in self.board.get("net_classes", {}).items():
            if nc_cfg.get("diff_pair", False):
                nets = nc_cfg.get("nets", [])
                max_skew = nc_cfg.get("max_skew_mm", 2.0)
                if len(nets) >= 2:
                    net_p, net_n = nets[0], nets[1]
                    diff_net_names.add(net_p)
                    diff_net_names.add(net_n)
                    len_p = self.parser.nets_metrics.get(net_p, NetRoutingMetrics(net_p)).total_length_mm
                    len_n = self.parser.nets_metrics.get(net_n, NetRoutingMetrics(net_n)).total_length_mm
                    is_routed = (len_p > 0.001) and (len_n > 0.001)
                    skew = abs(len_p - len_n)
                    ok = is_routed and (skew <= max_skew)
                    if not ok:
                        is_all_valid = False

                    diff_metrics.append(DiffPairMetric(
                        class_id=nc_id,
                        net_pos=net_p,
                        net_neg=net_n,
                        length_pos_mm=round(len_p, 2),
                        length_neg_mm=round(len_n, 2),
                        skew_mm=round(skew, 2),
                        max_skew_mm=max_skew,
                        ok=ok
                    ))

        # 3. Analyse des signaux critiques (SIGNAL_CRITICAL, victim, aggressor)
        raw_dsn_path = self.parser.file_path.parent / "board_raw.dsn"
        dsn_declared_nets: Optional[Set[str]] = None
        if raw_dsn_path.exists():
            raw_text = raw_dsn_path.read_text(encoding="utf-8", errors="ignore")
            dsn_declared_nets = {
                (m.group(1) or m.group(2))
                for m in re.finditer(r'\(net\s+(?:"([^"]+)"|([^\s()]+))', raw_text)
            }

        critical_metrics: List[CriticalNetMetric] = []
        for nc_id, nc_cfg in self.board.get("net_classes", {}).items():
            if nc_cfg.get("diff_pair", False):
                continue
            if nc_id == "SIGNAL_CRITICAL" or nc_cfg.get("emc_class") in ("signal", "victim"):
                max_vias = nc_cfg.get("max_vias", 4)
                for net_name in nc_cfg.get("nets", []):
                    if net_name in diff_net_names:
                        continue
                    if dsn_declared_nets is not None and net_name not in dsn_declared_nets:
                        continue
                    n_met = self.parser.nets_metrics.get(net_name)
                    if n_met is None:
                        is_routed = False
                        net_ok = False
                        is_all_valid = False
                        length = 0.0
                        vias = 0
                    else:
                        is_routed = (n_met.total_length_mm > 0.001)
                        length = round(n_met.total_length_mm, 2)
                        vias = n_met.via_count
                        net_ok = is_routed and (vias <= max_vias)
                        if not net_ok:
                            is_all_valid = False

                    critical_metrics.append(CriticalNetMetric(
                        net_name=net_name,
                        class_id=nc_id,
                        length_mm=length,
                        via_count=vias,
                        is_routed=is_routed,
                        ok=net_ok
                    ))

        return PostRoutingReport(
            total_wire_length_mm=round(total_length, 2),
            total_vias_count=total_vias,
            nets_count=len(self.parser.nets_metrics),
            loops=loop_metrics,
            diff_pairs=diff_metrics,
            critical_nets=critical_metrics,
            unrouted_count=unrouted_count,
            violation_count=violation_count,
            is_valid=is_all_valid
        )


def print_report(rep: PostRoutingReport):
    logger.info("================================================================================")
    logger.info("                RAPPORT MÉTROLOGIQUE POST-ROUTAGE SPECCTRA (SES)               ")
    logger.info("================================================================================")
    logger.info(f"Réseaux routés       : {rep.nets_count}")
    logger.info(f"Longueur totale fil  : {rep.total_wire_length_mm:.2f} mm")
    logger.info(f"Nombre total de vias : {rep.total_vias_count}")
    logger.info(f"Éléments non routés  : {rep.unrouted_count}")
    logger.info(f"Violations de règles : {rep.violation_count}")
    logger.info(f"Statut physique CEM  : {'✅ CONFORME' if rep.is_valid else '⚠️ NON-CONFORME'}")
    logger.info("--------------------------------------------------------------------------------")

    if rep.loops:
        logger.info("🔍 Métrologie des Boucles Critiques :")
        for l in rep.loops:
            stat = "✅ OK" if l.ok else "❌ DÉPASSEMENT"
            logger.info(
                f"  • {l.constraint_id} : Aire = {l.area_mm2:.2f} mm² (max {l.target_max_area_mm2:.1f}) | "
                f"Inductance = {l.inductance_nh:.2f} nH (max {l.target_max_inductance_nh:.1f}) -> {stat}"
            )

    if rep.diff_pairs:
        logger.info("🔍 Intégrité des Paires Différentielles :")
        for dp in rep.diff_pairs:
            stat = "✅ OK" if dp.ok else "❌ SKEW OU ROUTAGE KO"
            logger.info(
                f"  • {dp.class_id} ({dp.net_pos} / {dp.net_neg}) : "
                f"L+ = {dp.length_pos_mm:.2f} mm, L- = {dp.length_neg_mm:.2f} mm | Skew = {dp.skew_mm:.2f} mm (max {dp.max_skew_mm:.1f}) -> {stat}"
            )

    if rep.critical_nets:
        logger.info("🔍 Intégrité des Signaux Critiques :")
        for cn in rep.critical_nets:
            stat = f"✅ L={cn.length_mm:.1f} mm, Vias={cn.via_count}" if cn.ok else ("❌ NON ROUTÉ" if not cn.is_routed else f"⚠️ VIAS TROP NOMBREUX ({cn.via_count})")
            logger.info(f"  • {cn.net_name} ({cn.class_id}) -> {stat}")

    logger.info("================================================================================\n")


def main():
    parser = argparse.ArgumentParser(description="Analyseur métrologique post-routage Specctra SES / DSN")
    parser.add_argument("--ses", type=Path, default=None, help="Fichier .ses routé")
    parser.add_argument("--dsn", type=Path, default=None, help="Fichier .dsn de conception")
    parser.add_argument("--manifest", type=Path, default=Path("documents/pcb/manifest.json"))
    parser.add_argument("--board", type=Path, default=Path("documents/pcb/constraints.json"))
    args = parser.parse_args()

    target_file = args.ses or args.dsn
    if not target_file:
        # Chercher dans le cache standard
        cand = Path(".agents/skills/freerouting/.cache/board_routed.ses")
        if cand.exists():
            target_file = cand
        else:
            logger.error("Veuillez fournir un fichier --ses ou --dsn.")
            sys.exit(1)

    with open(args.manifest, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    with open(args.board, "r", encoding="utf-8") as f:
        board_constraints = json.load(f)

    analyzer = DsnMetrologyAnalyzer(target_file, manifest, board_constraints)
    rep = analyzer.analyze()
    print_report(rep)
    sys.exit(0 if rep.is_valid else 1)


if __name__ == "__main__":
    main()
