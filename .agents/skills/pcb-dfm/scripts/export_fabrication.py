#!/usr/bin/env python3
"""
Générateur Automatique du Dossier de Fabrication (Gerber, CPL, BOM)
==================================================================
Skill: pcb-dfm
Règle 1: Moteur agnostique, zéro composant codé en dur, exécution uv run.
Exporte les livrables de production industrielle depuis EasyEDA Pro via le pont local :
1. Archive Gerber RS-274X & Perçages Excellon (ZIP)
2. Fichier de Centroïdes Pick & Place (CPL CSV)
3. Fichier de Nomenclature d'Assemblage SMT (BOM CSV)
"""

import sys
import json
import base64
import zipfile
import logging
import argparse
import urllib.request
import urllib.error
from io import BytesIO
from pathlib import Path
from typing import Dict, Any, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pcb_dfm.export_fabrication")


class EasyEdaFabricationExporter:
    """Client d'exportation des livrables de fabrication depuis EasyEDA Pro."""

    def __init__(self, host: str = "127.0.0.1", port: int = 49620, timeout: float = 60.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{self.host}:{self.port}"

    def check_connection(self) -> bool:
        """Vérifie la disponibilité du pont et du client EasyEDA Pro."""
        try:
            req = urllib.request.Request(f"{self.base_url}/health")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("status") == "ok" and data.get("edaConnected", False)
        except Exception as e:
            logger.debug(f"Pont inaccessible : {e}")
            return False

    def execute_js(self, js_code: str) -> Any:
        """Exécute du code JavaScript dans le client EasyEDA Pro."""
        req = urllib.request.Request(
            f"{self.base_url}/execute",
            data=json.dumps({"code": js_code}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                if not res.get("success"):
                    raise RuntimeError(f"Erreur EasyEDA: {res.get('error')}")
                return res.get("result")
        except urllib.error.HTTPError as e:
            error_msg = e.read().decode("utf-8")
            raise RuntimeError(f"Erreur HTTP {e.code}: {error_msg}")

    def export_gerber_zip(self, file_prefix: str) -> bytes:
        """Génère et rapatrie l'archive ZIP des fichiers Gerber et de perçage."""
        js_code = f"""
        const gerber = await eda.pcb_ManufactureData.getGerberFile('{file_prefix}_Gerber');
        if (!gerber) {{
            return {{ success: false, error: 'Aucun fichier Gerber renvoyé par EasyEDA Pro' }};
        }}
        const buf = await gerber.arrayBuffer();
        const bytes = new Uint8Array(buf);
        let binary = '';
        const chunk = 8192;
        for (let i = 0; i < bytes.length; i += chunk) {{
            binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
        }}
        return {{
            success: true,
            fileName: gerber.name,
            size: bytes.length,
            base64: btoa(binary)
        }};
        """
        result = self.execute_js(js_code)
        if not result.get("success"):
            raise RuntimeError(f"Échec export Gerber : {result.get('error')}")
        return base64.b64decode(result["base64"])

    def export_cpl_csv(self, file_prefix: str) -> str:
        """Génère et rapatrie le fichier CSV Pick & Place (centroïdes et rotations)."""
        js_code = f"""
        // 1 = ESYS_Unit.MILLIMETER
        const pnp = await eda.pcb_ManufactureData.getPickAndPlaceFile('{file_prefix}_PickAndPlace', 'csv', 1);
        if (!pnp) {{
            return {{ success: false, error: 'Aucun fichier Pick & Place renvoyé par EasyEDA Pro' }};
        }}
        const text = await pnp.text();
        return {{
            success: true,
            fileName: pnp.name,
            content: text
        }};
        """
        result = self.execute_js(js_code)
        if not result.get("success"):
            raise RuntimeError(f"Échec export CPL : {result.get('error')}")
        return result["content"]

    def export_bom_csv(self, file_prefix: str) -> str:
        """Génère et rapatrie le fichier CSV de nomenclature BOM pour l'assemblage SMT."""
        js_code = f"""
        const bom = await eda.pcb_ManufactureData.getBomFile('{file_prefix}_BOM', 'csv');
        if (!bom) {{
            return {{ success: false, error: 'Aucun fichier BOM renvoyé par EasyEDA Pro' }};
        }}
        const text = await bom.text();
        return {{
            success: true,
            fileName: bom.name,
            content: text
        }};
        """
        result = self.execute_js(js_code)
        if not result.get("success"):
            raise RuntimeError(f"Échec export BOM : {result.get('error')}")
        return result["content"]

    def export_project_archive(self, prefix: str = "OBD2", receiver_port: int = 49698) -> bytes:
        """Exporte l'archive projet complète (.epro2) via flux HTTP local sécurisé."""
        import http.server
        import threading

        received_data = bytearray()
        done_event = threading.Event()

        class ReceiverHandler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                content_len = int(self.headers.get("Content-Length", 0))
                data = self.rfile.read(content_len)
                received_data.extend(data)
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b"OK")
                done_event.set()

            def do_OPTIONS(self):
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

            def log_message(self, format, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", receiver_port), ReceiverHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            js_code = f"""
            const f = await eda.sys_FileManager.getProjectFile('{prefix}', undefined, 'epro2');
            if (!f) throw new Error('Impossible d\\'obtenir le fichier projet epro2');
            await fetch('http://127.0.0.1:{receiver_port}/upload', {{
                method: 'POST',
                body: f,
                headers: {{ 'Content-Type': 'application/octet-stream' }}
            }});
            return {{ size: f.size, name: f.name }};
            """
            self.execute_js(js_code)
            done_event.wait(timeout=15.0)
            return bytes(received_data)
        finally:
            server.shutdown()


def run_fabrication_export(
    output_dir: str,
    prefix: str = "OBD2",
    port: int = 49620,
    include_gerber: bool = True,
    include_cpl: bool = True,
    include_bom: bool = True,
    include_epro2: bool = True
) -> Dict[str, Any]:
    """Exécute l'exportation complète des livrables de production."""
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    logger.info("==================================================")
    logger.info("Démarrage de l'Exportation du Dossier de Fabrication")
    logger.info(f"Dossier cible : {target_dir.resolve()}")
    logger.info(f"Préfixe des fichiers : {prefix}")

    client = EasyEdaFabricationExporter(port=port)
    if not client.check_connection():
        logger.error(f"Le pont EasyEDA Pro sur le port {port} n'est pas accessible ou aucun document PCB n'est ouvert.")
        return {"success": False, "error": "EasyEDA Pro non connecté"}

    exported_files = {}

    # 1. Export Gerber ZIP
    if include_gerber:
        logger.info("Génération et téléchargement des fichiers Gerber & Drill...")
        gerber_bytes = client.export_gerber_zip(prefix)
        gerber_filename = f"Gerber_{prefix}.zip"
        gerber_path = target_dir / gerber_filename
        with open(gerber_path, "wb") as f:
            f.write(gerber_bytes)

        # Inspection de l'archive ZIP générée
        layers = []
        with zipfile.ZipFile(BytesIO(gerber_bytes)) as z:
            layers = z.namelist()

        logger.info(f"Archive Gerber créée : {gerber_path.name} ({len(gerber_bytes) / 1024:.1f} Ko, {len(layers)} couches)")
        exported_files["gerber"] = {
            "path": str(gerber_path),
            "size_bytes": len(gerber_bytes),
            "file_count": len(layers),
            "layers": layers
        }

    # 2. Export Pick & Place (CPL) CSV
    if include_cpl:
        logger.info("Génération du fichier Pick & Place (CPL / Centroïdes)...")
        cpl_text = client.export_cpl_csv(prefix)
        cpl_filename = f"PickAndPlace_{prefix}.csv"
        cpl_path = target_dir / cpl_filename
        with open(cpl_path, "w", encoding="utf-8") as f:
            f.write(cpl_text)

        lines = [line for line in cpl_text.splitlines() if line.strip()]
        component_count = max(0, len(lines) - 1)  # Moins l'en-tête
        logger.info(f"Fichier CPL créé : {cpl_path.name} ({component_count} composants)")
        exported_files["cpl"] = {
            "path": str(cpl_path),
            "component_count": component_count
        }

    # 3. Export BOM CSV
    if include_bom:
        logger.info("Génération de la nomenclature de production (BOM SMT)...")
        bom_text = client.export_bom_csv(prefix)
        bom_filename = f"BOM_{prefix}.csv"
        bom_path = target_dir / bom_filename
        with open(bom_path, "w", encoding="utf-8") as f:
            f.write(bom_text)

        lines = [line for line in bom_text.splitlines() if line.strip()]
        row_count = max(0, len(lines) - 1)
        logger.info(f"Fichier BOM créé : {bom_path.name} ({row_count} lignes)")
        exported_files["bom"] = {
            "path": str(bom_path),
            "row_count": row_count
        }

    # 4. Export Archive Projet Native (.epro2)
    if include_epro2:
        logger.info("Génération de l'archive projet native EasyEDA Pro (.epro2)...")
        try:
            epro2_bytes = client.export_project_archive(prefix)
            if epro2_bytes:
                easyeda_dir = Path("documents/easyeda")
                easyeda_dir.mkdir(parents=True, exist_ok=True)
                epro2_path = easyeda_dir / f"{prefix}.epro2"
                with open(epro2_path, "wb") as f:
                    f.write(epro2_bytes)
                logger.info(f"Archive projet native créée : {epro2_path} ({len(epro2_bytes) / 1024:.1f} Ko)")
                exported_files["epro2"] = {
                    "path": str(epro2_path),
                    "size_bytes": len(epro2_bytes)
                }
        except Exception as e:
            logger.warning(f"Avertissement lors de l'export de l'archive .epro2 : {e}")

    logger.info("Dossier de fabrication généré avec succès !")
    return {"success": True, "output_dir": str(target_dir.resolve()), "files": exported_files}


def main():
    parser = argparse.ArgumentParser(description="Exportateur du Dossier de Fabrication JLCPCB depuis EasyEDA Pro")
    parser.add_argument(
        "--output-dir", "-o",
        default="documents/production",
        help="Répertoire de sortie des livrables (défaut: documents/production)"
    )
    parser.add_argument(
        "--prefix", "-p",
        default="OBD2",
        help="Préfixe des fichiers générés (défaut: OBD2)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=49620,
        help="Port HTTP du pont local EasyEDA Pro (défaut: 49620)"
    )
    parser.add_argument("--no-gerber", action="store_true", help="Ne pas exporter les Gerber")
    parser.add_argument("--no-cpl", action="store_true", help="Ne pas exporter le Pick & Place (CPL)")
    parser.add_argument("--no-bom", action="store_true", help="Ne pas exporter la BOM")
    parser.add_argument("--no-epro2", action="store_true", help="Ne pas exporter l'archive projet .epro2")

    args = parser.parse_args()
    res = run_fabrication_export(
        output_dir=args.output_dir,
        prefix=args.prefix,
        port=args.port,
        include_gerber=not args.no_gerber,
        include_cpl=not args.no_cpl,
        include_bom=not args.no_bom,
        include_epro2=not args.no_epro2
    )
    sys.exit(0 if res.get("success") else 1)


if __name__ == "__main__":
    main()
