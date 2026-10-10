#!/usr/bin/env python3
"""
Exportateur Specctra DSN depuis EasyEDA Pro via le pont local
============================================================
Skill: freerouting
Règle 0: Ce script est purement agnostique.
Il extrait dynamiquement le DSN du document PCB actuellement ouvert.
"""

import sys
import json
import logging
import urllib.request
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logger = logging.getLogger("freerouting.dsn_exporter")

BRIDGE_URL = "http://localhost:49620/execute"


def export_dsn_from_easyeda(output_path: Path, timeout_sec: float = 30.0) -> Path:
    """Exécute l'export DSN dans EasyEDA Pro et enregistre le fichier."""
    js_code = """
    const file = await eda.pcb_ManufactureData.getDsnFile('AutoRoute_DSN');
    if (!file) {
        return { success: false, error: 'Aucun fichier renvoyé par getDsnFile' };
    }
    const text = await file.text();
    return {
        success: true,
        fileName: file.name,
        length: text.length,
        dsnContent: text
    };
    """
    payload = json.dumps({"code": js_code}).encode("utf-8")
    req = urllib.request.Request(
        BRIDGE_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    logger.info("Demande d'exportation Specctra DSN à EasyEDA Pro...")
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise ConnectionError(f"Impossible de joindre le pont EasyEDA Pro sur {BRIDGE_URL}: {e}")

    if not data.get("success"):
        raise RuntimeError(f"Erreur renvoyée par le pont EasyEDA Pro : {data.get('error')}")

    res = data.get("result", {})
    if not res.get("success") or not res.get("dsnContent"):
        raise RuntimeError(
            f"Échec de l'export DSN EasyEDA Pro : {res.get('error', 'Contenu vide')}. "
            "Vérifiez que le contour de carte (BoardOutline) forme une boucle fermée et continue."
        )

    dsn_content = res["dsnContent"]
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(dsn_content)

    logger.info(
        f"Export DSN réussi ({res.get('length')} caractères) -> {output_path}"
    )
    return output_path


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="[dsn_exporter] %(message)s")
    parser = argparse.ArgumentParser(description="Exportateur Specctra DSN EasyEDA Pro")
    parser.add_argument("--out", type=Path, required=True, help="Chemin du fichier DSN de sortie")
    args = parser.parse_args()

    export_dsn_from_easyeda(args.out)
