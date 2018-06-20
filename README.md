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
pip install --process-dependency-links aiidalab
# note: pip can *enable* nbextensions, but not install them
jupyter nbextension install --sys-prefix --py fileupload        
```

## Testing

```
# install latest version from github
pip install --process-dependency-links git+https://github.com/materialscloud-org/aiidalab-metapkg
jupyter nbextension install --sys-prefix --py fileupload        
```

Note: `pip install -e .` does *not* process the `data_files` and thus does not enable the jupyter extensions.

## License

MIT

## Contact

aiidalab@materialscloud.org
