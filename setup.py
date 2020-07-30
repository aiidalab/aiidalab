# -*- coding: utf8 -*-
"""Setting up base widgets for base package for AiiDA lab."""
import json

from setuptools import setup, find_packages

if __name__ == '__main__':

    with open('setup.json', 'r') as info:
        kwargs = json.load(info)  # pylint: disable=invalid-name

    setup(
        packages=find_packages(),
        include_package_data=True,
        reentry_register=True,
        long_description=open('README.md').read(),
        long_description_content_type='text/markdown',
        data_files=[
            # like `jupyter nbextension enable --sys-prefix`
            ("etc/jupyter/nbconfig/notebook.d", ["jupyter-config/nbconfig/notebook.d/aiidalab.json"]),
            # like `jupyter serverextension enable --sys-prefix`
            ("etc/jupyter/jupyter_notebook_config.d", ["jupyter-config/jupyter_notebook_config.d/aiidalab.json"])
        ],
        zip_safe=False,
        entry_points={
            'console_scripts': ['aiidalab = aiidalab.__main__:cli',],
        },
        **kwargs)
