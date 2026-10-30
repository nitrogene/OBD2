#!/usr/bin/env python3
"""
export_pcb_images.py - Export Automatisé des Rendus Visuels PCB (2D Top, 2D Bottom, 3D PCBA, Export Menu PNG)
=============================================================================================================
Skill: pcb-dfm / pcb-silkscreen
Règle 1: Moteur agnostique, zéro composant codé en dur, exécution uv run.

Génère et exporte l'ensemble des livrables visuels depuis EasyEDA Pro via le pont local :
1. `2d-top.png`    : Vue 2D de dessus (masque bleu, pastilles dorées ENIG, pistes Top, sérigraphie Top)
2. `2d-bottom.png` : Vue 2D de dessous (sérigraphie fonctionnelle face arrière, cartouche)
3. `3d.png`        : Vue 3D photo-réaliste garnie de tous les composants CMS et connecteurs (PCBA)
4. `pcb.png`       : Rendu natif complet issu du menu Export -> PNG (toutes couches, DRC, vias, pistes)
"""

import sys
import json
import base64
import logging
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pcb_dfm.export_pcb_images")


class EasyEdaImageExporter:
    """Gestionnaire d'exportation d'images 2D, 3D et du rendu natif depuis EasyEDA Pro."""

    def __init__(self, host: str = "127.0.0.1", port: int = 49620, timeout: float = 40.0):
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
        except Exception:
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

    def capture_all_views(self, output_dir: Path) -> Dict[str, str]:
        """Capture les vues 2D Top, 2D Bottom, 3D PCBA et le rendu natif Export -> PNG."""
        output_dir.mkdir(parents=True, exist_ok=True)

        js_script = """
        const tree = await eda.dmt_EditorControl.getSplitScreenTree();
        const tabs = tree && tree.tabs ? tree.tabs : [];

        // Recherche des onglets PCB, 2D Preview et 3D Preview
        const pcbTab = tabs.find(t => t.data && t.data.doctype === 3);
        let tab2D = tabs.find(t => t.data && t.data.doctype === 12);
        let tab3D = tabs.find(t => t.data && t.data.doctype === 15);

        // Si 2D preview n'est pas ouvert, tenter de cliquer sur le bouton du bas
        if (!tab2D) {
            const btn2D = document.querySelector('[title="2D Preview"]');
            if (btn2D) btn2D.click();
            await new Promise(r => setTimeout(r, 600));
            const newTree = await eda.dmt_EditorControl.getSplitScreenTree();
            tab2D = (newTree.tabs || []).find(t => t.data && t.data.doctype === 12);
        }

        // Si 3D preview n'est pas ouvert, tenter de cliquer sur le bouton du bas
        if (!tab3D) {
            const btn3D = document.querySelector('[title="3D Preview"]');
            if (btn3D) btn3D.click();
            await new Promise(r => setTimeout(r, 600));
            const newTree = await eda.dmt_EditorControl.getSplitScreenTree();
            tab3D = (newTree.tabs || []).find(t => t.data && t.data.doctype === 15);
        }

        function clickToolbarBtn(title) {
            const el = document.querySelector(`.pcb3d-toolbar-btn-container_Y-1HS[title="${title}"]`);
            if (el) { el.click(); return true; }
            return false;
        }

        async function blobToBase64(blob) {
            if (!blob) return null;
            const buf = await blob.arrayBuffer();
            const bytes = new Uint8Array(buf);
            let binary = '';
            const chunk = 8192;
            for (let i = 0; i < bytes.length; i += chunk) {
                binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
            }
            return btoa(binary);
        }

        let topB64 = null;
        let bottomB64 = null;
        let pcb3dB64 = null;
        let nativePngB64 = null;

        // 1. Capture 2D Top et Bottom
        if (tab2D) {
            await eda.dmt_EditorControl.activateDocument(tab2D.tabId);
            await new Promise(r => setTimeout(r, 200));

            // Synchronisation avec les dernières modifications du PCB
            clickToolbarBtn('Import Changes');
            await new Promise(r => setTimeout(r, 400));
            clickToolbarBtn('Refresh');
            await new Promise(r => setTimeout(r, 400));

            // Vue Dessus (Top)
            clickToolbarBtn('Top Side');
            clickToolbarBtn('Fit All in Window');
            await new Promise(r => setTimeout(r, 300));
            const imgTop = await eda.dmt_EditorControl.getCurrentRenderedAreaImage(tab2D.tabId);
            topB64 = await blobToBase64(imgTop);

            // Vue Dessous (Bottom)
            clickToolbarBtn('Bottom Side');
            clickToolbarBtn('Fit All in Window');
            await new Promise(r => setTimeout(r, 300));
            const imgBottom = await eda.dmt_EditorControl.getCurrentRenderedAreaImage(tab2D.tabId);
            bottomB64 = await blobToBase64(imgBottom);
        }

        // 2. Capture 3D PCBA
        if (tab3D) {
            await eda.dmt_EditorControl.activateDocument(tab3D.tabId);
            await new Promise(r => setTimeout(r, 200));

            // Synchronisation 3D
            clickToolbarBtn('Import Changes');
            await new Promise(r => setTimeout(r, 400));
            clickToolbarBtn('Refresh');
            await new Promise(r => setTimeout(r, 400));

            clickToolbarBtn('Fit All in Window');
            await new Promise(r => setTimeout(r, 300));
            const img3D = await eda.dmt_EditorControl.getCurrentRenderedAreaImage(tab3D.tabId);
            pcb3dB64 = await blobToBase64(img3D);
        }

        // 3. Capture native Export -> PNG depuis le menu PCB principal
        if (pcbTab) {
            await eda.dmt_EditorControl.activateDocument(pcbTab.tabId);
            await eda.pcb_Document.zoomToBoardOutline();
            await new Promise(r => setTimeout(r, 200));

            let capturedBlob = null;
            const origCreateObjectURL = URL.createObjectURL;
            URL.createObjectURL = function(blob) {
                if (blob && blob.type === 'image/png') {
                    capturedBlob = blob;
                }
                return origCreateObjectURL.call(URL, blob);
            };

            const origAnchorClick = HTMLAnchorElement.prototype.click;
            HTMLAnchorElement.prototype.click = function() {};

            try {
                // Dérouler le menu Export
                const exportBtn = Array.from(document.querySelectorAll('.eda-menu-btn-top-text_QOuH2')).find(el => el.textContent.includes('Export'));
                if (exportBtn) {
                    exportBtn.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
                    exportBtn.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                    exportBtn.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                }
                await new Promise(r => setTimeout(r, 300));

                // Sélectionner PNG...
                const pngBtn = Array.from(document.querySelectorAll('*')).find(el => el.textContent.trim() === 'PNG...' && el.offsetParent !== null);
                if (pngBtn) {
                    pngBtn.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
                    pngBtn.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                    pngBtn.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                }
                await new Promise(r => setTimeout(r, 500));

                // Confirmer l'export dans la modale
                const dlg = document.querySelector('.lc_modal_dialog_box_5wCN6');
                const exportConfirmBtn = dlg ? Array.from(dlg.querySelectorAll('button, [class*="btn"]')).find(b => b.textContent.trim() === 'Export') : null;
                if (exportConfirmBtn) {
                    exportConfirmBtn.click();
                }
                await new Promise(r => setTimeout(r, 1200));
            } finally {
                URL.createObjectURL = origCreateObjectURL;
                HTMLAnchorElement.prototype.click = origAnchorClick;
            }

            if (capturedBlob) {
                nativePngB64 = await blobToBase64(capturedBlob);
            }
        }

        // Rétablir l'onglet PCB principal comme document actif
        if (pcbTab) {
            await eda.dmt_EditorControl.activateDocument(pcbTab.tabId);
            await new Promise(r => setTimeout(r, 200));
        }

        return {
            topB64,
            bottomB64,
            pcb3dB64,
            nativePngB64
        };
        """

        result = self.execute_js(js_script)
        saved_files = {}

        def safe_write_bytes(p: Path, data: bytes):
            for attempt in range(5):
                try:
                    p.write_bytes(data)
                    return
                except OSError:
                    import time
                    time.sleep(0.3)
            # Fallback
            tmp = p.with_suffix(".tmp")
            tmp.write_bytes(data)
            import shutil
            shutil.move(tmp, p)

        if result.get("topB64"):
            p = output_dir / "2d-top.png"
            safe_write_bytes(p, base64.b64decode(result["topB64"]))
            saved_files["2d-top.png"] = str(p.resolve())
            logger.info(f"✅ Image 2D Top : {p.name} ({p.stat().st_size} octets)")

        if result.get("bottomB64"):
            p = output_dir / "2d-bottom.png"
            safe_write_bytes(p, base64.b64decode(result["bottomB64"]))
            saved_files["2d-bottom.png"] = str(p.resolve())
            logger.info(f"✅ Image 2D Bottom : {p.name} ({p.stat().st_size} octets)")

        if result.get("pcb3dB64"):
            p = output_dir / "3d.png"
            safe_write_bytes(p, base64.b64decode(result["pcb3dB64"]))
            saved_files["3d.png"] = str(p.resolve())
            logger.info(f"✅ Image 3D PCBA : {p.name} ({p.stat().st_size} octets)")

        if result.get("nativePngB64"):
            p = output_dir / "pcb.png"
            safe_write_bytes(p, base64.b64decode(result["nativePngB64"]))
            saved_files["pcb.png"] = str(p.resolve())
            logger.info(f"✅ Image Menu Export PNG : {p.name} ({p.stat().st_size} octets)")

        return saved_files


def main():
    parser = argparse.ArgumentParser(description="Exportateur d'images 2D, 3D et PCB natif EasyEDA Pro")
    parser.add_argument("--output-dir", default="documents/pcb", help="Dossier de destination")
    parser.add_argument("--port", type=int, default=49620, help="Port du pont local EasyEDA Pro")
    args = parser.parse_args()

    exporter = EasyEdaImageExporter(port=args.port)
    if not exporter.check_connection():
        logger.error(f"Le pont EasyEDA Pro sur le port {args.port} n'est pas joignable.")
        sys.exit(1)

    out_path = Path(args.output_dir)
    results = exporter.capture_all_views(out_path)
    if len(results) < 4:
        logger.warning(f"Seulement {len(results)}/4 images ont été exportées : {list(results.keys())}")
    else:
        logger.info("🎉 Les 4 images (2d-top, 2d-bottom, 3d, pcb) ont été exportées avec succès.")


if __name__ == "__main__":
    main()
