import pytest
from packaging.markers import default_environment
from packaging.requirements import Requirement

from aiidalab.utils import Package, sort_semantic, split_git_url


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


# Tests for the `aiidalab.utils.Package` class

# Marker clauses built from the *actual* interpreter's marker environment
# so these are deterministically true/false regardless of which Python runs the
# suite (mirrors what `Marker.evaluate()` checks against when called with no
# explicit environment).
_ENV = default_environment()
APPLICABLE_MARKER = f"python_version == '{_ENV['python_version']}'"
INAPPLICABLE_MARKER = "python_version == '2.6'"


class TestPackageInit:
    def test_stores_version_when_given(self):
        pkg = Package("requests", "2.31.0")
        assert pkg.version == "2.31.0"

    def test_version_defaults_to_none(self):
        pkg = Package("requests")
        assert pkg.version is None

    def test_version_explicit_none(self):
        pkg = Package("requests", None)
        assert pkg.version is None

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("requests", "requests"),
            ("Requests", "requests"),
            ("My_Package", "my-package"),
            ("My.Package", "my-package"),
            ("My--Package", "my-package"),
            ("zope.interface", "zope-interface"),
            ("Flask_SQLAlchemy", "flask-sqlalchemy"),
        ],
    )
    def test_normalizes_various_forms(self, raw, expected):
        assert Package(raw).canonical_name == expected


class TestPackageDunderMethods:
    def test_repr_includes_class_canonical_name_and_version(self):
        pkg = Package("Requests", "2.31.0")
        assert repr(pkg) == "Package(requests, 2.31.0)"

    def test_repr_with_no_version(self):
        pkg = Package("Requests")
        assert repr(pkg) == "Package(requests, None)"

    def test_str_uses_canonical_name_and_version(self):
        pkg = Package("Requests", "2.31.0")
        assert str(pkg) == "requests==2.31.0"

    def test_str_with_no_version_renders_none(self):
        pkg = Package("Requests")
        assert str(pkg) == "requests==None"


class TestPackageFulfills:
    def test_true_when_name_matches_and_version_none(self):
        # No version confinement -> always fulfills, regardless of specifier
        pkg = Package("requests")
        req = Requirement("requests>=3.0")
        assert pkg.fulfills(req) is True

    def test_false_when_name_differs_even_if_version_none(self):
        pkg = Package("requests")
        req = Requirement("flask")
        assert pkg.fulfills(req) is False

    def test_true_when_version_satisfies_specifier(self):
        pkg = Package("requests", "2.31.0")
        req = Requirement("requests>=2.0,<3.0")
        assert pkg.fulfills(req) is True

    def test_false_when_version_does_not_satisfy_specifier(self):
        pkg = Package("requests", "1.0.0")
        req = Requirement("requests>=2.0,<3.0")
        assert pkg.fulfills(req) is False

    def test_false_when_name_matches_but_version_out_of_range(self):
        pkg = Package("requests", "4.0.0")
        req = Requirement("requests<3.0")
        assert pkg.fulfills(req) is False

    def test_false_when_both_name_and_version_mismatch(self):
        pkg = Package("requests", "1.0.0")
        req = Requirement("flask>=2.0")
        assert pkg.fulfills(req) is False

    def test_true_when_requirement_has_no_specifier(self):
        # An empty specifier set matches any version string
        pkg = Package("requests", "0.0.1")
        req = Requirement("requests")
        assert pkg.fulfills(req) is True

    def test_prerelease_fulfills_when_requirement_has_no_specifier(self):
        pkg = Package("requests", "0.0.1a0")
        req = Requirement("requests")
        assert pkg.fulfills(req) is True

    def test_prerelease_fulfills_when_requirement_has_git_url(self):
        pkg = Package("aiidalab-widgets-base", "3.0.0a3")
        req = Requirement(
            "aiidalab_widgets_base@git+https://github.com/aiidalab/aiidalab-widgets-base@master"
        )
        assert pkg.fulfills(req) is True

    def test_name_matching_is_canonicalized_on_both_sides(self):
        pkg = Package("Flask_SQLAlchemy", "3.0.0")
        req = Requirement("flask-sqlalchemy>=2.0")
        assert pkg.fulfills(req) is True

    def test_exact_version_pin_matches(self):
        pkg = Package("requests", "2.31.0")
        req = Requirement("requests==2.31.0")
        assert pkg.fulfills(req) is True

    def test_exact_version_pin_mismatch(self):
        pkg = Package("requests", "2.31.1")
        req = Requirement("requests==2.31.0")
        assert pkg.fulfills(req) is False

    def test_exclusion_specifier(self):
        pkg = Package("requests", "2.31.0")
        req = Requirement("requests!=2.31.0")
        assert pkg.fulfills(req) is False


