# -*- coding: utf8 -*-
from setuptools import setup, find_packages
import json

if __name__ == '__main__':

    with open('setup.json', 'r') as info:
        kwargs = json.load(info)

    with open('requirements.txt', 'r') as rfile:
        requirements = rfile.read().splitlines()

    setup(
        packages=find_packages(),
        include_package_data=True,
        reentry_register=True,
        long_description=open('README.md').read(),
        long_description_content_type='text/markdown',
        data_files=[
            # like `jupyter nbextension enable --sys-prefix`
            ("etc/jupyter/nbconfig/notebook.d", [
                "jupyter-config/nbconfig/notebook.d/aiidalab.json"
            ]),
            # like `jupyter serverextension enable --sys-prefix`
            ("etc/jupyter/jupyter_notebook_config.d", [
                "jupyter-config/jupyter_notebook_config.d/aiidalab.json"
            ])
        ],
        install_requires=requirements,
        # for packages not yet published on pypi
        dependency_links=[
            'git+https://github.com/ltalirz/aiida-gudhi.git@v0.1.0a#egg=aiida-gudhi-0.1.0a0',
            'git+https://github.com/ltalirz/aiida-phtools.git@v0.1.0a0#egg=aiida-phtools-0.1.0a0',
            'git+https://github.com/broeder-j/aiida-fleur@0.6.0#egg=aiida-fleur-0.6.0gh'
        ],
        zip_safe=False,
        **kwargs
    )
