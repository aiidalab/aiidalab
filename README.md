# aiidalab-metapkg

The `aiidalab` metapackage sets up the python environment found on the 
[AiiDA lab](aiidalab.materialscloud.org).
Amongst others, this includes

 * aiida-core
 * a wide range of aiida plugins
 * jupyter
 * ...

Note: The relevant jupyter notebook extensions are enabled automatically.

## Installation

```
# install latest version from github
pip install --process-dependency-links git+https://github.com/materialscloud-org/aiidalab-metapkg
# note: pip can *enable* nbextensions, but not install them
jupyter nbextension install --sys-prefix --py fileupload        

# alternative: install specific tag
# pip install --process-dependency-links git+https://github.com/materialscloud-org/aiidalab-metapkg@v18.06.0rc1
```

## Testing

Note: `pip install -e .` does *not* process the `data_files` and thus does not enable the jupyter extensions.

## License

MIT

## Contact

aiidalab@materialscloud.org
