#!/usr/bin/env python3
"""
Skill matching for smart skill embedding.
Maps detected technologies to relevant skills from local and ecosystem sources.
"""

import json
import os
import re
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SkillMatch:
    """A skill matched to project technologies."""
    name: str
    source: str  # "local" or "skills.sh"
    description: str
    triggers: list[str]  # When this skill should activate
    relevance: float  # 0.0 to 1.0
    matched_techs: list[str]  # Technologies that triggered this match
    install_cmd: Optional[str] = None  # For skills.sh skills


# Compound tech requirements
# Skills that require ALL listed technologies to be detected
# If a skill bundles multiple techs, it only matches if all are present
COMPOUND_TECH_REQUIREMENTS: dict[str, list[str]] = {
    "tailwind-v4-shadcn": ["tailwind", "shadcn"],
    # Add more compound skills as needed, e.g.:
    # "some-react-tailwind-skill": ["react", "tailwind"],
}


# Skill scope classification
# "project" = only appears in root CLAUDE.md (workflow/methodology skills)
# "technology" = only appears in directories with matching tech (tech-specific skills)
# Skills not listed default to "technology"
SKILL_SCOPES: dict[str, str] = {
    # Project-wide workflow skills (root only)
    "solution-design": "project",
    "problem-analysis": "project",
    "decision-critic": "project",
    "planner": "project",
    "deepthink": "project",
    "codebase-analysis": "project",
    "prompt-engineer": "project",
    "refactor": "project",
    "incoherence": "project",
    "doc-sync": "project",
    "claudeception": "project",

    # Tech-specific skills (directory level based on detection)
    # These are the default - only listed for documentation
    "vue-best-practices": "technology",
    "tailwind-v4-shadcn": "technology",
    "laravel-11-12-app-guidelines": "technology",
    "ui-skills": "technology",
}


# Technology -> skill mappings
# Maps technology names to skill patterns that are relevant
# IMPORTANT: Only include patterns that SPECIFICALLY indicate the skill is for that tech
# Avoid broad patterns like "ui", "component", "pipeline" which match too many skills
TECH_SKILL_MAPPINGS: dict[str, list[dict]] = {
    # PHP/Laravel skills - be specific to Laravel/PHP ecosystem
    "laravel": [
        {"pattern": r"laravel|eloquent|artisan|blade", "boost": 0.9},
        {"pattern": r"inertia", "boost": 0.5},
    ],
    "php": [
        {"pattern": r"\bphp\b|composer", "boost": 0.6},
    ],
    "inertia": [
        {"pattern": r"inertia", "boost": 0.9},
    ],

    # CSS/UI skills - only match explicit tech names
    "tailwind": [
        {"pattern": r"tailwind", "boost": 0.9},
    ],
    "shadcn": [
        {"pattern": r"shadcn|radix", "boost": 0.9},
    ],
    "vue": [
        {"pattern": r"\bvue\b|composition.?api|script.?setup", "boost": 0.9},
        {"pattern": r"pinia|vue.?router", "boost": 0.6},
    ],

    # Database skills - match specific database names
    "prisma": [
        {"pattern": r"prisma", "boost": 0.9},
    ],
    "postgresql": [
        {"pattern": r"postgres|psql|pg_", "boost": 0.9},
    ],
    "mongodb": [
        {"pattern": r"mongo|mongoose", "boost": 0.9},
    ],
    "surrealdb": [
        {"pattern": r"surreal", "boost": 0.9},
    ],

    # Framework skills - match specific framework names
    "nextjs": [
        {"pattern": r"next\.?js|nextjs", "boost": 0.9},
        {"pattern": r"app.?router|server.?component", "boost": 0.5},
    ],
    "react": [
        {"pattern": r"\breact\b", "boost": 0.9},
        {"pattern": r"use[A-Z]\w+\(", "boost": 0.3},  # React hooks pattern
    ],
    "fastapi": [
        {"pattern": r"fastapi", "boost": 0.9},
    ],
    "django": [
        {"pattern": r"django", "boost": 0.9},
    ],

    # AI/ML skills - match specific library names, NOT generic "llm" or "pipeline"
    "langchain": [
        {"pattern": r"langchain", "boost": 0.9},
    ],
    "openai": [
        {"pattern": r"openai|gpt-[34]", "boost": 0.9},
    ],
    "anthropic": [
        {"pattern": r"anthropic|claude", "boost": 0.9},
    ],
    "huggingface": [
        {"pattern": r"hugging.?face|transformers", "boost": 0.9},
    ],

    # Testing skills - match specific framework names
    "pytest": [
        {"pattern": r"pytest|conftest", "boost": 0.9},
    ],
    "phpunit": [
        {"pattern": r"phpunit", "boost": 0.9},
    ],
    "jest": [
        {"pattern": r"\bjest\b", "boost": 0.9},
    ],
    "vitest": [
        {"pattern": r"vitest", "boost": 0.9},
    ],
    "playwright": [
        {"pattern": r"playwright", "boost": 0.9},
    ],

    # General language skills
    "python": [
        {"pattern": r"\bpython\b|\.py\b", "boost": 0.5},
    ],
    "typescript": [
        {"pattern": r"typescript|\.tsx?\b", "boost": 0.5},
    ],
    "go": [
        {"pattern": r"\bgolang\b|\.go\b", "boost": 0.5},
    ],
    "rust": [
        {"pattern": r"\brust\b|cargo", "boost": 0.5},
    ],

    # DevOps skills
    "docker": [
        {"pattern": r"docker|dockerfile", "boost": 0.8},
    ],
    "kubernetes": [
        {"pattern": r"kubernetes|k8s|kubectl", "boost": 0.9},
    ],
    "vercel": [
        {"pattern": r"vercel", "boost": 0.9},
    ],
    "github-actions": [
        {"pattern": r"github.?action|workflow\.ya?ml", "boost": 0.8},
    ],
}


