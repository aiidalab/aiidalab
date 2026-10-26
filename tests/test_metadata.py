import configparser
from textwrap import dedent

import pytest
import tomllib

from aiidalab.metadata import (
    Metadata,
    SimpleCitation,
    StandardCitation,
    package_name_from_pyproject_toml,
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


class TestPackageNameFromPyprojectToml:
    # Happy path
    def test_returns_name_from_project_table(self):
        pyproject_toml = dedent(
            """
            [project]
            name = "my-package"
            version = "2.3.4"
            description = "A test package"
            authors = [{name = "AiiDAlab crew"}]
            """
        )
        assert package_name_from_pyproject_toml(pyproject_toml) == "my-package"

    # Missing / absent data
    def test_returns_empty_string_for_empty_pyproject_toml(self):
        assert package_name_from_pyproject_toml("") == ""

        pyproject_toml = "# just a comment\n"
        assert package_name_from_pyproject_toml(pyproject_toml) == ""

        pyproject_toml = dedent(
            """
            [build-system]
            requires = ["setuptools"]
            """
        )
        assert package_name_from_pyproject_toml(pyproject_toml) == ""

        pyproject_toml = '[project]\nversion = "1.0.0"\n'
        assert package_name_from_pyproject_toml(pyproject_toml) == ""

        pyproject_toml = '[project]\nname = ""\n'
        assert package_name_from_pyproject_toml(pyproject_toml) == ""

    @pytest.mark.parametrize(
        "pyproject_toml,error",
        [
            ("[project]\nname = 42\n", "Could not parse project.name"),
            ('project = "my-package"\n', "Could not parse project"),
        ],
    )
    def test_returns_empty_string_for_invalid_types(
        self, caplog, pyproject_toml, error
    ):
        assert package_name_from_pyproject_toml(pyproject_toml) == ""
        assert len(caplog.messages) == 1
        assert caplog.messages[0].startswith(error)

    def test_raises_on_malformed_toml_content(self):
        pyproject_toml = "this is not valid toml content ==="
        with pytest.raises(tomllib.TOMLDecodeError):
            package_name_from_pyproject_toml(pyproject_toml)

    def test_raises_on_duplicate_name_keys_in_project(self):
        pyproject_toml = dedent(
            """
            [project]
            name = "first"
            name = "second"
            """
        )
        with pytest.raises(tomllib.TOMLDecodeError):
            package_name_from_pyproject_toml(pyproject_toml)


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

        standard = StandardCitation(**meta.citations[0])
        assert standard.authors == ["Bob", "Bobek"]
        assert standard.title == "HatApp"
        assert standard.journal == "Rabbits weekly"
        assert standard.volume == "12"
        assert standard.issue == "1"
        assert standard.pages == "72"
        assert standard.year == "2026"
        assert standard.doi == "10.1234/app"
        assert standard.issue == "1"

        simple = SimpleCitation(**meta.citations[1])
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

        standard = StandardCitation(**meta.citations[0])
        assert standard.authors == ["Bob", "Bobek"]
        assert standard.journal == "Rabbits weekly"
        assert standard.year == "2026"
        assert standard.doi == "10.1234/app"
        assert standard.title is None
        assert standard.volume is None
        assert standard.pages is None
        assert standard.issue is None

        simple = SimpleCitation(**meta.citations[1])
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

    @pytest.mark.parametrize("citations", ["{}", '{"text": "Simple citation"}'])
    def test_invalid_citations_not_a_list(self, caplog, citations):
        setup_cfg = f"[aiidalab]\ncitations = {citations}\n"
        assert Metadata.from_setup_cfg(setup_cfg).citations == []
        assert len(caplog.messages) == 1
        log = caplog.messages[0].replace("'", '"')
        assert log == f"Could not parse citations:\n{citations}\nERROR: Expected a list"

    def test_malformed_setup_cfg_raises(self):
        with pytest.raises(configparser.MissingSectionHeaderError):
            Metadata.from_setup_cfg("title = no section header")


class TestMetadataFromPyprojectToml:
    # TODO: Should we raise on empty or incomplete pyproject.toml?
    # We should probably require at least title and description,
    # according to the Metadata types
    # (same question applies to setup.cfg parsing)
    def test_empty_pyproject_toml(self):
        meta = Metadata.from_pyproject_toml("")
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

    def test_project_table(self):
        pyproject_toml = dedent(
            """
            [project]
            name = "my-app"
            version = "1.2.3"
            description = "My app description"
            authors = [
                {name = "AiiDAlab crew"},
                {name = "Bob", email = "bob@example.com"},
                {email = "anonymous@example.com"},
            ]
            classifiers = [
                "Development Status :: 5 - Production/Stable",
                "Framework :: AiiDA",
            ]

            [project.urls]
            Homepage = "https://example.com"
            Documentation = "https://docs.example.com"
            Logo = "https://example.com/logo.png"
            """
        )
        meta = Metadata.from_pyproject_toml(pyproject_toml)
        assert meta.title == "my-app"
        assert meta.version == "1.2.3"
        assert meta.description == "My app description"
        assert meta.authors == "AiiDAlab crew, Bob, anonymous@example.com"
        assert meta.external_url == "https://example.com"
        assert meta.documentation_url == "https://docs.example.com"
        assert meta.logo == "https://example.com/logo.png"
        assert meta.state == "stable"
        assert meta.categories == []
        assert meta.citations == []

    @pytest.mark.parametrize(
        "authors,expected",
        [
            ("[]", ""),
            ('[{name = "Jane"}]', "Jane"),
            ('[{name = "Jane", email = "jane@example.com"}]', "Jane"),
            ('[{name = "Jane"}, {email = "bob@example.com"}]', "Jane, bob@example.com"),
        ],
    )
    def test_authors(self, caplog, authors, expected):
        pyproject_toml = f"[project]\nauthors = {authors}\n"
        assert Metadata.from_pyproject_toml(pyproject_toml).authors == expected
        assert caplog.text == ""

    @pytest.mark.parametrize("authors", ['"Jane Doe"', "42", '{name = "Jane"}'])
    def test_invalid_authors_not_a_list(self, caplog, authors):
        pyproject_toml = f"[project]\nauthors = {authors}\n"
        assert Metadata.from_pyproject_toml(pyproject_toml).authors == ""
        assert len(caplog.messages) == 1
        assert caplog.messages[0].endswith("ERROR: Expected a list")

    @pytest.mark.parametrize(
        "invalid_author,error",
        [
            ('"Jane Doe"', "Expected a table"),
            ("42", "Expected a table"),
            ("{}", "Expected a non-empty 'name' or 'email'"),
            ('{name = ""}', "Expected a non-empty 'name' or 'email'"),
            ("{name = 42}", "Expected a non-empty 'name' or 'email'"),
        ],
    )
    def test_invalid_author_is_skipped(self, caplog, invalid_author, error):
        pyproject_toml = f'[project]\nauthors = [{{name = "Jane"}}, {invalid_author}, {{name = "Bob"}}]\n'
        assert Metadata.from_pyproject_toml(pyproject_toml).authors == "Jane, Bob"
        assert len(caplog.messages) == 1
        assert caplog.messages[0].startswith("Could not parse invalid author")
        assert caplog.messages[0].endswith(f"ERROR: {error}")

    @pytest.mark.parametrize(
        "field,key,invalid_value",
        [
            ("title", "title", '["My", "App"]'),
            ("version", "version", "1.0"),
            ("description", "description", "42"),
            ("authors", "authors", '["Jane", "Bob"]'),
            ("external_url", "external_url", "{url = 'https://example.com'}"),
            ("documentation_url", "documentation_url", "true"),
            ("logo", "logo", "42"),
            ("state", "state", '["stable"]'),
        ],
    )
    def test_invalid_aiidalab_string_falls_back(
        self, caplog, field, key, invalid_value
    ):
        pyproject_toml = dedent(
            """
            [project]
            name = "my-app"
            version = "1.2.3"
            description = "PEP 621 description"
            authors = [{name = "PEP 621 author"}]
            classifiers = ["Development Status :: 5 - Production/Stable"]

            [project.urls]
            Homepage = "https://example.com"
            Documentation = "https://docs.example.com"
            Logo = "https://example.com/logo.png"
            """
        )
        expected = Metadata.from_pyproject_toml(pyproject_toml)
        meta = Metadata.from_pyproject_toml(
            pyproject_toml + f"\n[tool.aiidalab]\n{key} = {invalid_value}\n"
        )
        assert getattr(meta, field) == getattr(expected, field)
        assert getattr(meta, field) != ""
        assert len(caplog.messages) == 1
        assert caplog.messages[0].startswith(f"Could not parse tool.aiidalab.{key}")
        assert caplog.messages[0].endswith("ERROR: Expected a string")

    @pytest.mark.parametrize(
        "field,key,invalid_value",
        [
            ("title", "name", "42"),
            ("version", "version", "1.0"),
            ("description", "description", '["A", "description"]'),
        ],
    )
    def test_invalid_project_string_is_ignored(self, caplog, field, key, invalid_value):
        pyproject_toml = f"[project]\n{key} = {invalid_value}\n"
        assert getattr(Metadata.from_pyproject_toml(pyproject_toml), field) == ""
        assert len(caplog.messages) == 1
        assert caplog.messages[0].startswith(f"Could not parse project.{key}")
        assert caplog.messages[0].endswith("ERROR: Expected a string")

    @pytest.mark.parametrize(
        "pyproject_toml,error",
        [
            ('project = "my-app"\n', "Could not parse project:\n"),
            ('tool = "my-tool"\n', "Could not parse tool:\n"),
            ('[tool]\naiidalab = "my-app"\n', "Could not parse tool.aiidalab:\n"),
            (
                '[project]\nurls = "https://example.com"\n',
                "Could not parse project.urls:\n",
            ),
        ],
    )
    def test_invalid_tables_are_ignored(self, caplog, pyproject_toml, error):
        meta = Metadata.from_pyproject_toml(pyproject_toml)
        assert meta == Metadata.from_pyproject_toml("")
        assert len(caplog.messages) == 1
        assert caplog.messages[0].startswith(error)
        assert caplog.messages[0].endswith("ERROR: Expected a table")

    def test_invalid_project_url_is_skipped(self, caplog):
        pyproject_toml = dedent(
            """
            [project.urls]
            Homepage = 42
            Documentation = "https://docs.example.com"
            """
        )
        meta = Metadata.from_pyproject_toml(pyproject_toml)
        assert meta.external_url == ""
        assert meta.documentation_url == "https://docs.example.com"
        assert len(caplog.messages) == 1
        assert caplog.messages[0].startswith("Could not parse project.urls.Homepage")

    @pytest.mark.parametrize(
        "classifiers,state,error",
        [
            (
                '"Development Status :: 5 - Production/Stable"',
                "registered",
                "Expected a list",
            ),
            (
                '[42, "Development Status :: 5 - Production/Stable"]',
                "stable",
                "Expected a string",
            ),
        ],
    )
    def test_invalid_classifiers(self, caplog, classifiers, state, error):
        pyproject_toml = f"[project]\nclassifiers = {classifiers}\n"
        assert Metadata.from_pyproject_toml(pyproject_toml).state == state
        assert len(caplog.messages) == 1
        assert caplog.messages[0].startswith("Could not parse")
        assert caplog.messages[0].endswith(f"ERROR: {error}")

    def test_project_url_labels_normalization(self):
        pyproject_toml = dedent(
            """
            [project.urls]
            "Home Page" = "https://example.com"
            documentation = "https://docs.example.com"
            "lo go" = "https://example.com/logo.png"
            """
        )
        meta = Metadata.from_pyproject_toml(pyproject_toml)
        assert meta.external_url == "https://example.com"
        assert meta.documentation_url == "https://docs.example.com"
        assert meta.logo == "https://example.com/logo.png"

    def test_aiidalab_table_takes_precedence(self):
        pyproject_toml = dedent(
            """
            [project]
            name = "my-app"
            version = "1.2.3"
            description = "PEP 621 description"
            authors = [{name = "PEP 621 author"}]
            classifiers = ["Development Status :: 5 - Production/Stable"]

            [project.urls]
            Homepage = "https://pep621.example.com"
            Documentation = "https://docs.pep621.example.com"
            Logo = "https://pep621.example.com/logo.png"

            [tool.aiidalab]
            title = "My App"
            version = "2.0.0"
            description = "AiiDAlab description"
            authors = "AiiDAlab author"
            external_url = "https://aiidalab.example.com"
            documentation_url = "https://docs.aiidalab.example.com"
            logo = "https://aiidalab.example.com/logo.png"
            state = "development"
            """
        )
        meta = Metadata.from_pyproject_toml(pyproject_toml)
        assert meta.title == "My App"
        assert meta.version == "2.0.0"
        assert meta.description == "AiiDAlab description"
        assert meta.authors == "AiiDAlab author"
        assert meta.external_url == "https://aiidalab.example.com"
        assert meta.documentation_url == "https://docs.aiidalab.example.com"
        assert meta.logo == "https://aiidalab.example.com/logo.png"
        assert meta.state == "development"

    def test_aiidalab_table_falls_back_to_project_table(self):
        pyproject_toml = dedent(
            """
            [project]
            name = "my-app"
            version = "1.2.3"

            [tool.aiidalab]
            title = "My App"
            """
        )
        meta = Metadata.from_pyproject_toml(pyproject_toml)
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
        pyproject_toml = dedent(
            f"""
            [project]
            classifiers = [
                "Programming Language :: Python :: 3",
                "{classifier}",
            ]
            """
        )
        assert Metadata.from_pyproject_toml(pyproject_toml).state == state

    @pytest.mark.parametrize(
        "categories,expected",
        [
            ('"quantum"', ["quantum"]),
            ('"""\nquantum\nutilities"""', ["quantum", "utilities"]),
            ('["quantum"]', ["quantum"]),
            ('["quantum", "utilities"]', ["quantum", "utilities"]),
        ],
    )
    def test_categories(self, categories, expected):
        pyproject_toml = f"[tool.aiidalab]\ncategories = {categories}\n"
        assert Metadata.from_pyproject_toml(pyproject_toml).categories == expected

    @pytest.mark.parametrize(
        "categories,expected,error",
        [
            ("42", [], "Expected a list"),
            ("{name = 'quantum'}", [], "Expected a list"),
            (
                '["quantum", 42, "utilities"]',
                ["quantum", "utilities"],
                "Expected a string",
            ),
        ],
    )
    def test_invalid_categories(self, caplog, categories, expected, error):
        pyproject_toml = f"[tool.aiidalab]\ncategories = {categories}\n"
        assert Metadata.from_pyproject_toml(pyproject_toml).categories == expected
        assert len(caplog.messages) == 1
        assert caplog.messages[0].startswith("Could not parse")
        assert caplog.messages[0].endswith(f"ERROR: {error}")

    def test_citations(self):
        pyproject_toml = dedent(
            """
            [[tool.aiidalab.citations]]
            authors = ["Bob", "Bobek"]
            title = "HatApp"
            journal = "Rabbits weekly"
            volume = "12"
            issue = "1"
            pages = "72"
            year = "2026"
            doi = "10.1234/app"

            [[tool.aiidalab.citations]]
            text = "A simple citation"
            link = "https://example.com"
            """
        )
        meta = Metadata.from_pyproject_toml(pyproject_toml)
        assert len(meta.citations) == 2

        standard = StandardCitation(**meta.citations[0])
        assert standard.authors == ["Bob", "Bobek"]
        assert standard.title == "HatApp"
        assert standard.journal == "Rabbits weekly"
        assert standard.volume == "12"
        assert standard.issue == "1"
        assert standard.pages == "72"
        assert standard.year == "2026"
        assert standard.doi == "10.1234/app"

        simple = SimpleCitation(**meta.citations[1])
        assert simple.text == "A simple citation"
        assert simple.link == "https://example.com"

    def test_minimal_citations(self, caplog):
        """Test citations without optional fields"""
        pyproject_toml = dedent(
            """
            [[tool.aiidalab.citations]]
            authors = ["Bob", "Bobek"]
            journal = "Rabbits weekly"
            year = "2026"
            doi = "10.1234/app"

            [[tool.aiidalab.citations]]
            text = "Simple citation without url"
            """
        )
        meta = Metadata.from_pyproject_toml(pyproject_toml)
        assert caplog.text == ""
        assert len(meta.citations) == 2

        standard = StandardCitation(**meta.citations[0])
        assert standard.authors == ["Bob", "Bobek"]
        assert standard.journal == "Rabbits weekly"
        assert standard.year == "2026"
        assert standard.doi == "10.1234/app"
        assert standard.title is None
        assert standard.volume is None
        assert standard.pages is None
        assert standard.issue is None

        simple = SimpleCitation(**meta.citations[1])
        assert simple.text == "Simple citation without url"
        assert simple.link is None

    def test_invalid_citations_warn(self, caplog):
        pyproject_toml = dedent(
            """
            [[tool.aiidalab.citations]]
            journal = "Journal of Missing Authors"
            year = "2026"
            doi = "10.1234/app"

            [[tool.aiidalab.citations]]
            text = "Simple citation with invalid field"
            invalid = "Whoops"
            """
        )
        meta = Metadata.from_pyproject_toml(pyproject_toml)
        assert len(meta.citations) == 0

        assert "missing 1 required positional argument: 'authors'" in caplog.messages[0]
        assert "got an unexpected keyword argument 'text'" in caplog.messages[1]

    @pytest.mark.parametrize(
        "citations",
        [
            "{}",
            '{text = "Simple citation"}',
            "42",
            '"Simple citation"',
            """'[{"text": "JSON citation"}]'""",
        ],
    )
    def test_invalid_citations_not_a_list(self, caplog, citations):
        pyproject_toml = f"[tool.aiidalab]\ncitations = {citations}\n"
        assert Metadata.from_pyproject_toml(pyproject_toml).citations == []
        assert len(caplog.messages) == 1
        assert caplog.messages[0].endswith("ERROR: Expected a list")

    def test_malformed_pyproject_toml_raises(self):
        with pytest.raises(tomllib.TOMLDecodeError):
            Metadata.from_pyproject_toml("[project\nname = 'unterminated'")


class TestMetadataFromPath:
    SETUP_CFG = dedent(
        """
        [aiidalab]
        title = {title}
        description = Test app
        """
    )
    PYPROJECT_TOML = dedent(
        """
        [tool.aiidalab]
        title = "{title}"
        description = "Test app"
        """
    )

    def test_setup_cfg_in_root(self, tmp_path):
        tmp_path.joinpath("setup.cfg").write_text(self.SETUP_CFG.format(title="root"))
        meta = Metadata.from_path(tmp_path)
        assert meta is not None
        assert meta.title == "root"
        assert meta.description == "Test app"

    def test_pyproject_toml_in_root(self, tmp_path):
        tmp_path.joinpath("pyproject.toml").write_text(
            self.PYPROJECT_TOML.format(title="root")
        )
        meta = Metadata.from_path(tmp_path)
        assert meta.title == "root"
        assert meta.description == "Test app"

    def test_setup_cfg_takes_precedence_over_pyproject_toml(self, tmp_path):
        tmp_path.joinpath("setup.cfg").write_text(self.SETUP_CFG.format(title="cfg"))
        tmp_path.joinpath("pyproject.toml").write_text(
            self.PYPROJECT_TOML.format(title="toml")
        )
        assert Metadata.from_path(tmp_path).title == "cfg"

    def test_no_setup_cfg_nor_pyproject_toml_raises(self, tmp_path):
        with pytest.raises(ValueError, match="setup.cfg nor pyproject.toml"):
            Metadata.from_path(tmp_path)

    def test_nonexistent_directory_raises(self, tmp_path):
        with pytest.raises(ValueError, match="does not exist"):
            Metadata.from_path(tmp_path / "missing")