class TestFulfillsWithMarkers:
    # If a PEP 496 environment marker does not apply to the current environment,
    # the requirement is automatically fulfilled not matter what.

    def test_true_when_marker_inapplicable_even_with_matching_name_and_version(self):
        pkg = Package("requests", "2.31.0")
        req = Requirement(f"requests>=2.0,<3.0; {INAPPLICABLE_MARKER}")
        assert pkg.fulfills(req) is True

    def test_true_when_marker_inapplicable_and_version_would_fail(self):
        pkg = Package("requests", "1.0.0")
        req = Requirement(f"requests>=2.0,<3.0; {INAPPLICABLE_MARKER}")
        assert pkg.fulfills(req) is True

    def test_true_when_marker_inapplicable_and_name_would_fail(self):
        pkg = Package("flask", "1.0.0")
        req = Requirement(f"requests>=2.0,<3.0; {INAPPLICABLE_MARKER}")
        assert pkg.fulfills(req) is True

    def test_true_when_marker_inapplicable_and_package_version_is_none(self):
        pkg = Package("flask")
        req = Requirement(f"requests>=2.0,<3.0; {INAPPLICABLE_MARKER}")
        assert pkg.fulfills(req) is True

    # -- marker applies to the current environment: falls through to the
    # -- ordinary name/version check, same as if there were no marker at all.

    def test_true_when_marker_applicable_and_name_and_version_match(self):
        pkg = Package("requests", "2.31.0")
        req = Requirement(f"requests>=2.0,<3.0; {APPLICABLE_MARKER}")
        assert pkg.fulfills(req) is True

    def test_false_when_marker_applicable_but_version_out_of_range(self):
        pkg = Package("requests", "1.0.0")
        req = Requirement(f"requests>=2.0,<3.0; {APPLICABLE_MARKER}")
        assert pkg.fulfills(req) is False

    def test_false_when_marker_applicable_but_name_differs(self):
        pkg = Package("flask", "2.31.0")
        req = Requirement(f"requests>=2.0,<3.0; {APPLICABLE_MARKER}")
        assert pkg.fulfills(req) is False

    def test_true_when_marker_applicable_and_package_version_is_none(self):
        pkg = Package("requests")
        req = Requirement(f"requests>=2.0,<3.0; {APPLICABLE_MARKER}")
        assert pkg.fulfills(req) is True

    # Test compound marker expressions
    def test_true_when_compound_marker_evaluates_false(self):
        pkg = Package("requests", "9.9.9")  # would otherwise fail the specifier
        req = Requirement(
            f"requests>=2.0,<3.0; {INAPPLICABLE_MARKER} and {APPLICABLE_MARKER}"
        )
        assert pkg.fulfills(req) is True

    def test_normal_check_when_compound_marker_evaluates_true(self):
        pkg = Package("requests", "2.31.0")
        req = Requirement(
            f"requests>=2.0,<3.0; {APPLICABLE_MARKER} or {INAPPLICABLE_MARKER}"
        )
        assert pkg.fulfills(req) is True
