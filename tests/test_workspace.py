import os
from pathlib import Path

import pytest

from judgement_call.workspace import WorkspaceManager


def test_workspace_initialization_and_snapshot():
    wm = WorkspaceManager()
    try:
        assert wm.root.exists()
        assert wm._pristine_snapshot == {}
    finally:
        wm.cleanup()


def test_workspace_with_fixture(tmp_path):
    fix_dir = tmp_path / "fixture"
    fix_dir.mkdir()
    (fix_dir / "sample.txt").write_text("hello")

    wm = WorkspaceManager(fixture_src=str(fix_dir))
    try:
        assert (wm.root / "sample.txt").exists()
        assert (wm.root / "sample.txt").read_text() == "hello"
        assert "sample.txt" in wm._pristine_snapshot
        assert wm._pristine_snapshot["sample.txt"] == "hello"
    finally:
        wm.cleanup()


def test_path_traversal_rejection():
    wm = WorkspaceManager()
    try:
        with pytest.raises(ValueError, match="Path traversal or escape denied"):
            wm.resolve_path("../outside.txt")
        with pytest.raises(ValueError, match="Path traversal or escape denied"):
            wm.resolve_path("/etc/passwd")
    finally:
        wm.cleanup()


def test_symlink_escape_denial():
    wm = WorkspaceManager()
    try:
        # Create an allowed file inside workspace and a symlink pointing outside
        outside_file = wm.root.parent / "outside_secret.txt"
        outside_file.write_text("secret")

        symlink_path = wm.root / "bad_link.txt"
        try:
            os.symlink(outside_file, symlink_path)
        except OSError:
            pytest.skip("Symlinks not supported in environment")

        with pytest.raises(ValueError, match="Symlink escape denied"):
            wm.resolve_path("bad_link.txt")

        if outside_file.exists():
            outside_file.unlink()
    finally:
        wm.cleanup()


def test_allowed_path_enforcement():
    wm = WorkspaceManager()
    try:
        allowed = ["src/allowed.py"]
        # Valid write
        valid_path = wm.validate_allowed_path("src/allowed.py", allowed)
        assert valid_path.relative_to(wm.root) == Path("src/allowed.py")

        # Invalid write not in allowed paths
        with pytest.raises(ValueError, match="Path not allowed by task contract"):
            wm.validate_allowed_path("src/forbidden.py", allowed)
    finally:
        wm.cleanup()


def test_diff_generation(tmp_path):
    fix_dir = tmp_path / "fixture"
    fix_dir.mkdir()
    (fix_dir / "file.txt").write_text("line1\n")

    wm = WorkspaceManager(fixture_src=str(fix_dir))
    try:
        # Modify file
        (wm.root / "file.txt").write_text("line1\nline2\n")
        diff = wm.compute_diff()
        assert "+line2" in diff
    finally:
        wm.cleanup()
