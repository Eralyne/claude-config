#!/bin/bash
# PostToolUse hook: After reading CLAUDE.md or AGENTS.md, extract and load required skills

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')
tool_result=$(echo "$input" | jq -r '.tool_result // empty')

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
if ! echo "$tool_result" | grep -qi "skills"; then
  echo '{}'
  exit 0
fi

# Extract skill names from Skill("name") patterns
skills=$(echo "$tool_result" | grep -oE 'Skill\("([^"]+)"\)' | sed 's/Skill("//g; s/")//g' | sort -u)

if [ -z "$skills" ]; then
  echo '{}'
  exit 0
fi

# Build the system message
skill_list=$(echo "$skills" | tr '\n' ',' | sed 's/,$//')
message="REQUIRED SKILLS DETECTED in $file_path. You MUST immediately load these skills before proceeding: $skill_list. Use the Skill tool for each one NOW."

# Return systemMessage to inject into Claude's context
echo "{\"systemMessage\": \"$message\"}"
