import configparser
from textwrap import dedent

import pytest

from aiidalab.metadata import (
    Metadata,
    SimpleCitation,
    StandardCitation,
    package_name_from_setup_cfg,
)


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

    # Missing / absent data
    def test_returns_empty_string_for_empty_setup_cfg(self):
        assert package_name_from_setup_cfg("") == ""

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


class TestMetadataFromSetupCfg:
    def test_empty_setup_cfg(self):
        meta = Metadata.from_setup_cfg("")
        assert meta == Metadata(
            title="",
            description="",
            authors="",
            state="registered",
            documentation_url="",
            external_url="",
            logo="",
            categories=[],
            version="",
            citations=[],
        )

    def test_metadata_section(self):
        setup_cfg = dedent(
            """
            [metadata]
            name = my-app
            version = 1.2.3
            description = My app description
            author = AiiDAlab crew
            url = https://example.com
            project_urls =
                Documentation = https://docs.example.com
                Logo = https://example.com/logo.png
            classifiers =
                Development Status :: 5 - Production/Stable
                Framework :: AiiDA
            """
        )
        meta = Metadata.from_setup_cfg(setup_cfg)
        assert meta.title == "my-app"
        assert meta.version == "1.2.3"
        assert meta.description == "My app description"
        assert meta.authors == "AiiDAlab crew"
        assert meta.external_url == "https://example.com"
        assert meta.documentation_url == "https://docs.example.com"
        assert meta.logo == "https://example.com/logo.png"
        assert meta.state == "stable"
        assert meta.categories == []
        assert meta.citations == []

    def test_lowercase_project_urls(self):
        setup_cfg = dedent(
            """
            [metadata]
            project_urls =
                documentation = https://docs.example.com
                logo = https://example.com/logo.png
            """
        )
        meta = Metadata.from_setup_cfg(setup_cfg)
        assert meta.documentation_url == "https://docs.example.com"
        assert meta.logo == "https://example.com/logo.png"

    def test_aiidalab_section_takes_precedence(self):
        setup_cfg = dedent(
            """
            [metadata]
            name = my-app
            version = 1.2.3
            description = PEP 426 description
            author = PEP 426 author
            url = https://pep426.example.com
            project_urls =
                Documentation = https://docs.pep426.example.com
                Logo = https://pep426.example.com/logo.png
            classifiers =
                Development Status :: 5 - Production/Stable

            [aiidalab]
            title = My App
            version = 2.0.0
            description = AiiDAlab description
            authors = AiiDAlab author
            external_url = https://aiidalab.example.com
            documentation_url = https://docs.aiidalab.example.com
            logo = https://aiidalab.example.com/logo.png
            state = development
            """
        )
        meta = Metadata.from_setup_cfg(setup_cfg)
        assert meta.title == "My App"
        assert meta.version == "2.0.0"
        assert meta.description == "AiiDAlab description"
        assert meta.authors == "AiiDAlab author"
        assert meta.external_url == "https://aiidalab.example.com"
        assert meta.documentation_url == "https://docs.aiidalab.example.com"
        assert meta.logo == "https://aiidalab.example.com/logo.png"
        assert meta.state == "development"

    def test_aiidalab_section_falls_back_to_metadata_section(self):
        setup_cfg = dedent(
            """
            [metadata]
            name = my-app
            version = 1.2.3

            [aiidalab]
            title = My App
            """
        )
        meta = Metadata.from_setup_cfg(setup_cfg)
        assert meta.title == "My App"
        assert meta.version == "1.2.3"

    @pytest.mark.parametrize(
        "classifier,state",
        [
            ("Development Status :: 1 - Planning", "registered"),
            ("Development Status :: 2 - Pre-Alpha", "development"),
            ("Development Status :: 3 - Alpha", "development"),
            ("Development Status :: 4 - Beta", "development"),
            ("Development Status :: 5 - Production/Stable", "stable"),
            ("Development Status :: 6 - Mature", "registered"),
            ("Framework :: AiiDA", "registered"),
        ],
    )
    def test_state_from_classifiers(self, classifier, state):
        setup_cfg = dedent(
            f"""
            [metadata]
            classifiers =
                Programming Language :: Python :: 3
                {classifier}
            """
        )
        assert Metadata.from_setup_cfg(setup_cfg).state == state

    @pytest.mark.parametrize(
        "categories,expected",
        [
            ("quantum", ["quantum"]),
            ("\n    quantum", ["quantum"]),
            ("\n    quantum\n    utilities", ["quantum", "utilities"]),
        ],
    )
    def test_categories(self, categories, expected):
        setup_cfg = f"[aiidalab]\ncategories = {categories}\n"
        assert Metadata.from_setup_cfg(setup_cfg).categories == expected

    def test_citations(self):
        setup_cfg = dedent(
            """
            [aiidalab]
            citations =
                [
                  {
                    "authors": ["Bob", "Bobek"],
                    "title": "HatApp",
                    "journal": "Rabbits weekly",
                    "volume": "12",
                    "issue": "1",
                    "pages": "72",
                    "year": "2026",
                    "doi": "10.1234/app"
                  },
                  {
                    "text": "A simple citation",
                    "link": "https://example.com"
                  }
                ]
            """
        )
        meta = Metadata.from_setup_cfg(setup_cfg)
        assert len(meta.citations) == 2

        standard = meta.citations[0]
        assert isinstance(standard, StandardCitation)
        assert standard.authors == ["Bob", "Bobek"]
        assert standard.title == "HatApp"
        assert standard.journal == "Rabbits weekly"
        assert standard.volume == "12"
        assert standard.issue == "1"
        assert standard.pages == "72"
        assert standard.year == "2026"
        assert standard.doi == "10.1234/app"
        assert standard.issue == "1"

        simple = meta.citations[1]
        assert isinstance(simple, SimpleCitation)
        assert simple.text == "A simple citation"
        assert simple.link == "https://example.com"

    def test_minimal_citations(self, caplog):
        """Test citations without optional fields"""
        setup_cfg = dedent(
            """
            [aiidalab]
            citations =
                [
                  {
                    "authors": ["Bob", "Bobek"],
                    "journal": "Rabbits weekly",
                    "year": "2026",
                    "doi": "10.1234/app"
                  },
                  {
                    "text": "Simple citation without url"
                  }
                ]
            """
        )
        meta = Metadata.from_setup_cfg(setup_cfg)
        assert caplog.text == ""
        assert len(meta.citations) == 2

        standard = meta.citations[0]
        assert standard.authors == ["Bob", "Bobek"]
        assert standard.journal == "Rabbits weekly"
        assert standard.year == "2026"
        assert standard.doi == "10.1234/app"
        assert standard.title is None
        assert standard.volume is None
        assert standard.pages is None
        assert standard.issue is None

        simple = meta.citations[1]
        assert simple.text == "Simple citation without url"
        assert simple.link is None

    def test_invalid_citations_warn(self, caplog):
        setup_cfg = dedent(
            """
            [aiidalab]
            citations =
                [
                  {
                    "journal": "Journal of Missing Authors",
                    "year": "2026",
                    "doi": "10.1234/app"
                  },
                  {
                    "text": "Simple citation with invalid field",
                    "invalid": "Whoops"
                  }
                ]
            """
        )
        meta = Metadata.from_setup_cfg(setup_cfg)
        assert len(meta.citations) == 0

        assert "missing 1 required positional argument: 'authors'" in caplog.messages[0]
        assert "got an unexpected keyword argument 'text'" in caplog.messages[1]

    @pytest.mark.parametrize("citations", ["", "not json", "[{broken"])
    def test_invalid_json_citations_are_ignored(self, caplog, citations):
        setup_cfg = f"[aiidalab]\ncitations = {citations}\n"
        assert Metadata.from_setup_cfg(setup_cfg).citations == []
        assert "Could not parse citations" in caplog.text

    def test_malformed_setup_cfg_raises(self):
        with pytest.raises(configparser.MissingSectionHeaderError):
            Metadata.from_setup_cfg("title = no section header")


