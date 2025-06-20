# codebase_intelligence/claude_integration.py
"""
Claude Code integration utilities.
"""
from re import L, sub
import dagster

import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import subprocess
import tempfile
from pathlib import Path
import re


LOGGER = dagster.get_dagster_logger()


@dataclass
class ClaudeCodeResult:
    """Result from Claude Code execution."""
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ClaudeCodeClient:
    """
    Client for interacting with Claude Code.
    
    In production, this would use the actual Claude Code API.
    For now, it provides a mock implementation that simulates the behavior.
    """
    
    def __init__(self, api_key: str, timeout: int = 300):
        self.api_key = api_key
        self.timeout = timeout
        self._validate_setup()
    
    def _validate_setup(self):
        """Validate that Claude Code is properly set up."""
        # In production, check if claude-code CLI is available
        # For now, just log
        LOGGER.info("Claude Code client initialized")
    
    async def execute_async(
        self, 
        prompt: str, 
        context: Dict[str, Any],
        workspace_path: Optional[Path] = None
    ) -> ClaudeCodeResult:
        """
        Execute Claude Code asynchronously.
        
        Args:
            prompt: The prompt to send to Claude Code
            context: Additional context for the execution
            workspace_path: Path to the workspace for code execution
            
        Returns:
            ClaudeCodeResult with the execution results
        """
        try:
            # Set working directory to the workspace path if provided, otherwise current directory
            cwd = str(workspace_path) if workspace_path else "."
            
            cmd = [
                "claude",
                '--model', 'claude-sonnet-4-20250514', 
                '--output-format', 'json',
                # '--allowedTools', 'Write', # TODO: This doesnt work... errors with a timeout
                prompt
            ]

            LOGGER.info(f"Executing Claude Code with command: {' '.join(cmd)}")
            LOGGER.info(f"Working directory: {cwd}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                # cwd=cwd  # Set working directory
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout)
            
            if process.returncode != 0:
                error_msg = stderr.decode()
                LOGGER.error(f"Claude CLI tool failed with stderr: {error_msg}")
                return ClaudeCodeResult(success=False, error=error_msg)

            output = stdout.decode()
            LOGGER.info(f"Raw Claude Code output: {output}")

            # The output can be a stream of JSON objects, we are interested in the last one
            # that is of type 'result'.
            last_result_obj = None
            for line in output.strip().split('\n'):
                if line.strip():
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict) and obj.get("type") == "result":
                            last_result_obj = obj
                    except json.JSONDecodeError:
                        LOGGER.warning(f"Could not decode JSON line from Claude output: {line}")
                        continue
            
            if not last_result_obj:
                # If no result object found, but we have output, treat the full output as the result
                if output.strip():
                    return ClaudeCodeResult(success=True, output=output.strip())
                else:
                    return ClaudeCodeResult(success=False, error="No 'result' type object found in Claude output.", output=output)

            if last_result_obj.get("is_error"):
                return ClaudeCodeResult(success=False, error=last_result_obj.get("result", "Unknown error"))

            # The actual content is in the 'result' field of this last object
            final_output = last_result_obj.get("result", "{}")

            # This result can be a JSON string wrapped in markdown, clean it up.
            if "```json" in final_output:
                match = re.search(r"```json\n(.*?)\n```", final_output, re.DOTALL)
                if match:
                    final_output = match.group(1)
                else: # Fallback for slightly different formats
                    final_output = final_output.replace("```json", "").replace("```", "").strip()

            return ClaudeCodeResult(
                success=True,
                output=final_output,
                metadata={"execution_time": 0.5} # mock
            )
            
        except asyncio.TimeoutError:
            LOGGER.error("Claude Code execution timed out.")
            return ClaudeCodeResult(success=False, error="Timeout")
        except Exception as e:
            LOGGER.error(f"Claude Code execution failed: {e}")
            return ClaudeCodeResult(
                success=False,
                error=str(e)
            )
    
    def execute(
        self, 
        prompt: str, 
        context: Dict[str, Any],
        workspace_path: Optional[Path] = None
    ) -> ClaudeCodeResult:
        """Synchronous wrapper for execute_async."""
        return asyncio.run(self.execute_async(prompt, context, workspace_path))
