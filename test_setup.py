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