def scan_local_skills(skills_dirs: list[Path]) -> list[dict]:
    """
    Scan local skill directories for available skills.
    Returns list of skill metadata dicts.
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

                        # Parse description - handle both single-line and multi-line YAML
                        description = ""
                        desc_match = re.search(r"description:\s*(.+)", frontmatter)
                        if desc_match:
                            first_line = desc_match.group(1).strip()
                            if first_line in ("|", ">", "|+", "|-", ">+", ">-"):
                                # Multi-line YAML - extract indented block
                                desc_start = desc_match.end()
                                lines = frontmatter[desc_start:].split("\n")
                                multi_lines = []
                                for line in lines:
                                    # Stop at next YAML key (non-indented line with colon)
                                    if line and not line[0].isspace() and ":" in line:
                                        break
                                    # Collect indented content
                                    stripped = line.strip()
                                    if stripped:
                                        multi_lines.append(stripped)
                                description = " ".join(multi_lines)
                            else:
                                description = first_line

                        if name_match:
                            name = name_match.group(1).strip()

                            skills.append({
                                "name": name,
                                "description": description,
                                "path": str(skill_path),
                                "source": "local"
                            })
            except Exception:
                continue

    return skills


def query_skills_sh(query: str, limit: int = 10) -> list[dict]:
    """
    Query skills.sh for relevant skills.
    Returns list of skill metadata dicts.
    """
    try:
        # Use npx skills find to query
        result = subprocess.run(
            ["npx", "--yes", "skills", "find", query, "--json"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0 and result.stdout:
            data = json.loads(result.stdout)
            return [
                {
                    "name": s.get("name", ""),
                    "description": s.get("description", ""),
                    "install_cmd": s.get("install_cmd", f"npx skills add {s.get('name', '')}"),
                    "source": "skills.sh"
                }
                for s in data[:limit]
            ]
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        pass

    return []


def match_skills_to_techs(
    detected_techs: list[dict],
    local_skills: list[dict],
    ecosystem_skills: list[dict],
    max_skills: int = 15,
    scope_filter: Optional[str] = None  # "project", "technology", or None for all
) -> list[SkillMatch]:
    """
    Match skills to detected technologies.

    Args:
        detected_techs: List of detected technology dicts
        local_skills: List of local skill dicts
        ecosystem_skills: List of ecosystem skill dicts
        max_skills: Maximum skills to return
        scope_filter: If set, only return skills matching this scope

    Returns list of SkillMatch sorted by relevance.
    """
    matches: dict[str, SkillMatch] = {}

    all_skills = local_skills + ecosystem_skills

    for tech in detected_techs:
        tech_name = tech["name"]
        tech_confidence = tech.get("confidence", 0.5)

        mappings = TECH_SKILL_MAPPINGS.get(tech_name, [])

        for skill in all_skills:
            skill_name = skill["name"]
            skill_desc = skill.get("description", "").lower()
            skill_text = f"{skill_name} {skill_desc}".lower()

            relevance = 0.0
            matched = False

            # Check each mapping pattern
            for mapping in mappings:
                pattern = mapping["pattern"]
                boost = mapping["boost"]

                if re.search(pattern, skill_text, re.IGNORECASE):
                    relevance += boost * tech_confidence
                    matched = True

            # Also check for direct tech name match in skill
            if re.search(rf"\b{re.escape(tech_name)}\b", skill_text, re.IGNORECASE):
                relevance += 0.5 * tech_confidence
                matched = True

            if matched and relevance > 0:
                if skill_name in matches:
                    # Update existing match
                    matches[skill_name].relevance = max(matches[skill_name].relevance, relevance)
                    if tech_name not in matches[skill_name].matched_techs:
                        matches[skill_name].matched_techs.append(tech_name)
                else:
                    # Extract triggers from description
                    triggers = extract_triggers(skill.get("description", ""))

                    matches[skill_name] = SkillMatch(
                        name=skill_name,
                        source=skill["source"],
                        description=skill.get("description", ""),
                        triggers=triggers,
                        relevance=min(1.0, relevance),
                        matched_techs=[tech_name],
                        install_cmd=skill.get("install_cmd")
                    )

    # Filter by scope if requested
    if scope_filter:
        filtered_matches = {}
        for name, match in matches.items():
            skill_scope = SKILL_SCOPES.get(name, "technology")
            if skill_scope == scope_filter:
                filtered_matches[name] = match
        matches = filtered_matches

    # Filter by compound tech requirements
    # Skills that bundle multiple techs only match if ALL required techs are detected
    detected_tech_names = {t["name"] for t in detected_techs}
    compound_filtered = {}
    for name, match in matches.items():
        required_techs = COMPOUND_TECH_REQUIREMENTS.get(name)
        if required_techs:
            # Check if ALL required technologies are detected
            if all(tech in detected_tech_names for tech in required_techs):
                compound_filtered[name] = match
            # else: skip this skill - not all required techs present
        else:
            # No compound requirement, keep the skill
            compound_filtered[name] = match
    matches = compound_filtered

    # Filter by minimum relevance threshold to avoid weak matches
    MIN_RELEVANCE = 0.4
    matches = {name: m for name, m in matches.items() if m.relevance >= MIN_RELEVANCE}

    # Sort by relevance and limit
    sorted_matches = sorted(matches.values(), key=lambda x: x.relevance, reverse=True)
    return sorted_matches[:max_skills]


def extract_triggers(description: str) -> list[str]:
    """Extract trigger conditions from skill description."""
    triggers = []

    # Look for "Use when" or "when" patterns
    patterns = [
        r"[Uu]se when[:\s]+(.+?)(?:\.|$)",
        r"[Ww]hen[:\s]+\((\d+)\)(.+?)(?:,|\.|$)",
        r"[Ff]ix for[:\s]+(.+?)(?:\.|$)",
        r"[Hh]elps with[:\s]+(.+?)(?:\.|$)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, description)
        for match in matches:
            if isinstance(match, tuple):
                trigger = " ".join(match).strip()
            else:
                trigger = match.strip()

            if len(trigger) > 10 and len(trigger) < 100:
                triggers.append(trigger)

    return triggers[:5]  # Limit triggers


SKILL_SECTION_START = "<!-- doc-sync:skills-start -->"
SKILL_SECTION_END = "<!-- doc-sync:skills-end -->"


def update_claude_md(file_path: Path, skill_markdown: str) -> bool:
    """
    Update a CLAUDE.md file with skill section, handling re-runs idempotently.

    Uses HTML comment markers to identify the skill section:
    <!-- doc-sync:skills-start -->
    ... skill content ...
    <!-- doc-sync:skills-end -->

    Returns True if file was modified, False if unchanged.
    """
    if not skill_markdown.strip():
        return False

    # Wrap content with markers
    wrapped_content = f"{SKILL_SECTION_START}\n{skill_markdown}\n{SKILL_SECTION_END}"

    if file_path.exists():
        content = file_path.read_text()

        # Check if markers exist
        if SKILL_SECTION_START in content and SKILL_SECTION_END in content:
            # Replace existing section
            pattern = re.compile(
                rf"{re.escape(SKILL_SECTION_START)}.*?{re.escape(SKILL_SECTION_END)}",
                re.DOTALL
            )
            new_content = pattern.sub(wrapped_content, content)

            if new_content == content:
                return False  # No change needed

            file_path.write_text(new_content)
            return True
        else:
            # Append at end
            new_content = content.rstrip() + "\n\n" + wrapped_content + "\n"
            file_path.write_text(new_content)
            return True
    else:
        # File doesn't exist - don't create, doc-sync handles CLAUDE.md creation
        return False


def output_skill_index(matches: list[SkillMatch], format: str = "markdown", compact: bool = False) -> str:
    """Output skill matches in specified format.

    Args:
        matches: List of matched skills
        format: Output format ("json" or "markdown")
        compact: If True, output minimal format for directory-level embedding
    """
    if format == "json":
        return json.dumps([
            {
                "name": m.name,
                "source": m.source,
                "description": m.description[:200],
                "triggers": m.triggers,
                "relevance": round(m.relevance, 2),
                "matched_techs": m.matched_techs,
                "install_cmd": m.install_cmd
            }
            for m in matches
        ], indent=2)

    if compact:
        # Compact format for directory-level CLAUDE.md
        # Just skill names and brief triggers, no headers
        if not matches:
            return ""
        lines = [
            "## Skills",
            "",
            "| Skill | When to use |",
            "|-------|-------------|"
        ]
        for m in matches[:5]:  # Limit to 5 for directory level
            trigger_text = m.description[:60] + "..." if len(m.description) > 60 else m.description
            trigger_text = trigger_text.replace("|", "\\|").replace("\n", " ")
            lines.append(f"| `{m.name}` | {trigger_text} |")
        return "\n".join(lines)

    # Full markdown format for root CLAUDE.md embedding
    lines = [
        "## Relevant Skills",
        "",
        "Skills matched to this project's technology stack. Descriptions are passive context;",
        "full skill content loads on-demand when triggers match.",
        "",
        "| Skill | Triggers | Source |",
        "|-------|----------|--------|"
    ]

    for m in matches:
        # Truncate description for trigger column
        trigger_text = m.description[:80] + "..." if len(m.description) > 80 else m.description
        trigger_text = trigger_text.replace("|", "\\|").replace("\n", " ")
        source = "local" if m.source == "local" else "[skills.sh](https://skills.sh)"
        lines.append(f"| `{m.name}` | {trigger_text} | {source} |")

    # Add install suggestions for skills.sh skills
    ecosystem_skills = [m for m in matches if m.source == "skills.sh"]
    if ecosystem_skills:
        lines.extend([
            "",
            "### Suggested Installations",
            "",
            "These skills.sh skills match your tech stack but aren't installed:",
            ""
        ])
        for m in ecosystem_skills[:5]:
            lines.append(f"- `{m.install_cmd}` - {m.description[:60]}...")

    return "\n".join(lines)


def match_skills_for_directory(
    dir_techs: list[dict],
    local_skills: list[dict],
    max_skills: int = 5
) -> list[SkillMatch]:
    """
    Match skills for a specific directory based on its detected technologies.

    This is a lighter version of match_skills_to_techs that:
    - Only uses local skills (no ecosystem query per directory)
    - Returns fewer skills (max 5 per directory)
    - Only returns "technology" scoped skills (excludes project-wide skills)
    - Focuses on high-relevance matches only
    """
    return match_skills_to_techs(
        dir_techs,
        local_skills,
        [],  # No ecosystem skills for directory-level matching
        max_skills=max_skills,
        scope_filter="technology"  # Only tech-specific skills at directory level
    )


def match_skills_for_root(
    project_techs: list[dict],
    local_skills: list[dict],
    ecosystem_skills: list[dict],
    max_skills: int = 15
) -> tuple[list[SkillMatch], list[SkillMatch]]:
    """
    Match skills for root CLAUDE.md.

    Returns two lists:
    - Project-wide skills (workflow/methodology - always shown)
    - Technology skills (based on detected stack)
    """
    project_skills = match_skills_to_techs(
        project_techs,
        local_skills,
        [],  # Project skills don't come from ecosystem
        max_skills=max_skills,
        scope_filter="project"
    )

    tech_skills = match_skills_to_techs(
        project_techs,
        local_skills,
        ecosystem_skills,
        max_skills=max_skills,
        scope_filter="technology"
    )

    return project_skills, tech_skills


if __name__ == "__main__":
    import argparse
    from detect_tech import detect_technologies, detect_directory_tree

    parser = argparse.ArgumentParser(description="Match skills to project technologies")
    parser.add_argument("path", nargs="?", default=".", help="Project path to scan")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    parser.add_argument("--max-skills", type=int, default=15, help="Maximum skills to return")
    parser.add_argument("--skip-ecosystem", action="store_true", help="Skip skills.sh query")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--tree", action="store_true", help="Match skills for entire directory tree")
    parser.add_argument("--compact", action="store_true", help="Output compact format for directory embedding")
    parser.add_argument("--scope", choices=["project", "technology", "all"], default="all",
                        help="Filter by skill scope: project (workflow), technology (tech-specific), or all")
    parser.add_argument("--update", action="store_true",
                        help="Update agent files in place (AGENTS.md if referenced, else CLAUDE.md). Idempotent.")

    args = parser.parse_args()

    # Scan project-level skills only (not global ~/.claude/skills)
    # This ensures skills are committed with the project and shared across team
    project_root = Path(args.path).resolve()
    local_skills = scan_local_skills([
        project_root / ".claude" / "skills"
    ])

    # Detect which agent file convention to use
    # Priority: AGENTS.md if referenced from CLAUDE.md, otherwise CLAUDE.md
    def detect_agent_file(dir_path: Path) -> str:
        """Detect whether to use AGENTS.md or CLAUDE.md for a directory."""
        claude_md = dir_path / "CLAUDE.md"
        if claude_md.exists():
            try:
                content = claude_md.read_text()
                # Check if CLAUDE.md references @AGENTS.md
                if "@AGENTS.md" in content or "AGENTS.md" in content:
                    agents_md = dir_path / "AGENTS.md"
                    if agents_md.exists():
                        return "AGENTS.md"
            except Exception:
                pass
        return "CLAUDE.md"

    if args.verbose:
        print(f"Found {len(local_skills)} project-level skills")

    # === Interactive skill suggestion when no project skills exist ===
    # First, scan global skills that could be copied to project
    global_skills_dir = Path.home() / ".claude" / "skills"
    global_skills = scan_local_skills([global_skills_dir])

    if args.tree and len(local_skills) == 0 and global_skills:
        # Detect root-level technologies for suggestions
        root_techs = detect_technologies(args.path, verbose=args.verbose)
        if root_techs:
            tech_names = [t.name for t in root_techs[:10]]  # Top 10 techs
            print(f"\nDetected technologies: {', '.join(tech_names)}")
            print("No project-level skills installed.\n")

            # Match global skills to detected technologies
            tech_dicts = [{"name": t.name, "category": t.category, "confidence": t.confidence} for t in root_techs]
            matched_global = match_skills_to_techs(tech_dicts, global_skills, [], max_skills=10, scope_filter="technology")

            if matched_global:
                print("Available skills from your global collection:\n")
                for i, skill in enumerate(matched_global, 1):
                    desc = skill.description[:60] + "..." if len(skill.description) > 60 else skill.description
                    print(f"  {i}. {skill.name}")
                    print(f"     {desc}")
                print()

                # Prompt for confirmation
                try:
                    response = input("Copy to project? [Y/n/numbers]: ").strip().lower()
                    if response in ("", "y", "yes"):
                        skills_to_copy = matched_global
                    elif response in ("n", "no"):
                        skills_to_copy = []
                    else:
                        # Parse numbers like "1,3" or "1 3"
                        indices = [int(x.strip()) - 1 for x in response.replace(",", " ").split() if x.strip().isdigit()]
                        skills_to_copy = [matched_global[i] for i in indices if 0 <= i < len(matched_global)]

                    if skills_to_copy:
                        # Use .agents/skills/ for canonical copy, symlink to .claude/skills/
                        agents_skills_dir = project_root / ".agents" / "skills"
                        claude_skills_dir = project_root / ".claude" / "skills"
                        agents_skills_dir.mkdir(parents=True, exist_ok=True)
                        claude_skills_dir.mkdir(parents=True, exist_ok=True)

                        print(f"\nInstalling {len(skills_to_copy)} skills to project...")
                        import shutil
                        for skill in skills_to_copy:
                            # Find the skill in global skills
                            for gs in global_skills:
                                if gs["name"] == skill.name:
                                    src = Path(gs["path"])
                                    canonical = agents_skills_dir / src.name
                                    symlink = claude_skills_dir / src.name

                                    if symlink.exists() or symlink.is_symlink():
                                        print(f"  {skill.name}: already exists, skipping")
                                    else:
                                        # Copy to canonical location
                                        shutil.copytree(src, canonical)
                                        # Create symlink from .claude/skills/ to .agents/skills/
                                        symlink.symlink_to(f"../../.agents/skills/{src.name}")
                                        print(f"  ✓ {skill.name}")
                                    break

                        # Rescan after copying
                        local_skills = scan_local_skills([project_root / ".claude" / "skills"])
                        print(f"\nNow have {len(local_skills)} project-level skills.\n")
                except (EOFError, KeyboardInterrupt):
                    print("\nSkipping skill installation.")

    if args.tree:
        # Directory tree mode - match skills per directory
        tree = detect_directory_tree(args.path, verbose=args.verbose, min_confidence=0.3)

        # === PHASE 1: First pass - collect all skill matches to calculate frequency ===
        dir_skill_matches: dict[str, list[SkillMatch]] = {}
        skill_frequency: dict[str, int] = {}  # skill_name -> count of directories
        total_subdirs = 0

        for dir_path, techs in tree.items():
            tech_dicts = [{"name": t.name, "category": t.category, "confidence": t.confidence} for t in techs]
            dir_path_obj = Path(dir_path)
            is_root = dir_path_obj == project_root

            if is_root:
                # Root - get all PROJECT-scoped skills unconditionally
                # These are workflow/methodology skills that apply to any project
                project_matches = []
                for skill in local_skills:
                    skill_name = skill["name"]
                    skill_scope = SKILL_SCOPES.get(skill_name, "technology")
                    if skill_scope == "project":
                        triggers = extract_triggers(skill.get("description", ""))
                        project_matches.append(SkillMatch(
                            name=skill_name,
                            source="local",
                            description=skill.get("description", ""),
                            triggers=triggers,
                            relevance=1.0,  # Project skills always relevant at root
                            matched_techs=[],
                            install_cmd=None
                        ))
                dir_skill_matches[dir_path] = project_matches
            else:
                # Subdirectory - get technology skills
                matches = match_skills_for_directory(tech_dicts, local_skills, max_skills=10)
                dir_skill_matches[dir_path] = matches
                total_subdirs += 1

                # Count skill frequency across subdirectories
                for m in matches:
                    skill_frequency[m.name] = skill_frequency.get(m.name, 0) + 1

        # === PHASE 2: Identify skills to promote (appear in >80% of subdirectories) ===
        PROMOTION_THRESHOLD = 0.8
        promoted_skills: set[str] = set()

        if total_subdirs > 0:
            for skill_name, count in skill_frequency.items():
                frequency = count / total_subdirs
                if frequency >= PROMOTION_THRESHOLD:
                    promoted_skills.add(skill_name)
                    if args.verbose:
                        print(f"Promoting '{skill_name}' to root-only ({frequency:.0%} of directories)")

        # === PHASE 2.5: Match root-level tech skills that don't appear in subdirs ===
        # These are technologies detected at root but not in any subdir (e.g., tailwind)
        root_techs = tree.get(str(project_root), [])
        root_tech_dicts = [{"name": t.name, "category": t.category, "confidence": t.confidence} for t in root_techs]
        root_tech_skills = match_skills_to_techs(
            root_tech_dicts, local_skills, [], max_skills=10, scope_filter="technology"
        )

        # Filter to only skills that don't appear in ANY subdirectory
        all_subdir_skills = set()
        for dir_path, matches in dir_skill_matches.items():
            if Path(dir_path) != project_root:
                for m in matches:
                    all_subdir_skills.add(m.name)

        orphan_root_skills = [m for m in root_tech_skills if m.name not in all_subdir_skills]
        if args.verbose and orphan_root_skills:
            print(f"Root-only tech skills (not in subdirs): {[m.name for m in orphan_root_skills]}")

        # === PHASE 3: Rebuild skill lists with promotion applied ===
        result = {}
        updated_files = []
        unchanged_files = []

        for dir_path, techs in tree.items():
            dir_path_obj = Path(dir_path)
            is_root = dir_path_obj == project_root
            matches = dir_skill_matches[dir_path]

            if is_root:
                # Root gets PROJECT skills + PROMOTED skills + ORPHAN ROOT TECH skills
                all_matches = list(matches)  # Start with project skills

                # Add promoted skills (tech skills that appear in >80% of directories)
                for skill_name in promoted_skills:
                    # Find the skill from any subdir match
                    for subdir_path, subdir_matches in dir_skill_matches.items():
                        if subdir_path == dir_path:
                            continue  # Skip root itself
                        for m in subdir_matches:
                            if m.name == skill_name:
                                all_matches.append(m)
                                break
                        else:
                            continue
                        break

                # Add orphan root tech skills (detected at root but not in any subdir)
                for m in orphan_root_skills:
                    if m.name not in [existing.name for existing in all_matches]:
                        all_matches.append(m)

                skill_markdown = output_skill_index(all_matches, format="markdown", compact=False)
            else:
                # Subdirectories get only NON-promoted skills (distinctive skills)
                distinctive_matches = [m for m in matches if m.name not in promoted_skills]
                all_matches = distinctive_matches
                skill_markdown = output_skill_index(distinctive_matches, format="markdown", compact=True)

            # Get relative path
            try:
                rel = str(dir_path_obj.relative_to(project_root))
                if rel == ".":
                    rel = "/"
                else:
                    rel = "/" + rel
            except ValueError:
                rel = dir_path

            result[rel] = {
                "technologies": [t.name for t in techs],
                "skills": [m.name for m in all_matches],
                "promoted_to_root": list(promoted_skills) if is_root else [],
                "markdown": skill_markdown if args.format == "markdown" else None
            }

            # Update agent file if --update flag is set
            if args.update:
                agent_file_name = detect_agent_file(dir_path_obj)
                agent_file = dir_path_obj / agent_file_name
                if agent_file.exists():
                    if all_matches:  # Only update if there are skills to embed
                        if update_claude_md(agent_file, skill_markdown):
                            updated_files.append(str(agent_file.relative_to(project_root)))
                        else:
                            unchanged_files.append(str(agent_file.relative_to(project_root)))
                    elif skill_markdown == "":
                        # No distinctive skills - remove skill section if it exists
                        if update_claude_md(agent_file, ""):
                            updated_files.append(str(agent_file.relative_to(project_root)))

        if args.format == "json":
            output = {
                "directories": result,
                "promoted_skills": list(promoted_skills),
                "promotion_threshold": f"{PROMOTION_THRESHOLD:.0%}"
            }
            if args.update:
                output["updated"] = updated_files
                output["unchanged"] = unchanged_files
            print(json.dumps(output, indent=2))
        else:
            # Print summary
            if args.update:
                print(f"## Skill Sync Report\n")
                print(f"Updated: {len(updated_files)} files")
                print(f"Unchanged: {len(unchanged_files)} files\n")
                if updated_files:
                    print("### Updated Files")
                    for f in updated_files:
                        print(f"  - {f}")
                    print()

            # Show promoted skills
            if promoted_skills:
                print(f"## Promoted Skills (>{PROMOTION_THRESHOLD:.0%} frequency)\n")
                print("These skills appear in most directories and are embedded at root only:\n")
                for skill in sorted(promoted_skills):
                    freq = skill_frequency.get(skill, 0)
                    pct = freq / total_subdirs * 100 if total_subdirs > 0 else 0
                    print(f"  - `{skill}` ({pct:.0f}% of directories)")
                print()

            print(f"## Directory Skill Index\n")
            for dir_path, data in sorted(result.items()):
                skills_list = data["skills"]
                if dir_path == "/" or skills_list:
                    print(f"### `{dir_path}`")
                    print(f"Technologies: {', '.join(data['technologies'][:5])}")
                    if skills_list:
                        print(f"Skills: {', '.join(skills_list)}")
                    else:
                        print(f"Skills: (none - all promoted to root)")
                    print()
    else:
        # Single directory mode (original behavior)
        techs = detect_technologies(args.path, verbose=args.verbose)
        tech_dicts = [{"name": t.name, "category": t.category, "confidence": t.confidence} for t in techs]

        if args.verbose:
            print(f"\nDetected {len(techs)} technologies")

        # Query skills.sh
        ecosystem_skills = []
        if not args.skip_ecosystem:
            # Query for top technologies
            for tech in techs[:5]:
                ecosystem_skills.extend(query_skills_sh(tech.name, limit=5))

            if args.verbose:
                print(f"Found {len(ecosystem_skills)} ecosystem skills")

        # Determine scope filter
        scope_filter = None if args.scope == "all" else args.scope

        # Match skills
        matches = match_skills_to_techs(
            tech_dicts,
            local_skills,
            ecosystem_skills,
            max_skills=args.max_skills,
            scope_filter=scope_filter
        )

        if args.verbose:
            print(f"Matched {len(matches)} skills (scope: {args.scope})\n")

        # Output
        print(output_skill_index(matches, format=args.format, compact=args.compact))
