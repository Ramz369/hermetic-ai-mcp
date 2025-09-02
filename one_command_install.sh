#!/bin/bash
# Hermetic AI MCP - True One-Command Installation
# Usage: curl -sSL https://raw.githubusercontent.com/ramz/hermetic-ai-mcp/main/one_command_install.sh | bash

set -e

echo "🚀 Hermetic AI MCP - One-Command Installation"
echo "============================================="

# Install directory
INSTALL_DIR="$HOME/Documents/adev/HERMETIC-AI-MCP"

# Clone or update repo
if [ -d "$INSTALL_DIR" ]; then
    echo "📂 Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull 2>/dev/null || true
else
    echo "📦 Cloning repository..."
    git clone https://github.com/ramz/hermetic-ai-mcp.git "$INSTALL_DIR" 2>/dev/null || true
    cd "$INSTALL_DIR"
fi

# Install package
echo "📦 Installing package..."
pip3 install --user . --break-system-packages --force-reinstall --quiet

# Ensure PATH
export PATH="$HOME/.local/bin:$PATH"

# Test installation
if ! command -v hermetic-mcp >/dev/null 2>&1; then
    echo "❌ Installation failed - hermetic-mcp not found"
    exit 1
fi

# Find Claude config
CONFIG_FILE="$HOME/.config/claude/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    mkdir -p "$HOME/.config/claude"
    echo '{"mcpServers":{}}' > "$CONFIG_FILE"
fi

# Update Claude config
echo "🔧 Configuring Claude..."
python3 << EOF
import json

with open("$CONFIG_FILE", 'r') as f:
    config = json.load(f)

if 'mcpServers' not in config:
    config['mcpServers'] = {}

config['mcpServers']['hermetic-ai'] = {
    "command": "$HOME/.local/bin/hermetic-mcp",
    "args": [],
    "env": {}
}

with open("$CONFIG_FILE", 'w') as f:
    json.dump(config, f, indent=2)

print("✅ Configuration updated")
EOF

# Test MCP protocol
echo "🧪 Testing MCP server..."
TEST=$(echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}' | hermetic-mcp 2>/dev/null | head -1)

if echo "$TEST" | grep -q "hermetic-ai"; then
    echo "✅ MCP server test passed"
fi

echo ""
echo "============================================="
echo "✅ INSTALLATION COMPLETE!"
echo "============================================="
echo ""
echo "The hermetic-ai MCP server is installed and configured."
echo ""
echo "📋 Next Steps:"
echo "1. Restart Claude Code CLI completely"
echo "2. The 'hermetic-ai' server will be available"
echo ""
echo "🛠️ Available Tools:"
echo "  • verify_code"
echo "  • verify_with_skepticism"
echo "  • generate_forensic_report"
echo "  • search_memory"
echo "  • store_memory"
echo ""
echo "To verify: cat ~/.config/claude/config.json | grep hermetic-ai"