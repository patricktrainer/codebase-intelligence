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

from codebase_intelligence.claude_integration import ClaudeCodeClient, ClaudeCodeResult, LOGGER



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

# Utility to write documentation updates to file
def write_documentation_file(doc_update: DocumentationUpdate):
    """Writes the documentation update to the specified file."""
    os.makedirs(os.path.dirname(doc_update.file_path), exist_ok=True)
    mode = "a" if doc_update.update_type == "update" else "w"
    with open(doc_update.file_path, mode, encoding="utf-8") as f:
        f.write(f"\n# Update Reason: {doc_update.reason}\n")
        f.write(doc_update.content)
        f.write("\n")


class KnowledgeGraphNode(BaseModel):
    """Represents a node in the codebase knowledge graph."""
    id: str
    type: str  # module, class, function, service
    name: str
    dependencies: List[str]
    dependents: List[str]
    metadata: Dict[str, Any]


# Utility Functions
def execute_claude_code(prompt: str, context: Dict[str, Any], config: ClaudeCodeConfig) -> str:
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

    result: ClaudeCodeResult = claude_code_client.execute(prompt, context)
    LOGGER.info(f"Claude Code execution completed with status: {result.success}")

    if not result.success:
        raise RuntimeError(f"Claude Code execution failed: {result.output}")
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
            "commit": commit.dict(),
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
        
        analysis = execute_claude_code(prompt, claude_context, ClaudeCodeConfig())
        
        # Convert commit to dict with proper datetime serialization
        analyzed_change = commit.dict()
        # Convert datetime to ISO string for JSON serialization
        if 'timestamp' in analyzed_change and isinstance(analyzed_change['timestamp'], datetime):
            analyzed_change['timestamp'] = analyzed_change['timestamp'].isoformat()
        claude_analysis_output = json.loads(analysis)
        # analyzed_change["analysis"] = claude_analysis_output[-1] # the result from Claude Code is expected to be a list with the last item being the analysis
        analyzed_change["analysis"] = claude_analysis_output # the result from Claude Code is expected to be a list with the last item being the analysis
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
    Asset that assesses the impact of detected code changes.
    """
    # Aggregate all changes for comprehensive analysis
    all_files_changed = set()
    all_analyses = []
    
    for change in code_changes:
        all_files_changed.update(change["files_changed"])
        if "analysis" in change:
            all_analyses.append(change["analysis"])
    
    # Create comprehensive prompt for impact assessment
    prompt = f"""
    Assess the collective impact of these code changes:
    
    Total commits: {len(code_changes)}
    Files affected: {', '.join(sorted(all_files_changed))}
    
    Individual analyses:
    {safe_json_dumps(all_analyses, indent=2)}
    
    Provide a comprehensive impact assessment including:
    1. Architectural changes and their implications
    2. Breaking changes that need communication
    3. New patterns introduced
    4. Performance implications
    5. Security considerations
    6. Overall risk level (low/medium/high)
    7. Recommended actions
    """
    
    impact_result = execute_claude_code(prompt, {"changes": code_changes}, ClaudeCodeConfig())
    impact_data = json.loads(impact_result)
    
    # Create ImpactAnalysis object
    impact = ImpactAnalysis(
        architectural_changes=impact_data.get("architectural_changes", []),
        breaking_changes=impact_data.get("breaking_changes", []),
        new_patterns=impact_data.get("new_patterns", []),
        performance_implications=impact_data.get("performance_implications", []),
        affected_components=list(all_files_changed),
        risk_level=impact_data.get("risk_level", "low")
    )
    
    return Output(
        value=impact.dict(),
        metadata={
            "risk_level": impact.risk_level,
            "num_breaking_changes": len(impact.breaking_changes),
            "num_affected_files": len(all_files_changed)
        }
    )


@asset(
    ins={"impact_assessment": AssetIn()},
    description="Generates documentation updates based on code changes",
    compute_kind="claude_code"
)
def documentation_updates(
    context: AssetExecutionContext,
    impact_assessment: Dict[str, Any]
) -> Output[List[Dict[str, Any]]]:
    """
    Asset that generates documentation updates based on impact assessment.
    """
    # Generate documentation updates for each type of change
    prompt = f"""
    Based on this impact assessment, generate necessary documentation updates:
    
    {safe_json_dumps(impact_assessment, indent=2)}
    
    For each significant change, provide:
    1. Which documentation file needs updating
    2. The type of update (create new, update existing, add warning, etc.)
    3. The actual content to add/update
    4. Why this documentation change is needed
    
    Focus on:
    - API documentation for breaking changes
    - Architecture documentation for structural changes
    - Migration guides for breaking changes
    - Performance documentation for optimization changes
    - Security documentation for security-related changes
    """
    
    doc_result = execute_claude_code(prompt, {"impact": impact_assessment}, ClaudeCodeConfig())
    doc_data = json.loads(doc_result)
    
    updates = []
    for update in doc_data.get("updates", []):
        doc_update = DocumentationUpdate(
            file_path=update["file"],
            update_type=update.get("type", "update"),
            content=update["content"],
            reason=update.get("reason", "Code changes detected")
        )
        updates.append(doc_update.dict())
        
        # In production, actually write the documentation files
        write_documentation_file(doc_update)
    
    return Output(
        value=updates,
        metadata={
            "num_updates": len(updates),
            "update_types": list(set(u["update_type"] for u in updates))
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
    # Get list of all source files
    repo_path = Path(config.repo_path)
    source_files = list(repo_path.rglob("*.py")) + list(repo_path.rglob("*.js"))

    # respect .gitignore files
    gitignore_path = repo_path / ".gitignore"
    
    def gitignore_to_regex(pattern):
        """Convert gitignore pattern to regex pattern."""
        # Skip empty patterns
        if not pattern:
            return None
            
        # Escape special regex characters except for gitignore wildcards
        escaped = re.escape(pattern)
        
        # Convert gitignore patterns to regex
        # ** means match any number of directories
        escaped = escaped.replace(r'\*\*', '.*')
        # * means match any characters except /
        escaped = escaped.replace(r'\*', '[^/]*')
        # ? means match any single character except /
        escaped = escaped.replace(r'\?', '[^/]')
        
        # If pattern doesn't start with /, it can match anywhere in the path
        if not pattern.startswith('/'):
            escaped = '.*' + escaped
            
        # If pattern ends with /, it only matches directories
        if pattern.endswith('/'):
            escaped = escaped + '.*'
            
        return escaped
    
    if gitignore_path.exists():
        with open(gitignore_path, "r") as f:
            gitignore_lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        
        # Convert gitignore patterns to regex patterns
        gitignore_patterns = []
        for line in gitignore_lines:
            try:
                regex_pattern = gitignore_to_regex(line)
                if regex_pattern:
                    # Test if the regex is valid
                    re.compile(regex_pattern)
                    gitignore_patterns.append(regex_pattern)
            except re.error as e:
                context.log.warning(f"Invalid gitignore pattern '{line}': {e}")
                continue
        
        # Filter source files using gitignore patterns
        filtered_files = []
        for file_path in source_files:
            file_str = str(file_path.relative_to(repo_path))
            should_ignore = False
            
            for pattern in gitignore_patterns:
                try:
                    if re.search(pattern, file_str):
                        should_ignore = True
                        break
                except re.error as e:
                    context.log.warning(f"Error matching pattern '{pattern}' against '{file_str}': {e}")
                    continue
            
            if not should_ignore:
                filtered_files.append(file_path)
        
        source_files = filtered_files
        
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
    
    audit_result = execute_claude_code(prompt, {"files": [str(f) for f in source_files]}, ClaudeCodeConfig())
    audit_data = json.loads(audit_result)
    
    issues = []
    for issue in audit_data.get("issues", []):
        quality_issue = CodeQualityIssue(
            severity=issue["severity"],
            category=issue["category"],
            file_path=issue.get("file", ""),
            line_range=issue.get("line_range"),
            description=issue["description"],
            suggested_fix=issue.get("suggested_fix")
        )
        issues.append(quality_issue.dict())
    
    return Output(
        value=issues,
        metadata={
            "total_issues": len(issues),
            "critical_issues": len([i for i in issues if i["severity"] == "critical"]),
            "files_analyzed": len(source_files)
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
    prompt = f"""
    Build a comprehensive knowledge graph of the codebase:
    
    Repository: {config.repo_path}
    Recent changes: {safe_json_dumps(code_changes, indent=2)}
    Impact assessment: {safe_json_dumps(impact_assessment, indent=2)}
    
    Create a graph that includes:
    1. Modules and their relationships
    2. Service boundaries and interactions
    3. Data flow paths
    4. Key abstractions and their evolution
    5. Component dependencies
    6. API contracts between components
    
    For each node, provide:
    - Unique ID
    - Type (module/class/function/service)
    - Name and description
    - Dependencies (what it depends on)
    - Dependents (what depends on it)
    - Metadata (version, last modified, complexity metrics)
    
    Also identify:
    - Circular dependencies
    - Highly coupled components
    - Central points of failure
    - Opportunities for decoupling
    """
    
    graph_result = execute_claude_code(prompt, {
        "changes": code_changes,
        "impact": impact_assessment
    }, ClaudeCodeConfig())
    graph_data = json.loads(graph_result)
    
    # Build the knowledge graph
    nodes = []
    edges = []
    
    for node_data in graph_data.get("nodes", []):
        node = KnowledgeGraphNode(
            id=node_data["id"],
            type=node_data["type"],
            name=node_data.get("name", node_data["id"]),
            dependencies=node_data.get("dependencies", []),
            dependents=node_data.get("dependents", []),
            metadata=node_data.get("metadata", {})
        )
        nodes.append(node.dict())
        
        # Create edges for visualization
        for dep in node.dependencies:
            edges.append({
                "from": node.id,
                "to": dep,
                "type": "depends_on"
            })
    
    knowledge_graph = {
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "circular_dependencies": graph_data.get("circular_dependencies", []),
            "coupling_issues": graph_data.get("coupling_issues", [])
        }
    }
    
    return Output(
        value=knowledge_graph,
        metadata={
            "num_nodes": len(nodes),
            "num_edges": len(edges),
            "has_circular_deps": len(knowledge_graph["metadata"]["circular_dependencies"]) > 0
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
