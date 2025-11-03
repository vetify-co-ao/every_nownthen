#!/bin/bash
set -e

echo "Installing UV tools from Git repositories..."

UV_TOOLS_FILE="uv_tools.txt"

# Check if uv_tools.txt exists
if [ ! -f "$UV_TOOLS_FILE" ]; then
    echo "Warning: $UV_TOOLS_FILE not found. No tools to install."
    exit 0
fi

# Read each line from uv_tools.txt
while IFS= read -r line || [ -n "$line" ]; do
    # Skip empty lines and comments
    if [[ -z "$line" ]] || [[ "$line" =~ ^[[:space:]]*# ]]; then
        continue
    fi

    # Extract tool name from repository URL
    tool_name=$(echo "$line" | sed -E 's/.*\/([^/]+)\.git$/\1/')

    echo "Installing tool: $tool_name from $line"

    # Install the tool using UV
    if uv tool install "$line"; then
        echo "✓ $tool_name installed successfully"
    else
        echo "✗ Failed to install $tool_name"
        exit 1
    fi

done < "$UV_TOOLS_FILE"

echo ""
echo "All UV tools installed successfully!"
echo ""
echo "Installed tools:"
uv tool list
