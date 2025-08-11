# Codebase Intelligence System

A Dagster-based orchestration system for automated codebase analysis and documentation using Claude Code. This system provides continuous analysis, quality auditing, knowledge graph maintenance, and living documentation for your codebase.

## Features

- **Continuous Analysis**: Monitors code changes and updates documentation automatically
- **Quality Auditing**: Periodic code quality assessments  
- **Knowledge Graph**: Maintains relationships between code components
- **Living Documentation**: Auto-generated and maintained documentation

## Quick Start

### Prerequisites

- Python 3.9 or higher
- Git
- Claude Code API access

### Installation

1. **Clone and setup**:
   ```bash
   git clone <repository-url>
   cd codebase-intelligence
   ./setup.sh
   ```

2. **Configure your environment**:
   Edit `.env` file with your Claude Code API key:
   ```bash
   CLAUDE_CODE_API_KEY=your_api_key_here
   ```

3. **Validate setup**:
   ```bash
   python test_setup.py
   ```

4. **Launch the system**:
   ```bash
   ./launch.sh
   ```

5. **Access the UI**:
   Open http://localhost:3000 in your browser

## Configuration

The system uses two main configuration files:

### `.env` file
```bash
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
```

### `config.yaml` file
```yaml
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
```

## System Architecture

### Core Components

- **`codebase_intelligence/assets/assets.py`**: Dagster assets for orchestrating analysis workflows
- **`codebase_intelligence/claude_integration.py`**: Client for interfacing with Claude Code API
- **`codebase_intelligence/jobs/jobs.py`**: Job definitions for different analysis workflows
- **`codebase_intelligence/utils/utils.py`**: Utilities for documentation management and code analysis
- **`codebase_intelligence/config.py`**: Configuration management system

### Data Storage

- **`./docs/`**: Generated documentation
- **`./data/knowledge_graph/`**: Code relationship mappings
- **`./data/metrics/`**: Analysis metrics and historical data
- **`./exports/`**: Export outputs
- **`./workspace/`**: Temporary working files

## Available Jobs

1. **continuous_analysis_job**: Triggered by code changes, analyzes impact and updates docs
2. **quality_audit_job**: Scheduled quality assessments
3. **full_analysis_job**: Complete codebase analysis (all assets)

## Usage

### Running Analysis Jobs

From the Dagster UI (http://localhost:3000):

1. Navigate to "Jobs" tab
2. Select the job you want to run:
   - **Continuous Analysis**: For analyzing recent changes
   - **Quality Audit**: For comprehensive code quality review
   - **Full Analysis**: For complete codebase analysis
3. Click "Launch Run"

### Manual Execution

You can also run jobs programmatically:

```python
from dagster import execute_job
from codebase_intelligence.jobs import continuous_analysis_job

result = execute_job(continuous_analysis_job)
```

## Development

### Manual Launch (Alternative)
```bash
source venv/bin/activate
export $(cat .env | xargs)
dagster dev -f codebase_intelligence/__init__.py
```

### Dependencies

- dagster
- dagster-webserver  
- gitpython
- pydantic
- pyyaml

## Troubleshooting

### Common Issues

1. **Python version error**: Ensure Python 3.9+ is installed
2. **API key issues**: Verify your Claude Code API key in `.env`
3. **Permission errors**: Check file permissions on directories and scripts
4. **Port conflicts**: Dagster UI runs on port 3000 by default

### Validation

Run the setup validation script:
```bash
python test_setup.py
```

## Support

- Check the logs in `./logs/codebase_intelligence.log`
- Review Dagster UI for job execution details
- Validate configuration files are properly formatted

## License

See LICENSE file for details.