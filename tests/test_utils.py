import pytest

from aiidalab.utils import sort_semantic, split_git_url


@pytest.mark.parametrize(
    "versions,sorted_versions",
    [
        (("1.0.0", "2.0", "2.0.3"), ["1.0.0", "2.0", "2.0.3"]),
        (("2.0", "2.0.3", "1.0.0"), ["1.0.0", "2.0", "2.0.3"]),
        (("2.0", "2.0.3", "1.0.0a0"), ["2.0", "2.0.3"]),
        (("2.0rc0", "2.0.3dev", "1.0.0b0"), []),
        ([], []),
    ],
)
def test_sort_semantic_ascending(versions, sorted_versions):
    assert sort_semantic(versions, reverse=False) == sorted_versions


@pytest.mark.parametrize(
    "versions,sorted_versions",
    [
        (("1.0.0b1", "2.0.0a0", "2.0.0"), ["1.0.0b1", "2.0.0a0", "2.0.0"]),
        (("2.0", "2.0.3", "1.0.0rc0"), ["1.0.0rc0", "2.0", "2.0.3"]),
        (("2.0", "2.0.3", "1.0.0a0"), ["1.0.0a0", "2.0", "2.0.3"]),
    ],
)
def test_sort_semantic_with_prereleases(versions, sorted_versions):
    assert sort_semantic(versions, reverse=False, prereleases=True) == sorted_versions


@pytest.mark.parametrize(
    "versions,sorted_versions",
    [
        (("1.0.0", "2.0", "2.0.3"), ["2.0.3", "2.0", "1.0.0"]),
        (("2.0", "2.0.3", "1.0.0"), ["2.0.3", "2.0", "1.0.0"]),
    ],
)
def test_sort_semantic_descending(versions, sorted_versions):
    assert sort_semantic(versions) == sorted_versions


@pytest.mark.parametrize(
    "url,base,ref",
    [
        (
            "https://github.com/aiidalab/test@v1",
            "https://github.com/aiidalab/test",
            "v1",
        ),
        (
            "git+https://gitlab.com/aiidalab/test",
            "git+https://gitlab.com/aiidalab/test",
            None,
        ),
        ("git@github.com/aiidalab/test@v1", "git@github.com/aiidalab/test", "v1"),
        # TODO: These test cases currently fail
        # ("git@github.com/aiidalab/test", "https://gitlab.com/aiidalab/test", None),
        # ("https://gitlab.com/aiidalab/test@weird@branch", "https://gitlab.com/aiidalab/test", "weird@branch"),
    ],
)
def test_split_git_url(url, base, ref):
    base_url, git_ref = split_git_url(url)
    assert base_url == base
    assert git_ref == ref
