[![Build Status](https://travis-ci.org/aiidalab/aiidalab.svg?branch=master)](https://travis-ci.org/aiidalab/aiidalab)
[![Documentation Status](https://readthedocs.org/projects/aiidalab/badge/)](https://aiidalab.readthedocs.io/)
# AiiDAlab package

The `aiidalab` package sets up the python environment found on the
[AiiDAlab](https://aiidalab.materialscloud.org).
Amongst others, this includes

 * a wide range of aiida plugins
 * jupyter
 * AiiDAlab base widgets
 * ...

The relevant jupyter notebook extensions are enabled automatically.

**Note:** This is the development version for **AiiDA 1.0**.

## Installation

```
# install latest version from pypi
pip install aiidalab
# note: pip can *enable* nbextensions [1,2], but not install them
jupyter nbextension install --sys-prefix --py fileupload        
```
[1] See the [jupyter-notebook documentation](http://jupyter-notebook.readthedocs.io/en/stable/examples/Notebook/Distributing%20Jupyter%20Extensions%20as%20Python%20Packages.html#Automatically-enabling-a-server-extension-and-nbextension)  
[2] http://jupyter-contrib-nbextensions.readthedocs.io/en/latest/install.html

## Documentation
The documentation can be found on the [following web page](https://aiidalab.readthedocs.io).

## Testing

```
# install latest version from github
pip install git+https://github.com/aiidalab/aiidalab-metapkg
jupyter nbextension install --sys-prefix --py fileupload        
```

Note: `pip install -e .` does *not* process the `data_files` and thus does not enable the jupyter extensions.


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

