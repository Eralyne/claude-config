#!/usr/bin/env python3
"""
Technology detection for smart skill embedding.
Scans project files to identify technologies, frameworks, and patterns.
"""

import json
import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TechSignature:
    """A technology signature with detection rules."""
    name: str
    category: str  # language, framework, database, tool, etc.
    files: list[str] = field(default_factory=list)  # file patterns to match
    content_patterns: dict[str, list[str]] = field(default_factory=dict)  # file -> regex patterns
    confidence_boost: float = 0.0  # bonus confidence when found


# Technology signatures for detection
SIGNATURES: list[TechSignature] = [
    # Languages
    TechSignature("python", "language", ["*.py", "pyproject.toml", "setup.py", "requirements.txt"]),
    TechSignature("typescript", "language", ["*.ts", "*.tsx", "tsconfig.json"]),
    TechSignature("javascript", "language", ["*.js", "*.jsx", "*.mjs"]),
    TechSignature("php", "language", ["*.php", "composer.json", "composer.lock", "artisan"]),
    TechSignature("go", "language", ["*.go", "go.mod", "go.sum"]),
    TechSignature("rust", "language", ["*.rs", "Cargo.toml", "Cargo.lock"]),
    TechSignature("c++", "language", ["*.cpp", "*.hpp", "*.cc", "*.h", "CMakeLists.txt"]),
    TechSignature("java", "language", ["*.java", "pom.xml", "build.gradle"]),

    # Frontend frameworks
    TechSignature("nextjs", "framework", ["next.config.js", "next.config.mjs", "next.config.ts"],
                  {"package.json": [r'"next":\s*"']}),
    TechSignature("react", "framework", [], {"package.json": [r'"react":\s*"']}),
    TechSignature("vue", "framework", ["*.vue"], {"package.json": [r'"vue":\s*"']}),
    TechSignature("svelte", "framework", ["*.svelte", "svelte.config.js"]),
    TechSignature("angular", "framework", ["angular.json"], {"package.json": [r'"@angular/core"']}),

    # Backend frameworks
    TechSignature("laravel", "framework", ["artisan", "bootstrap/app.php"],
                  {"composer.json": [r'"laravel/framework"', r'"laravel/laravel"']}),
    TechSignature("inertia", "framework", [],
                  {"composer.json": [r'"inertiajs/inertia-laravel"'], "package.json": [r'"@inertiajs/']}),
    TechSignature("fastapi", "framework", [], {"requirements.txt": [r"fastapi"], "pyproject.toml": [r"fastapi"]}),
    TechSignature("django", "framework", ["manage.py"], {"requirements.txt": [r"django"], "settings.py": [r"INSTALLED_APPS"]}),
    TechSignature("flask", "framework", [], {"requirements.txt": [r"flask"], "pyproject.toml": [r"flask"]}),
    TechSignature("express", "framework", [], {"package.json": [r'"express":\s*"']}),
    TechSignature("gin", "framework", [], {"go.mod": [r"github.com/gin-gonic/gin"]}),
    TechSignature("actix", "framework", [], {"Cargo.toml": [r"actix-web"]}),

    # Databases
    TechSignature("prisma", "database", ["prisma/schema.prisma"], {"package.json": [r'"@prisma/client"', r'"prisma"']}),
    TechSignature("postgresql", "database", [], {
        "docker-compose.yml": [r"postgres"],
        ".env": [r"postgres://", r"postgresql://"],
        "*.py": [r"psycopg", r"asyncpg"]
    }),
    TechSignature("mongodb", "database", [], {"package.json": [r'"mongodb"', r'"mongoose"'], "*.py": [r"pymongo"]}),
    TechSignature("redis", "database", [], {"package.json": [r'"redis"', r'"ioredis"'], "*.py": [r"redis"]}),
    TechSignature("surrealdb", "database", [], {"Cargo.toml": [r"surrealdb"], "*.py": [r"surrealdb"]}),
    TechSignature("sqlite", "database", ["*.db", "*.sqlite"], {"*.py": [r"sqlite3", r"aiosqlite"]}),

    # ORMs
    TechSignature("sqlalchemy", "orm", [], {"requirements.txt": [r"sqlalchemy"], "pyproject.toml": [r"sqlalchemy"]}),
    TechSignature("typeorm", "orm", [], {"package.json": [r'"typeorm"']}),
    TechSignature("drizzle", "orm", ["drizzle.config.ts"], {"package.json": [r'"drizzle-orm"']}),

    # AI/ML
    TechSignature("langchain", "ai", [], {"requirements.txt": [r"langchain"], "pyproject.toml": [r"langchain"]}),
    TechSignature("openai", "ai", [], {"package.json": [r'"openai"'], "requirements.txt": [r"openai"]}),
    TechSignature("anthropic", "ai", [], {"package.json": [r'"@anthropic-ai/sdk"'], "requirements.txt": [r"anthropic"]}),
    TechSignature("huggingface", "ai", [], {"requirements.txt": [r"transformers", r"huggingface"], "pyproject.toml": [r"transformers"]}),

    # Testing
    TechSignature("pytest", "testing", ["pytest.ini", "conftest.py"], {"pyproject.toml": [r"pytest"]}),
    TechSignature("phpunit", "testing", ["phpunit.xml", "phpunit.xml.dist"],
                  {"composer.json": [r'"phpunit/phpunit"']}),
    TechSignature("jest", "testing", ["jest.config.js", "jest.config.ts"], {"package.json": [r'"jest"']}),
    TechSignature("vitest", "testing", ["vitest.config.ts"], {"package.json": [r'"vitest"']}),
    TechSignature("playwright", "testing", ["playwright.config.ts"], {"package.json": [r'"@playwright/test"']}),

    # DevOps
    TechSignature("docker", "devops", ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"]),
    TechSignature("kubernetes", "devops", ["*.yaml", "*.yml"], {"*.yaml": [r"kind:\s*Deployment", r"kind:\s*Service"]}),
    TechSignature("terraform", "devops", ["*.tf", "terraform.tfstate"]),
    TechSignature("github-actions", "devops", [".github/workflows/*.yml", ".github/workflows/*.yaml"]),

    # Build tools
    TechSignature("webpack", "build", ["webpack.config.js"], {"package.json": [r'"webpack"']}),
    TechSignature("vite", "build", ["vite.config.ts", "vite.config.js"], {"package.json": [r'"vite"']}),
    TechSignature("turbo", "build", ["turbo.json"], {"package.json": [r'"turbo"']}),

    # CSS frameworks
    TechSignature("tailwind", "css", ["tailwind.config.js", "tailwind.config.ts"],
                  {"package.json": [r'"tailwindcss"', r'"@tailwindcss/']}),

    # UI component libraries
    TechSignature("shadcn", "ui", ["components.json"],
                  {"package.json": [r'"@radix-ui/', r'"class-variance-authority"', r'"clsx"'],
                   "components.json": [r'"style":\s*"', r'"tailwind":\s*\{']}),

    # Serverless
    TechSignature("vercel", "serverless", ["vercel.json"], {"package.json": [r'"@vercel/']}),
    TechSignature("aws-lambda", "serverless", ["serverless.yml", "template.yaml"], {"*.py": [r"aws_lambda_powertools"]}),
]


@dataclass
class DetectedTech:
    """A detected technology with confidence score."""
    name: str
    category: str
    confidence: float  # 0.0 to 1.0
    evidence: list[str]  # files/patterns that triggered detection


def detect_technologies(
    project_path: str,
    verbose: bool = False,
    local_only: bool = False,
    inherit_from: Optional[list["DetectedTech"]] = None
) -> list[DetectedTech]:
    """
    Scan a project directory and detect technologies.

    Args:
        project_path: Directory to scan
        verbose: Print detection details
        local_only: Only check files directly in this directory (no recursion)
        inherit_from: Base technologies to inherit (from parent/root detection)

    Returns list of detected technologies sorted by confidence.
    """
    project = Path(project_path).resolve()
    detected: dict[str, DetectedTech] = {}

    # Start with inherited technologies at reduced confidence
    if inherit_from:
        for tech in inherit_from:
            detected[tech.name] = DetectedTech(
                name=tech.name,
                category=tech.category,
                confidence=tech.confidence * 0.3,  # Reduce inherited confidence
                evidence=[f"inherited from root"]
            )

    for sig in SIGNATURES:
        evidence = []
        confidence = 0.0

        # Check file patterns
        for pattern in sig.files:
            if local_only:
                # Only check direct children, not recursive
                if "**" in pattern:
                    continue  # Skip recursive patterns in local mode
                elif "*" in pattern:
                    # Convert glob to check only direct children
                    matches = [f for f in project.iterdir() if f.match(pattern)]
                else:
                    matches = [project / pattern] if (project / pattern).exists() else []
            else:
                if "**" in pattern or "*" in pattern:
                    matches = list(project.glob(pattern))
                else:
                    matches = [project / pattern] if (project / pattern).exists() else []

            for match in matches[:5]:  # Limit evidence
                if match.exists():
                    rel_path = match.relative_to(project)
                    evidence.append(f"file: {rel_path}")
                    confidence += 0.3

        # Check content patterns
        for file_pattern, regexes in sig.content_patterns.items():
            if local_only:
                # Only check files directly in this directory
                if file_pattern.startswith("*."):
                    ext = file_pattern[1:]  # e.g., ".py"
                    files = [f for f in project.iterdir() if f.is_file() and f.suffix == ext][:10]
                else:
                    f = project / file_pattern
                    files = [f] if f.exists() else []
            else:
                if file_pattern.startswith("*."):
                    files = list(project.glob(f"**/{file_pattern}"))[:10]
                else:
                    f = project / file_pattern
                    files = [f] if f.exists() else []

            for file_path in files:
                if not file_path.exists() or file_path.stat().st_size > 1_000_000:
                    continue
                try:
                    content = file_path.read_text(errors="ignore")
                    for regex in regexes:
                        if re.search(regex, content):
                            rel_path = file_path.relative_to(project)
                            evidence.append(f"pattern '{regex}' in {rel_path}")
                            confidence += 0.4
                            break  # One match per file is enough
                except Exception:
                    continue

        if evidence:
            # Cap confidence at 1.0
            confidence = min(1.0, confidence + sig.confidence_boost)

            # If we already have this tech (from inheritance), boost it
            if sig.name in detected:
                existing = detected[sig.name]
                detected[sig.name] = DetectedTech(
                    name=sig.name,
                    category=sig.category,
                    confidence=min(1.0, existing.confidence + confidence),
                    evidence=existing.evidence + evidence[:3]
                )
            else:
                detected[sig.name] = DetectedTech(
                    name=sig.name,
                    category=sig.category,
                    confidence=confidence,
                    evidence=evidence[:5]
                )

    # Sort by confidence
    result = sorted(detected.values(), key=lambda x: x.confidence, reverse=True)

    if verbose:
        mode = "local" if local_only else "recursive"
        print(f"Detected {len(result)} technologies in {project} ({mode})")
        for tech in result:
            print(f"  {tech.name} ({tech.category}): {tech.confidence:.1%}")

    return result


def detect_directory_tree(
    project_path: str,
    verbose: bool = False,
    min_confidence: float = 0.3
) -> dict[str, list[DetectedTech]]:
    """
    Detect technologies for each directory in a project tree.

    Returns a dict mapping directory paths to their detected technologies.
    Each directory inherits root-level detection but refines based on local files.
    """
    project = Path(project_path).resolve()
    result: dict[str, list[DetectedTech]] = {}

    # Directories to skip
    skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv',
                 'target', 'dist', 'build', 'vendor', '.idea', '.vscode'}

    # First, detect at root level (recursive) for inheritance
    root_techs = detect_technologies(str(project), verbose=verbose)
    result[str(project)] = root_techs

    if verbose:
        print(f"\nRoot detection: {[t.name for t in root_techs]}")

    # Walk the directory tree
    for dirpath, dirnames, filenames in os.walk(project):
        # Skip excluded directories
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]

        current = Path(dirpath)
        if current == project:
            continue  # Already processed root

        # Detect locally, inheriting from root
        local_techs = detect_technologies(
            str(current),
            verbose=False,
            local_only=True,
            inherit_from=root_techs
        )

        # Filter to only significant technologies
        filtered = [t for t in local_techs if t.confidence >= min_confidence]

        if filtered:
            result[str(current)] = filtered
            if verbose:
                rel = current.relative_to(project)
                print(f"  {rel}/: {[t.name for t in filtered[:5]]}")

    return result


