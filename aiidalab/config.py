"""Module to manange AiiDAlab configuration."""
from os import getenv

AIIDALAB_HOME = getenv('AIIDALAB_HOME', '/project')
AIIDALAB_APPS = getenv('AIIDALAB_APPS', '/project/apps')
AIIDALAB_SCRIPTS = getenv('AIIDALAB_SCRIPTS', '/opt')
AIIDALAB_REGISTRY = getenv('AIIDALAB_REGISTRY', 'https://aiidalab.materialscloud.org/appsdata/apps_meta.json')
AIIDALAB_DEFAULT_GIT_BRANCH = getenv('AIIDALAB_DEFAULT_GIT_BRANCH', 'master')
AIIDALAB_ENVIRONMENT_VERSION = getenv('AIIDALAB_ENVIRONMENT_VERSION', '1.0.0')
