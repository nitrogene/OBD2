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
        """Scanne les ports 49620 à 49629 pour localiser rapidement le serveur pont actif."""
        for p in self.PORT_RANGE:
            try:
                url = f"http://localhost:{p}/health"
                resp = requests.get(url, timeout=0.25)
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

    def is_connected(self) -> bool:
        """Vérifie si le pont et une fenêtre EasyEDA Pro sont actifs."""
        try:
            h = self.health()
            return bool(h.get("edaConnected", False))
        except Exception:
            return False

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
        code = """
        try {
            const raw = await eda.dmt_Project.getCurrentProjectInfo() || {};
            let boardName = null;
            let projectTitle = raw.friendlyName || raw.name || null;
            let pcbUuid = null;

            if (raw.data && Array.isArray(raw.data)) {
                for (const item of raw.data) {
                    if (item.pcb) {
                        boardName = item.pcb.name || item.pcb.parentBoardName;
                        pcbUuid = item.pcb.uuid;
                        break;
                    }
                }
            }
            return {
                raw: raw,
                boardName: boardName,
                projectTitle: projectTitle,
                pcbUuid: pcbUuid
            };
        } catch(e) {
            return { error: e.message };
        }
        """
        return self.execute_js(code) or {}

    def is_pcb_active(self) -> bool:
        """Vérifie si un document PCB est actuellement ouvert et actif."""
        code = """
        try {
            const comps = await eda.pcb_PrimitiveComponent.getAll?.();
            return comps !== undefined;
        } catch(e) {
            return false;
        }
        """
        try:
            return bool(self.execute_js(code))
        except Exception:
            return False

    def get_board_outline(self) -> Dict[str, Any]:
        """
        Récupère toutes les lignes et arcs de contour de carte (Layer 11 = BOARD_OUTLINE).
        Calcule et retourne également la boîte englobante (Bounding Box) en mil et en mm.
        """
        code = """
        try {
            const lines = (await eda.pcb_PrimitiveLine.getAll(undefined, 11)) || [];
            const arcs = (await eda.pcb_PrimitiveArc.getAll?.(undefined, 11)) || [];
            
            let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
            const segments = [];

            for (const l of lines) {
                const sx = l.getState_StartX();
                const sy = l.getState_StartY();
                const ex = l.getState_EndX();
                const ey = l.getState_EndY();
                minX = Math.min(minX, sx, ex);
                maxX = Math.max(maxX, sx, ex);
                minY = Math.min(minY, sy, ey);
                maxY = Math.max(maxY, sy, ey);
                segments.push({
                    type: "line",
                    id: l.getState_PrimitiveId(),
                    startX: sx,
                    startY: sy,
                    endX: ex,
                    endY: ey,
                    lineWidth: l.getState_LineWidth()
                });
            }

            for (const a of arcs) {
                const cx = a.getState_CenterX ? a.getState_CenterX() : 0;
                const cy = a.getState_CenterY ? a.getState_CenterY() : 0;
                const r = a.getState_Radius ? a.getState_Radius() : 0;
                minX = Math.min(minX, cx - r);
                maxX = Math.max(maxX, cx + r);
                minY = Math.min(minY, cy - r);
                maxY = Math.max(maxY, cy + r);
                segments.push({
                    type: "arc",
                    id: a.getState_PrimitiveId(),
                    centerX: cx,
                    centerY: cy,
                    radius: r
                });
            }

            const valid = isFinite(minX) && isFinite(maxX);
            return {
                segmentsCount: segments.length,
                segments: segments,
                boundingBox: valid ? {
                    minX: minX,
                    maxX: maxX,
                    minY: minY,
                    maxY: maxY,
                    width_mil: maxX - minX,
                    height_mil: maxY - minY,
                    width_mm: (maxX - minX) * 0.0254,
                    height_mm: (maxY - minY) * 0.0254
                } : null
            };
        } catch(e) {
            return { segmentsCount: 0, segments: [], boundingBox: null, error: e.message };
        }
        """
        return self.execute_js(code) or {"segmentsCount": 0, "segments": [], "boundingBox": None}

    def create_board_outline(self, width_mil: float, height_mil: float, origin_x: float = 0.0, origin_y: float = 0.0, line_width_mil: float = 10.0) -> bool:
        """
        Crée un contour de carte rectangulaire sur le Layer 11 (BOARD_OUTLINE).
        """
        code = f"""
        try {{
            const ox = {origin_x};
            const oy = {origin_y};
            const w = {width_mil};
            const h = {height_mil};
            const lw = {line_width_mil};

            // 4 segments rectangulaires : Sud, Est, Nord, Ouest
            await eda.pcb_PrimitiveLine.create('', 11, ox, oy, ox + w, oy, lw);
            await eda.pcb_PrimitiveLine.create('', 11, ox + w, oy, ox + w, oy + h, lw);
            await eda.pcb_PrimitiveLine.create('', 11, ox + w, oy + h, ox, oy + h, lw);
            await eda.pcb_PrimitiveLine.create('', 11, ox, oy + h, ox, oy, lw);
            return true;
        }} catch(e) {{
            return false;
        }}
        """
        return bool(self.execute_js(code))

    def create_mounting_hole(self, x_mil: float, y_mil: float, hole_dia_mil: float = 86.6, pad_dia_mil: float = 177.2, pad_number: str = "MH", net: str = "GND") -> bool:
        """
        Crée un trou de fixation mécanique sur le multi-layer (Layer 12 = MULTI).
        hole_dia_mil : diamètre de perçage (ex: 86.6 mil = 2.2 mm pour vis M2).
        pad_dia_mil  : diamètre de la collerette/pastille (ex: 177.2 mil = 4.5 mm pour tête de vis M2).
        """
        code = f"""
        try {{
            const pad = await eda.pcb_PrimitivePad.create(
                12,
                '{pad_number}',
                {x_mil},
                {y_mil},
                0,
                ['ELLIPSE', {pad_dia_mil}, {pad_dia_mil}],
                '{net}',
                ['ROUND', {hole_dia_mil}],
                0, 0, 0,
                {str(bool(net)).lower()},
                0,
                undefined,
                null,
                null,
                true
            );
            return pad !== undefined;
        }} catch(e) {{
            return false;
        }}
        """
        return bool(self.execute_js(code))

    def delete_pads(self, pad_ids: List[str]) -> bool:
        """Supprime une liste de pastilles par leurs identifiants primitifs."""
        if not pad_ids:
            return True
        code = f"""
        try {{
            const ids = {json.dumps(pad_ids)};
            return await eda.pcb_PrimitivePad.delete(ids);
        }} catch(e) {{
            return false;
        }}
        """
        return bool(self.execute_js(code))

    def ensure_mounting_holes(self, holes_config: List[Dict[str, Any]]) -> bool:
        """
        Vérifie et instancie les trous de fixation mécaniques M2 (Layer 12 = MULTI)
        conformément aux contraintes du floorplan.
        """
        existing_pads = self.get_all_pads()
        existing_mh_numbers = {p.get("number") for p in existing_pads if p.get("number")}
        all_ok = True
        for h in holes_config:
            hid = h.get("id", "MH")
            if hid not in existing_mh_numbers:
                x_mil = h.get("x_mil", 0.0)
                y_mil = h.get("y_mil", 0.0)
                hole_dia = h.get("hole_diameter_mil", 86.6)
                pad_dia = h.get("head_clearance_mil", 177.2)
                net = h.get("net", "GND")
                ok = self.create_mounting_hole(x_mil, y_mil, hole_dia_mil=hole_dia, pad_dia_mil=pad_dia, pad_number=hid, net=net)
                if not ok:
                    all_ok = False
        return all_ok

    def sync_schematic_to_pcb(self, sch_uuid: Optional[str] = None, auto_confirm: bool = True) -> Dict[str, Any]:
        """
        Synchronise le PCB actif depuis le schéma associé du projet
        (équivalent de 'Update PCB from Schematic' dans EasyEDA Pro).
        Importe les composants modifiés/ajoutés et régénère le chevelu des nets.
        Si auto_confirm=True, valide automatiquement la boîte de dialogue modale.
        """
        code = f"""
        try {{
            const schUuid = {"'" + sch_uuid + "'" if sch_uuid else "undefined"};

            const clickApplyChanges = () => {{
                const candidates = Array.from(document.querySelectorAll('button, .el-button, .ant-btn, input[type="button"], div, span'));
                const btn = candidates.find(b => {{
                    if (b.offsetParent === null) return false;
                    const txt = (b.innerText || b.textContent || b.value || '').trim();
                    return txt === 'Apply Changes' || txt === 'Apply' || txt === '确定' || txt === 'OK' || txt === 'Appliquer' || txt === '应用更改';
                }});
                if (btn) {{
                    btn.click();
                    return true;
                }}
                const primary = document.querySelector('.el-button--primary, .ant-btn-primary');
                if (primary && primary.offsetParent !== null) {{
                    primary.click();
                    return true;
                }}
                return false;
            }};

            let clicked = clickApplyChanges();

            const importPromise = eda.pcb_Document.importChanges(schUuid);

            if ({str(auto_confirm).lower()}) {{
                for (let delay of [400, 800, 1500, 2500, 4000]) {{
                    await new Promise(r => setTimeout(r, delay));
                    if (clickApplyChanges()) {{
                        clicked = true;
                        break;
                    }}
                }}
            }}

            const res = await importPromise;
            await new Promise(r => setTimeout(r, 1500));

            return {{ success: res === true, result: res, autoConfirmed: clicked }};
        }} catch(e) {{
            return {{ success: false, error: e.message }};
        }}
        """
        return self.execute_js(code) or {"success": False, "error": "No response"}

    def get_open_dialogs(self) -> Dict[str, Any]:
        """Inspecte les dialogues ou fenêtres modales ouvertes dans le DOM d'EasyEDA Pro (y compris iframes)."""
        code = """
        try {
            const docs = [document];
            for (const f of Array.from(document.querySelectorAll('iframe'))) {
                try {
                    if (f.contentDocument) docs.push(f.contentDocument);
                } catch(e) {}
            }

            const allButtons = [];
            for (const doc of docs) {
                const btns = Array.from(doc.querySelectorAll('button, .el-button, .ant-btn, input[type="button"], a, div[role="button"]'));
                for (const b of btns) {
                    const txt = (b.innerText || b.textContent || b.value || b.title || '').trim();
                    if (txt) {
                        allButtons.push({
                            text: txt,
                            className: b.className,
                            visible: b.offsetParent !== null || b.getClientRects().length > 0
                        });
                    }
                }
            }

            // Recherche spécifique de Apply Changes
            let applyFound = false;
            for (const doc of docs) {
                const els = Array.from(doc.querySelectorAll('*'));
                for (const el of els) {
                    const t = (el.innerText || el.textContent || '').trim();
                    if (t === 'Apply Changes') {
                        applyFound = true;
                        break;
                    }
                }
                if (applyFound) break;
            }

            return {
                iframeCount: document.querySelectorAll('iframe').length,
                applyFound: applyFound,
                buttonCount: allButtons.length,
                visibleButtons: allButtons.filter(b => b.visible).map(b => b.text)
            };
        } catch(e) {
            return { error: e.message };
        }
        """
        return self.execute_js(code) or {}

    def confirm_active_dialog(self) -> Dict[str, Any]:
        """
        Détecte et clique automatiquement sur le bouton de confirmation ('Apply Changes', '确定', 'OK')
        d'une boîte de dialogue modale active (ex: synchronisation Schéma -> PCB).
        """
        code = """
        try {
            const candidates = Array.from(document.querySelectorAll('button, .el-button, .ant-btn, input[type="button"], div, span'));
            const confirmBtn = candidates.find(b => {
                if (b.offsetParent === null) return false;
                const txt = (b.innerText || b.textContent || b.value || '').trim();
                return txt === 'Apply Changes' || txt === 'Apply' || txt === '确定' || txt === 'OK' || txt === 'Appliquer' || txt === '应用更改';
            });

            if (confirmBtn) {
                const btnText = (confirmBtn.innerText || confirmBtn.textContent || confirmBtn.value || '').trim();
                confirmBtn.click();
                return { clicked: true, buttonText: btnText, tag: confirmBtn.tagName, className: confirmBtn.className };
            }

            const primaryBtn = document.querySelector('.el-button--primary, .ant-btn-primary');
            if (primaryBtn && primaryBtn.offsetParent !== null) {
                const btnText = (primaryBtn.innerText || primaryBtn.textContent || primaryBtn.value || '').trim();
                primaryBtn.click();
                return { clicked: true, buttonText: btnText, tag: primaryBtn.tagName, className: primaryBtn.className };
            }

            return { clicked: false, message: "Aucun bouton de confirmation détecté" };
        } catch(e) {
            return { clicked: false, error: e.message };
        }
        """
        return self.execute_js(code) or {"clicked": False}

    def get_components(self) -> List[Dict[str, Any]]:
        """
        Extrait la liste exhaustive des composants instanciés sur le PCB
        avec leurs coordonnées réelles (en mil), rotation, couche et verrouillage.
        """
        code = """
        try {
            const comps = await eda.pcb_PrimitiveComponent.getAll();
            if (!comps || !comps.length) return [];
            return comps.map(c => ({
                id: c.getState_PrimitiveId(),
                designator: c.getState_Designator(),
                x: c.getState_X(),
                y: c.getState_Y(),
                rotation: c.getState_Rotation(),
                layer: c.getState_Layer(),
                locked: c.getState_PrimitiveLock ? c.getState_PrimitiveLock() : false
            }));
        } catch(e) {
            return [];
        }
        """
        return self.execute_js(code) or []

    def get_components_with_pads(self) -> List[Dict[str, Any]]:
        """
        Extrait chaque composant avec la liste exhaustive de ses broches/pastilles
        (numéro, coordonnées réelles et net associé).
        """
        code = """
        try {
            const comps = await eda.pcb_PrimitiveComponent.getAll();
            if (!comps || !comps.length) return [];
            const result = [];
            for (const c of comps) {
                const pins = (await c.getAllPins?.()) || [];
                const padInfos = pins.map(p => ({
                    id: p.getState_PrimitiveId(),
                    number: p.getState_PadNumber ? p.getState_PadNumber() : null,
                    x: p.getState_X(),
                    y: p.getState_Y(),
                    net: p.getState_Net(),
                    layer: p.getState_Layer()
                }));
                result.push({
                    id: c.getState_PrimitiveId(),
                    designator: c.getState_Designator(),
                    x: c.getState_X(),
                    y: c.getState_Y(),
                    rotation: c.getState_Rotation(),
                    layer: c.getState_Layer(),
                    locked: c.getState_PrimitiveLock ? c.getState_PrimitiveLock() : false,
                    pads: padInfos
                });
            }
            return result;
        } catch(e) {
            return [];
        }
        """
        return self.execute_js(code) or []

    def get_all_pads(self) -> List[Dict[str, Any]]:
        """
        Extrait toutes les pastilles (pads) du PCB avec coordonnées, net et numéro de broche.
        Indispensable pour le calcul des distances euclidiennes réelles (découplage < 2 mm).
        """
        code = """
        try {
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
        } catch(e) {
            return [];
        }
        """
        return self.execute_js(code) or []

    def get_nets(self) -> List[str]:
        """
        Récupère la liste de tous les noms de nets électriques du PCB.
        Utilise les méthodes normalisées d'EasyEDA Pro (getAllNetsName / getAllNetName).
        """
        code = """
        try {
            const nets = (await eda.pcb_Net.getAllNetsName?.()) || (await eda.pcb_Net.getAllNetName?.()) || [];
            return nets;
        } catch(e) {
            return [];
        }
        """
        return self.execute_js(code) or []

    def batch_move_components(self, adjustments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Applique par lot de nouvelles coordonnées et rotations aux composants du PCB.
        Format attendu pour chaque élément de adjustments :
          {"designator": "<DESIGNATOR>", "x": <X_COORD>, "y": <Y_COORD>, "rotation": <ROT_DEG>, "locked": bool}
          ou
          {"id": "<PRIMITIVE_ID>", "x": <X_COORD>, "y": <Y_COORD>, "rotation": <ROT_DEG>, "locked": bool}
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
                details.push({{ designator: adj.designator, success: false, reason: "Non trouvé sur le PCB" }});
                continue;
            }}

            const asyncComp = comp.toAsync();
            if (adj.x !== undefined) asyncComp.setState_X(adj.x);
            if (adj.y !== undefined) asyncComp.setState_Y(adj.y);
            if (adj.rotation !== undefined) asyncComp.setState_Rotation(adj.rotation);
            if (adj.layer !== undefined) asyncComp.setState_Layer(adj.layer);
            if (adj.locked !== undefined) asyncComp.setState_PrimitiveLock(adj.locked);
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

    # =========================================================================
    # Gestion du Routage (Pistes, Vias, DSN & SES)
    # =========================================================================

    def get_routing_summary(self) -> Dict[str, Any]:
        """Retourne le décompte et le détail des pistes (lignes/arcs de cuivre) et des vias."""
        code = """
        try {
            const lines = (await eda.pcb_PrimitiveLine.getAll()) || [];
            const arcs = (await eda.pcb_PrimitiveArc.getAll?.()) || [];
            const vias = (await eda.pcb_PrimitiveVia.getAll?.()) || [];

            const copperLines = lines.filter(l => (l.getState_Layer() === 1 || l.getState_Layer() === 2) && l.getState_Net());
            const copperArcs = arcs.filter(a => (a.getState_Layer() === 1 || a.getState_Layer() === 2) && a.getState_Net());

            const lockedLines = copperLines.filter(l => l.getState_PrimitiveLock && l.getState_PrimitiveLock());
            const lockedArcs = copperArcs.filter(a => a.getState_PrimitiveLock && a.getState_PrimitiveLock());
            const lockedVias = vias.filter(v => v.getState_PrimitiveLock && v.getState_PrimitiveLock());

            return {
                totalCopperLines: copperLines.length,
                totalCopperArcs: copperArcs.length,
                totalVias: vias.length,
                lockedLines: lockedLines.length,
                lockedArcs: lockedArcs.length,
                lockedVias: lockedVias.length,
                unlockedCount: (copperLines.length - lockedLines.length) + (copperArcs.length - lockedArcs.length) + (vias.length - lockedVias.length)
            };
        } catch(e) {
            return { error: e.message };
        }
        """
        return self.execute_js(code) or {}

    def clear_unlocked_routing(self) -> Dict[str, Any]:
        """
        Supprime proprement et instantanément toutes les pistes de cuivre et vias non verrouillés.
        Contrairement à clearRouting(), cette opération par primitives ne déclenche aucun dialogue
        bloquant (modal) dans l'interface EasyEDA Pro.
        """
        code = """
        try {
            const lines = (await eda.pcb_PrimitiveLine.getAll()) || [];
            const arcs = (await eda.pcb_PrimitiveArc.getAll?.()) || [];
            const vias = (await eda.pcb_PrimitiveVia.getAll?.()) || [];

            const copperLinesToDelete = lines
                .filter(l => (l.getState_Layer() === 1 || l.getState_Layer() === 2) && l.getState_Net() && (!l.getState_PrimitiveLock || !l.getState_PrimitiveLock()))
                .map(l => l.getState_PrimitiveId());

            const copperArcsToDelete = arcs
                .filter(a => (a.getState_Layer() === 1 || a.getState_Layer() === 2) && a.getState_Net() && (!a.getState_PrimitiveLock || !a.getState_PrimitiveLock()))
                .map(a => a.getState_PrimitiveId());

            const viasToDelete = vias
                .filter(v => !v.getState_PrimitiveLock || !v.getState_PrimitiveLock())
                .map(v => v.getState_PrimitiveId());

            if (copperLinesToDelete.length) await eda.pcb_PrimitiveLine.delete(copperLinesToDelete);
            if (copperArcsToDelete.length) await eda.pcb_PrimitiveArc.delete(copperArcsToDelete);
            if (viasToDelete.length) await eda.pcb_PrimitiveVia.delete(viasToDelete);

            return {
                success: true,
                deletedLines: copperLinesToDelete.length,
                deletedArcs: copperArcsToDelete.length,
                deletedVias: viasToDelete.length
            };
        } catch(e) {
            return { success: false, error: e.message };
        }
        """
        return self.execute_js(code)

    def export_dsn(self, filename: str = "AutoRoute_DSN") -> Optional[str]:
        """
        Exporte le fichier Specctra DSN depuis la session active EasyEDA Pro.
        Retourne le contenu textuel complet du DSN.
        """
        code = f"""
        try {{
            const dsnFile = await eda.pcb_ManufactureData.getDsnFile('{filename}');
            if (!dsnFile) return null;
            return await dsnFile.text();
        }} catch(e) {{
            return null;
        }}
        """
        return self.execute_js(code)

    def import_ses(self, ses_content: str, filename: str = "AutoRoute_SES.ses") -> bool:
        """
        Réimporte le fichier Specctra SES généré par FreeRouting dans EasyEDA Pro.
        """
        payload = json.dumps(ses_content)
        code = f"""
        try {{
            const content = {payload};
            const blob = new Blob([content], {{ type: 'text/plain' }});
            const file = new File([blob], '{filename}');
            return await eda.pcb_Document.importAutoRouteSesFile(file);
        }} catch(e) {{
            return false;
        }}
        """
        return bool(self.execute_js(code))

    def run_drc(self) -> Dict[str, Any]:
        """Déclenche le DRC physique sous EasyEDA Pro et retourne le bilan d'erreurs."""
        code = """
        try {
            const result = await eda.pcb_Drc.run();
            return result || { errorCount: 0, warningCount: 0 };
        } catch(e) {
            return { errorCount: 0, warningCount: 0, error: e.message };
        }
        """
        return self.execute_js(code) or {}

    def save_pcb(self) -> bool:
        """Sauvegarde le document PCB actif."""
        code = "return await eda.pcb_Document.save();"
        try:
            return bool(self.execute_js(code))
        except Exception:
            return False


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
            print("   1. Ouvrez EasyEDA Pro et chargez le projet.")
            print("   2. Assurez-vous que l'extension 'run-api-gateway.eext' est installée et active.")
            return

        prj = client.get_project_info()
        project_name = prj.get("projectTitle") or "Non défini"
        board_name = prj.get("boardName") or "Non défini"
        print(f"   Projet : {project_name} | Carte PCB active : {board_name}")

        comps = client.get_components()
        print(f"   Composants détectés sur le PCB : {len(comps)}")

        nets = client.get_nets()
        print(f"   Nets détectés sur le PCB : {len(nets)} ({', '.join(nets[:5])}{'...' if len(nets) > 5 else ''})")

        outline = client.get_board_outline()
        bbox = outline.get("boundingBox")
        if bbox:
            print(f"   Contour de carte détecté : {bbox['width_mm']:.2f} × {bbox['height_mm']:.2f} mm ({bbox['width_mil']:.0f} × {bbox['height_mil']:.0f} mil)")
        else:
            print(f"   Contour de carte : Aucun segment détecté sur le Layer 11")

        routing = client.get_routing_summary()
        print(f"   Routage actuel : {routing.get('totalCopperLines', 0)} lignes de cuivre, {routing.get('totalVias', 0)} vias")

        dialogs_info = client.get_open_dialogs()
        print(f"   Iframes détectés : {dialogs_info.get('iframeCount', 0)} | 'Apply Changes' trouvé : {dialogs_info.get('applyFound')}")
        if dialogs_info.get("visibleButtons"):
            print(f"   Boutons visibles : {', '.join(dialogs_info['visibleButtons'][:15])}")

        btn_action = client.confirm_active_dialog()
        if btn_action.get("clicked"):
            print(f"   ⚡ Validation automatique : Clic sur '{btn_action.get('buttonText')}' ({btn_action.get('className')}) effectué !")

        print("\n✅ Test de communication et requêtes API exécutés avec succès !")

    except Exception as e:
        print(f"❌ Erreur lors de l'exécution : {e}")


if __name__ == "__main__":
    main()
