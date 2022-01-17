[![Documentation Status](https://readthedocs.org/projects/aiidalab/badge/)](https://aiidalab.readthedocs.io/)
# AiiDAlab package

The `aiidalab` package sets up the python environment found on the
[AiiDAlab](https://aiidalab.materialscloud.org).


## Installation

Install latest version from pypi:
```
pip install aiidalab
```

## Documentation
The documentation can be found on the [following web page](https://aiidalab.readthedocs.io).

## For maintainers

To create a new release, clone the repository, install development dependencies with `pip install -e '.[dev]'`, and then execute `bumpver update`.
This will:

  1. Create a tagged release with bumped version and push it to the repository.
  2. Trigger a GitHub actions workflow that creates a GitHub release.

Additional notes:

  - Use the `--dry` option to preview the release change.
  - The release tag (e.g. a/b/rc) is determined from the last release.
    Use the `--tag` option to switch the release tag.

## License

MIT

## Citation

Users of AiiDAlab are kindly asked to cite the following publication in their own work:

A. V. Yakutovich et al., Comp. Mat. Sci. 188, 110165 (2021).
[DOI:10.1016/j.commatsci.2020.110165](https://doi.org/10.1016/j.commatsci.2020.110165)

## Contact

aiidalab@materialscloud.org

## Acknowledgements

This work is supported by the [MARVEL National Centre for Competency in Research](<http://nccr-marvel.ch>)
funded by the [Swiss National Science Foundation](<http://www.snf.ch/en>), as well as by the [MaX
European Centre of Excellence](<http://www.max-centre.eu/>) funded by the Horizon 2020 EINFRA-5 program,
Grant No. 676598.

![MARVEL](miscellaneous/logos/MARVEL.png)
![MaX](miscellaneous/logos/MaX.png)
