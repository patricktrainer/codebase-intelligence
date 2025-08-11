# codebase_intelligence/assets.py
"""
Dagster assets for the Automated Codebase Intelligence System.
Orchestrates Claude Code instances to maintain living documentation of codebases.
"""

import json
import re
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import os
from pathlib import Path

import dagster
from dagster import (
    asset, 
    AssetExecutionContext, 
    MaterializeResult,
    MetadataValue,
    Output,
    AssetIn,
    DailyPartitionsDefinition,
    WeeklyPartitionsDefinition,
    Config,
    Definitions,
    ScheduleDefinition,
    sensor,
    RunRequest,
    SensorEvaluationContext,
    DefaultSensorStatus,
    OpExecutionContext,
    DagsterEventType,
    RunsFilter,
    DagsterInstance,
    EventRecordsFilter
)
import git
from pydantic import BaseModel

from codebase_intelligence.claude_integration import ClaudeCodeClient, ClaudeCodeResult
from codebase_intelligence.logging_config import get_logger
from codebase_intelligence.utils.utils import DocumentationManager, CodebaseAnalyzer, KnowledgeGraphStore

LOGGER = get_logger(__name__)


# Utility Functions for JSON Serialization
def json_serializer(obj):
    """Custom JSON serializer for datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def safe_json_dumps(data, **kwargs):
    """Safe JSON dumps that handles datetime objects."""
    return json.dumps(data, default=json_serializer, **kwargs)


# Configuration Models
class ClaudeCodeConfig(Config):
    """Configuration for Claude Code execution."""
    api_key: str = os.getenv("CLAUDE_CODE_API_KEY", "")
    max_retries: int = 3
    timeout_seconds: int = 300


class RepositoryConfig(Config):
    """Configuration for repository analysis."""
    repo_path: str = "."
    branch: str = "main"
    lookback_days: int = 7


# Data Models
class CodeChange(BaseModel):
    """Represents a code change detected in the repository."""
    commit_hash: str
    author: str
    timestamp: datetime
    files_changed: List[str]
    additions: int
    deletions: int
    message: str
    diff_summary: Optional[str] = None


class ImpactAnalysis(BaseModel):
    """Represents the impact analysis of code changes."""
    architectural_changes: List[str]
    breaking_changes: List[str]
    new_patterns: List[str]
    performance_implications: List[str]
    affected_components: List[str]
    risk_level: str  # low, medium, high


class DocumentationUpdate(BaseModel):
    """Represents documentation updates needed."""
    file_path: str
    update_type: str  # create, update, deprecate
    content: str
    reason: str


class CodeQualityIssue(BaseModel):
    """Represents a code quality issue found."""
    severity: str  # low, medium, high, critical
    category: str  # tech_debt, security, performance, consistency
    file_path: str
    line_range: Optional[tuple] = None
    description: str
    suggested_fix: Optional[str] = None


class KnowledgeGraphNode(BaseModel):
    """Represents a node in the codebase knowledge graph."""
    id: str
    type: str  # module, class, function, service
    name: str
    dependencies: List[str]
    dependents: List[str]
    metadata: Dict[str, Any]


# Utility Functions
def execute_claude_code(prompt: str, context: Dict[str, Any], config: ClaudeCodeConfig, workspace_path: Optional[Path] = None) -> str:
    """
    Execute Claude Code with the given prompt and context.
    In production, this would call the actual Claude Code API.
    """
    # Mock implementation - replace with actual Claude Code API call
    # In reality, this would be something like:
    # response = claude_code_client.execute(prompt=prompt, context=context)
    
    claude_code_client = ClaudeCodeClient(
        api_key=config.api_key,
        timeout=config.timeout_seconds
    )

    LOGGER.info(f"Executing Claude Code with prompt: {prompt[:100]}...")  # Log first 100 chars for brevity

    result: ClaudeCodeResult = claude_code_client.execute(prompt, context, workspace_path)
    LOGGER.info(f"Claude Code execution completed with status: {result.success}")

    if not result.success:
        raise RuntimeError(f"Claude Code execution failed: {result.error}")

    if result.output is None:
        raise RuntimeError("Claude Code execution succeeded but returned no output.")
        
    LOGGER.info(f"Claude Code output: {result.output}")
    return result.output


def get_git_commits(repo_path: str, since: datetime, branch: str = "main") -> List[CodeChange]:
    """Fetch git commits since the specified date."""
    repo = git.Repo(repo_path)
    commits = []
    
    for commit in repo.iter_commits(branch, since=since):
        # Get the files changed in this commit
        files_changed = []
        if commit.parents:
            # Compare with first parent to get changed files
            for diff in commit.diff(commit.parents[0]):
                if diff.a_path:
                    files_changed.append(diff.a_path)
                if diff.b_path and diff.b_path != diff.a_path:
                    files_changed.append(diff.b_path)
        else:
            # Initial commit - all files are "changed"
            for diff in commit.diff(None):
                if diff.b_path:
                    files_changed.append(diff.b_path)
        
        # Remove duplicates and None values
        files_changed = list(set(f for f in files_changed if f))
        
        # Get commit stats
        stats = commit.stats.total
        
        # Handle message encoding
        message = commit.message
        if isinstance(message, bytes):
            message = message.decode('utf-8', errors='ignore')
        elif not isinstance(message, str):
            message = str(message) if message else ""
        
        commits.append(CodeChange(
            commit_hash=commit.hexsha,
            author=commit.author.name or "Unknown",
            timestamp=datetime.fromtimestamp(commit.committed_date),
            files_changed=files_changed,
            additions=stats.get("insertions", 0),
            deletions=stats.get("deletions", 0),
            message=message
        ))
    
    return commits


# Assets
@asset(
    description="Detects and analyzes recent code changes in the repository",
    compute_kind="claude_code"
)
def code_changes(
    context: AssetExecutionContext,
    config: RepositoryConfig
) -> Output[List[Dict[str, Any]]]:
    """
    Asset that detects code changes using git and analyzes them with Claude Code.
    """
    # Get commits from the last N days
    since = datetime.now() - timedelta(days=config.lookback_days)
    commits = get_git_commits(config.repo_path, since, config.branch)

    context.log.info(f"Found {len(commits)} commits since {since}")
    
    # Analyze each commit with Claude Code
    analyzed_changes = []
    for commit in commits:
        # Prepare context for Claude Code
        claude_context = {
            "commit": commit.model_dump(),
            "repo_path": config.repo_path
        }
        
        # Get detailed diff for the commit
        repo = git.Repo(config.repo_path)
        commit_obj = repo.commit(commit.commit_hash)
        diff_text = ""
        for diff in commit_obj.diff(commit_obj.parents[0] if commit_obj.parents else None):
            diff_text += f"\n--- {diff.a_path}\n+++ {diff.b_path}\n"
            if diff.diff:
                # Handle different types of diff content
                diff_content = diff.diff
                if isinstance(diff_content, bytes):
                    diff_content = diff_content.decode('utf-8', errors='ignore')
                elif not isinstance(diff_content, str):
                    diff_content = str(diff_content)
                diff_text += diff_content[:1000]  # Limit diff size
        
        # Analyze with Claude Code
        prompt = f"""
        Analyze this git commit and provide a structured analysis:
        
        Commit: {commit.commit_hash}
        Message: {commit.message}
        Files changed: {', '.join(commit.files_changed)}
        
        Diff preview:
        {diff_text}
        
        Provide:
        1. Type of change (feature, bugfix, refactor, etc.)
        2. Key modifications
        3. Potential impacts
        4. Code quality observations
        """
        
        analysis = execute_claude_code(prompt, claude_context, ClaudeCodeConfig(), workspace_path=Path(config.repo_path))
        
        # Convert commit to dict with proper datetime serialization
        analyzed_change = commit.model_dump()
        # Convert datetime to ISO string for JSON serialization
        if 'timestamp' in analyzed_change and isinstance(analyzed_change['timestamp'], datetime):
            analyzed_change['timestamp'] = analyzed_change['timestamp'].isoformat()
        
        # Parse Claude Code analysis output with error handling
        try:
            if analysis.strip():
                claude_analysis_output = json.loads(analysis)
                # If it's a list, take the last element; otherwise use as-is
                if isinstance(claude_analysis_output, list) and claude_analysis_output:
                    analyzed_change["analysis"] = claude_analysis_output[-1]
                else:
                    analyzed_change["analysis"] = claude_analysis_output
            else:
                LOGGER.warning(f"Empty analysis output for commit {commit.commit_hash}")
                analyzed_change["analysis"] = {"error": "Empty analysis output"}
        except json.JSONDecodeError as e:
            LOGGER.error(f"Failed to parse Claude Code analysis as JSON for commit {commit.commit_hash}: {e}")
            LOGGER.error(f"Raw analysis output: {analysis}")
            analyzed_change["analysis"] = {"error": f"JSON parse error: {str(e)}", "raw_output": analysis}
        analyzed_changes.append(analyzed_change)
        # pretty print the analyzed changes
        LOGGER.info(safe_json_dumps(analyzed_changes, indent=2))

    return Output(
        value=analyzed_changes,
        metadata={
            "num_commits": len(commits),
            "date_range": f"{since} to {datetime.now()}",
            "branch": config.branch
        }
    )


@asset(
    ins={"code_changes": AssetIn()},
    description="Assesses the impact of code changes on the system",
    compute_kind="claude_code"
)
def impact_assessment(
    context: AssetExecutionContext,
    code_changes: List[Dict[str, Any]]
) -> Output[Dict[str, Any]]:
    """
    Analyzes the overall impact of a set of code changes.
    """
    context.log.info(f"Assessing impact of {len(code_changes)} code changes.")

    # Combine all changes for a single analysis
    if not code_changes:
        context.log.info("No code changes to assess.")
        return Output({}, metadata={"num_changes_analyzed": 0, "risk_level": "none"})

    prompt = f"""
    Based on the following code change analyses, provide a comprehensive impact assessment.
    
    Changes:
    {safe_json_dumps(code_changes, indent=2)}
    
    Provide a JSON object conforming to the ImpactAnalysis model with keys:
    - architectural_changes: List[str]
    - breaking_changes: List[str]
    - new_patterns: List[str]
    - performance_implications: List[str]
    - affected_components: List[str]
    - risk_level: str (low, medium, high)
    """
    
    claude_context = {"code_changes": code_changes}
    # Get repository config - we need to access it from the context or use a default
    repo_config = RepositoryConfig()
    analysis_output = execute_claude_code(prompt, claude_context, ClaudeCodeConfig(), workspace_path=Path(repo_config.repo_path))
    
    # Log the raw output for debugging
    LOGGER.info(f"Raw Claude output for impact assessment: {analysis_output}")
    
    # Parse the Claude output to extract the actual impact analysis data
    try:
        # analysis_output is already parsed JSON from Claude integration
        # Try to extract the structured data from the response
        if isinstance(analysis_output, str):
            # Try to parse as JSON first
            parsed_output = json.loads(analysis_output)
        else:
            parsed_output = analysis_output
            
        LOGGER.info(f"Parsed output type: {type(parsed_output)}, content: {parsed_output}")
        
        # If it's a list, take the last item
        if isinstance(parsed_output, list):
            impact_data = parsed_output[-1]
        # If it's a dict, check if it has the expected structure
        elif isinstance(parsed_output, dict):
            if "architectural_changes" in parsed_output:
                impact_data = parsed_output
            else:
                # This might be a Claude response wrapper - try to extract JSON from it
                if isinstance(parsed_output, str):
                    # Try to extract JSON from text
                    import re
                    json_match = re.search(r'\{.*\}', parsed_output, re.DOTALL)
                    if json_match:
                        impact_data = json.loads(json_match.group())
                    else:
                        raise ValueError("No JSON found in output")
                else:
                    # Create a default response
                    LOGGER.warning(f"Unexpected Claude output structure: {parsed_output}")
                    impact_data = {
                        "architectural_changes": [],
                        "breaking_changes": [],
                        "new_patterns": [],
                        "performance_implications": [],
                        "affected_components": [],
                        "risk_level": "low"
                    }
        else:
            raise ValueError("Unexpected output format from Claude")
            
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        LOGGER.warning(f"Could not parse Claude output: {e}, using default. Raw output: {analysis_output}")
        # Provide a default impact analysis
        impact_data = {
            "architectural_changes": [],
            "breaking_changes": [],
            "new_patterns": [],
            "performance_implications": [],
            "affected_components": [],
            "risk_level": "low"
        }
    
    # Validate with Pydantic model
    validated_impact = ImpactAnalysis(**impact_data)
    
    return Output(
        value=validated_impact.model_dump(),
        metadata={
            "num_changes_analyzed": len(code_changes),
            "risk_level": validated_impact.risk_level
        }
    )


@asset(
    ins={"impact_assessment": AssetIn()},
    description="Generates documentation updates based on code changes",
    compute_kind="claude_code"
)
def documentation_updates(
    context: AssetExecutionContext,
    impact_assessment: Dict[str, Any],
    config: RepositoryConfig
) -> Output[List[Dict[str, Any]]]:
    """
    Generates documentation updates based on the impact assessment.
    """
    context.log.info("Generating documentation updates based on impact assessment.")
    
    if not impact_assessment:
        context.log.info("No impact assessment to generate documentation from.")
        return Output([], metadata={"num_updates": 0})

    doc_manager = DocumentationManager(docs_root=Path(config.repo_path) / "docs")

    docs_path = Path(config.repo_path) / "docs"
    docs_path.mkdir(exist_ok=True)
    
    prompt = f"""
    Based on the following impact assessment, create or update documentation files directly.
    Write the documentation files to the ./docs/ directory.
    
    Focus on creating these types of documentation:
    1. Architecture changes documentation
    2. Breaking changes and migration guide
    3. New features and API documentation
    4. Deployment and configuration updates
    
    Impact Assessment:
    {safe_json_dumps(impact_assessment, indent=2)}
    
    Please create/update the documentation files directly. After creating the files, 
    provide a brief summary of what documentation was updated.
    """
    
    claude_context = {"impact_assessment": impact_assessment, "docs_path": str(docs_path)}
    updates_output = execute_claude_code(prompt, claude_context, ClaudeCodeConfig(), workspace_path=Path(config.repo_path))
    
    # Instead of parsing JSON, just log the summary and check what files were created
    context.log.info(f"Documentation update summary: {updates_output}")
    
    # Find all markdown files in docs directory to see what was created/updated
    written_files = []
    if docs_path.exists():
        for md_file in docs_path.glob("**/*.md"):
            written_files.append(str(md_file.relative_to(docs_path)))
    
    # Generate/update index using DocumentationManager
    index_content = doc_manager.generate_index()
    doc_manager.write_documentation("index.md", index_content, "update")
    context.log.info("Updated documentation index.")
    
    # Create simple documentation update objects for return value
    doc_updates = [
        {
            "file_path": f,
            "update_type": "update", 
            "content": f"Documentation updated for {f}",
            "reason": "Generated from impact assessment"
        } for f in written_files
    ]

    return Output(
        value=doc_updates,
        metadata={
            "num_updates": len(doc_updates),
            "updated_files": written_files,
            "index_updated": True
        }
    )


@asset(
    description="Performs scheduled code quality audit",
    compute_kind="claude_code",
    partitions_def=WeeklyPartitionsDefinition(start_date="2024-01-01")
)
def code_quality_audit(
    context: AssetExecutionContext,
    config: RepositoryConfig
) -> Output[List[Dict[str, Any]]]:
    """
    Asset that performs regular code quality audits.
    """
    analyzer = CodebaseAnalyzer(repo_path=Path(config.repo_path))
    source_files = analyzer.get_source_files()

    if not source_files:
        context.log.warning("No source files found for code quality audit. Check your repository path and file patterns.")
        return Output(value=[], metadata={"message": "No source files found."})
    context.log.info(f"Found {len(source_files)} source files for audit in {config.repo_path}")


    prompt = f"""
    Perform a comprehensive code quality audit for this codebase:
    
    Repository: {config.repo_path}
    Number of files: {len(source_files)}
    File types: Python, JavaScript
    
    Analyze for:
    1. Technical debt accumulation
    2. Inconsistent patterns across modules
    3. Security vulnerability patterns
    4. Performance bottlenecks
    5. Missing abstractions or over-engineering
    6. Test coverage gaps
    
    For each issue found, provide:
    - Severity (low/medium/high/critical)
    - Category (tech_debt/security/performance/consistency)
    - Affected files and line ranges
    - Description of the issue
    - Suggested fix or refactoring
    """
    
    audit_result = execute_claude_code(prompt, {"files": [str(f) for f in source_files]}, ClaudeCodeConfig(), workspace_path=Path(config.repo_path))
    
    # Log the audit result instead of parsing as JSON
    context.log.info(f"Code quality audit result: {audit_result}")
    
    # Create a basic audit structure
    issues = []
    # Create a simple default issue if we can't parse the result
    if "error" in audit_result.lower() or "warning" in audit_result.lower():
        issues.append({
            "severity": "medium",
            "category": "general",
            "affected_files": [str(f) for f in source_files[:3]],  # First 3 files
            "description": f"Audit completed: {audit_result[:100]}...",
            "suggested_fix": "Review the audit output for detailed recommendations"
        })
    
    quality_issues = []
    for issue in issues:
        quality_issue = CodeQualityIssue(
            severity=issue["severity"],
            category=issue["category"],
            file_path=issue.get("file", ""),
            line_range=issue.get("line_range"),
            description=issue["description"],
            suggested_fix=issue.get("suggested_fix")
        )
        quality_issues.append(quality_issue.model_dump())
    
    return Output(
        value=quality_issues,
        metadata={
            "total_issues": len(quality_issues),
            "critical_issues": len([i for i in quality_issues if i["severity"] == "critical"]),
            "files_analyzed": len(source_files),
            "audit_summary": audit_result[:200] + "..." if len(audit_result) > 200 else audit_result
        }
    )


@asset(
    ins={
        "code_changes": AssetIn(),
        "impact_assessment": AssetIn()
    },
    description="Builds and maintains a knowledge graph of the codebase",
    compute_kind="claude_code"
)
def codebase_knowledge_graph(
    context: AssetExecutionContext,
    code_changes: List[Dict[str, Any]],
    impact_assessment: Dict[str, Any],
    config: RepositoryConfig
) -> Output[Dict[str, Any]]:
    """
    Asset that builds a knowledge graph of the codebase structure and relationships.
    """
    # Create knowledge graph data directory
    graph_path = Path(config.repo_path) / "data" / "knowledge_graph"
    graph_path.mkdir(parents=True, exist_ok=True)
    
    prompt = f"""
    Analyze the codebase and create knowledge graph files in the ./data/knowledge_graph/ directory.
    
    Repository: {config.repo_path}
    Recent changes: {safe_json_dumps(code_changes, indent=2)}
    Impact assessment: {safe_json_dumps(impact_assessment, indent=2)}
    
    Please analyze the codebase structure and create these files:
    1. nodes.json - Components, modules, classes, functions
    2. edges.json - Dependencies and relationships
    3. metrics.json - Complexity and quality metrics
    4. analysis.md - Human-readable analysis report
    
    Focus on:
    - Module and service relationships
    - Data flow paths
    - Key abstractions and their evolution
    - Component dependencies
    - API contracts between components
    - Circular dependencies
    - Highly coupled components
    - Central points of failure
    
    """
    
    graph_result = execute_claude_code(prompt, {
        "changes": code_changes,
        "impact": impact_assessment,
        "graph_path": str(graph_path)
    }, ClaudeCodeConfig(), workspace_path=Path(config.repo_path))
    
    # Log the summary instead of parsing JSON
    context.log.info(f"Knowledge graph analysis: {graph_result}")
    
    # Check what files were created and build a simple graph structure
    created_files = []
    nodes = []
    edges = []
    
    if graph_path.exists():
        for json_file in graph_path.glob("*.json"):
            created_files.append(str(json_file.name))
        for md_file in graph_path.glob("*.md"):
            created_files.append(str(md_file.name))
    
    # Create a simple default graph structure
    edges = []
    
    knowledge_graph = {
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "created_files": created_files,
            "analysis_summary": graph_result[:200] + "..." if len(graph_result) > 200 else graph_result
        }
    }
    
    # Save the knowledge graph
    kg_store = KnowledgeGraphStore(store_path=Path(config.repo_path) / "data" / "knowledge_graph")
    kg_store.save_graph(knowledge_graph)
    context.log.info(f"Knowledge graph saved to {kg_store.graph_file}")

    return Output(
        value=knowledge_graph,
        metadata={
            "num_nodes": len(knowledge_graph["nodes"]),
            "num_edges": len(knowledge_graph["edges"]),
            "total_files_analyzed": knowledge_graph["metadata"].get("total_files_analyzed", 0),
            "total_loc": knowledge_graph["metadata"].get("total_lines_of_code", 0),
            "analysis_method": knowledge_graph["metadata"].get("analysis_method", "unknown")
        }
    )


# Sensors and Schedules
@sensor(
    job_name="continuous_analysis",
    default_status=DefaultSensorStatus.RUNNING,
    description="Triggers analysis when new commits are detected"
)
def commit_sensor(context: SensorEvaluationContext):
    """
    Sensor that triggers the pipeline when new commits are detected.
    """
    # Check for new commits (in production, this would check actual git state)
    # For now, we'll use a simple file-based approach
    last_commit_file = Path("/tmp/dagster_last_commit.txt")
    
    # Get current HEAD commit
    repo = git.Repo(".")
    current_head = repo.head.commit.hexsha
    
    # Check if this is a new commit
    if last_commit_file.exists():
        last_commit = last_commit_file.read_text().strip()
        if last_commit == current_head:
            return  # No new commits
    
    # Write current commit
    last_commit_file.write_text(current_head)
    
    # Trigger run for code_changes asset
    return RunRequest(
        run_key=f"commit_{current_head}",
        tags={"commit": current_head}
    )


# Schedule for weekly quality audits
quality_audit_schedule = ScheduleDefinition(
    name="weekly_quality_audit",
    cron_schedule="0 0 * * 0",  # Every Sunday at midnight
    job_name="quality_audit_job",
    description="Weekly code quality audit"
)


# Main Dagster Definitions
defs = Definitions(
    assets=[
        code_changes,
        impact_assessment,
        documentation_updates,
        code_quality_audit,
        codebase_knowledge_graph
    ],
    sensors=[commit_sensor],
    schedules=[quality_audit_schedule],
)
