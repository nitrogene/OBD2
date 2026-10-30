# Project Rules: ESP32 OBD-II Scanner

## 1. Modularity & Agnostic Engines
- **Zero hardcoded components:** Skills under `.agents/skills/` are pure algorithmic engines. No component designator (`U4`, `R13`), coordinate, or hardcoded value in their Python source code. Data must be injected at runtime via configuration (`documents/pcb/constraints.json`, `documents/schema/bom.json`) or CLI arguments (`--config`).
- **Python execution exclusively via `uv`:** Every Python script or command must imperatively be executed via `uv run` (e.g. `uv run <script>.py`). Direct calls to `python` are strictly prohibited.

## 2. Safety & Control of the EasyEDA Bridge
- **Transparency:** State intent and technical parameters explicitly before any call to the local bridge (`http://localhost:49620`). Modifications must be strictly confined to the local project (clean up temporary `.js`/`.mjs` scripts).
- **Physical components:** Never instantiate components blindly by script. Request the user to add them in EasyEDA Pro by supplying designator, value, package/footprint, and LCSC part number.
- **API Rules:** Explicit net names mandatory (no `$1N...`). Adhere strictly to API argument order (vias: drill before diameter; tracks: coordinates before width).
- **Autonomy limits:** Maximum 3 consecutive attempts to resolve a recurring DRC/ERC violation. In case of a geometric dead-end (repeated conflicts), stop blind modifications, save a clean state, and yield control back to the user.

## 3. Design & Documentation Sequencing
- **Hardware sequence:** Schematic (ERC = 0, physical wires on NetPorts) -> Mechanics (anchors, M2 mounting holes, J1/J2 connectors) -> Floorplanning (decoupling < 2 mm, RF keepout) -> Differential & power routing -> Ground planes & stitching vias -> Verification (DRC = 0, ERC = 0).
- **Zero documentation anticipation:** Document updates (`bom.json`, `semantics.json`, `hardware.md`, `constraints.json`, `manifest.json`) and checking tasks in `todo.md` (`- [x]`) occur **strictly after** the action has been verified in EasyEDA Pro by the user.
- **Dynamic designators:** Never fix designators in advance in `todo.md` or during reviews. Describe components by their function and assign the next free sequential number in the BOM at implementation time.

## 4. Technical Review Gateway (`review/`)
- Scan `review/review*.md`, sort by criticality (Blocking / Important / Minor), arbitrate with the user, convert validated items into `todo.md`, and delete the processed review file.
- Mandatory critical scrutiny: cross-reference every observation against actual schematics and manufacturer datasheets (weed out obsolescence, duplicates, and false leads).

## 5. Post-Validation & Closure Steps (Enforcing / Blocking)
1. Save inside EasyEDA (`eda.pcb_Document.save()`) and purge temporary files.
2. Certify DRC = 0 and ERC = 0.
3. Validate semantic synchronization (`uv run python .agents/skills/stingy-schematics/scripts/sync_semantics.py check`).
4. Regenerate `documents/pcb/placement.svg` on every modification or recalculated placement via `pcb-placer`.
5. Export `documents/easyeda/OBD2.epro2` and request high-resolution PNG exports from the user.
6. Commit and push **only** after explicit textual approval from the user on the commit message.

## 6. Typography & Formulas
- **No LaTeX for components or values:** Formal prohibition of LaTeX notation for designators and simple values (e.g. inline dollar signs around components). Strictly use plain text with Markdown code: `J1`, `R16`, `10 kΩ`, `3.3V`.
- Dollar markup `$ ... $` is exclusively reserved for complex mathematical equations (e.g. loop stability or filter derivations).
