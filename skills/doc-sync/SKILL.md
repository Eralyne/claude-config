---
name: doc-sync
description: Synchronizes docs across a repository. Use when user asks to sync docs.
---

# Doc Sync

Maintains the CLAUDE.md navigation hierarchy, README.md invisible knowledge docs,
and **smart skill embedding** across a repository. This skill is self-contained
and performs all documentation work directly.

## Skill Embedding

Doc-sync intelligently embeds relevant skill descriptions in CLAUDE.md/AGENTS.md.
**You (the LLM) do the matching** - no hardcoded patterns.

**Why this matters:** Passive context (always available) outperforms on-demand
retrieval. But loading ALL skills pollutes context. Smart embedding solves this:
only skills relevant to the project are embedded.

**Agent file priority:** If CLAUDE.md contains `@AGENTS.md`, embed skills in
AGENTS.md instead (agent-agnostic convention).

## Documentation Conventions

For authoritative CLAUDE.md and README.md format specification:

<file working-dir=".claude" uri="conventions/documentation.md" />

The conventions/ directory contains all universal documentation standards.

## Scope Resolution

Determine scope FIRST:

| User Request                                            | Scope                                     |
| ------------------------------------------------------- | ----------------------------------------- |
| "sync docs" / "update documentation" / no specific path | REPOSITORY-WIDE                           |
| "sync docs in src/validator/"                           | DIRECTORY: src/validator/ and descendants |
| "update CLAUDE.md for parser.py"                        | FILE: single file's parent directory      |

For REPOSITORY-WIDE scope, perform a full audit. For narrower scopes, operate only within the specified boundary.

## Workflow

### Phase 0: Skill Discovery

**Step 1: Read project dependencies**

Read the project's dependency files to understand the tech stack:
- `package.json` (Node/JS/TS projects)
- `composer.json` (PHP projects)
- `requirements.txt` / `pyproject.toml` (Python projects)
- `Cargo.toml` (Rust projects)
- `go.mod` (Go projects)

**Step 2: Scan available skills**

```bash
python3 ~/.claude/skills/doc-sync/scripts/match_skills.py . --global
```

This returns a JSON list of available skills with names and descriptions.

**Step 3: Match skills intelligently**

Using your understanding of the project dependencies AND each skill's description,
identify which skills are relevant. Consider:

- Does the skill mention technologies the project uses?
- Would the skill help with this project's stack?
- For compound skills (e.g., "tailwind-v4-shadcn"), does the project use ALL
  the technologies bundled in that skill?

**Step 4: Suggest skills to user**

If no project-level skills exist (`.claude/skills/` is empty), present suggestions
using AskUserQuestion:

```
Found relevant skills in your global collection:

1. vue-best-practices - Vue 3 Composition API patterns
2. laravel-11-12-app-guidelines - Laravel application guidelines

Copy to project? (This makes them available to your team)
```

**Step 5: Install confirmed skills**

For skills user confirms, copy from global to project:
- Canonical copy: `.agents/skills/<skill-name>/`
- Symlink: `.claude/skills/<skill-name>` → `../../.agents/skills/<skill-name>`

This follows the vercel-labs/skills structure for agent-agnostic skill storage.

### Phase 1: Discovery

Map directories requiring CLAUDE.md verification:

```bash
# Find all directories (excluding .git, node_modules, __pycache__, etc.)
find . -type d \( -name .git -o -name node_modules -o -name __pycache__ -o -name .venv -o -name target -o -name dist -o -name build \) -prune -o -type d -print
```

For each directory in scope, record:

1. Does CLAUDE.md exist?
2. If yes, does it have the required table-based index structure?
3. What files/subdirectories exist that need indexing?

### Phase 2: Audit

For each directory, check for drift and misplaced content:

```
<audit_check dir="[path]">
CLAUDE.md exists: [YES/NO]
Has table-based index: [YES/NO]
Files in directory: [list]
Files in index: [list]
Missing from index: [list]
Stale in index (file deleted): [list]
Triggers are task-oriented: [YES/NO/PARTIAL]
Contains misplaced content: [YES/NO] (architecture/design docs that belong in README.md)
README.md exists: [YES/NO]
README.md warranted: [YES/NO] (invisible knowledge present?)
</audit_check>
```

### Phase 3: Content Migration

**Critical:** If CLAUDE.md contains content that does NOT belong there, migrate it:

Content that MUST be moved from CLAUDE.md to README.md:

- Architecture explanations or diagrams
- Design decision documentation
- Component interaction descriptions
- Overview sections with prose (beyond one sentence)
- Invariants or rules documentation
- Any "why" explanations beyond simple triggers
- Key Invariants sections
- Dependencies sections (explanatory -- index can note dependencies exist)
- Constraints sections
- Purpose sections with prose (beyond one sentence)
- Any bullet-point lists explaining rationale

Content that MAY stay in CLAUDE.md (operational sections):

- Build commands specific to this directory
- Test commands specific to this directory
- Regeneration/sync commands (e.g., protobuf regeneration)
- Deploy commands
- Other copy-pasteable procedural commands

