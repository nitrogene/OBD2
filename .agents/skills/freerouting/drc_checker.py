#!/usr/bin/env python3
"""
Vérificateur DRC physique pour EasyEDA Pro
==========================================
Skill: freerouting
Règle 0: Ce script est purement agnostique.
Il interroge le moteur DRC d'EasyEDA Pro pour remonter les violations en temps réel.
"""

import sys
import json
import logging
import urllib.request
from typing import Dict, Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logger = logging.getLogger("freerouting.drc_checker")

BRIDGE_URL = "http://localhost:49620/execute"


def run_drc_check() -> Dict[str, Any]:
    """Déclenche la vérification DRC sous EasyEDA Pro et synthétise les résultats."""
    js_code = """
    const groups = await eda.pcb_Drc.check(true, false, true);
    let totalErrors = 0;
    const categories = [];
    if (Array.isArray(groups)) {
        for (const g of groups) {
            const count = g.count || (g.list ? g.list.length : 0);
            totalErrors += count;
            categories.push({
                name: g.name,
                count: count,
                title: Array.isArray(g.title) ? g.title.join(' ') : (g.title || g.name)
            });
        }
    }
    return {
        totalErrors,
        categories,
        success: (totalErrors === 0)
    };
    """
    payload = json.dumps({"code": js_code}).encode("utf-8")
    req = urllib.request.Request(
        BRIDGE_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    logger.info("Lancement du contrôle DRC sous EasyEDA Pro...")
    try:
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise ConnectionError(f"Impossible de joindre le pont EasyEDA Pro : {e}")

    if not data.get("success"):
        raise RuntimeError(f"Erreur DRC renvoyée par EasyEDA : {data.get('error')}")

    res = data.get("result", {})
    total = res.get("totalErrors", 0)
    cats = res.get("categories", [])

    logger.info(f"Résultat du DRC EasyEDA Pro : {total} violation(s) au total.")
    for c in cats:
        logger.info(f"  - {c.get('name', 'Violation'):<30} : {c.get('count', 0)} élément(s)")

    return res


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="[drc_checker] %(message)s")
    parser = argparse.ArgumentParser(description="Vérificateur DRC EasyEDA Pro")
    args = parser.parse_args()

    res = run_drc_check()
    sys.exit(0 if res["success"] else 1)
