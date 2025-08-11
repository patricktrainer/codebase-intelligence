# codebase_intelligence/utils.py
"""
Utility functions for the Codebase Intelligence System.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
import hashlib
from datetime import datetime
import yaml
import git
import re
import uuid
import logging


class DocumentationManager:
    """Manages documentation generation and updates."""
    
    def __init__(self, docs_root: Path):
        self.docs_root = Path(docs_root).resolve()  # Resolve to absolute path
        self.docs_root.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
    
    def write_documentation(
        self, 
        file_path: str, 
        content: str, 
        update_type: str = "update"
    ) -> bool:
        """Write documentation to file."""
        try:
            # Sanitize file path to prevent directory traversal
            sanitized_path = Path(file_path).name if "/" in file_path or "\\" in file_path else file_path
            full_path = (self.docs_root / sanitized_path).resolve()
            
            # Ensure the resolved path is still within docs_root
            if not str(full_path).startswith(str(self.docs_root)):
                raise ValueError(f"Path {file_path} would escape docs directory")
            
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            if update_type == "create" and full_path.exists():
                # Backup existing file with unique timestamp
                backup_suffix = f".{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.bak"
                backup_path = full_path.with_suffix(backup_suffix)
                full_path.rename(backup_path)
                self.logger.info(f"Backed up existing file to {backup_path}")
            
            full_path.write_text(content, encoding='utf-8')
            self.logger.info(f"Successfully wrote documentation to {full_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to write documentation to {file_path}: {e}")
            return False
    
    def generate_index(self) -> str:
        """Generate an index of all documentation."""
        try:
            index_content = "# Documentation Index\n\n"
            
            for doc_file in sorted(self.docs_root.rglob("*.md")):
                if doc_file.name == "index.md":
                    continue
                
                try:
                    rel_path = doc_file.relative_to(self.docs_root)
                    # Escape special characters in filename for markdown
                    safe_name = doc_file.stem.replace("[", "\\[").replace("]", "\\]")
                    index_content += f"- [{safe_name}]({rel_path})\n"
                except ValueError as e:
                    self.logger.warning(f"Skipping file outside docs root: {doc_file}")
                    continue
            
            return index_content
            
        except Exception as e:
            self.logger.error(f"Failed to generate documentation index: {e}")
            return "# Documentation Index\n\nError generating index."


class KnowledgeGraphStore:
    """Stores and manages the codebase knowledge graph."""
    
    def __init__(self, store_path: Path):
        self.store_path = Path(store_path)
        self.store_path.mkdir(exist_ok=True)
        self.graph_file = self.store_path / "knowledge_graph.json"
    
    def save_graph(self, graph_data: Dict[str, Any]) -> None:
        """Save the knowledge graph to storage."""
        try:
            # Add version and timestamp
            graph_data["version"] = self._get_next_version()
            graph_data["timestamp"] = datetime.now().isoformat()
            
            json_content = json.dumps(graph_data, indent=2)
            
            # Save current version
            self.graph_file.write_text(json_content, encoding='utf-8')
            
            # Archive previous version
            archive_file = self.store_path / f"graph_v{graph_data['version']}.json"
            archive_file.write_text(json_content, encoding='utf-8')
            
            logging.getLogger(__name__).info(f"Saved knowledge graph version {graph_data['version']}")
            
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to save knowledge graph: {e}")
            raise
    
    def load_graph(self) -> Optional[Dict[str, Any]]:
        """Load the current knowledge graph."""
        try:
            if self.graph_file.exists():
                return json.loads(self.graph_file.read_text(encoding='utf-8'))
            return None
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to load knowledge graph: {e}")
            return None
    
    def get_graph_diff(self, old_version: int, new_version: int) -> Dict[str, Any]:
        """Get differences between two graph versions."""
        old_file = self.store_path / f"graph_v{old_version}.json"
        new_file = self.store_path / f"graph_v{new_version}.json"
        
        try:
            if not old_file.exists() or not new_file.exists():
                return {"error": "Version not found"}
            
            old_graph = json.loads(old_file.read_text(encoding='utf-8'))
            new_graph = json.loads(new_file.read_text(encoding='utf-8'))
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to load graph versions: {e}")
            return {"error": f"Failed to load versions: {str(e)}"}
        
        # Calculate differences
        old_nodes = {n["id"]: n for n in old_graph.get("nodes", [])}
        new_nodes = {n["id"]: n for n in new_graph.get("nodes", [])}
        
        added_nodes = [n for n_id, n in new_nodes.items() if n_id not in old_nodes]
        removed_nodes = [n for n_id, n in old_nodes.items() if n_id not in new_nodes]
        modified_nodes = [
            n for n_id, n in new_nodes.items() 
            if n_id in old_nodes and n != old_nodes[n_id]
        ]
        
        return {
            "added_nodes": added_nodes,
            "removed_nodes": removed_nodes,
            "modified_nodes": modified_nodes,
            "total_changes": len(added_nodes) + len(removed_nodes) + len(modified_nodes)
        }
    
    def _get_next_version(self) -> int:
        """Get the next version number."""
        versions = []
        for f in self.store_path.glob("graph_v*.json"):
            try:
                version = int(f.stem.split("_v")[1])
                versions.append(version)
            except:
                continue
        
        return max(versions, default=0) + 1


class CodebaseAnalyzer:
    """Analyzes codebase structure and metrics."""
    
    def __init__(self, repo_path: Path):
        self.repo_path = Path(repo_path)
        self.repo = git.Repo(repo_path)
    
    def _gitignore_to_regex(self, pattern: str) -> Optional[str]:
        """Convert gitignore pattern to regex pattern."""
        if not pattern:
            return None
        escaped = re.escape(pattern)
        escaped = escaped.replace(r'\*\*', '.*')
        escaped = escaped.replace(r'\*', '[^/]*')
        escaped = escaped.replace(r'\?', '[^/]')
        if not pattern.startswith('/'):
            escaped = '.*' + escaped
        if pattern.endswith('/'):
            escaped = escaped + '.*'
        return escaped

    def get_source_files(self) -> List[Path]:
        """Get all source files in the repository, respecting .gitignore."""
        source_files = list(self.repo_path.rglob("*.py")) + list(self.repo_path.rglob("*.js"))
        
        gitignore_path = self.repo_path / ".gitignore"
        if gitignore_path.exists():
            with open(gitignore_path, "r") as f:
                gitignore_lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            
            gitignore_patterns = []
            for line in gitignore_lines:
                try:
                    regex_pattern = self._gitignore_to_regex(line)
                    if regex_pattern:
                        re.compile(regex_pattern)
                        gitignore_patterns.append(regex_pattern)
                except re.error:
                    continue
            
            filtered_files = []
            for file_path in source_files:
                file_str = str(file_path.relative_to(self.repo_path))
                should_ignore = False
                for pattern in gitignore_patterns:
                    try:
                        if re.search(pattern, file_str):
                            should_ignore = True
                            break
                    except re.error:
                        continue
                if not should_ignore:
                    filtered_files.append(file_path)
            source_files = filtered_files
            
        return source_files

    def get_file_metrics(self, file_path: Path) -> Dict[str, Any]:
        """Get metrics for a specific file."""
        try:
            if not file_path.exists():
                return {}
            
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            lines = content.splitlines()
            
            return {
                "lines_of_code": len(lines),
                "blank_lines": len([l for l in lines if not l.strip()]),
                "comment_lines": self._count_comment_lines(lines, file_path.suffix),
                "file_size": file_path.stat().st_size,
                "last_modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
            }
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to get metrics for {file_path}: {e}")
            return {}
    
    def _count_comment_lines(self, lines: List[str], suffix: str) -> int:
        """Count comment lines based on file type."""
        count = 0
        in_multiline = False
        
        for line in lines:
            stripped = line.strip()
            
            if suffix in ['.py']:
                # Handle Python docstrings and comments
                if '"""' in stripped or "'''" in stripped:
                    # Count quotes in line
                    quote_count = stripped.count('"""') + stripped.count("'''")
                    if quote_count % 2 == 1:  # Odd number means toggle
                        in_multiline = not in_multiline
                    count += 1
                elif in_multiline or stripped.startswith('#'):
                    count += 1
            
            elif suffix in ['.js', '.ts']:
                # Handle JavaScript/TypeScript comments
                if '/*' in stripped:
                    in_multiline = True
                if in_multiline:
                    count += 1
                if '*/' in stripped:
                    in_multiline = False
                elif stripped.startswith('//'):
                    count += 1
        
        return count
    
    def find_dependencies(self, file_path: Path) -> List[str]:
        """Find dependencies for a given file."""
        dependencies = []
        
        try:
            if not file_path.exists():
                return dependencies
            
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            
            if file_path.suffix == '.py':
                # Find Python imports using regex for better parsing
                import_patterns = [
                    r'^\s*import\s+([a-zA-Z_][\w\.]*)',
                    r'^\s*from\s+([a-zA-Z_][\w\.]*)\s+import'
                ]
                
                for line in content.splitlines():
                    line = line.strip()
                    if line.startswith(('import ', 'from ')) and not line.startswith('#'):
                        for pattern in import_patterns:
                            match = re.match(pattern, line)
                            if match:
                                module = match.group(1).split('.')[0]
                                dependencies.append(module)
                                break
            
            elif file_path.suffix in ['.js', '.ts']:
                # Find JavaScript/TypeScript imports with regex
                import_patterns = [
                    r'import.*from\s+["\']([^"\']*)["\']',
                    r'require\(["\']([^"\']*)["\']',
                    r'import\s*\(\s*["\']([^"\']*)["\']'
                ]
                
                for pattern in import_patterns:
                    matches = re.findall(pattern, content)
                    for match in matches:
                        # Extract module name from path
                        module = match.split('/')[0] if '/' in match else match
                        if module and not module.startswith('.'):
                            dependencies.append(module)
            
            return list(set(dependencies))
            
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to find dependencies for {file_path}: {e}")
            return []
