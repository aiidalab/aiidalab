# -*- coding: utf-8 -*-
"""Utility module for git-managed AiiDAlab apps."""
import locale
import os
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from subprocess import CalledProcessError, run
from urllib.parse import urldefrag

from dulwich.porcelain import branch_list, status
from dulwich.repo import Repo


class BranchTrackingStatus(Enum):
    """Descripe the tracking status of a branch."""

    BEHIND = -1
    EQUAL = 0
    AHEAD = 1
    DIVERGED = 2


class GitManagedAppRepo(Repo):
    """Utility class to simplify management of git-based apps."""

    def list_branches(self):
        """List all repository branches."""
        return branch_list(self)

    def branch(self):
        """Return the current branch.

        Raises RuntimeError if the repository is in a detached HEAD state.
        """
        branches = self._get_branch_for_ref(b"HEAD")
        if branches:
            return branches[0]
        raise RuntimeError("In detached HEAD state.")

    def get_tracked_branch(self, branch=None):
        """Return the tracked branch for a given branch or None if the branch is not tracking."""
        if branch is None:
            branch = self.branch()

        cfg = self.get_config()
        try:
            remote = cfg[(b"branch", branch)][b"remote"]
            merge = cfg[(b"branch", branch)][b"merge"]
            pattern = rb"refs\/heads"
            remote_ref = b"refs/remotes/" + remote + re.sub(pattern, b"", merge)
            return remote_ref
        except KeyError:
            return None

    def dirty(self):
        """Check if there are likely local user modifications to the app repository."""
        status_ = status(self)
        return bool(any(bool(_) for _ in status_.staged.values()) or status_.unstaged)

    def update_available(self):
        """Check whether there non-pulled commits on the tracked branch."""
        return (
            self.get_branch_tracking_status(self.branch())
            is BranchTrackingStatus.BEHIND
        )

    def get_branch_tracking_status(self, branch):
        """Return the tracking status of branch."""
        tracked_branch = self.get_tracked_branch(branch)
        if tracked_branch:
            ref = b"refs/heads/" + branch

            # Check if local branch points to same commit as tracked branch:
            if self.refs[ref] == self.refs[tracked_branch]:
                return BranchTrackingStatus.EQUAL

            # Check if local branch is behind the tracked branch:
            for commit in self.get_walker(self.refs[tracked_branch]):
                if commit.commit.id == self.refs[ref]:
                    return BranchTrackingStatus.BEHIND

            # Check if local branch is ahead of tracked branch:
            for commit in self.get_walker(self.refs[ref]):
                if commit.commit.id == self.refs[tracked_branch]:
                    return BranchTrackingStatus.AHEAD

            return BranchTrackingStatus.DIVERGED

        return None

    def _get_branch_for_ref(self, ref):
        """Get the branch name for a given reference."""
        pattern = rb"refs\/heads\/"
        return [
            re.sub(pattern, b"", ref)
            for ref in self.refs.follow(ref)[0]
            if re.match(pattern, ref)
        ]


def git_clone(url, commit, path):
    try:
        run(
            ["git", "clone", str(url), str(path)],
            capture_output=True,
            encoding="utf-8",
            check=True,
        )
        if commit is not None:
            run(
                ["git", "checkout", str(commit)],
                capture_output=True,
                encoding="utf-8",
                check=True,
                cwd=str(path),
            )
    except CalledProcessError as error:
        raise RuntimeError(error.stderr)


