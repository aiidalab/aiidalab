# -*- coding: utf-8 -*-
"""Generate the app registry website HTML pages."""
from copy import deepcopy
from dataclasses import asdict

from jinja2 import Environment, PackageLoader, select_autoescape

from .apps_meta import extract_git_url_from_releases


def build_html(base_path, data):
    """Generate the app registry website at the base_path path."""

    # Create base_path directory if needed
    base_path.mkdir(parents=True, exist_ok=True)

    # Load template environment
    env = Environment(
        loader=PackageLoader(__name__),
        autoescape=select_autoescape(["html", "xml"]),
    )
    singlepage_template = env.get_template("singlepage.html")
    main_index_template = env.get_template("main_index.html")

    # Make single-entry pages based on singlepage.html
    base_path.joinpath("apps").mkdir()
    for app_id, app_data in data.apps.items():
        subpage = base_path.joinpath("apps", app_id, "index.html")
        app_data["subpage"] = str(subpage.relative_to(base_path))
        app_data["git_url"] = extract_git_url_from_releases(app_data["releases"])

        subpage.parent.mkdir()
        subpage.write_text(
            singlepage_template.render(category_map=data.categories, **app_data),
            encoding="utf-8",
        )
        yield subpage

    # Make index page based on main_index.html
    rendered = main_index_template.render(**asdict(deepcopy(data)))
    outfile = base_path / "index.html"
    outfile.write_text(rendered, encoding="utf-8")
    yield outfile
