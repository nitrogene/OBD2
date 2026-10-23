#!/usr/bin/env python3
"""
Importateur Specctra SES dans EasyEDA Pro via le pont local
==========================================================
Skill: freerouting
Règle 0: Ce script est purement agnostique.
Il transmet le fichier SES au document PCB actif dans EasyEDA Pro.
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

logger = logging.getLogger("freerouting.ses_importer")

BRIDGE_URL = "http://localhost:49620/execute"


def import_ses_into_easyeda(
    ses_path: Path,
    save_after_import: bool = False,
    timeout_sec: float = 60.0,
) -> bool:
    """Importe un fichier SES dans la session active d'EasyEDA Pro."""
    ses_path = Path(ses_path).resolve()
    if not ses_path.exists():
        raise FileNotFoundError(f"Fichier SES introuvable : {ses_path}")

    with open(ses_path, "r", encoding="utf-8") as f:
        ses_content = f.read()

    # Purger les mini-réseaux temporaires de fanout (*_f1, *_f2...) déjà présents sur le PCB
    import re
    pattern_f = re.compile(r'\(net\s+(?:"[^"]+_f\d+"|[^\s()]+_f\d+)\b')
    while True:
        m = pattern_f.search(ses_content)
        if not m:
            break
        s_idx = m.start()
        depth = 0
        e_idx = s_idx
        for i in range(s_idx, len(ses_content)):
            if ses_content[i] == '(':
                depth += 1
            elif ses_content[i] == ')':
                depth -= 1
                if depth == 0:
                    e_idx = i + 1
                    break
        ses_content = ses_content[:s_idx] + ses_content[e_idx:]

    logger.info(f"Préparation de l'import SES ({len(ses_content)} octets) vers EasyEDA Pro...")

    # Injection JS dans EasyEDA Pro
    js_code = """
    const sesText = SES_CONTENT_PLACEHOLDER;
    const file = new File([sesText], "autoroute.ses", { type: "text/plain" });
    const importSuccess = await eda.pcb_Document.importAutoRouteSesFile(file);
    let saved = false;
    if (importSuccess && SAVE_FLAG) {
        saved = await eda.pcb_Document.save();
    }
    return {
        success: Boolean(importSuccess),
        saved: Boolean(saved)
    };
    """
    js_code = js_code.replace("SES_CONTENT_PLACEHOLDER", json.dumps(ses_content))
    js_code = js_code.replace("SAVE_FLAG", "true" if save_after_import else "false")

    payload = json.dumps({"code": js_code}).encode("utf-8")
    req = urllib.request.Request(
        BRIDGE_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise ConnectionError(f"Impossible de joindre le pont EasyEDA Pro sur {BRIDGE_URL}: {e}")

    if not data.get("success"):
        raise RuntimeError(f"Erreur d'exécution de l'import SES dans EasyEDA : {data.get('error')}")

    res = data.get("result", {})
    success = res.get("success", False)
    if success:
        logger.info(f"Import SES validé dans EasyEDA Pro (sauvegarde auto: {res.get('saved')})")
    else:
        logger.warning("EasyEDA Pro a renvoyé false lors de l'appel à importAutoRouteSesFile.")

    return success


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="[ses_importer] %(message)s")
    parser = argparse.ArgumentParser(description="Importateur Specctra SES dans EasyEDA Pro")
    parser.add_argument("--ses", type=Path, required=True, help="Chemin du fichier SES à importer")
    parser.add_argument("--save", action="store_true", help="Sauvegarde le PCB après l'import")
    args = parser.parse_args()

    ok = import_ses_into_easyeda(args.ses, save_after_import=args.save)
    sys.exit(0 if ok else 1)
