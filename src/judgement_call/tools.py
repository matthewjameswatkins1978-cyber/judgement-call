import subprocess
from typing import Any, Callable

from strands import tool

from judgement_call.ledger import RunLedger
from judgement_call.workspace import WorkspaceManager


class ProductToolContext:
    def __init__(
        self,
        workspace: WorkspaceManager,
        ledger: RunLedger,
        allowed_paths: list[str],
        acceptance_command: str = "python -m pytest -q",
    ) -> None:
        self.workspace = workspace
        self.ledger = ledger
        self.allowed_paths = allowed_paths
        self.acceptance_command = acceptance_command


def create_product_tools(
    context: ProductToolContext,
) -> list[Callable[..., Any]]:
    @tool
    def list_tree(path: str = ".") -> str:
        """List files and directories in the workspace tree."""
        try:
            target = context.workspace.resolve_path(path)
            if not target.exists():
                return f"Path does not exist: {path}"

            lines = []
            for p in sorted(target.glob("**/*")):
                rel_p = p.relative_to(context.workspace.root)
                if any(
                    part.startswith(".git") for part in rel_p.parts
                ):
                    continue
                rel = p.relative_to(context.workspace.root)
                prefix = "DIR " if p.is_dir() else "FILE"
                lines.append(f"[{prefix}] {rel}")
            return "\n".join(lines) if lines else "(empty directory)"
        except Exception as e:
            return f"Error listing tree: {e}"

    @tool
    def read_text(path: str) -> str:
        """Read text content of a file within the workspace."""
        try:
            target = context.workspace.resolve_path(path)
            if not target.is_file():
                return f"Not a file: {path}"
            return target.read_text(encoding="utf-8")
        except Exception as e:
            return f"Error reading text: {e}"

    @tool
    def search_text(pattern: str, path: str = ".") -> str:
        """Search for a text pattern in files within the workspace."""
        try:
            target = context.workspace.resolve_path(path)
            matches = []
            import re
            regex = re.compile(pattern)

            search_files = [target] if target.is_file() else target.glob("**/*")
            for fp in search_files:
                if fp.is_file():
                    rel_fp = fp.relative_to(context.workspace.root)
                    if any(
                        part.startswith(".git") for part in rel_fp.parts
                    ):
                        continue
                    try:
                        content = fp.read_text(encoding="utf-8")
                        for i, line in enumerate(content.splitlines(), 1):
                            if regex.search(line):
                                rel = fp.relative_to(
                                    context.workspace.root
                                )
                                matches.append(f"{rel}:{i}: {line}")
                    except Exception:
                        pass
            return "\n".join(matches) if matches else "No matches found."
        except Exception as e:
            return f"Error searching text: {e}"

    @tool
    def write_text(path: str, content: str) -> str:
        """Write text content to a file, restricted to allowed paths."""
        try:
            target = context.workspace.validate_allowed_path(
                path, context.allowed_paths
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return f"Successfully wrote to {path}"
        except Exception as e:
            context.ledger.record_policy_denial()
            return f"Policy denied write: {e}"

    @tool
    def run_tests() -> str:
        """Run acceptance tests in the workspace using pytest."""
        context.ledger.record_test_run()
        try:
            cmd = context.acceptance_command.split()
            if cmd and cmd[0] in ("python", "python3"):
                venv_python = context.workspace.root / ".venv" / "bin" / "python"
                if venv_python.exists():
                    cmd[0] = str(venv_python)
                else:
                    import sys
                    cmd[0] = sys.executable
            result = subprocess.run(
                cmd,
                cwd=str(context.workspace.root),
                capture_output=True,
                text=True,
                timeout=60,
            )
            output = (
                f"Exit code: {result.returncode}\n"
                f"Stdout:\n{result.stdout}\n"
                f"Stderr:\n{result.stderr}"
            )
            return output
        except Exception as e:
            return f"Error running tests: {e}"

    @tool
    def request_decision(
        question: str,
        options: list[dict],
        recommendation: str,
        dimensions: list[str],
        impact: str,
        reversible: bool,
        evidence: str,
        constraint_key: str | None = None,
    ) -> str:
        """Request human decision or governor auto-resolution."""
        return recommendation

    return [
        list_tree,
        read_text,
        search_text,
        write_text,
        run_tests,
        request_decision,
    ]
