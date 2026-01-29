#!/usr/bin/env python3
"""
Skill scanner for doc-sync.
Returns available skills with their descriptions. The LLM handles matching.
"""

import json
import re
from pathlib import Path


def scan_skills(skills_dirs: list[Path]) -> list[dict]:
    """
    Scan skill directories and return skill metadata.

    Returns list of dicts with: name, description, path
    """
    skills = []

    for skills_dir in skills_dirs:
        if not skills_dir.exists():
            continue

        for skill_path in skills_dir.iterdir():
            if not skill_path.is_dir():
                continue

            skill_md = skill_path / "SKILL.md"
            if not skill_md.exists():
                continue

            try:
                content = skill_md.read_text()

                # Parse YAML frontmatter
                if content.startswith("---"):
                    end = content.find("---", 3)
                    if end != -1:
                        frontmatter = content[3:end]
                        name_match = re.search(r"name:\s*(.+)", frontmatter)

                        # Parse description - handle multi-line YAML
                        description = ""
                        desc_match = re.search(r"description:\s*(.+)", frontmatter)
                        if desc_match:
                            first_line = desc_match.group(1).strip()
                            if first_line in ("|", ">", "|+", "|-", ">+", ">-"):
                                desc_start = desc_match.end()
                                lines = frontmatter[desc_start:].split("\n")
                                multi_lines = []
                                for line in lines:
                                    if line and not line[0].isspace() and ":" in line:
                                        break
                                    stripped = line.strip()
                                    if stripped:
                                        multi_lines.append(stripped)
                                description = " ".join(multi_lines)
                            else:
                                description = first_line

                        if name_match:
                            skills.append({
                                "name": name_match.group(1).strip(),
                                "description": description,
                                "path": str(skill_path)
                            })
            except Exception:
                continue

    return skills


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scan available skills")
    parser.add_argument("path", nargs="?", default=".", help="Project root")
    parser.add_argument("--global", dest="include_global", action="store_true",
                        help="Include global ~/.claude/skills")
    parser.add_argument("--format", choices=["json", "list"], default="json")

    args = parser.parse_args()
    project_root = Path(args.path).resolve()

    # Scan skill directories
    dirs = [project_root / ".claude" / "skills"]
    if args.include_global:
        dirs.append(Path.home() / ".claude" / "skills")

    skills = scan_skills(dirs)

    if args.format == "json":
        print(json.dumps(skills, indent=2))
    else:
        for s in skills:
            print(f"- {s['name']}: {s['description'][:80]}...")
