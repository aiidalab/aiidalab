# -*- coding: utf-8 -*-
"""Utility functions for the application registry."""

import json
import string
from pathlib import Path
from urllib.parse import urlparse


def get_html_app_fname(app_name):
    valid_characters = set(string.ascii_letters + string.digits + "_-")

    simple_string = "".join(c for c in app_name if c in valid_characters)

    return f"{simple_string}.html"


def get_hosted_on(url):
    netloc = urlparse(url).netloc

    # Remove port (if any)
    netloc = netloc.partition(":")[0]

    # Remove subdomains (this only works for domain suffixes of length 1!)
    # TODO: fix it for domains like yyy.co.uk
    netloc = ".".join(netloc.split(".")[-2:])

    return netloc


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())
