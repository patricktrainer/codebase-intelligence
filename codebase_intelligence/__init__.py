# codebase_intelligence/__init__.py
"""
Codebase Intelligence System - A Dagster-based orchestration system for
automated code analysis and documentation using Claude Code.
"""

from dagster import Definitions

from codebase_intelligence.logging_config import setup_logging
from codebase_intelligence.jobs.jobs import continuous_analysis_job, quality_audit_job, full_analysis_job
from codebase_intelligence.assets.assets import defs

# Initialize centralized logging
setup_logging() 


defs = Definitions(
    assets=defs.assets,
    jobs=[
        continuous_analysis_job,
        quality_audit_job,
        full_analysis_job
    ],
    resources=defs.resources,
    schedules=defs.schedules,
    sensors=defs.sensors
)
 