**Test:** Ask "is this explaining WHY or telling HOW?" Explanatory content
(architecture, decisions, rationale) goes to README.md. Operational content
(commands, procedures) stays in CLAUDE.md.

Migration process:

1. Identify misplaced content in CLAUDE.md
2. Create or update README.md with the architectural content
3. Strip CLAUDE.md down to pure index format
4. Add README.md to the CLAUDE.md index table

### Phase 4: Index Updates

For each directory needing work:

**Creating/Updating CLAUDE.md:**

1. Use the appropriate template (ROOT or SUBDIRECTORY)
2. Populate tables with all files and subdirectories
3. Write "What" column: factual content description
4. Write "When to read" column: action-oriented triggers
5. If README.md exists, include it in the Files table

**Creating README.md (when invisible knowledge exists):**

1. Verify invisible knowledge exists (semantic trigger, not structural)
2. Document architecture, design decisions, invariants, tradeoffs
3. Apply the content test: remove anything visible from code
4. Keep as concise as possible while capturing all invisible knowledge
5. Must be self-contained: do not reference external authoritative sources

### Phase 5: Verification

After all updates complete, verify:

1. Every directory in scope has CLAUDE.md
2. All CLAUDE.md files use table-based index format (pure navigation)
3. No drift remains (files <-> index entries match)
4. No misplaced content in CLAUDE.md (explanatory prose moved to README.md)
5. README.md files are indexed in their parent CLAUDE.md
6. CLAUDE.md contains only: one-sentence overview + tabular index + operational sections
7. README.md exists wherever invisible knowledge was identified
8. README.md files are self-contained (no external authoritative references)

### Phase 6: Skill Embedding

Embed skill references in the agent file (AGENTS.md if referenced, else CLAUDE.md).

**Skill categories:**

1. **Project-wide skills** (workflow/methodology): Skills like `solution-design`,
   `problem-analysis`, `planner` that apply to any project
2. **Technology skills**: Skills matching the project's specific tech stack

**Embedding format:**

Use HTML comment markers for idempotent updates:

```markdown
<!-- doc-sync:skills-start -->
## Skills

| Skill | When to use |
|-------|-------------|
| `vue-best-practices` | Vue components, Composition API |
| `laravel-11-12-app-guidelines` | Laravel controllers, Eloquent |
<!-- doc-sync:skills-end -->
```

**Embedding rules:**

1. Root: Both project-wide + technology skills (max 15)
2. Subdirectories: Only technology skills relevant to that directory (max 5)
3. Embed descriptions only, not full skill content
4. Skills appearing in >80% of directories should be promoted to root only

## Output Format

```
## Doc Sync Report

### Scope: [REPOSITORY-WIDE | directory path]

### Changes Made
- CREATED: [list of new CLAUDE.md files]
- UPDATED: [list of modified CLAUDE.md files]
- MIGRATED: [list of content moved to README.md]
- SKILLS: [count] skills embedded

### Verification
- Directories audited: [count]
- CLAUDE.md coverage: [count]/[total]
- Drift fixed: [count] entries
```

### Phase 7: Content Accuracy

After structure is fixed, use AskUserQuestion to offer the incoherence check:

```
Doc-sync has fixed documentation structure.

Would you like to run a coherence check?
- Yes: Run comprehensive 21-step analysis to verify documentation matches code
- No: Skip (structure is synced, content accuracy not verified)
```

The incoherence skill is thorough but long. It detects contradictions between
documentation and implementation, stale claims, and content drift.

## Exclusions

DO NOT create CLAUDE.md for:

- Generated files directories (dist/, build/, compiled outputs)
- Vendored dependencies (node_modules/, vendor/, third_party/)
- Git internals (.git/)
- IDE/editor configs (.idea/, .vscode/ unless project-specific settings)
- **Stub directories** (contain only `.gitkeep` or no code files) - these do not
  require CLAUDE.md until code is added

DO NOT index (skip these files in CLAUDE.md):

- Generated files (_.generated._, compiled outputs)
- Vendored dependency files

DO index:

- Hidden config files that affect development (.eslintrc, .env.example, .gitignore)
- Test files and test directories
- Documentation files (including README.md)

## Anti-Patterns

### Index Anti-Patterns

**Too vague (matches everything):**

```markdown
| `config/` | Configuration | Working with configuration |
```

**Content description instead of trigger:**

```markdown
| `cache.rs` | Contains the LRU cache implementation | - |
```

**Missing action verb:**

```markdown
| `parser.py` | Input parsing | Input parsing and format handling |
```

### Correct Examples

```markdown
| `cache.rs` | LRU cache with O(1) get/set | Implementing caching, debugging misses, tuning eviction |
| `config/` | YAML config parsing, env overrides | Adding config options, changing defaults, debugging config loading |
```

## When NOT to Use This Skill

- Single file documentation (inline comments, docstrings) - handle directly
- Code comments - handle directly
- Function/module docstrings - handle directly
- This skill is for CLAUDE.md/README.md synchronization specifically

## Reference

For additional trigger pattern examples, see `references/trigger-patterns.md`.
