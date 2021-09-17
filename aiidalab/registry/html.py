# -*- coding: utf-8 -*-
"""Generate the app registry website HTML pages."""
from collections import defaultdict

from jinja2 import Environment, PackageLoader, select_autoescape


def build_html(base_path, apps_index, apps_data):
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
    html_template_data = defaultdict(dict)

    for app_id in apps_index["apps"]:
        subpage = base_path.joinpath("apps", app_id, "index.html")
        html_template_data[app_id]["subpage"] = str(subpage.relative_to(base_path))
        html_template_data[app_id]["metadata"] = apps_data[app_id]["metadata"]

        subpage.parent.mkdir()
        subpage.write_text(
            singlepage_template.render(
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
