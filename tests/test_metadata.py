import configparser

import pytest

from aiidalab.metadata import package_name_from_setup_cfg


class TestPackageNameFromSetupCfg:
    # Happy path
    def test_returns_name_from_metadata_section(self):
        setup_cfg = """
        [metadata]
        name = my-package
        version = 2.3.4
        author = AiiDAlab crew
        description = A test package

        [options]
        packages = find:

        [options.extras_require]
        dev = pytest
        """
        assert package_name_from_setup_cfg(setup_cfg) == "my-package"

    @pytest.mark.parametrize(
        "name_value",
        [
            "simple_package",
            "package-with-dashes",
            "package.with.dots",
            "Package_With_Mixed_Case",
            "a",
            "123package",
        ],
    )
    def test_returns_various_valid_name_formats(self, name_value):
        setup_cfg = f"""
        [metadata]
        name = {name_value}
        """
        assert package_name_from_setup_cfg(setup_cfg) == name_value

    def test_strips_surrounding_whitespace_from_name(self):
        setup_cfg = """
        [metadata]
        name =    spaced-package
        """
        assert package_name_from_setup_cfg(setup_cfg) == "spaced-package"

    # Missing / absent data
    def test_returns_empty_string_for_empty_input(self):
        assert package_name_from_setup_cfg("") == ""

    def test_returns_empty_string_when_no_sections_at_all(self):
        setup_cfg = "# just a comment\n"
        assert package_name_from_setup_cfg(setup_cfg) == ""

    def test_returns_empty_string_when_no_metadata_section(self):
        setup_cfg = """
        [options]
        packages = find:
        """
        assert package_name_from_setup_cfg(setup_cfg) == ""

    def test_returns_empty_string_when_metadata_has_no_name(self):
        setup_cfg = """
        [metadata]
        version = 1.0.0
        """
        assert package_name_from_setup_cfg(setup_cfg) == ""

    def test_returns_empty_string_when_name_value_is_blank(self):
        setup_cfg = """
        [metadata]
        name =
        """
        assert package_name_from_setup_cfg(setup_cfg) == ""

    def test_raises_on_malformed_cfg_content(self):
        setup_cfg = "this is not valid ini content ==="
        with pytest.raises(configparser.MissingSectionHeaderError):
            package_name_from_setup_cfg(setup_cfg)

    def test_raises_on_duplicate_metadata_sections(self):
        # ConfigParser is strict by default and rejects a section
        # defined twice.
        setup_cfg = """
        [metadata]
        name = first

        [metadata]
        name = second
        """
        with pytest.raises(configparser.DuplicateSectionError):
            package_name_from_setup_cfg(setup_cfg)

    def test_raises_on_duplicate_name_keys_in_metadata(self):
        setup_cfg = """
        [metadata]
        name = first
        name = second
        """
        with pytest.raises(configparser.DuplicateOptionError):
            package_name_from_setup_cfg(setup_cfg)
