"""Keep the vendored WanFlow UI copy and its source fork in lockstep.

``plugins/wan2gp-wanflow-ui`` is tracked in this repository (a .gitignore
negation) while also being a live git fork with its own history. Two copies
of the truth can drift apart: a commit made only in the fork leaves the
repo's vendored snapshot behind, and an unsynced vendoring edit dirties the
fork. Both directions must fail loudly; see that folder's RECONCILIATION.md.
"""
import os
import subprocess

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PLUGINS_ROOT = os.path.dirname(PLUGIN_DIR)
REPO_ROOT = os.path.dirname(PLUGINS_ROOT)

FORK_DIR = os.path.join(PLUGINS_ROOT, "wan2gp-wanflow-ui")
VENDORED_PATH = "plugins/wan2gp-wanflow-ui"


def _git(repo_cwd, *args):
    result = subprocess.run(
        ["git", *args], cwd=repo_cwd, capture_output=True, text=True, timeout=60, check=False
    )
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {(result.stderr or result.stdout).strip()[:300]}")
    return result.stdout.strip()


def test_vendored_wanflow_matches_fork_head():
    if not os.path.isdir(os.path.join(FORK_DIR, ".git")):
        pytest.skip("checkout without the fork's git history (CI vendored-only clone)")

    # 1. The fork's working tree must be committed: uncommitted edits here
    #    would make "fork HEAD" and the files this repo tracks two different
    #    truths.
    dirty = _git(FORK_DIR, "status", "--porcelain", "--untracked-files=no")
    assert not dirty, (
        "wan2gp-wanflow-ui fork has uncommitted changes; commit them in the "
        "fork repository first, then sync the vendored copy:\n" + dirty[:800]
    )

    # 2. The vendoring commit in this repository must match the fork HEAD.
    #    Both snapshots cover exactly the fork's tracked files; runtime files
    #    (user workflows, caches) are ignored on both sides.
    stale = _git(REPO_ROOT, "status", "--porcelain", "--untracked-files=no", "--", VENDORED_PATH)
    assert not stale, (
        "the vendored wan2gp-wanflow-ui snapshot diverged from the fork HEAD; "
        "commit the current files in this repository to re-sync:\n" + stale[:800]
    )
