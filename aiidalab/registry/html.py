# -*- coding: utf-8 -*-
"""Generate the app registry website HTML pages."""
from collections import defaultdict

from jinja2 import (
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    PackageLoader,
    select_autoescape,
)

from . import template_filters


def build_html(base_path, apps_index, apps_data, templates_path):
    """Generate the app registry website at the base_path path."""

    # Create base_path directory if needed
    base_path.mkdir(parents=True, exist_ok=True)

    # Setup template environment
    loaders = [PackageLoader(__name__)]
    if templates_path:
        loaders.insert(0, FileSystemLoader(templates_path))

    env = Environment(
        loader=ChoiceLoader(loaders),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters["sort_semantic"] = template_filters.sort_semantic

    app_page_template = env.get_template("app_page.html")
    main_index_template = env.get_template("index.html")

    # Make single-entry pages based on app_page.html
    base_path.joinpath("apps").mkdir()
    html_template_data = defaultdict(dict)

    for app_id in apps_index["apps"]:
        subpage = base_path.joinpath("apps", app_id, "index.html")
        html_template_data[app_id]["subpage"] = str(subpage.relative_to(base_path))
        html_template_data[app_id]["metadata"] = apps_data[app_id]["metadata"]
        html_template_data[app_id]["releases"] = apps_data[app_id]["releases"]

        subpage.parent.mkdir()
        subpage.write_text(
            app_page_template.render(
                category_map=apps_index["categories"], **html_template_data[app_id]
            ),
            encoding="utf-8",
        )
        yield subpage

    # Make index page based on main_index.html
    rendered = main_index_template.render(apps=html_template_data)
    outfile = base_path / "index.html"
    outfile.write_text(rendered, encoding="utf-8")
    yield outfile
