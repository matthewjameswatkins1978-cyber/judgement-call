import importlib.util
import inspect
import subprocess
import sys
from pathlib import Path

from judgement_call.contracts import TaskContract
from judgement_call.workspace import WorkspaceManager


class IndependentVerifier:
    def __init__(
        self, workspace: WorkspaceManager, contract: TaskContract
    ) -> None:
        self.workspace = workspace
        self.contract = contract

    def verify(self) -> tuple[bool, str]:
        """Independent deterministic verifier checking edits and tests."""
        current_files: dict[str, str] = {}
        for path in self.workspace.root.glob("**/*"):
            if path.is_file():
                rel = path.relative_to(self.workspace.root)
                if any(part.startswith(".git") for part in rel.parts):
                    continue
                try:
                    content = path.read_text(encoding="utf-8")
                except Exception:
                    content = ""
                current_files[str(rel)] = content

        edited_paths = []
        for p, new_content in current_files.items():
            old_content = self.workspace._pristine_snapshot.get(p, "")
            if old_content != new_content:
                edited_paths.append(p)

        allowed_normalized = {
            str(Path(ap)) for ap in self.contract.allowed_paths
        }
        for ep in edited_paths:
            if ep not in allowed_normalized and Path(ep) not in [
                Path(ap) for ap in self.contract.allowed_paths
            ]:
                return (
                    False,
                    f"Verification failed: edited path '{ep}' is not in "
                    f"allowed_paths ({self.contract.allowed_paths})",
                )

        cmd = self.contract.acceptance_command.split()
        if cmd and cmd[0] in ("python", "python3"):
            venv_python = self.workspace.root / ".venv" / "bin" / "python"
            if venv_python.exists():
                cmd[0] = str(venv_python)
            else:
                cmd[0] = sys.executable
        try:
            res = subprocess.run(
                cmd,
                cwd=str(self.workspace.root),
                capture_output=True,
                text=True,
                timeout=60,
            )
            if res.returncode != 0:
                return (
                    False,
                    f"Verification failed: tests failed with exit code "
                    f"{res.returncode}\nStdout:\n{res.stdout}\n"
                    f"Stderr:\n{res.stderr}",
                )
        except Exception as e:
            return False, f"Verification failed: exception running tests: {e}"

        processor_path = (
            self.workspace.root / "src" / "demoqueue" / "processor.py"
        )
        if processor_path.exists():
            try:
                spec = importlib.util.spec_from_file_location(
                    "demoqueue.processor", str(processor_path)
                )
                mod = importlib.util.module_from_spec(spec)
                assert spec and spec.loader
                spec.loader.exec_module(mod)
                if hasattr(mod, "process_items"):
                    sig = inspect.signature(mod.process_items)
                    param_names = list(sig.parameters.keys())
                    if param_names != ["items", "worker"]:
                        return (
                            False,
                            f"Verification failed: public signature changed "
                            f"to {param_names}, expected ['items', 'worker']",
                        )

                    test_items = [3, 1, 2]
                    test_res = mod.process_items(
                        test_items, lambda x: x * 2
                    )
                    if test_res != [6, 2, 4]:
                        return (
                            False,
                            f"Verification failed: result order not "
                            f"preserved, got {test_res}, expected [6, 2, 4]",
                        )
            except Exception as e:
                return (
                    False,
                    f"Verification failed during signature/order inspection: {e}",
                )

        return True, "Verification passed successfully."
