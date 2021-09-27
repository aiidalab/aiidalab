# -*- coding: utf-8 -*-
"""Core data classes for the app registry."""
import json
from dataclasses import dataclass, fields

import jsonschema
import pkg_resources

from .util import load_json


@dataclass
class AppRegistrySchemas:
    """The app registry JSON-schema objects."""

    app: dict
    apps: dict
    apps_index: dict
    categories: dict
    environment: dict
    metadata: dict

    @classmethod
    def from_path(cls, path):
        return cls(
            **{
                field.name: load_json(path.joinpath(f"{field.name}.schema.json"))
                for field in fields(cls)
            }
        )

    @classmethod
    def from_package(cls):
        return cls(
            **{
                field.name: json.loads(
                    pkg_resources.resource_string(
                        "aiidalab.registry", f"schemas/{field.name}.schema.json"
                    )
                )
                for field in fields(cls)
            }
        )


@dataclass
class AppRegistryData:
    """The app registry data objects (apps and categories)."""

    apps: dict
    categories: dict

    def validate(self, schemas: AppRegistrySchemas):
        """Validate the registry data against the provided registry schemas."""
        jsonschema.validate(instance=self.apps, schema=schemas.apps)
        jsonschema.validate(instance=self.categories, schema=schemas.categories)
