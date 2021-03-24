****************
Develop AiiDAlab
****************

Key AiiDAlab components
=======================

The key components of AiiDAlab are:

- `AiiDAlab package <https://github.com/aiidalab/aiidalab>`__ provides the core functionality of the service.
- `AiiDAlab home app <https://github.com/aiidalab/aiidalab-home>`__ provides the web-interface to the service
- `AiiDAlab docker stack <https://github.com/aiidalab/aiidalab-docker-stack>`__ is the repository containing the source code to build the `AiiDAlab docker image <https://hub.docker.com/repository/docker/aiidalab/aiidalab-docker-stack>`__.
- `AiiDAlab app registry <https://github.com/aiidalab/aiidalab-registry>`__  registry for apps shared by the AiiDAlab community.

The `aiidalab package <https://github.com/aiidalab/aiidalab>`__ is used to implement the back-end application logic for the AiiDAlab environment.
This includes the installation and removal of apps, their discovery, and the app store.

An app is a collection of Jupyter notebooks (with optional dependencies which are either directly vendored or declared as dependencies in a ``setup.py`` or ``requirements.txt`` file.

.. note::

    In the current implementation status, those dependencies must be
    pre-installed and are not installed with the app!

The `aiidalab-home package <https://github.com/aiidalab/aiidalab-home/>`__ implements the front-end for the AiiDAlab environment in the form of the so called *home app*.
That includes for example the start page, the terminal, the app store, and the app management interfaces.
The aiidalab-home package depends on the aiidalab package.
Unlike other apps, it is not intended for users to uninstall the home app, or change the installed version.
That is to ensure that the AiiDAlab environment remains functional for a specific docker image and to make it possible to release backwards incompatible changes to the environment (e.g. a new version of the aiidalab package or other dependencies), without breaking existing user environments.

The aiidalab-home app is installed into the system environment and then linked into the user's user space via a symbolic link.
This ensures that the system package is largely immutable but is still available as an app in user space.
For development purposes, developers can remove the symbolic link and replaces it with a different version of aiidalab-home; an eventual user installation of aiidalab-home will be automatically moved to backup location and replaced with the symbolic link upon updating the environment's docker image.

The AiiDAlab environment is released and deployed through the `aiidalab-docker-stack <https://github.com/aiidalab/aiidalab-docker-stack>`__ Docker `images <https://hub.docker.com/repository/docker/aiidalab/aiidalab-docker-stack>`__.
Those images install specific versions of aiidalab, aiidalab-home, and other system-wide dependencies, that are expected to be compatible.
Continuous integration tests for compatibility are executed upon each commit of the aiidalab-docker-stack image.

Testing
-------

.. note::

    Please see the documentation of each individual component for
    instructions on how exactly to implement and execute tests.

The `aiidalab <https://github.com/aiidalab/aiidalab>`__ package is tested via `unit and integration
tests <https://github.com/aiidalab/aiidalab/tree/develop/tests>`__ for function and compatibility.
All tests are targeted at ensuring that new development does not inadvertently break existing behavior and that new features behave as expected.

The `aiidalab-home <https://github.com/aiidalab/aiidalab-home/>`__ package is tested via front-end tests using the `aiidalab-test-app-action <https://github.com/aiidalab/aiidalab-test-app-action>`__.
Those tests are targeted at ensuring that the home app is functional on the latest development version of the aiidalab-docker-stack.
This means that the introduction of incompatibilities must be addressed after updating the aiidalab-docker-stack development version.

The aiidalab-docker-stack is tested via front-end tests that are implemented as part of a select set of tested applications, including the aiidalab-home app.
This is to ensure that these apps work as intended when installed.

AiiDAlab and AiiDAlab Home app development
------------------------------------------

For the following instructions, it is assumed that any development is directly performed within the AiiDAlab Terminal environment.

.. tip::

    The steps to setup (and teardown) an AiiDAlab development workflow are automated within the `aiidalab-dev <https://github.com/aiidalab/aiidalab-dev>`__ package.

Setup for front-end development (home app)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In your development environment (local or in the cloud), remove the symbolic link of aiidalab-home (``/home/aiida/apps/home``) and replace it with a link to a clone of your fork of the aiidalab-home app.
Then commence development on a new branch:

.. code-block:: console

    ~$ git clone git@github.com:<USERNAME>/aiidalab-home.git
    ~$ cd apps/
    ~/apps$ rm home   # DO NOT USE `rm -r`!
    ~/apps$ ln -s ~/aiidalab-home/ home

Once satisfied with the change set, push it to your fork and create a
(draft) pull request.
This will ensure that the front-end tests are executed against the latest development version of aiidalab-docker-stack.
Address all issues and then release a new version.

Setup for back-end development (aiidalab package)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

First, replace the system home app with a local copy based on your fork as described in the instructions for development of the home app.
The clone your fork of the aiidalab package into a location within user space of your choice (e.g. ``$HOME/aiidalab``) and create a symbolic link within the home app to that location:

.. code-block:: console

    ~$ git clone git@github.com:<USERNAME>/aiidalab.git
    ~$ cd apps/home/
    ~/apps/home$ ln -s $HOME/aiidalab/aiidalab

In this way, you can test the function of the home app directly against
your development version of aiidalab.

Once satisfied with the change set, push it to your fork and create a
(draft) pull request.
This will ensure that the unit and integration tests are executed.

How to make a new release (aiidalab and aiidalab-home)
------------------------------------------------------

1. Switch to ``develop`` branch.
2. Make a new release branch e.g. ``release/1.0.0a2``.

.. code-block:: console

       $ git checkout -b release/1.0.0a2

3. Increment ``__version__`` in ``__init__.py`` AND ``setup.json``
   (setup.py).
4. Commit the changes with the commit message: "Prepare release
   1.0.0a2".
5. Push the changes to GitHub.
6. Create a PR from ``release/1.0.0a2`` branch to the ``master`` branch.
7. Once the tests are passed, merge the PR via merge commit (do not use
   rebase, it will recreate all the commits' sha!).
8. Go to the command line and pull the ``master`` branch.
9. Delete ``release/1.0.0a2`` branch locally.

.. code-block:: console

       $ git branch -d release/1.0.0a2

10. Make a new annotated tag. Commit message: "Release 1.0.0a2"

.. code-block:: console

       $ git tag -a 1.0.0a2

11. Push the new tag to GitHub:

.. code-block:: console

       $ git push --tags

12. List all new changes (with links to PRs) while making a release on GitHub.
13. Remove the old dist folder.

.. code-block:: console

       $ rm -r dist

14. Create a new ``dist`` folder.

.. code-block:: console

       $ python setup.py sdist

15. Upload things on test.pypi.org

.. code-block:: console

       $ twine upload --repository-url https://test.pypi.org/legacy/ dist/*

16. Check on test.pypi.org that everything is alright.
17. Upload things on pypi.org:

.. code-block:: console

       $ twine upload dist/*

18. Merge ``master`` back to ``develop`` and push the ``develop`` branch to GitHub.

.. code-block:: console

       $ git checkout develop && git merge master && git push


AiiDAlab Docker Stack
=====================

[TODO]

AiiDAlab App Registry
=====================

[TODO]
