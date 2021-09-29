*******************
Administrator guide
*******************

This guide explains how to deploy and manage AiiDAlab servers for multiple users.
See :ref:`usage:run-locally` for how to run the AiiDAlab docker container locally (e.g. for testing purposes).

Multi-user deployment
=====================

Single-server deployment
-------------------------

For medium-sized deployments (a handful of users), an AiiDAlab multi-user server can deployed on a single (virtual or bare-metal) machine.

Since deploying a multi-user server requires additional packages, such as `JupyterHub <https://jupyter.org/hub>`__, `DockerSpawner <https://github.com/jupyterhub/dockerspawner>`__, `Apache HTTP Server <https://www.apache.org/>`__, and `Docker <http://www.docker.com>`__, we provide the ``aiidalab-server`` `Ansible <https://www.ansible.com/>`__ role which automates the setup of the server.
Please see the `corresponding git repository <https://github.com/aiidalab/ansible-role-aiidalab-server>`__ for more information.


Kubernetes deployment
---------------------

If you are expecting a large number of users (>50), consider deploying AiiDAlab on a scalable Kubernetes cluster.
We provide `instructions and deployment scripts <https://github.com/aiidalab/aiidalab-k8s>`__ for this use case.

.. _admin-guide:maintain-app-registry:

Maintaining an apps registry
============================

By default, AiiDAlab is configured to use the `AiiDAlab application registry <https://aiidalab.github.io/aiidalab-registry/>`_ maintained by the AiiDAlab team for installing new apps.
However, organizations are encouraged to maintain their own registry with apps suitable for their organization's needs.
Here we describe how to maintain and publish a dedicated AiiDAlab apps registry.

