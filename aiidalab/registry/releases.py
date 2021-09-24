# -*- coding: utf-8 -*-
import logging
import os
import re
from dataclasses import dataclass, replace
from urllib.parse import urlsplit, urlunsplit

from aiidalab.environment import Environment
from aiidalab.fetch import fetch_from_url
from aiidalab.git_util import GitRepo
from aiidalab.metadata import Metadata

logger = logging.getLogger(__name__)


@dataclass
class Release:
    environment: Environment
    metadata: Metadata
    url: str


RELEASE_LINE_PATTERN = r"^(?P<rev>[^:]*?)(:(?P<rev_selection>.*))?$"


def _split_release_line(url):
    parsed_url = urlsplit(url)
    if "@" in parsed_url.path:
        path, release_line = parsed_url.path.rsplit("@", 1)
        return urlunsplit(parsed_url._replace(path=path)), release_line
    return url, None


def _get_release_commits(repo, release_line):
    match = re.match(RELEASE_LINE_PATTERN, release_line)

    if not match:
        raise ValueError(f"Invalid release line specification: {release_line}")

    rev = match.groupdict()["rev"] or repo.get_current_branch()

    if match.groupdict()["rev_selection"] is None:
        # No rev_selection means to select this and only this specific
        # revision.  For example: '@main' means, simply checkout 'main' (could
        # be a branch or a tag, however branches have priority).
        for ref in [
            f"refs/heads/{rev}",
            f"refs/remotes/origin/{rev}",
            f"refs/tags/{rev}",
        ]:
            if ref.encode() in repo.refs:
                yield rev, repo.get_peeled(ref.encode()).decode()
                return
        # rev likely committish (commit)
        yield rev, rev

    elif match.groupdict()["rev_selection"]:
        # A rev selection is provided, we fetch the full rev list for the given
        # selection.  For example: '@main:v1..v2' means all commits from v1
        # (exclusive) to v2 (inclusive).

        rev_selection = match.groupdict()["rev_selection"]

        # While the git rev-list command supports listing revisions for a
        # single ref, in this context we only support rev selections for a
        # range, not for individual refs.
        if ".." not in match.groupdict()["rev_selection"]:
            raise ValueError(
                "The rev_selection '{rev_selection}' must specify a range, "
                "that means must contain the range operator '..'."
            )

        # Incomplete revision selections such as `@main:v1..` must be expanded to
        # `@main:v1..main`. Therefore, we first determine the branch ref for the
        # given rev:
        for ref in [f"refs/heads/{rev}", f"refs/remotes/origin/{rev}"]:
            if ref.encode() in repo.refs:
                break
        else:
            raise RuntimeError(f"Revision '{rev}' not a valid branch name.")

        # Transform a potentially incomplete rev_selection into one that
        # contains the branch ref. For example `v1..` is expanded to
        # `v1..{ref}`, where `{ref}` is replaced with the actual reference.
        start, _, stop = rev_selection.rpartition("..")
        selected_commits = repo.rev_list(f"{start or ref}..{stop or ref}")

        for tag in repo.get_merged_tags(rev):
            commit = repo.get_commit_for_tag(tag)
            if commit in selected_commits:
                yield tag, commit

    else:
        # The rev selection is empty, select all tagged commits for the
        # selected revision.  For example: '@main:' means all tagged commits on
        # the main branch.
        for tag in repo.get_merged_tags(rev):
            yield tag, repo.get_commit_for_tag(tag)


def _gather_releases(release_specs, scan_app_repository, app_metadata):
    for release_spec in release_specs:
        if isinstance(release_spec, str):
            url = release_spec
            environment_override = None
            metadata_override = None
            version_override = None
        else:
            url = release_spec["url"]
            environment_override = release_spec.get("environment")
            metadata_override = release_spec.get("metadata", app_metadata)
            version_override = release_spec.get("version")

        def _set_overrides(version, release):
            return version_override or version, replace(
                release,
                environment=environment_override or release.environment,
                metadata=metadata_override or release.metadata,
            )

        # The way that an app is retrieved is determined by the scheme of the
        # release url.  For example, "git+https://example.com/my-app.git" means
        # that the app is located at a remote git repository from which it can
        # be downloaded (cloned) via https.
        base_url, release_line = _split_release_line(url)
        parsed_url = urlsplit(base_url)

        with fetch_from_url(base_url) as repo_path:
            if parsed_url.scheme.startswith("git+"):
                repo = GitRepo(os.fspath(repo_path))
                for ref, sha in _get_release_commits(
                    repo, release_line or repo.get_current_branch()
                ):
                    # Parse environment from local copy of repository.
                    metadata_and_environment = scan_app_repository(
                        f"git+file:{os.fspath(repo_path.resolve())}@{sha}"
                    )
                    if (
                        metadata_and_environment["metadata"] is None
                        and metadata_override is None
                    ):
                        logger.warning(
                            f"Failed to parse metadata for {base_url}@{ref} and no override specified, skipping release!"
                        )
                        continue

                    # Replace release specifier to point to specific commit.
                    path = f"{parsed_url.path.rsplit('@', 1)[0]}@{sha}"
                    release = Release(
                        url=urlunsplit(parsed_url._replace(path=path)),
                        **metadata_and_environment,
                    )
                    yield _set_overrides(ref, release)
            else:
                release = Release(
                    url=url,
                    **scan_app_repository(f"file:{os.fspath(repo_path.resolve())}"),
                )
                yield _set_overrides(None, release)


def gather_releases(app_data, scan_app_repository):
    for version, release in _gather_releases(
        app_data.get("releases", []),
        scan_app_repository,
        app_metadata=app_data.get("metadata"),
    ):
        if version is None:
            raise ValueError(f"Unable to determine version for: {release}")
        yield version, release
