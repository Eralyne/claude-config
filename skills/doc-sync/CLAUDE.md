# doc-sync/

Cross-repository documentation synchronization skill with smart skill embedding.

## Files

| File        | What                                              | When to read                 |
| ----------- | ------------------------------------------------- | ---------------------------- |
| `SKILL.md`  | Skill activation, workflow phases, skill embedding | Using this skill             |
| `README.md` | Architecture and design decisions                 | Understanding skill behavior |

## Subdirectories

| Directory     | What                                        | When to read                       |
| ------------- | ------------------------------------------- | ---------------------------------- |
| `scripts/`    | Technology detection and skill matching     | Debugging skill embedding behavior |
| `references/` | Trigger pattern examples                    | Writing better index triggers      |

## Scripts

| Script           | What                                      | When to run                    |
| ---------------- | ----------------------------------------- | ------------------------------ |
| `detect_tech.py` | Scans project for technology stack        | Phase 0: Technology Detection  |
| `match_skills.py`| Matches technologies to relevant skills   | Phase 0.5: Skill Discovery     |

## Skill Scope System

Skills are classified by scope in `match_skills.py`:

| Scope | Where embedded | Example skills |
|-------|----------------|----------------|
| `project` | Root CLAUDE.md only | `solution-design`, `planner`, `deepthink` |
| `technology` | Directory CLAUDE.md based on local tech | `vue-best-practices`, `laravel-11-12-app-guidelines` |

### Directory-level Detection

```bash
# Detect tech for entire tree
python3 scripts/detect_tech.py /path/to/project --tree

# Match skills per directory
python3 scripts/match_skills.py /path/to/project --tree
```

This enables PHP directories to get Laravel skills, Vue directories to get Vue skills, etc.
