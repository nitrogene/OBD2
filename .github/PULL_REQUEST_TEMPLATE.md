## Summary
Describe the hardware, documentation, or tooling changes in this PR.

## Validation Checklist
- [ ] `uv run python .agents/skills/stingy-schematics/scripts/sync_semantics.py check` passes
- [ ] DRC = 0 and ERC = 0 verified in EasyEDA Pro (if schematic/PCB modified)
- [ ] `documents/pcb/placement.svg` regenerated (if placement modified)
- [ ] `documents/easyeda/OBD2.epro2` exported and up to date (if CAD modified)
- [ ] Documentation updated strictly after EasyEDA Pro validation