@dataclass
class GitPath(os.PathLike):
    """Utility class to operate on git objects like path objects."""

    repo: Path
    commit: str
    path: Path = Path(".")

    def __fspath__(self):
        return str(Path(self.repo).joinpath(self.path))

    def joinpath(self, *other):
        return type(self)(
            repo=self.repo, path=self.path.joinpath(*other), commit=self.commit
        )

    def resolve(self, strict=False):
        return type(self)(
            repo=self.repo,
            path=Path(self.repo)
            .joinpath(self.path)
            .resolve(strict=strict)
            .relative_to(Path(self.repo).resolve()),
            commit=self.commit,
        )

    def _get_type(self):
        # Git expects that a current directory path ("." or "./") is
        # represented with a trailing slash for this function.
        path = "./" if self.path == Path() else self.path

        try:
            return (
                run(
                    ["git", "cat-file", "-t", f"{self.commit}:{path}"],
                    cwd=self.repo,
                    check=True,
                    capture_output=True,
                )
                .stdout.decode(errors="ignore")
                .strip()
            )
        except CalledProcessError as error:
            if error.returncode == 128:
                return None
            raise

    def is_file(self):
        return self._get_type() == "blob"

    def is_dir(self):
        return self._get_type() == "tree"

    def read_bytes(self):
        try:
            return run(
                ["git", "show", f"{self.commit}:{self.path}"],
                cwd=os.fspath(self.repo),
                check=True,
                capture_output=True,
            ).stdout
        except CalledProcessError as error:
            error_message = error.stderr.decode(errors="ignore").strip()
            if re.match(
                f"fatal: Path '{re.escape(str(self.path))}' (exists on disk, but not in|does not exist)",
                error_message,
                flags=re.IGNORECASE,
            ):
                raise FileNotFoundError(f"{self.commit}:{self.path}")
            elif re.match(
                "fatal: Invalid object name", error_message, flags=re.IGNORECASE
            ):
                raise ValueError(f"Unknown commit: {self.commit}")
            else:
                raise  # unexpected error

    def read_text(self, encoding=None, errors=None):
        if encoding is None:
            encoding = locale.getpreferredencoding(False)
        if errors is None:
            errors = "strict"
        return self.read_bytes().decode(encoding=encoding, errors=errors)


class GitRepo(Repo):
    def get_current_branch(self):
        try:
            branch = run(
                ["git", "branch", "--show-current"],
                cwd=Path(self.path),
                check=True,
                capture_output=True,
                encoding="utf-8",
            ).stdout
        except CalledProcessError as error:
            if error.returncode == 129:
                raise RuntimeError("This function equires at least git version 2.22.")
            raise
        if not branch:
            raise RuntimeError(
                "Unable to determine current branch name, likely in detached HEAD state."
            )
        return branch.strip()

    def get_commit_for_tag(self, tag):
        return self.get_peeled(f"refs/tags/{tag}".encode()).decode()

    def get_merged_tags(self, branch):
        for branch_ref in [f"refs/heads/{branch}", f"refs/remotes/origin/{branch}"]:
            if branch_ref.encode() in self.refs:
                yield from run(
                    ["git", "tag", "--merged", branch_ref],
                    cwd=self.path,
                    check=True,
                    capture_output=True,
                    encoding="utf-8",
                ).stdout.splitlines()
                break
        else:
            raise ValueError(f"Not a branch: {branch}")

    def rev_list(self, rev_selection):
        return run(
            ["git", "rev-list", rev_selection],
            cwd=self.path,
            check=True,
            encoding="utf-8",
            capture_output=True,
        ).stdout.splitlines()

    def ref_from_rev(self, rev):
        """Determine ref from rev.

        Returns branch reference if a branch with that name exists, otherwise a
        tag reference, otherwise the rev itself (assuming it is a commit id).
        """

        if f"refs/heads/{rev}".encode() in self.refs:
            return f"refs/heads/{rev}"
        elif f"refs/remotes/origin/{rev}".encode() in self.refs:
            return f"refs/remotes/origin/{rev}"
        elif f"refs/tags/{rev}".encode() in self.refs:
            return f"refs/tags/{rev}"
        else:
            return rev

    @classmethod
    def clone_from_url(cls, url, path):
        run(
            ["git", "clone", urldefrag(url).url, path],
            cwd=Path(path).parent,
            check=True,
            capture_output=True,
        )
        return GitRepo(path)
