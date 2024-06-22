import os

import pytest

from aiidalab.fetch import GitRepo, fetch_from_url

pytestmark = pytest.mark.registry


def test_get_all_tagged_releases():
    """Test that all tagged releases are returned."""
    from aiidalab.registry.releases import _get_release_commits, _split_release_line

    url = "git+https://github.com/aiidalab/aiidalab-qe.git@*:v23.04.0^.."
    base_url, release_line = _split_release_line(url)

    with fetch_from_url(base_url) as repo_path:
        repo = GitRepo(os.fspath(repo_path))
        releases = [tag for tag, _ in _get_release_commits(repo, release_line)]

    assert "v23.04.2" in releases


def test_get_releases_from_branch():
    """Test that all tagged releases of perticular branch (main) are returned."""
    from aiidalab.registry.releases import _get_release_commits, _split_release_line

    url = "git+https://github.com/aiidalab/aiidalab-qe.git@main:v23.04.0^.."
    base_url, release_line = _split_release_line(url)

    with fetch_from_url(base_url) as repo_path:
        repo = GitRepo(os.fspath(repo_path))
        releases = [tag for tag, _ in _get_release_commits(repo, release_line)]

    assert "v23.04.2" not in releases
    assert "v23.04.0" in releases