def output_json(techs: list[DetectedTech]) -> str:
    """Output detected technologies as JSON."""
    return json.dumps([
        {
            "name": t.name,
            "category": t.category,
            "confidence": round(t.confidence, 2),
            "evidence": t.evidence
        }
        for t in techs
    ], indent=2)


def output_markdown(techs: list[DetectedTech], threshold: float = 0.3) -> str:
    """Output detected technologies as markdown table."""
    filtered = [t for t in techs if t.confidence >= threshold]
    if not filtered:
        return "No technologies detected above threshold."

    lines = ["| Technology | Category | Confidence |", "|------------|----------|------------|"]
    for t in filtered:
        lines.append(f"| {t.name} | {t.category} | {t.confidence:.0%} |")

    return "\n".join(lines)


def output_directory_tree(tree: dict[str, list[DetectedTech]], root: str) -> str:
    """Output directory tree detection as JSON."""
    root_path = Path(root).resolve()
    result = {}

    for dir_path, techs in tree.items():
        try:
            rel = str(Path(dir_path).relative_to(root_path))
            if rel == ".":
                rel = "/"
            else:
                rel = "/" + rel
        except ValueError:
            rel = dir_path

        result[rel] = [
            {"name": t.name, "category": t.category, "confidence": round(t.confidence, 2)}
            for t in techs
        ]

    return json.dumps(result, indent=2)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Detect technologies in a project")
    parser.add_argument("path", nargs="?", default=".", help="Project path to scan")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--threshold", type=float, default=0.3, help="Minimum confidence threshold")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--local", action="store_true", help="Only detect in specified directory (no recursion)")
    parser.add_argument("--tree", action="store_true", help="Detect for entire directory tree")

    args = parser.parse_args()

    if args.tree:
        # Directory tree mode
        tree = detect_directory_tree(args.path, verbose=args.verbose, min_confidence=args.threshold)
        print(output_directory_tree(tree, args.path))
    else:
        # Single directory mode
        techs = detect_technologies(args.path, verbose=args.verbose, local_only=args.local)

        if args.format == "json":
            print(output_json(techs))
        else:
            print(output_markdown(techs, threshold=args.threshold))
