from os import getenv

aiidalab_home = getenv('AIIDALAB_HOME', '/project')
aiidalab_apps = getenv('AIIDALAB_APPS', '/project/apps')
aiidalab_scripts = getenv('AIIDALAB_SCRIPTS', '/opt')
aiidalab_registry = getenv('AIIDALAB_REGISTRY', 'https://aiidalab.materialscloud.org/appsdata/apps_meta.json')
