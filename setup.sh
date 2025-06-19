#!/bin/bash
# setup.sh - Quick setup script for Codebase Intelligence System

set -e

echo "🚀 Setting up Codebase Intelligence System..."

# Check Python version
python_version=$(python --version 2>&1 | awk '{print $2}')
required_version="3.9"

if ! python -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)"; then
    echo "❌ Python 3.9+ is required. Current version: $python_version"
    exit 1
fi

echo "✅ Python version: $python_version"

# Create project structure
echo "📁 Creating project structure..."
mkdir -p codebase_intelligence/{assets,jobs,utils}
mkdir -p {docs,data,exports,workspace}
mkdir -p data/{knowledge_graph,metrics}

# Create virtual environment
echo "🐍 Creating virtual environment..."
python -m venv venv
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install dagster dagster-webserver gitpython pydantic pyyaml

# Create environment file
if [ ! -f .env ]; then
    echo "🔧 Creating .env file..."
    cat > .env << EOF
# Claude Code Configuration
CLAUDE_CODE_API_KEY=your_api_key_here

# Repository Configuration
REPO_PATH=.
REPO_BRANCH=main
LOOKBACK_DAYS=7

# Storage Configuration
DOCS_ROOT=./docs
GRAPH_STORE=./data/knowledge_graph
METRICS_STORE=./data/metrics

# Notification Configuration (optional)
SLACK_WEBHOOK=
SMTP_HOST=
SMTP_PORT=587
FROM_EMAIL=
EOF
    echo "⚠️  Please edit .env file with your configuration"
fi

# Create sample configuration
if [ ! -f config.yaml ]; then
    echo "📝 Creating config.yaml..."
    cat > config.yaml << EOF
claude_code:
  timeout: 300
  max_retries: 3

repository:
  path: "."
  branch: "main"
  lookback_days: 7

storage:
  docs_root: "./docs"
  graph_store: "./data/knowledge_graph"
  metrics_store: "./data/metrics"

notifications:
  email_config:
    smtp_host: "smtp.gmail.com"
    smtp_port: 587
EOF
fi

# Create __init__.py files
touch codebase_intelligence/__init__.py
touch codebase_intelligence/assets/__init__.py
touch codebase_intelligence/jobs/__init__.py
touch codebase_intelligence/utils/__init__.py

# Create a simple test script
cat > test_setup.py << EOF
#!/usr/bin/env python
"""Test if the setup is working correctly."""

import sys
from pathlib import Path

def test_imports():
    """Test if all required packages can be imported."""
    try:
        import dagster
        print("✅ Dagster installed")
        
        import git
        print("✅ GitPython installed")
        
        import pydantic
        print("✅ Pydantic installed")
        
        import yaml
        print("✅ PyYAML installed")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_directories():
    """Test if all required directories exist."""
    dirs = ["docs", "data", "exports", "workspace", "codebase_intelligence"]
    
    for dir_name in dirs:
        if Path(dir_name).exists():
            print(f"✅ Directory '{dir_name}' exists")
        else:
            print(f"❌ Directory '{dir_name}' missing")
            return False
    
    return True

def test_config():
    """Test if configuration files exist."""
    files = [".env", "config.yaml"]
    
    for file_name in files:
        if Path(file_name).exists():
            print(f"✅ Config file '{file_name}' exists")
        else:
            print(f"❌ Config file '{file_name}' missing")
            return False
    
    return True

if __name__ == "__main__":
    print("🧪 Testing Codebase Intelligence System setup...")
    print()
    
    all_good = True
    
    if not test_imports():
        all_good = False
    
    print()
    
    if not test_directories():
        all_good = False
    
    print()
    
    if not test_config():
        all_good = False
    
    print()
    
    if all_good:
        print("✅ All tests passed! Setup is complete.")
        print()
        print("Next steps:")
        print("1. Edit .env file with your Claude Code API key")
        print("2. Copy the Python files from the artifacts to codebase_intelligence/")
        print("3. Run: dagster dev -f codebase_intelligence/__init__.py")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        sys.exit(1)
EOF

chmod +x test_setup.py

# Create a launcher script
cat > launch.sh << EOF
#!/bin/bash
# Launch the Dagster UI

source venv/bin/activate
export \$(cat .env | xargs)

echo "🚀 Launching Dagster UI..."
echo "📊 Open http://localhost:3000 in your browser"
echo "Press Ctrl+C to stop"

dagster dev -f codebase_intelligence/__init__.py
EOF

chmod +x launch.sh

# Run tests
echo ""
echo "🧪 Running setup tests..."
python test_setup.py

echo ""
echo "✨ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Copy the Python code from the artifacts to codebase_intelligence/"
echo "2. Edit .env file with your configuration"
echo "3. Run ./launch.sh to start the Dagster UI"
echo ""
echo "For detailed instructions, see the README.md"
