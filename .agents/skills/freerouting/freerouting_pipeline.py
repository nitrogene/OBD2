#!/usr/bin/env python3
"""
Pipeline Maître d'Auto-Routage Headless FreeRouting pour EasyEDA Pro
===================================================================
Skill: freerouting
Règle 0: Ce pipeline est un moteur d'orchestration purement agnostique.
Il ne contient aucun composant ni règle figée en dur dans son code.
Toutes les règles géométriques et CEM proviennent du fichier de contraintes (--config).
"""

import sys
import json
import time
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from jre_manager import ensure_environment
from dsn_exporter import export_dsn_from_easyeda
from dsn_patcher import patch_dsn_file
from router import FreeRoutingRunner
from ses_importer import import_ses_into_easyeda

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="[freerouting] %(message)s")
logger = logging.getLogger("freerouting")


class FreeRoutingPipeline:
    """Orchestre la chaîne complète d'auto-routage headless."""

    def __init__(
        self,
        config_path: Path,
        cache_dir: Optional[Path] = None,
        max_passes: int = 10,
        threads: int = 1,
        updating_strategy: str = "hybrid",
        incremental: bool = False,
        clean: bool = False,
    ):
        self.config_path = Path(config_path).resolve()
        self.cache_dir = (cache_dir or (Path(__file__).resolve().parent / ".cache")).resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_passes = max_passes
        self.threads = threads
        self.updating_strategy = updating_strategy
        self.incremental = incremental
        self.clean = clean

    def clear_routing_in_easyeda(self) -> bool:
        """Efface les pistes des couches cuivre (Top/Bottom) et vias pour un re-routage à blanc sans toucher au contour."""
        import urllib.request
        js_code = """
        const lines = await eda.pcb_PrimitiveLine.getAll();
        const trackIds = lines ? lines.filter(l => l.layer === 1 || l.layer === 2 || l.layer === '1' || l.layer === '2').map(l => l.primitiveId) : [];
        if (trackIds.length > 0) {
            await eda.pcb_PrimitiveLine.delete(trackIds);
        }
        const vias = await eda.pcb_PrimitiveVia.getAll();
        const viaIds = vias ? vias.map(v => v.primitiveId) : [];
        if (viaIds.length > 0) {
            await eda.pcb_PrimitiveVia.delete(viaIds);
        }
        return true;
        """
        payload = json.dumps({"code": js_code}).encode("utf-8")
        req = urllib.request.Request(
            "http://localhost:49620/execute",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return bool(data.get("result"))
        except Exception as e:
            logger.warning(f"Impossible de supprimer les pistes dans EasyEDA : {e}")
            return False

    def run(
        self,
        dsn_input: Optional[Path] = None,
        auto_import: bool = True,
        save_after_import: bool = False,
    ) -> Dict[str, Any]:
        """Exécute les 4 étapes du pipeline de routage."""
        start_time = time.time()
        results: Dict[str, Any] = {
            "success": False,
            "stage": "INIT",
            "duration_sec": 0.0,
            "metrics": {},
        }

        print("\n" + "=" * 65)
        print("  DÉMARRAGE DU PIPELINE D'AUTO-ROUTAGE FREEROUTING HEADLESS")
        print("=" * 65)

        # ÉTAPE 0 : Vérification environnement JRE + JAR
        logger.info("[1/4] Vérification de l'environnement d'exécution portable...")
        java_exe, jar_bin = ensure_environment()
        logger.info(f"      Java : {java_exe.name} | Moteur : {jar_bin.name}")

        # ÉTAPE 1 : Nettoyage éventuel et acquisition du fichier Specctra DSN
        if self.clean:
            logger.info("Mode --clean activé : effacement des pistes non fixées dans EasyEDA Pro...")
            self.clear_routing_in_easyeda()

        raw_dsn = self.cache_dir / "board_raw.dsn"
        if dsn_input and Path(dsn_input).exists():
            logger.info(f"[2/4] Utilisation du fichier DSN fourni : {dsn_input}")
            shutil.copyfile(dsn_input, raw_dsn)
        else:
            logger.info("[2/4] Extraction directe du Specctra DSN depuis EasyEDA Pro...")
            try:
                export_dsn_from_easyeda(raw_dsn)
            except Exception as e:
                logger.error(f"Échec de l'export DSN : {e}")
                results["stage"] = "DSN_EXPORT"
                return results

        # ÉTAPE 2 : Injection des contraintes et classes de nets
        patched_dsn = self.cache_dir / "board_patched.dsn"
        logger.info(f"[3/4] Injection des contraintes depuis {self.config_path.name}...")
        try:
            patch_dsn_file(
                input_dsn=raw_dsn,
                config_path=self.config_path,
                output_dsn=patched_dsn,
                incremental=self.incremental,
            )
        except Exception as e:
            logger.error(f"Échec de l'injection des contraintes : {e}")
            results["stage"] = "DSN_PATCH"
            return results

        # ÉTAPE 3 : Exécution de FreeRouting en CLI
        output_ses = self.cache_dir / "board_routed.ses"
        logger.info(f"[4/4] Lancement du moteur FreeRouting (passes={self.max_passes}, threads={self.threads})...")
        runner = FreeRoutingRunner(
            dsn_path=patched_dsn,
            ses_path=output_ses,
            max_passes=self.max_passes,
            threads=self.threads,
            updating_strategy=self.updating_strategy,
        )
        router_metrics = runner.run()
        results["metrics"] = router_metrics

        if not router_metrics.get("output_ses_exists"):
            logger.error("Le fichier de session de routage (SES) n'a pas été produit.")
            results["stage"] = "ROUTING"
            return results

        # ÉTAPE 4 : Réimport dans EasyEDA Pro
        if auto_import:
            logger.info("Réimport automatique du résultat (.ses) dans EasyEDA Pro...")
            try:
                import_ok = import_ses_into_easyeda(output_ses, save_after_import=save_after_import)
                if not import_ok:
                    logger.warning("L'import SES a été refusé par EasyEDA Pro.")
            except Exception as e:
                logger.error(f"Erreur lors du réimport SES : {e}")
                results["stage"] = "SES_IMPORT"
                return results

        results["success"] = router_metrics.get("success", False)
        results["duration_sec"] = round(time.time() - start_time, 2)
        results["stage"] = "COMPLETED"

        print("\n" + "=" * 65)
        print(f"  SYNTHÈSE DU PIPELINE ({results['duration_sec']} s)")
        print("=" * 65)
        print(f"  Statut global : {'SUCCÈS' if results['success'] else 'PARTIEL / ATTENTION'}")
        print(f"  Non routés    : {router_metrics.get('unrouted_items')}")
        print(f"  Violations    : {router_metrics.get('violations')}")
        print(f"  Score final   : {router_metrics.get('score')}")
        print(f"  Passes        : {router_metrics.get('passes_completed')}")
        print(f"  Fichier SES   : {output_ses}")
        print("=" * 65 + "\n")

        return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Pipeline d'auto-routage FreeRouting pour EasyEDA Pro")
    parser.add_argument("--config", type=Path, required=True, help="Chemin vers le fichier de contraintes JSON")
    parser.add_argument("--dsn", type=Path, help="Fichier DSN source (optionnel, exporté en live si omis)")
    parser.add_argument("--passes", type=int, default=10, help="Nombre maximal de passes d'auto-routage (défaut: 10)")
    parser.add_argument("--threads", type=int, default=1, help="Nombre de threads (défaut: 1)")
    parser.add_argument("--strategy", type=str, default="hybrid", choices=["greedy", "global", "hybrid"], help="Stratégie d'optimisation")
    parser.add_argument("--incremental", action="store_true", help="Protège les pistes existantes du circuit")
    parser.add_argument("--clean", action="store_true", help="Efface les pistes existantes non protégées avant le routage")
    parser.add_argument("--no-import", action="store_true", help="Génère le .ses sans le réimporter dans EasyEDA Pro")
    parser.add_argument("--save", action="store_true", help="Sauvegarde le document PCB après l'importation")
    args = parser.parse_args()

    pipeline = FreeRoutingPipeline(
        config_path=args.config,
        max_passes=args.passes,
        threads=args.threads,
        updating_strategy=args.strategy,
        incremental=args.incremental,
        clean=args.clean,
    )
    res = pipeline.run(
        dsn_input=args.dsn,
        auto_import=not args.no_import,
        save_after_import=args.save,
    )
    sys.exit(0 if res["success"] else 1)
