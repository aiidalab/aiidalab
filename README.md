[![Build Status](https://travis-ci.org/aiidalab/aiidalab-metapkg.svg?branch=master)](https://travis-ci.org/aiidalab/aiidalab-metapkg)

# aiidalab-metapkg

The `aiidalab` metapackage sets up the python environment found on the 
[AiiDA lab](https://aiidalab.materialscloud.org).
Amongst others, this includes

 * aiida-core
 * a wide range of aiida plugins
 * jupyter
 * ...

Note: The relevant jupyter notebook extensions are enabled automatically.

## Installation

```
# install latest version from pypi
pip install aiidalab
# note: pip can *enable* nbextensions [1,2], but not install them
jupyter nbextension install --sys-prefix --py fileupload        
```
[1] See the [jupyter-notebook documentation](http://jupyter-notebook.readthedocs.io/en/stable/examples/Notebook/Distributing%20Jupyter%20Extensions%20as%20Python%20Packages.html#Automatically-enabling-a-server-extension-and-nbextension)  
[2] http://jupyter-contrib-nbextensions.readthedocs.io/en/latest/install.html

## Testing

```
# install latest version from github
pip install git+https://github.com/aiidalab/aiidalab-metapkg
jupyter nbextension install --sys-prefix --py fileupload        
```

Note: `pip install -e .` does *not* process the `data_files` and thus does not enable the jupyter extensions.

## Updating requirements

Start by adjusting the [`Pipfile`](Pipfile) according to the latest releases.
Then do:
```
pip install pipenv
pipenv lock --requirements > requirements.txt
```

Note: We try to keep the number of explicit dependencies in the `Pipfile` to a minimum.
Consider using [pipdeptree](https://pypi.org/project/pipdeptree/) to figure out the dependency tree and which dependencies are actually needed.

## License

MIT

## Contact

aiidalab@materialscloud.org

## Acknowledgements

This work is supported by the [MARVEL National Centre for Competency in Research](<http://nccr-marvel.ch>)
funded by the [Swiss National Science Foundation](<http://www.snf.ch/en>), as well as by the [MaX
European Centre of Excellence](<http://www.max-centre.eu/>) funded by the Horizon 2020 EINFRA-5 program,
Grant No. 676598.

![MARVEL](miscellaneous/logos/MARVEL.png)
![MaX](miscellaneous/logos/MaX.png)

