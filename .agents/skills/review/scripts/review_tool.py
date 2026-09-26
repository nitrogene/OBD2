#!/usr/bin/env python3
"""
review_tool.py - Outil agnostique de gestion, validation et dépouillement des revues techniques.

Conforme à la Règle 0 (AGENTS.md) :
- Aucune référence en dur à des composants, broches ou valeurs spécifiques du projet.
- Manipulation d'abstractions (schéma de métadonnées, niveaux de criticité B/I/M, sections standard).
- Données injectées via arguments CLI, fichiers de configuration ou flux de données.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Observation:
    ref: str
    criticality: str  # "Bloquant", "Important", "Mineur"
    title: str
    components_nets: str
    technical_finding: str
    justification: str
    solution: str


@dataclass
class ReviewReport:
    title: str
    reviewer: str
    date: str
    scope: str
    version_audited: str
    verdict: str
    executive_summary: str
    observations: List[Observation] = field(default_factory=list)
    raw_path: Optional[str] = None


class ReviewValidator:
    """Valideur syntaxique et sémantique de fichiers de revue face aux guidelines."""

    RE_HEADER_FIELD = {
        "title": re.compile(r"^#\s+Revue Technique\s*:\s*(.+)$", re.MULTILINE),
        "reviewer": re.compile(r"^-\s+\*\*Nom du Reviewer\s*(?:/\s*Agent)?\s*:\*\*\s*(.+)$", re.MULTILINE | re.IGNORECASE),
        "date": re.compile(r"^-\s+\*\*Date\s*:\*\*\s*(.+)$", re.MULTILINE | re.IGNORECASE),
        "scope": re.compile(r"^-\s+\*\*Périmètre audité\s*:\*\*\s*(.+)$", re.MULTILINE | re.IGNORECASE),
        "version_audited": re.compile(r"^-\s+\*\*Version\s*(?:/\s*Référence examinée)?\s*:\*\*\s*(.+)$", re.MULTILINE | re.IGNORECASE),
        "verdict": re.compile(r"^-\s+\*\*Verdict global\s*:\*\*\s*(.+)$", re.MULTILINE | re.IGNORECASE),
    }

    RE_OBSERVATION_HEADER = re.compile(
        r"^####\s+([BIM]\d+)\.\s+(.+)$", re.MULTILINE
    )

    @classmethod
    def parse(cls, content: str, source_path: Optional[str] = None) -> Tuple[Optional[ReviewReport], List[str]]:
        errors: List[str] = []
        
        # 1. Vérification des métadonnées obligatoires
        meta: Dict[str, str] = {}
        for key, pattern in cls.RE_HEADER_FIELD.items():
            match = pattern.search(content)
            if match:
                meta[key] = match.group(1).strip()
            else:
                errors.append(f"Métadonnée manquante ou mal formatée : '{key}'")

        title = meta.get("title", "Revue Technique")
        reviewer = meta.get("reviewer", "")
        date = meta.get("date", "")
        scope = meta.get("scope", "")
        version_audited = meta.get("version_audited", "")
        verdict = meta.get("verdict", "")

        # 2. Vérification du Résumé Exécutif
        summary_match = re.search(
            r"##\s+Résumé Exécutif\s*\n+([\s\S]*?)(?=\n##|\Z)", content, re.MULTILINE
        )
        executive_summary = ""
        if summary_match:
            executive_summary = summary_match.group(1).strip()
            if not executive_summary or executive_summary.startswith("["):
                errors.append("Le Résumé Exécutif est vide ou contient encore le placeholder du template.")
        else:
            errors.append("Section obligatoire manquante : '## Résumé Exécutif'")

        # 3. Extraction des observations détaillées
        observations: List[Observation] = []
        obs_sections = cls.RE_OBSERVATION_HEADER.split(content)
        
        # obs_sections format: [prefix, ref1, title1, body1, ref2, title2, body2, ...]
        if len(obs_sections) > 1:
            for i in range(1, len(obs_sections), 3):
                ref = obs_sections[i].strip()
                obs_title = obs_sections[i+1].strip()
                body = obs_sections[i+2] if i+2 < len(obs_sections) else ""
                
                crit = "Bloquant" if ref.startswith("B") else ("Important" if ref.startswith("I") else "Mineur")
                
                # Extraction des sous-champs (compatible format B/I et format allégé M)
                comp_match = re.search(r"-\s+\*\*Composants\s*(?:/\s*Nets concernés)?\s*:\*\*\s*(.+)$", body, re.MULTILINE)
                constat_match = re.search(r"-\s+\*\*Constat(?: technique|\s*&\s*Proposition)?\s*:\*\*\s*([\s\S]*?)(?=-\s+\*\*|\Z)", body)
                justif_match = re.search(r"-\s+\*\*Justification(?: [^:]+)?\s*:\*\*\s*([\s\S]*?)(?=-\s+\*\*|\Z)", body)
                sol_match = re.search(r"-\s+\*\*Solution(?: recommandée)?\s*:\*\*\s*([\s\S]*?)(?=-\s+\*\*|\n###|\n##|\Z)", body)
                gain_match = re.search(r"-\s+\*\*Gain attendu\s*:\*\*\s*([\s\S]*?)(?=-\s+\*\*|\n###|\n##|\Z)", body)

                comp = comp_match.group(1).strip() if comp_match else ""
                constat = constat_match.group(1).strip() if constat_match else ""
                justif = justif_match.group(1).strip() if justif_match else ""
                sol = sol_match.group(1).strip() if sol_match else ""
                gain = gain_match.group(1).strip() if gain_match else ""

                if not comp:
                    errors.append(f"Observation {ref} : champ 'Composants / Nets concernés' manquant.")
                if not constat:
                    errors.append(f"Observation {ref} : champ 'Constat technique' (ou 'Constat & Proposition') manquant.")
                
                # Pour les remarques mineures (M), 'Gain attendu' équivaut à la solution/justification
                if crit == "Mineur":
                    if not sol and not gain:
                        errors.append(f"Observation {ref} : champ 'Gain attendu' ou 'Solution recommandée' manquant.")
                    if not sol and gain:
                        sol = gain
                else:
                    if not justif:
                        errors.append(f"Observation {ref} : champ 'Justification & Risque' manquant.")
                    if not sol:
                        errors.append(f"Observation {ref} : champ 'Solution recommandée' manquant.")

                observations.append(Observation(
                    ref=ref,
                    criticality=crit,
                    title=obs_title,
                    components_nets=comp,
                    technical_finding=constat,
                    justification=justif,
                    solution=sol,
                ))
        else:
            errors.append("Aucune observation détaillée trouvée (format '#### [B|I|M]x. Titre' attendu).")

        report = ReviewReport(
            title=title,
            reviewer=reviewer,
            date=date,
            scope=scope,
            version_audited=version_audited,
            verdict=verdict,
            executive_summary=executive_summary,
            observations=observations,
            raw_path=source_path,
        )

        return report, errors


class ReviewTriager:
    """Dépouilleur de revue : convertit les remarques en items actionnables pour TODO.md."""

    @staticmethod
    def format_todo_item(obs: Observation) -> str:
        tag = obs.criticality.upper()
        title_clean = obs.title.rstrip(".")
        first_line_sol = obs.solution.splitlines()[0].strip().rstrip(".")
        return f"- [ ] **[{tag}] {title_clean} :** {first_line_sol} ({obs.components_nets})."

    @classmethod
    def generate_todo_block(cls, report: ReviewReport) -> str:
        lines: List[str] = [
            f"### Actions issues de la revue du {report.date} ({report.reviewer})",
            f"<!-- Source : {report.raw_path or 'review.md'} - Verdict : {report.verdict} -->",
            "",
        ]
        
        bloquants = [o for o in report.observations if o.criticality == "Bloquant"]
        importants = [o for o in report.observations if o.criticality == "Important"]
        mineurs = [o for o in report.observations if o.criticality == "Mineur"]

        if bloquants:
            lines.append("#### Correctifs Critiques (Bloquants)")
            for o in bloquants:
                lines.append(cls.format_todo_item(o))
            lines.append("")

        if importants:
            lines.append("#### Améliorations de Robustesse & CEM (Importants)")
            for o in importants:
                lines.append(cls.format_todo_item(o))
            lines.append("")

        if mineurs:
            lines.append("#### Optimisations de Nomenclature & DFM (Mineurs)")
            for o in mineurs:
                lines.append(cls.format_todo_item(o))
            lines.append("")

        return "\n".join(lines)


def get_next_review_filename(review_dir: Path) -> Path:
    """Calcule le prochain nom de fichier reviewXXX.md disponible."""
    existing = list(review_dir.glob("review*.md"))
    max_num = 0
    for p in existing:
        m = re.search(r"review(\d+)\.md", p.name)
        if m:
            max_num = max(max_num, int(m.group(1)))
    next_num = max_num + 1
    return review_dir / f"review{next_num:03d}.md"


def extract_template_from_guidelines(guidelines_path: Path) -> Optional[str]:
    """Extrait dynamiquement le modèle Markdown depuis la Section 5 de guidelines.md (Single Source of Truth)."""
    if not guidelines_path.exists():
        return None
    content = guidelines_path.read_text(encoding="utf-8")
    # Recherche du bloc ```markdown sous ## 5. Modèle Type de Revue
    match = re.search(r"##\s+5\.\s+Modèle Type[\s\S]*?```markdown\s*\n([\s\S]*?)\n```", content)
    if match:
        return match.group(1).strip() + "\n"
    return None


def cmd_generate(args: argparse.Namespace) -> int:
    guidelines_path = Path(args.guidelines) if getattr(args, "guidelines", None) else Path("review/guidelines.md")
    content = extract_template_from_guidelines(guidelines_path)
    
    if not content:
        sys.stderr.write(f"Erreur : Impossible d'extraire le modèle depuis '{guidelines_path}' (Section 5 introuvable ou fichier manquant).\n")
        return 1
    
    if args.output:
        out_path = Path(args.output)
    else:
        review_dir = Path("review")
        review_dir.mkdir(parents=True, exist_ok=True)
        out_path = get_next_review_filename(review_dir)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    print(f"Modèle de revue extrait depuis {guidelines_path} et généré dans : {out_path}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if not path.exists():
        sys.stderr.write(f"Erreur : fichier introuvable : {path}\n")
        return 1

    content = path.read_text(encoding="utf-8")
    report, errors = ReviewValidator.parse(content, str(path))

    if args.json:
        result = {
            "valid": len(errors) == 0,
            "errors": errors,
            "report": asdict(report) if report else None,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if len(errors) == 0 else 1

    print(f"=== Audit de conformité du fichier : {path} ===")
    if report:
        print(f"Titre    : {report.title}")
        print(f"Reviewer : {report.reviewer}")
        print(f"Date     : {report.date}")
        print(f"Verdict  : {report.verdict}")
        print(f"Total observations : {len(report.observations)}")
        b_count = sum(1 for o in report.observations if o.criticality == "Bloquant")
        i_count = sum(1 for o in report.observations if o.criticality == "Important")
        m_count = sum(1 for o in report.observations if o.criticality == "Mineur")
        print(f"  - 🔴 Bloquants : {b_count}")
        print(f"  - 🟠 Importants: {i_count}")
        print(f"  - 🟢 Mineurs   : {m_count}")

    if errors:
        print("\n❌ Anomalies de format détectées :")
        for err in errors:
            print(f"  - {err}")
        return 1
    else:
        print("\n✅ Le document est 100% conforme au formalisme des guidelines.")
        return 0


def cmd_triage(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if not path.exists():
        sys.stderr.write(f"Erreur : fichier de revue introuvable : {path}\n")
        return 1

    content = path.read_text(encoding="utf-8")
    report, errors = ReviewValidator.parse(content, str(path))
    if not report:
        sys.stderr.write("Erreur critique : échec d'analyse de la revue.\n")
        for e in errors:
            sys.stderr.write(f"  - {e}\n")
        return 1

    todo_block = ReviewTriager.generate_todo_block(report)

    if args.todo_file:
        todo_path = Path(args.todo_file)
        if not todo_path.exists():
            sys.stderr.write(f"Erreur : fichier TODO introuvable : {todo_path}\n")
            return 1
        
        todo_content = todo_path.read_text(encoding="utf-8")
        
        # Vérification des collisions potentielles
        print("Vérification des collisions avec le TODO existant...")
        for obs in report.observations:
            words = [w for w in re.findall(r"\w+", obs.title) if len(w) > 4]
            matches = [w for w in words if w.lower() in todo_content.lower()]
            if len(matches) >= 2:
                print(f"  ⚠️ Collision potentielle détectée pour [{obs.ref}] : '{obs.title}' (termes trouvés : {', '.join(matches[:3])})")

        if args.apply:
            target_heading = args.section or "## Phase 1"
            if target_heading in todo_content:
                parts = todo_content.split(target_heading, 1)
                new_content = parts[0] + target_heading + "\n\n" + todo_block + "\n" + parts[1]
                todo_path.write_text(new_content, encoding="utf-8")
                print(f"✅ Actions injectées avec succès dans {todo_path} sous '{target_heading}'.")
            else:
                new_content = todo_content + "\n\n" + todo_block + "\n"
                todo_path.write_text(new_content, encoding="utf-8")
                print(f"⚠️ Section '{target_heading}' non trouvée. Actions ajoutées en fin de {todo_path}.")

            if args.delete_review:
                path.unlink()
                print(f"🗑️ Fichier de revue traité supprimé : {path}")
        else:
            print("\n--- Bloc de tâches généré (utiliser --apply pour insérer) ---")
            print(todo_block)
    else:
        print(todo_block)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Moteur agnostique de gestion, audit et dépouillement des revues techniques matérielles."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Commande generate
    p_gen = subparsers.add_parser("generate", help="Générer un modèle vierge de revue extrait de guidelines.md.")
    p_gen.add_argument("-o", "--output", help="Chemin du fichier de sortie (défaut: review/reviewXXX.md).")
    p_gen.add_argument("--guidelines", default="review/guidelines.md", help="Chemin vers guidelines.md servant de source unique de vérité (défaut: review/guidelines.md).")

    # Commande validate
    p_val = subparsers.add_parser("validate", help="Valider la structure et la conformité d'un fichier de revue.")
    p_val.add_argument("file", help="Chemin du fichier de revue à auditer (ex: review/review001.md).")
    p_val.add_argument("--json", action="store_true", help="Sortie structurée au format JSON.")

    # Commande triage
    p_tri = subparsers.add_parser("triage", help="Dépouiller une revue et convertir les observations en checklist TODO.")
    p_tri.add_argument("file", help="Chemin du fichier de revue à dépouiller.")
    p_tri.add_argument("--todo-file", help="Chemin vers le fichier TODO.md cible pour détection de collisions et insertion.")
    p_tri.add_argument("--section", help="En-tête Markdown de la section sous laquelle insérer (ex: '### 1.1 Correctifs').")
    p_tri.add_argument("--apply", action="store_true", help="Appliquer l'insertion dans le fichier TODO.md.")
    p_tri.add_argument("--delete-review", action="store_true", help="Supprimer définitivement le fichier de revue après dépouillement.")

    args = parser.parse_args()

    if args.command == "generate":
        return cmd_generate(args)
    elif args.command == "validate":
        return cmd_validate(args)
    elif args.command == "triage":
        return cmd_triage(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
