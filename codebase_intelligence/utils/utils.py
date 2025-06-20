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


class DocumentationManager:
    """Manages documentation generation and updates."""
    
    def __init__(self, docs_root: Path):
        self.docs_root = Path(docs_root)
        self.docs_root.mkdir(exist_ok=True)
    
    def write_documentation(
        self, 
        file_path: str, 
        content: str, 
        update_type: str = "update"
    ) -> bool:
        """Write documentation to file."""
        full_path = self.docs_root / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        if update_type == "create" and full_path.exists():
            # Backup existing file
            backup_path = full_path.with_suffix(f".{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak")
            full_path.rename(backup_path)
        
        full_path.write_text(content)
        return True
    
    def generate_index(self) -> str:
        """Generate an index of all documentation."""
        index_content = "# Documentation Index\n\n"
        
        for doc_file in sorted(self.docs_root.rglob("*.md")):
            if doc_file.name == "index.md":
                continue
            
            rel_path = doc_file.relative_to(self.docs_root)
            index_content += f"- [{doc_file.stem}]({rel_path})\n"
        
        return index_content


class KnowledgeGraphStore:
    """Stores and manages the codebase knowledge graph."""
    
    def __init__(self, store_path: Path):
        self.store_path = Path(store_path)
        self.store_path.mkdir(exist_ok=True)
        self.graph_file = self.store_path / "knowledge_graph.json"
    
    def save_graph(self, graph_data: Dict[str, Any]) -> None:
        """Save the knowledge graph to storage."""
        # Add version and timestamp
        graph_data["version"] = self._get_next_version()
        graph_data["timestamp"] = datetime.now().isoformat()
        
        # Save current version
        self.graph_file.write_text(json.dumps(graph_data, indent=2))
        
        # Archive previous version
        archive_file = self.store_path / f"graph_v{graph_data['version']}.json"
        archive_file.write_text(json.dumps(graph_data, indent=2))
    
    def load_graph(self) -> Optional[Dict[str, Any]]:
        """Load the current knowledge graph."""
        if self.graph_file.exists():
            return json.loads(self.graph_file.read_text())
        return None
    
    def get_graph_diff(self, old_version: int, new_version: int) -> Dict[str, Any]:
        """Get differences between two graph versions."""
        old_file = self.store_path / f"graph_v{old_version}.json"
        new_file = self.store_path / f"graph_v{new_version}.json"
        
        if not old_file.exists() or not new_file.exists():
            return {"error": "Version not found"}
        
        old_graph = json.loads(old_file.read_text())
        new_graph = json.loads(new_file.read_text())
        
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
    
    def get_file_metrics(self, file_path: Path) -> Dict[str, Any]:
        """Get metrics for a specific file."""
        if not file_path.exists():
            return {}
        
        content = file_path.read_text()
        lines = content.splitlines()
        
        return {
            "lines_of_code": len(lines),
            "blank_lines": len([l for l in lines if not l.strip()]),
            "comment_lines": self._count_comment_lines(lines, file_path.suffix),
            "file_size": file_path.stat().st_size,
            "last_modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
        }
    
    def _count_comment_lines(self, lines: List[str], suffix: str) -> int:
        """Count comment lines based on file type."""
        count = 0
        in_multiline = False
        
        for line in lines:
            line = line.strip()
            
            if suffix in ['.py']:
                if line.startswith('"""') or line.startswith("'''"):
                    in_multiline = not in_multiline
                    count += 1
                elif in_multiline or line.startswith('#'):
                    count += 1
            
            elif suffix in ['.js', '.ts']:
                if line.startswith('/*'):
                    in_multiline = True
                if in_multiline:
                    count += 1
                if line.endswith('*/'):
                    in_multiline = False
                elif line.startswith('//'):
                    count += 1
        
        return count
    
    def find_dependencies(self, file_path: Path) -> List[str]:
        """Find dependencies for a given file."""
        dependencies = []
        
        if not file_path.exists():
            return dependencies
        
        content = file_path.read_text()
        
        if file_path.suffix == '.py':
            # Find Python imports
            import_lines = [
                l for l in content.splitlines() 
                if l.strip().startswith(('import ', 'from '))
            ]
            for line in import_lines:
                if line.startswith('import '):
                    module = line.split()[1].split('.')[0]
                    dependencies.append(module)
                elif line.startswith('from '):
                    module = line.split()[1].split('.')[0]
                    dependencies.append(module)
        
        elif file_path.suffix in ['.js', '.ts']:
            # Find JavaScript/TypeScript imports
            import_lines = [
                l for l in content.splitlines()
                if 'import' in l and ('from' in l or 'require(' in l)
            ]
            # Simplified parsing - in production use proper AST parsing
            dependencies.extend(['parsed_js_dependency'])
        
        return list(set(dependencies))
