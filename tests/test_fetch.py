"""Tests for the aiidalab.fetch module."""

import io
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest
import requests

from aiidalab import fetch
from aiidalab.fetch import fetch_from_url
from aiidalab.git_util import GitPath, GitRepo, InvalidGitRefError

APP_FILES = {
    "app/setup.cfg": b"[metadata]\nname = test-app\n",
    "app/start.py": b"print('hello')\n",
}


def _make_tar(files, mode="w:gz", symlinks=None):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode=mode) as tar:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
        for name, target in (symlinks or {}).items():
            info = tarfile.TarInfo(name)
            info.type = tarfile.SYMTYPE
            info.linkname = target
            tar.addfile(info)
    return buffer.getvalue()


def _make_zip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        for name, content in files.items():
            zip_file.writestr(name, content)
    return buffer.getvalue()


def _git(*args, cwd):
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "tag.gpgsign=false",
            *args,
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def git_repo(tmp_path):
    """Local git repository with an app directory, an app archive and a tag."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    _git("init", "-b", "main", cwd=repo_path)
    for name, content in APP_FILES.items():
        (repo_path / name).parent.mkdir(parents=True, exist_ok=True)
        (repo_path / name).write_bytes(content)
    (repo_path / "app.tar.gz").write_bytes(_make_tar(APP_FILES))
    _git("add", ".", cwd=repo_path)
    _git("commit", "-m", "Initial commit", cwd=repo_path)
    _git("tag", "v1.0", cwd=repo_path)
    # Change the working tree after tagging, so that we can tell revisions apart.
    (repo_path / "app" / "start.py").write_bytes(b"print('changed')\n")
    _git("commit", "-am", "Change start.py", cwd=repo_path)
    return repo_path


class _FakeResponse:
    def __init__(self, content=b"", status_code=200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Error")


@pytest.fixture
def mock_https(monkeypatch):
    """Serve the given content for any https request, without network access."""

    def _mock_https(content=b"", status_code=200):
        requested_urls = []

        def fake_get(url, **kwargs):
            requested_urls.append(url)
            return _FakeResponse(content, status_code)

        monkeypatch.setattr(fetch.requests, "get", fake_get)
        return requested_urls

    return _mock_https


def _assert_app_files(path):
    for name, content in APP_FILES.items():
        assert (Path(path) / Path(name).name).read_bytes() == content


def test_public_api():
    assert fetch.__all__ == ["fetch_from_url"]


# Local file system


@pytest.mark.parametrize("scheme", ["", "file://"])
def test_fetch_local_directory(tmp_path, scheme):
    (tmp_path / "setup.cfg").write_text("[metadata]\n")
    with fetch_from_url(f"{scheme}{tmp_path}") as path:
        assert path == tmp_path
    # A local directory is used in place and must not be removed.
    assert (tmp_path / "setup.cfg").exists()


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("app.tar.gz", _make_tar(APP_FILES, mode="w:gz")),
        ("app.tar.bz2", _make_tar(APP_FILES, mode="w:bz2")),
        ("app.tar", _make_tar(APP_FILES, mode="w")),
        ("app.zip", _make_zip(APP_FILES)),
    ],
)
def test_fetch_local_archive(tmp_path, filename, content):
    archive = tmp_path / filename
    archive.write_bytes(content)
    with fetch_from_url(str(archive)) as path:
        # The only top-level directory of the archive is returned.
        assert path.name == "app"
        _assert_app_files(path)
    # The extracted files are cleaned up when the context exits.
    assert not path.exists()


@pytest.mark.parametrize("make_archive", [_make_tar, _make_zip])
def test_fetch_local_archive_multiple_toplevel_members(tmp_path, make_archive):
    archive = tmp_path / "archive"
    archive.write_bytes(make_archive({"a.txt": b"a", "b/c.txt": b"c"}))
    with fetch_from_url(f"file://{archive}") as path:
        assert sorted(p.name for p in path.iterdir()) == ["a.txt", "b"]


def test_fetch_local_invalid_archive(tmp_path):
    archive = tmp_path / "app.tar.gz"
    archive.write_bytes(b"This is not an archive.")
    with (
        pytest.raises(RuntimeError, match="Failed to extract archive"),
        fetch_from_url(str(archive)),
    ):
        pass


@pytest.mark.parametrize(
    ("files", "symlinks"),
    [
        pytest.param({"../evil.txt": b"evil"}, None, id="path-traversal"),
        pytest.param({}, {"app/link": "/etc/passwd"}, id="absolute-symlink"),
        pytest.param({}, {"app/link": "../../outside"}, id="relative-symlink"),
    ],
)
def test_fetch_local_unsafe_tar_archive(tmp_path, files, symlinks):
    archive = tmp_path / "evil.tar.gz"
    archive.write_bytes(_make_tar(files, symlinks=symlinks))
    with (
        pytest.raises(RuntimeError, match="Failed to extract archive"),
        fetch_from_url(str(archive)),
    ):
        pass


def test_fetch_local_tar_archive_absolute_member_path(tmp_path):
    # The "data" filter strips the leading slash and extracts into the destination.
    archive = tmp_path / "app.tar.gz"
    archive.write_bytes(_make_tar({"/app/start.py": b"print('hello')\n"}))
    with fetch_from_url(str(archive)) as path:
        assert (path / "start.py").read_bytes() == b"print('hello')\n"


def test_fetch_local_tar_archive_internal_symlink(tmp_path):
    archive = tmp_path / "app.tar.gz"
    archive.write_bytes(_make_tar(APP_FILES, symlinks={"app/main.py": "start.py"}))
    with fetch_from_url(str(archive)) as path:
        assert (path / "main.py").read_bytes() == APP_FILES["app/start.py"]


def test_fetch_local_nonexistent_path(tmp_path):
    with (
        pytest.raises(RuntimeError, match="No such file or directory"),
        fetch_from_url(str(tmp_path / "does-not-exist")),
    ):
        pass


def test_fetch_local_relative_path_hint():
    # The first component of a relative path after "file://" is parsed as netloc.
    with (
        pytest.raises(RuntimeError, match="Did you use a relative path?"),
        fetch_from_url("file://does-not-exist/app.tar.gz"),
    ):
        pass


# HTTPS


@pytest.mark.parametrize(
    "content", [_make_tar(APP_FILES), _make_zip(APP_FILES)], ids=["tar", "zip"]
)
def test_fetch_https_archive(mock_https, content):
    url = "https://example.com/app.tar.gz"
    requested_urls = mock_https(content)
    with fetch_from_url(url) as path:
        assert path.name == "app"
        _assert_app_files(path)
    assert requested_urls == [url]
    assert not path.exists()


def test_fetch_https_http_error(mock_https):
    mock_https(status_code=404)
    with (
        pytest.raises(requests.HTTPError, match="404"),
        fetch_from_url("https://example.com/app.tar.gz"),
    ):
        pass


def test_fetch_https_invalid_archive(mock_https):
    mock_https(b"<html>Not an archive</html>")
    with (
        pytest.raises(RuntimeError, match="Failed to extract archive"),
        fetch_from_url("https://example.com/app.tar.gz"),
    ):
        pass


def test_fetch_https_unsafe_archive(mock_https):
    mock_https(_make_tar({"../evil.txt": b"evil"}))
    with (
        pytest.raises(RuntimeError, match="outside the destination"),
        fetch_from_url("https://example.com/app.tar.gz"),
    ):
        pass


# Git


def test_fetch_git_local_directory(git_repo):
    with fetch_from_url(f"git+file://{git_repo}#app") as path:
        assert isinstance(path, GitPath)
        assert path.is_dir()
        assert path.joinpath("start.py").read_bytes() == b"print('changed')\n"  # HEAD


def test_fetch_git_local_tag(git_repo):
    with fetch_from_url(f"git+file://{git_repo}@v1.0#app") as path:
        assert path.joinpath("start.py").read_bytes() == APP_FILES["app/start.py"]


def test_fetch_git_local_branch(git_repo):
    with fetch_from_url(f"git+file://{git_repo}@main#app") as path:
        assert path.joinpath("start.py").read_bytes() == b"print('changed')\n"


def test_fetch_git_local_archive(git_repo):
    with fetch_from_url(f"git+file://{git_repo}#app.tar.gz") as path:
        assert path.name == "app"
        _assert_app_files(path)
    assert not path.exists()


def test_fetch_git_local_unknown_ref(git_repo):
    with (
        pytest.raises(InvalidGitRefError),
        fetch_from_url(f"git+file://{git_repo}@does-not-exist#app"),
    ):
        pass


def test_fetch_git_local_not_a_repository(tmp_path):
    with (
        pytest.raises(RuntimeError, match="No git repository was found"),
        fetch_from_url(f"git+file://{tmp_path}"),
    ):
        pass


def test_fetch_git_https(monkeypatch, git_repo):
    """Clone from a local repository instead of the network."""
    cloned_urls = []
    clone_from_url = GitRepo.clone_from_url

    def fake_clone_from_url(url, path):
        cloned_urls.append(url)
        return clone_from_url(str(git_repo), path)

    monkeypatch.setattr(fetch.GitRepo, "clone_from_url", fake_clone_from_url)

    url = "git+https://example.com/org/repo.git@v1.0#app"
    with fetch_from_url(url) as path:
        assert path.joinpath("start.py").read_bytes() == APP_FILES["app/start.py"]
        repo_path = Path(path.repo)
        assert repo_path.exists()
    # The clone is removed when the context exits.
    assert not repo_path.exists()
    assert cloned_urls == ["https://example.com/org/repo.git"]


# Other


@pytest.mark.parametrize(
    "url", ["ftp://example.com/app.tar.gz", "http://example.com/app.tar.gz"]
)
def test_fetch_unsupported_scheme(url):
    with pytest.raises(ValueError, match="Unsupported scheme"), fetch_from_url(url):
        pass


@pytest.mark.parametrize(
    ("scheme", "exception"),
    [
        (scheme, exception)
        for scheme in ["file", "https", "git+file"]
        for exception in [RuntimeError, tarfile.ReadError, FileNotFoundError]
    ],
)
def test_exception_in_caller_propagates(
    tmp_path, mock_https, git_repo, scheme, exception
):
    """Exceptions raised in the caller's context are not handled by fetch_from_url."""
    archive = _make_tar(APP_FILES)
    if scheme == "file":
        (tmp_path / "app.tar.gz").write_bytes(archive)
        url = f"file://{tmp_path / 'app.tar.gz'}"
    elif scheme == "https":
        mock_https(archive)
        url = "https://example.com/app.tar.gz"
    else:
        url = f"git+file://{git_repo}#app.tar.gz"

    with pytest.raises(exception, match="from caller"), fetch_from_url(url):
        raise exception("from caller")