class TestMetadataFromPath:
    SETUP_CFG = dedent(
        """
        [aiidalab]
        title = {title}
        description = Test app
        """
    )

    def test_setup_cfg_in_root(self, tmp_path):
        tmp_path.joinpath("setup.cfg").write_text(self.SETUP_CFG.format(title="root"))
        meta = Metadata.from_path(tmp_path)
        assert meta is not None
        assert meta.title == "root"
        assert meta.description == "Test app"

    def test_setup_cfg_in_aiidalab_dir(self, tmp_path):
        aiidalab_dir = tmp_path / ".aiidalab"
        aiidalab_dir.mkdir()
        aiidalab_dir.joinpath("setup.cfg").write_text(
            self.SETUP_CFG.format(title="aiidalab")
        )
        meta = Metadata.from_path(tmp_path)
        assert meta is not None
        assert meta.title == "aiidalab"

    def test_aiidalab_dir_takes_precedence(self, tmp_path):
        tmp_path.joinpath("setup.cfg").write_text(self.SETUP_CFG.format(title="root"))
        aiidalab_dir = tmp_path / ".aiidalab"
        aiidalab_dir.mkdir()
        aiidalab_dir.joinpath("setup.cfg").write_text(
            self.SETUP_CFG.format(title="aiidalab")
        )
        meta = Metadata.from_path(tmp_path)
        assert meta is not None
        assert meta.title == "aiidalab"

    def test_empty_aiidalab_dir_does_not_fallback_to_root(self, tmp_path):
        tmp_path.joinpath("setup.cfg").write_text(self.SETUP_CFG.format(title="root"))
        tmp_path.joinpath(".aiidalab").mkdir()
        with pytest.raises(ValueError):
            meta = Metadata.from_path(tmp_path)
            assert meta is not None
            assert meta.title == "root"

    def test_no_setup_cfg_raises(self, tmp_path):
        with pytest.raises(ValueError):
            Metadata.from_path(tmp_path)

    def test_nonexistent_directory_raises(self, tmp_path):
        with pytest.raises(ValueError, match="does not exist"):
            Metadata.from_path(tmp_path / "missing")
