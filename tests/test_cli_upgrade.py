from __future__ import annotations

import sys

from click.testing import CliRunner

from homely import cli


def test_upgrade_without_permission_says_to_use_sudo(monkeypatch):
    monkeypatch.setattr(cli.os, "access", lambda path, mode: False)
    result = CliRunner().invoke(cli.main, ["upgrade"])
    assert result.exit_code != 0
    assert "sudo homely upgrade" in result.output and sys.prefix in result.output


def test_link_onto_path(tmp_path):
    target = tmp_path / "venv" / "bin" / "homely"
    target.parent.mkdir(parents=True)
    target.write_text("#!/bin/sh\n")
    link = tmp_path / "usr-local-bin" / "homely"
    link.parent.mkdir()
    cli._link_onto_path(target, link)
    assert link.is_symlink() and link.resolve() == target.resolve()
    other = tmp_path / "other"
    other.write_text("")
    cli._link_onto_path(other, link)  # an existing link is left alone
    assert link.resolve() == target.resolve()
    cli._link_onto_path(tmp_path / "missing", tmp_path / "usr-local-bin" / "nope")
    assert not (tmp_path / "usr-local-bin" / "nope").exists()
