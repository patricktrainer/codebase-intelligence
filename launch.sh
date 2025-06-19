#!/bin/bash
# Launch the Dagster UI

source venv/bin/activate
export $(cat .env | xargs)

echo "🚀 Launching Dagster UI..."
echo "📊 Open http://localhost:3000 in your browser"
echo "Press Ctrl+C to stop"

dagster dev -f codebase_intelligence/__init__.py
