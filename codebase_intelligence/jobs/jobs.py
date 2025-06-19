# codebase_intelligence/jobs.py
"""
Job definitions for the Codebase Intelligence System.
"""

from dagster import (
    job,
    op,
    In,
    Out,
    DynamicOut,
    DynamicOutput,
    OpExecutionContext,
    DagsterType,
    Config,
    AssetSelection,
    define_asset_job,
    AssetKey,
)


# Define asset jobs
continuous_analysis_job = define_asset_job(
    name="continuous_analysis",
    selection=AssetSelection.assets(
        "code_changes",
        "impact_assessment",
        "documentation_updates",
        "codebase_knowledge_graph",
    ),
    description="Continuous analysis pipeline triggered by code changes",
)

quality_audit_job = define_asset_job(
    name="quality_audit_job",
    selection=AssetSelection.assets("code_quality_audit"),
    description="Scheduled code quality audit job",
)

full_analysis_job = define_asset_job(
    name="full_analysis",
    selection=AssetSelection.all(),
    description="Complete analysis of the codebase",
)
