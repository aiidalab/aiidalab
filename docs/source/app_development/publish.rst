.. _develop-apps:publish-app:

*************************
Publish your AiiDAlab app
*************************

Here we explain how an app can be made available to AiiDAlab users by registering it on the `AiiDAlab registry`_.

.. panels::
   :container: container-lg pb-3
   :column: col-lg-12 p-2

   **Prepare the app for registration**

   .. important::

       If the app was created with the app cookiecutter it should already have all necessary information and this step can be skipped.

   In preparation of registering your AiiDAlab app in the `AiiDAlab registry`_, ensure you have a valid and updated ``setup.cfg`` file in the root of your app's repository.
   The ``setup.cfg`` file can alternatively also be placed within a hidden ``.aiidalab/`` directory in which case it will be parsed with precedence.

   AiiDAlab parses the ``setup.cfg`` file for metadata and will recognize fields both from the standard `[metadata] <https://setuptools.pypa.io/en/latest/userguide/declarative_config.html#metadata>`__ section and a dedicated ``[aiidalab]`` section (fiends declared within the ``[aiidalab]`` section take precedence).
   We suggest using the ``[aiidalab]`` section only for the ``title`` and ``categories`` fields, and the ``[metadata]`` for all others.

   .. dropdown:: List of all recognized keys and their correspondence (where applicable) between the ``[metadata]`` and the ``[aiidalab]`` sections.

       =================  ============================  ======== =========================================================
       [aiidalab]         [metadata]                    required description
       =================  ============================  ======== =========================================================
       title              *n/a* [#f0]_                  yes      A human-readable title for the app.
       description        description                   yes      A brief description of the app's purpose and function.
       authors            author                        no       A list of all contributing authors.
       version            version                       no       A version specifier. [#f1]_
       external_url       url                           no       A URL for the app home page.
       documentation_url  project_urls: documentation   no       A URL for the app's documentation, e.g., a README file.
       logo               project_urls: logo            no       A URL for the app's logo.
       state [#f2]_       *from classifiers* [#f3]_     no       A classification of the app's development state.
       categories         *n/a* [#f4]_                  no       Categories under which the app will be listed.
       =================  ============================  ======== =========================================================

       .. [#f0] The title cannot be declared within the ``[metadata]`` section.
       .. [#f1] If an app is automatically released from git tags, the registry will use the tag as a version identifier instead.
       .. [#f2] The app state must be one of ["registered", "development", "stable"].
       .. [#f3] The development state is parsed from the *Development State* `trove classifiers <https://pypi.org/classifiers/>`__ and automatically mapped to the AiiDAlab development states.
       .. [#f4] The categories cannot be declared within the ``[metadata]`` section. The complete list of valid categories can be found `here <https://github.com/aiidalab/aiidalab-registry/blob/master/categories.yaml>`__.

   .. dropdown:: Example of a ``setup.cfg`` file generated with the AiiDAlab app cutter

      .. code-block:: ini

          [aiidalab]
          title = My App

          [metadata]
          name = aiidalab-my-app
          version = 0.1-alpha
          author = The AiiDAlab Team
          author_email = email@example.com
          description = This AiiDAlab application was created with the app cutter.
          long_description = file: README.md
          long_description_content_type = text/markdown
          url = https://github.com/aiidalab/aiidalab-my-app
          project_urls =
              Logo = https://raw.githubusercontent.com/aiidalab/aiidalab-my-app/master/img/logo.png
              Documentation = https://github.com/aiidalab/aiidalab-my-app/#readme
              Bug Tracker = https://github.com/aiidalab/aiidalab-my-app/issues

          classifiers =
              License :: OSI Approved :: MIT License
              Operating System :: OS Independent
              Programming Language :: Python :: 3
              Development Status :: 1 - Planning

   .. tip::

      Use the ``aiidalab registry parse-app-repo`` command to test what metadata would be parsed from your app repository.

      Example: ``aiidalab registry parse-app-repo ~/apps/my-app``.

   ---

   .. _develop-apps:publish-app:register:

   **Register the app**

   The app registry uses a *pull* approach, meaning it regularly scans the registered app repositories for new releases. [#f5]_
   This is to simplify the release procedure for app developers.
   For example, typically an app developer will register an app such that newly created tags on a dedicated git branch are automatically released to users.

   .. |fa-edit| raw:: html

      <i class="fa fa-edit"></i>

   To register an app, simply edit the `apps.yaml file <https://github.com/aiidalab/aiidalab-registry/blob/master/apps.yaml>`__ on GitHub by clicking on the :opticon:`pencil` icon in the top right corner and add an entry for your app according to one of the approaches shown below.

   Releases are specified in the form of a list, where each list entry corresponds to one or more tagged commits of a git repository branch.
   In case that it corresponds to multiple commits, the release entry is called a *release line*.

   .. tabbed:: Release all tagged commits

       The simplest approach to release new app versions, is to register the app *once* and then push new releases by creating tagged commits on a specific branch, e.g., the *main* branch.

       .. code-block:: yaml

           my-app:
             releases:
               - "git+https://github.com/aiidalab/aiidalab-my-app@main:"

       where you replace the URL shown here with the one applicable for your app.

       .. hint::

          You can use the standard `git revision selection syntax <https://git-scm.com/book/en/v2/Git-Tools-Revision-Selection>`__ to further reduce the selected commits on a release line.
          For example, ``@main:v1.0.0..`` means "select all tagged commits on the *main* branch after commit tagged with *v1.0.0*".
          See the "Other" tab for details and more examples.

   .. tabbed:: Release specific tagged commits

       Instead of automatically releasing every tagged commit, you can also specify dedicated commmits instead.

       .. code-block:: yaml

           my-app:
             releases:
             - "git+https://github.com/aiidalab/aiidalab-my-app.git@v2"
             - "git+https://github.com/aiidalab/aiidalab-my-app.git@v1"

       Use this approach if you want more control over which versions of your app are installable through the app store.

       .. dropdown:: :fa:`cog` Override the version specifier

            By default, the name of the specified tag will be used as the version of each release.
            You can override the version for individual releases, by simply adding the version explicitly, for example:

            .. code-block:: yaml

                 my-app:
                   releases:
                   - "git+https://github.com/aiidalab/aiidalab-my-app.git@v2"
                   - url: "git+https://github.com/aiidalab/aiidalab-my-app.git@version-1.0"
                     version: v1

   .. tabbed:: Other

      The formal definition of the *release URL* is:

      .. productionlist::
         release-url : app-repository-url + [ "@" ( release | release-line ) ]
         release: ( git-tag | git-commit-sha )
         release-line: branch + ":" + [ revision-selection ]

      where the ``app-repository-url`` should point to a git repository and use the URL scheme ``git+https://``.
      The optional ``revision-selection`` follows the standard `git revision selection syntax <https://git-scm.com/book/en/v2/Git-Tools-Revision-Selection>`__ and can be used to specify a tag range and thus, e.g., exclude early tagged commits, as opposed to releasing all tagged commits.

      .. dropdown:: Examples

          | All tagged commits on the repository's default branch:
          | ``git+https://github.com/aiidalab/aiidalab-hello-world.git@:``

          | All tagged commits on the repository's *develop* branch:
          | ``git+https://github.com/aiidalab/aiidalab-hello-world.git@develop:``

          | All tagged commits on the ``main`` branch from ``v0.1.0`` (exclusive) onwards:
          | ``git+https://github.com/aiidalab/aiidalab-hello-world.git@main:v0.1.0..``

          | All tagged commits on the ``main`` branch from ``v0.1.0`` (inclusive) onwards:
          | ``git+https://github.com/aiidalab/aiidalab-hello-world.git@main:v0.1.0^..``

          | All tagged commits on the ``main`` branch from ``v0.1.0`` (exclusive) until ``v1.0.0``:
          | ``git+https://github.com/aiidalab/aiidalab-hello-world.git@main:v0.1.0..v1.0.0``

          | Specifically the commit tagged with ``v1.0.0``:
          | ``git+https://github.com/aiidalab/aiidalab-hello-world.git@v1.0.0``

   .. [#f5] As opposed to an approach where users *push* new releases to the registry.

   ---

   **Review your app on the app store!**

   Once submmited, your pull request will be reviewed by the AiiDAlab registry maintainers.
   After it is accepted and merged it typically takes 15-30 minutes for your app (and new releases) to appear in the AiiDAlab app store.

   .. figure:: https://github.com/aiidalab/aiidalab/raw/v21.10.0/aiidalab/registry/static/static/gotobutton.svg
       :alt: Go to AiiDAlab app registry
       :align: center
       :target: `AiiDAlab registry web page`_

   You can also test whether your app is listed on the registry by either opening the app store in AiiDAlab or running the following command:

   .. code-block:: console

       $ aiidalab search my-app

   and install it with

   .. code-block:: bash

       $ aiidalab install my-app

.. _AiiDAlab registry: https://github.com/aiidalab/aiidalab-registry
.. _AiiDAlab registry web page: http://aiidalab.github.io/aiidalab-registry
