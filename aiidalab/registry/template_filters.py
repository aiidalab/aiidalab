# -*- coding: utf-8 -*-
"""Custom filters for the Jinja2 template engine."""
from packaging.version import parse


def sort_semantic(versions, pre=False):
    return [
        version
        for version in sorted(versions, key=parse, reverse=True)
        if pre or not parse(version).is_prerelease
    ]
