import difflib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional


class WorkspaceManager:
    def __init__(
        self,
        base_dir: Optional[str] = None,
        fixture_src: Optional[str] = None,
    ) -> None:
        if base_dir:
            self.root = Path(base_dir).resolve()
            self.root.mkdir(parents=True, exist_ok=True)
            self._temp_dir = None
        else:
            self._temp_dir = tempfile.TemporaryDirectory(
                prefix="judgement_workspace_"
            )
            self.root = Path(self._temp_dir.name).resolve()

        if fixture_src and Path(fixture_src).exists():
            src_path = Path(fixture_src).resolve()
            for item in src_path.iterdir():
                dest = self.root / item.name
                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)

        self._pristine_snapshot: dict[str, str] = {}
        self._capture_pristine_snapshot()

    def _capture_pristine_snapshot(self) -> None:
        self._pristine_snapshot.clear()
        for path in self.root.glob("**/*"):
            if path.is_file():
                rel = path.relative_to(self.root)
                if any(part.startswith(".git") for part in rel.parts):
                    continue
                try:
                    content = path.read_text(encoding="utf-8")
                except Exception:
                    content = ""
                self._pristine_snapshot[str(rel)] = content

    def resolve_path(self, path_str: str) -> Path:
        """Resolve path within workspace root, rejecting traversal/symlink escape."""
        if os.path.isabs(path_str):
            abs_path = Path(path_str)
        else:
            abs_path = self.root / path_str

        rel_parts = []
        try:
            if abs_path.is_absolute() and abs_path.is_relative_to(self.root):
                rel_parts = abs_path.relative_to(self.root).parts
            elif not abs_path.is_absolute():
                rel_parts = Path(path_str).parts
        except Exception:
            pass

        curr_check = self.root
        for part in rel_parts:
            if part == "..":
                raise ValueError(
                    f"Path traversal or escape denied: {path_str}"
                )
            curr_check = curr_check / part
            if curr_check.is_symlink():
                resolved_symlink = curr_check.resolve(strict=False)
                try:
                    resolved_symlink.relative_to(self.root)
                except ValueError:
                    raise ValueError(
                        f"Symlink escape denied: {curr_check} -> "
                        f"{resolved_symlink}"
                    )

        try:
            canonical = abs_path.resolve(strict=False)
        except Exception as e:
            raise ValueError(f"Invalid path resolution for {path_str}: {e}")

        try:
            canonical.relative_to(self.root)
        except ValueError:
            raise ValueError(f"Path traversal or escape denied: {path_str}")

        return canonical

    def validate_allowed_path(
        self, path_str: str, allowed_paths: list[str]
    ) -> Path:
        canonical = self.resolve_path(path_str)
        rel = canonical.relative_to(self.root)
        rel_str = str(rel)

        allowed = False
        for ap in allowed_paths:
            ap_norm = str(Path(ap))
            if (
                rel_str == ap_norm
                or rel_str == ap
                or Path(rel_str) == Path(ap)
            ):
                allowed = True
                break
        if not allowed:
            raise ValueError(
                f"Path not allowed by task contract: {path_str} "
                f"(resolved as {rel_str})"
            )
        return canonical

    def compute_diff(self) -> str:
        """Compute unified diff against pristine snapshot."""
        current_files: dict[str, str] = {}
        for path in self.root.glob("**/*"):
            if path.is_file():
                rel = path.relative_to(self.root)
                if any(part.startswith(".git") for part in rel.parts):
                    continue
                try:
                    content = path.read_text(encoding="utf-8")
                except Exception:
                    content = ""
                current_files[str(rel)] = content

        all_paths = sorted(
            set(
                list(self._pristine_snapshot.keys())
                + list(current_files.keys())
            )
        )
        diff_lines = []

        for p in all_paths:
            old_content = self._pristine_snapshot.get(p, "")
            new_content = current_files.get(p, "")
            if old_content != new_content:
                old_lines = old_content.splitlines(keepends=True)
                new_lines = new_content.splitlines(keepends=True)
                diff = difflib.unified_diff(
                    old_lines,
                    new_lines,
                    fromfile=f"a/{p}",
                    tofile=f"b/{p}",
                )
                diff_lines.extend(list(diff))

        return "".join(diff_lines)

    def cleanup(self) -> None:
        if self._temp_dir:
            self._temp_dir.cleanup()