.. panels::
   :container: container-lg pb-3
   :column: col-lg-12 p-2

   .. _admin-guide:maintain-app-registry:create:

   **Create the new registry**

   To create a registry, first make sure to install the ``aiidalab`` package on the machine that you want to *build* the registry on.

   .. code-block:: console

        $ pip install aiidalab

   .. note::

        For testing, you could build the registry on a running AiiDAlab instance, in this case the ``aiidalab`` package is already installed.

   Next, create a directory for your registry repository, e.g., with:

   .. code-block:: console

      ~$ mkdir my-aiidalab-registry
      ~$ cd my-aiidalab-registry/
      ~/my-aiidalab-registry$

   Then create two files: a :file:`apps.yaml` and a :file:`categories.yaml` file.
   The first one contains our index of registered applications and the second one the available categories for apps in this registry.

   The definition for entries in the ``apps.yaml`` file are described in detail in :ref:`the documentation on app registration <develop-apps:publish-app:register>`.
   Example:

   .. code-block:: yaml
       :caption: apps.yaml

        hello-world:
          releases:
            - "git+https://github.com/aiidalab/aiidalab-hello-world@master:"

   The ``categories.yaml`` file is a dictionary where, the key of each entry is the category's id and the value consist of a ``title`` and a ``description`` field.
   Example:

   .. code-block:: yaml
      :caption: categories.yaml

       classical:
         description: Apps for performing calculations based on classical/empirical force
           fields.
         title: Classical
       quantum:
         description: Apps for performing quantum-mechanical calculations.
         title: Quantum

   .. tip::

        Instead of creating a new repository from scratch, you can also fork the official `AiiDAlab registry repository <https://github.com/aiidalab/aiidalab-registry>`_ and adjust it for your needs.

   ---

   .. _admin-guide:maintain-app-registry:build:

   **Build the new registry**

   Make sure to switch into the directory in which you previously created the ``apps.yaml`` and ``categories.yaml`` files, then build the registry with:

   .. code-block:: console

        ~/my-aiidalab-registry$ aiidalab registry build

   By default, this will create the registry website and API pages in the ``./build/`` directory.

   You can check whether the registry was successfully built by opening the ``./build/index.html`` page directly in your browser or by inspecting the ``./build/api/v1/apps_index.json`` file.

   ---

   .. _admin-guide:maintain-app-registry:serve:

   **Serve the new registry**

   The registry is generated via static HTML pages and can therefore be easily published with any standard web server.
   For a quick test, you could use the Python built-in web server, with:

   .. code-block:: console

      ~/my-aiidalab-registry$ cd ./build/
      ~/my-aiidalab-registry/build$ python -m http.server
      Serving HTTP on 0.0.0.0 port 8000 (http://0.0.0.0:8000/) ..

   This will launch a simple web server, which is reachable via the address: ``http://0.0.0.0:8000``.

   You can test whether the registry is reachable by executing:

   .. code-block:: console

      ~$ curl localhost:8000/api/v1/apps_index.json


   .. tip::

        You can use `ngrok <https://ngrok.com>`__ to temporarily server the registry over the internet for testing.

        First, `install ngrok <https://ngrok.com/download>`__, then start your local web server as described above, and in a separate terminal run ``ngrok http 8000``.
        This will give you a public address that you can use as the base URL for your registry address.

   .. note::

        The official `AiiDAlab registry repository <https://github.com/aiidalab/aiidalab-registry>`_ is automatically published on `GitHub pages <https://pages.github.com/>`__ via a `GitHub actions <https://github.com/features/actions>`__ integration.
        If you forked the repository, it should automatically publish the registry under your GitHub pages domain.

   ---

   .. _admin-guide:maintain-app-registry:configure:

   **Configure AiiDAlab to use the new registry**

   To instruct AiiDAlab to use a different registry, you can either create a configuration file called ``aiidalab.toml`` in the user's home directory or set the ``AIIDALAB_REGISTRY`` environment variable.
   The former is especially suitable for testing, while the latter is probably the better approach to specify a dedicated registry organization-wide.

   .. tabbed:: Configuration file

       To instruct an AiiDAlab instance to use this registry, simply logon to AiiDAlab, and then create a file called ``aiidalab.toml`` in the home directory, with the following content:

       .. code-block:: toml
          :caption: ~/aiidalab.toml

          registry = "http://localhost:8000/api/v1"

       Where you replace the URL with the one where you serve the newly created registry.


   .. tabbed:: Environment variable (with Docker)

       The registry can be specified by setting the ``AIIDALAB_REGISTRY`` environment variable.
       For example, to pass the variable when starting the container, add the following argument:

       .. code-block:: console

            -e AIIDALAB_REGISTRY=http://localhost:8000/api/v1

       .. dropdown:: :fa:`wrench` Forward the registry from the docker host

           When running a test registry on the docker host, make sure to pass the following flags to ``docker run``:

           * ``--add-host=host.docker.internal:host-gateway`` (only required on Linux, not MacOS)
           * ``-e AIIDALAB_REGISTRY=http://host.docker.internal:8000/api/v1``

   To verify that the new registry is being used, open the terminal and run:

       .. code-block:: bash

           $ aiidalab info
           AiiDAlab, version 21.10.0
           Apps path:      /home/aiida/apps
           Apps registry:  http://localhost:8000/api/v1

   The value behind "Apps registry" should point to the just configured address.

   ---

   .. _admin-guide:maintain-app-registry:test:

   **Test the new registry**

   Try to search for registered applications by opening the App Store in AiiDAlab (:fa:`puzzle-piece`), or by listing the registered apps (and their releases) on the command line with:

   .. code-block:: console

      ~$ aiidalab search
      Collecting apps and releases... Done.
      hello-world==v1.1.0


Troubleshooting
================

Slow I/O
---------

When running AiiDAlab on disks through OpenStack's block storage, observe the following command for a **few minutes**:

.. code-block:: bash

    watch -n 0.1 "ps axu| awk '{print \$8, \"   \", \$11}' | sort | head -n 10"

Almost all processes should be in the ``S`` state.
If a process stays in the ``D`` state for a longer time, it is most likely waiting for slow I/O.
