#!/usr/bin/env python3
"""
Client Python pour le pont EasyEDA Pro (easyeda-api-skill)
==========================================================
Permet d'interroger, d'auditer et d'automatiser les schémas et le layout PCB
en temps réel via le serveur de pont local (ports 49620-49629).

Architecture :
  Skill Python <---> HTTP POST (/execute) <---> Serveur Pont Node.js (49620)
  Serveur Pont <---> WebSocket Local <---> Extension EasyEDA Pro (run-api-gateway)
"""

import sys
import json
import logging
from typing import Any, Dict, List, Optional
import requests

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EasyEDAClient")


class EasyEDAClient:
    """Client d'interface avec l'API d'EasyEDA Pro via le bridge WebSocket/HTTP."""

    PORT_RANGE = range(49620, 49630)

    def __init__(self, port: Optional[int] = None, timeout: float = 15.0):
        self.timeout = timeout
        self.port = port or self.find_bridge_port()
        if not self.port:
            logger.warning("Aucun serveur pont EasyEDA détecté sur la plage 49620-49629.")
        else:
            logger.info(f"Connecté au pont EasyEDA sur http://localhost:{self.port}")

    def find_bridge_port(self) -> Optional[int]:
        """Scanne les ports 49620 à 49629 pour localiser le serveur pont actif."""
        for p in self.PORT_RANGE:
            try:
                url = f"http://localhost:{p}/health"
                resp = requests.get(url, timeout=1.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("service") == "easyeda-bridge":
                        return p
            except requests.RequestException:
                continue
        return None

    @property
    def base_url(self) -> str:
        if not self.port:
            raise ConnectionError("Pont EasyEDA non disponible.")
        return f"http://localhost:{self.port}"

    def health(self) -> Dict[str, Any]:
        """Récupère l'état de santé du pont et la connexion au client EasyEDA."""
        resp = requests.get(f"{self.base_url}/health", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_windows(self) -> Dict[str, Any]:
        """Liste les fenêtres EasyEDA Pro actuellement connectées au pont."""
        resp = requests.get(f"{self.base_url}/eda-windows", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def execute_js(self, code: str) -> Any:
        """
        Exécute un bloc de code JavaScript asynchrone dans le contexte d'EasyEDA Pro.
        Le code doit utiliser 'return ...' pour renvoyer une valeur.
        """
        url = f"{self.base_url}/execute"
        payload = {"code": code}
        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success", False):
                err = data.get("error", "Erreur inconnue renvoyée par EasyEDA Pro")
                raise RuntimeError(f"Erreur API EasyEDA : {err}")
            return data.get("result")
        except requests.RequestException as e:
            raise ConnectionError(f"Échec de communication HTTP avec le pont EasyEDA : {e}")

    # =========================================================================
    # Requêtes de Haut Niveau sur le Projet et le PCB
    # =========================================================================

    def get_project_info(self) -> Dict[str, Any]:
        """Récupère les métadonnées du projet actif dans EasyEDA Pro."""
        code = "return await eda.dmt_Project.getCurrentProjectInfo();"
        return self.execute_js(code) or {}

    def get_board_outline(self) -> List[Dict[str, Any]]:
        """
        Récupère toutes les lignes de contour de carte (Layer 11 = BOARD_OUTLINE).
        Permet de délimiter l'enveloppe mécanique du PCB.
        """
        code = """
        const lines = await eda.pcb_PrimitiveLine.getAll(11);
        if (!lines || !lines.length) return [];
        return lines.map(l => ({
            id: l.getState_PrimitiveId(),
            startX: l.getState_StartX(),
            startY: l.getState_StartY(),
            endX: l.getState_EndX(),
            endY: l.getState_EndY(),
            lineWidth: l.getState_LineWidth()
        }));
        """
        return self.execute_js(code) or []

    def get_components(self) -> List[Dict[str, Any]]:
        """
        Extrait la liste exhaustive des composants instanciés sur le PCB
        avec leurs coordonnées réelles (en mil), rotation et couches.
        """
        code = """
        const comps = await eda.pcb_PrimitiveComponent.getAll();
        if (!comps || !comps.length) return [];
        return comps.map(c => ({
            id: c.getState_PrimitiveId(),
            designator: c.getState_Designator(),
            x: c.getState_X(),
            y: c.getState_Y(),
            rotation: c.getState_Rotation(),
            layer: c.getState_Layer(),
            locked: c.getState_PrimitiveLock()
        }));
        """
        return self.execute_js(code) or []

    def get_all_pads(self) -> List[Dict[str, Any]]:
        """
        Extrait toutes les pastilles (pads) du PCB avec coordonnées, net et numéro de broche.
        Indispensable pour le calcul des distances euclidiennes réelles (découplage < 2 mm).
        """
        code = """
        const pads = await eda.pcb_PrimitivePad.getAll();
        if (!pads || !pads.length) return [];
        return pads.map(p => ({
            id: p.getState_PrimitiveId(),
            x: p.getState_X(),
            y: p.getState_Y(),
            layer: p.getState_Layer(),
            net: p.getState_Net(),
            number: p.getState_PadNumber ? p.getState_PadNumber() : null
        }));
        """
        return self.execute_js(code) or []

    def get_nets(self) -> List[str]:
        """Récupère la liste de tous les noms de nets électriques du PCB."""
        code = """
        const nets = await eda.pcb_Net.getAll();
        if (!nets || !nets.length) return [];
        return nets.map(n => n.getState_Name());
        """
        return self.execute_js(code) or []

    def batch_move_components(self, adjustments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Applique par lot de nouvelles coordonnées et rotations aux composants du PCB.
        Format attendu pour chaque élément de adjustments :
          {"designator": "C1", "x": 1200.0, "y": 800.0, "rotation": 90.0}
          ou
          {"id": "...", "x": 1200.0, "y": 800.0, "rotation": 90.0}
        """
        payload_json = json.dumps(adjustments)
        code = f"""
        const adjustments = {payload_json};
        const comps = await eda.pcb_PrimitiveComponent.getAll();
        if (!comps || !comps.length) return {{ success: false, error: "Aucun composant sur le PCB" }};

        const compMapByDes = new Map();
        const compMapById = new Map();
        for (const c of comps) {{
            compMapByDes.set(c.getState_Designator(), c);
            compMapById.set(c.getState_PrimitiveId(), c);
        }}

        let modifiedCount = 0;
        const details = [];

        for (const adj of adjustments) {{
            const comp = compMapByDes.get(adj.designator) || compMapById.get(adj.id);
            if (!comp) {{
                details.push({{ designator: adj.designator, success: false, reason: "Non trouvé" }});
                continue;
            }}

            const asyncComp = comp.toAsync();
            if (adj.x !== undefined) asyncComp.setState_X(adj.x);
            if (adj.y !== undefined) asyncComp.setState_Y(adj.y);
            if (adj.rotation !== undefined) asyncComp.setState_Rotation(adj.rotation);
            await asyncComp.done();
            modifiedCount++;
            details.push({{
                designator: comp.getState_Designator(),
                success: true,
                newX: comp.getState_X(),
                newY: comp.getState_Y(),
                newRotation: comp.getState_Rotation()
            }});
        }}

        return {{ success: true, modifiedCount, details }};
        """
        return self.execute_js(code)

    def run_drc(self) -> Dict[str, Any]:
        """Déclenche le DRC physique sous EasyEDA Pro et retourne le bilan d'erreurs."""
        code = """
        const result = await eda.pcb_Drc.run();
        return result || { errorCount: 0, warningCount: 0 };
        """
        return self.execute_js(code) or {}

    def save_pcb(self) -> bool:
        """Sauvegarde le document PCB actif."""
        code = "return await eda.pcb_Document.save();"
        return bool(self.execute_js(code))


# =============================================================================
# Point d'Entrée CLI pour Test & Diagnostic
# =============================================================================

def main():
    print("=" * 70)
    print(" Diagnostic du Pont EasyEDA Pro (Python Bridge Client)")
    print("=" * 70)

    try:
        client = EasyEDAClient()
    except Exception as e:
        print(f"❌ Erreur d'initialisation : {e}")
        sys.exit(1)

    if not client.port:
        print("❌ Pont introuvable sur les ports 49620-49629.")
        print("Veuillez vérifier que le serveur bridge Node.js est démarré.")
        sys.exit(1)

    try:
        h = client.health()
        print(f"✅ Serveur bridge actif : Port {client.port} | Statut : {h.get('status')}")
        print(f"   Connexion client EasyEDA : {'Connecté' if h.get('edaConnected') else 'Non connecté'}")
        print(f"   Nombre de fenêtres EDA actives : {h.get('edaWindowCount', 0)}")

        if not h.get("edaConnected"):
            print("\n⚠️  Note : Le client EasyEDA Pro n'est pas connecté au pont.")
            print("   Pour interagir avec le schéma/PCB en direct :")
            print("   1. Ouvrez EasyEDA Pro et chargez le projet 'ODB2-Scanner'.")
            print("   2. Assurez-vous que l'extension 'run-api-gateway.eext' est installée et active.")
            return

        print("\n🔍 Test de lecture du projet en direct...")
        prj = client.get_project_info()
        print(f"   Projet actuel : {prj.get('title', 'Inconnu')}")

        comps = client.get_components()
        print(f"   Composants détectés sur le PCB : {len(comps)}")

        outline = client.get_board_outline()
        print(f"   Lignes de contour de carte : {len(outline)}")

        print("\n✅ Test de communication réussi avec succès !")

    except Exception as e:
        print(f"❌ Erreur lors de l'exécution : {e}")


if __name__ == "__main__":
    main()
