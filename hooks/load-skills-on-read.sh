#!/bin/bash
# PostToolUse hook: After reading CLAUDE.md or AGENTS.md, extract and load required skills

input=$(cat)

# Extract fields without jq to handle multi-line content
# tool_name is always a simple string near the start
tool_name=$(echo "$input" | grep -o '"tool_name"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"tool_name"[[:space:]]*:[[:space:]]*"//; s/"$//')

# file_path is in tool_input object
file_path=$(echo "$input" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"file_path"[[:space:]]*:[[:space:]]*"//; s/"$//')

# Only process Read tool for CLAUDE.md or AGENTS.md files
if [ "$tool_name" != "Read" ]; then
  echo '{}'
  exit 0
fi

if [[ "$file_path" != *"CLAUDE.md" && "$file_path" != *"AGENTS.md" ]]; then
  echo '{}'
  exit 0
fi

# Check if content has a skills section (case-insensitive)
# Search the entire input since tool_result contains the file content
if ! echo "$input" | grep -qi "skills"; then
  echo '{}'
  exit 0
fi

# Extract skill names from Skill("name") patterns in the raw input
# Handle both escaped quotes (\") and regular quotes (")
skills=$(echo "$input" | grep -oE 'Skill\(\\?"([^"\\]+)\\?"\)' | sed 's/Skill(\\*"//g; s/\\*")//g' | sort -u)

if [ -z "$skills" ]; then
  echo '{}'
  exit 0
fi

# Build the system message
skill_list=$(echo "$skills" | tr '\n' ',' | sed 's/,$//')
message="REQUIRED SKILLS DETECTED in $file_path. You MUST immediately load these skills before proceeding: $skill_list. Use the Skill tool for each one NOW."

# Return systemMessage to inject into Claude's context
echo "{\"systemMessage\": \"$message\"}"
