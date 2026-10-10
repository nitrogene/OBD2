#!/usr/bin/env python3
"""
Orchestrateur d'exécution de FreeRouting en mode headless
=========================================================
Skill: freerouting
Règle 0: Ce module est un moteur d'exécution algorithmique agnostique.
Il ne contient aucun composant ni règle spécifique en dur.
"""

import sys
import re
import time
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from jre_manager import ensure_environment

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logger = logging.getLogger("freerouting.router")


class FreeRoutingRunner:
    """Pilote l'exécution de FreeRouting en ligne de commande et analyse les métriques."""

    def __init__(
        self,
        dsn_path: Path,
        ses_path: Path,
        max_passes: int = 10,
        threads: int = 1,
        updating_strategy: str = "hybrid",
        selection_strategy: str = "prioritized",
        timeout_sec: int = 600,
    ):
        self.dsn_path = Path(dsn_path).resolve()
        self.ses_path = Path(ses_path).resolve()
        self.max_passes = max_passes
        self.threads = threads
        self.updating_strategy = updating_strategy
        self.selection_strategy = selection_strategy
        self.timeout_sec = timeout_sec

        self.java_bin, self.jar_bin = ensure_environment()

    def build_command(self) -> list[str]:
        """Construit la ligne de commande FreeRouting CLI."""
        cmd = [
            str(self.java_bin),
            "-jar",
            str(self.jar_bin),
            "-de",
            str(self.dsn_path),
            "-do",
            str(self.ses_path),
            "-mp",
            str(self.max_passes),
            "-mt",
            str(self.threads),
            "-us",
            self.updating_strategy,
            "-is",
            self.selection_strategy,
        ]
        return cmd

    def run(self) -> Dict[str, Any]:
        """Exécute FreeRouting et analyse la sortie en continu."""
        if not self.dsn_path.exists():
            raise FileNotFoundError(f"Fichier DSN source introuvable : {self.dsn_path}")

        cmd = self.build_command()
        logger.info(f"Lancement de FreeRouting (passes={self.max_passes}, threads={self.threads}, mode={self.updating_strategy})...")
        logger.info(f"DSN source : {self.dsn_path}")
        logger.info(f"SES cible  : {self.ses_path}")

        start_time = time.time()
        metrics: Dict[str, Any] = {
            "success": False,
            "duration_sec": 0.0,
            "unrouted_items": None,
            "violations": None,
            "score": None,
            "passes_completed": 0,
            "output_ses_exists": False,
            "output_ses_size_bytes": 0,
            "summary": "",
        }

        # Regex de parsing des logs FreeRouting
        re_pass = re.compile(
            r"Auto-routing pass #(\d+) .* completed in ([\d.]+) seconds with score ([\d.]+) \((\d+) unrouted and (\d+) violations\)",
            re.IGNORECASE,
        )
        re_stage = re.compile(
            r"Auto-routing stage completed: .* final score: ([\d.]+) \((\d+) unrouted and (\d+) violations\)",
            re.IGNORECASE,
        )
        re_opt = re.compile(
            r"Optimization was completed in ([\d.]+) seconds with the score of ([\d.]+) \((\d+) unrouted and (\d+) violations\)",
            re.IGNORECASE,
        )

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        try:
            for line in proc.stdout:
                line_str = line.strip()
                if not line_str:
                    continue

                # Détection de passes autoroute
                m_pass = re_pass.search(line_str)
                if m_pass:
                    p_num = int(m_pass.group(1))
                    dur = float(m_pass.group(2))
                    score = float(m_pass.group(3))
                    unrouted = int(m_pass.group(4))
                    viols = int(m_pass.group(5))
                    metrics["passes_completed"] = max(metrics["passes_completed"], p_num)
                    metrics["unrouted_items"] = unrouted
                    metrics["violations"] = viols
                    metrics["score"] = score
                    logger.info(
                        f"  -> Passe #{p_num} terminée ({dur:.1f}s) | Score: {score:.1f} | Non routés: {unrouted} | Violations: {viols}"
                    )
                    continue

                # Détection de complétion autoroute
                m_stage = re_stage.search(line_str)
                if m_stage:
                    score = float(m_stage.group(1))
                    unrouted = int(m_stage.group(2))
                    viols = int(m_stage.group(3))
                    metrics["unrouted_items"] = unrouted
                    metrics["violations"] = viols
                    metrics["score"] = score
                    logger.info(
                        f"  -> Autoroutage terminé | Score: {score:.1f} | Non routés: {unrouted} | Violations: {viols}"
                    )
                    continue

                # Détection de complétion optimisation
                m_opt = re_opt.search(line_str)
                if m_opt:
                    score = float(m_opt.group(2))
                    unrouted = int(m_opt.group(3))
                    viols = int(m_opt.group(4))
                    metrics["unrouted_items"] = unrouted
                    metrics["violations"] = viols
                    metrics["score"] = score
                    logger.info(
                        f"  -> Optimisation terminée | Score: {score:.1f} | Non routés: {unrouted} | Violations: {viols}"
                    )
                    continue

                if "WARN" in line_str:
                    logger.warning(f"  [FreeRouting] {line_str}")
                elif "ERROR" in line_str or "Exception" in line_str:
                    logger.error(f"  [FreeRouting] {line_str}")

            proc.wait(timeout=self.timeout_sec)
        except subprocess.TimeoutExpired:
            logger.error(f"Délai d'attente dépassé ({self.timeout_sec}s). Arrêt forcé de FreeRouting.")
            proc.kill()
            proc.wait()

        duration = time.time() - start_time
        metrics["duration_sec"] = round(duration, 2)

        if self.ses_path.exists():
            metrics["output_ses_exists"] = True
            metrics["output_ses_size_bytes"] = self.ses_path.stat().st_size
            if metrics["unrouted_items"] == 0 and metrics["violations"] == 0:
                metrics["success"] = True
                metrics["summary"] = f"Routage 100% complet sans violation ({metrics['passes_completed']} passes, {duration:.1f}s)"
            else:
                metrics["success"] = False
                metrics["summary"] = (
                    f"Routage partiel : {metrics['unrouted_items']} non routés, "
                    f"{metrics['violations']} violations ({duration:.1f}s)"
                )
        else:
            metrics["success"] = False
            metrics["summary"] = f"Échec : le fichier SES n'a pas été généré ({duration:.1f}s)"

        logger.info("=" * 60)
        logger.info(f"Bilan du Routage : {metrics['summary']}")
        logger.info(f"Fichier SES généré : {self.ses_path} ({metrics['output_ses_size_bytes']} octets)")
        logger.info("=" * 60)

        return metrics


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="[router] %(message)s")
    parser = argparse.ArgumentParser(description="Exécuteur FreeRouting headless")
    parser.add_argument("--dsn", type=Path, required=True, help="Fichier Specctra DSN d'entrée")
    parser.add_argument("--ses", type=Path, required=True, help="Fichier Specctra SES de sortie")
    parser.add_argument("--passes", type=int, default=10, help="Nombre max de passes (défaut: 10)")
    parser.add_argument("--threads", type=int, default=1, help="Nombre de threads (défaut: 1 pour éviter les violations)")
    parser.add_argument("--strategy", type=str, default="hybrid", choices=["greedy", "global", "hybrid"], help="Stratégie de mise à jour")
    args = parser.parse_args()

    runner = FreeRoutingRunner(
        dsn_path=args.dsn,
        ses_path=args.ses,
        max_passes=args.passes,
        threads=args.threads,
        updating_strategy=args.strategy,
    )
    res = runner.run()
    sys.exit(0 if res["success"] else 1)
