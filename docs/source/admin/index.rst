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

Run a separate registry
=======================

By default, the AiiDAlab containers use the central `AiiDAlab application registry <https://aiidalab.github.io/aiidalab-registry/>`_ for installing new apps.
However, maintaining your own registry is straightforward.

Serve the new registry:

    1. Fork the `AiiDAlab registry repository <https://github.com/aiidalab/aiidalab-registry>`_ and edit the ``apps.yaml`` file to point to your apps of interest.
    2. Run ``python src/build.py`` to collect all necessary information.
    3. | Publish the ``src/build/html`` directory to a server of your choice.
       | For a quick test, run ``python -m http.server`` inside the ``html`` directory.
    4. | Try fetching ``http://<your-server>/api/v1/``.
       | In the above test example: ``http://0.0.0.0:8000/api/v1``.
    5. Make sure that the registry server is accessible from the AiiDAlab server.

Use the new registry:

    1. | When creating the AiiDAlab docker container, pass the URL to the registry server to the container in the ``AIIDALAB_REGISTRY`` environment variable (e.g. using `docker-compose <https://docs.docker.com/compose/reference/>`_).
       | When running a test registry on the docker host, pass the following flags to ``docker run``:

        * ``--add-host=host.docker.internal:host-gateway`` (only required on Linux, not MacOS)
        * ``-e AIIDALAB_REGISTRY=http://host.docker.internal:8000/api/v1``

To verify that the new registry is being used, open a terminal in an AiiDAlab container and run:

.. code-block:: bash

    $ aiidalab info
    AiiDAlab, version 21.07.2
    Apps path:      /home/aiida/apps
    Apps registry:  http://docker.host.internal:8000/api/v1


Troubleshooting
================

Slow I/O
---------

When running AiiDAlab on disks through OpenStack's block storage, observe the following command for a **few minutes**:

.. code-block:: bash

    watch -n 0.1 "ps axu| awk '{print \$8, \"   \", \$11}' | sort | head -n 10"

Almost all processes should be in the ``S`` state.
If a process stays in the ``D`` state for a longer time, it is most likely waiting for slow I/O.
