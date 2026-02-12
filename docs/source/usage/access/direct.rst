.. _docker-cli:

Docker CLI
**********

It is not necessary to use AiiDAlab launch to run the AiiDAlab container.
You can also use the docker CLI directly by running

.. code-block:: console

   docker run -p 8888:8888 aiidalab/full-stack:latest

Follow the URL on the screen to open AiiDAlab in the browser.

.. important::

   If you use the docker CLI directly, the data in the home directory of the container will be lost when the container is deleted. You can use the ``-v`` option to mount a local directory to the container to store the data persistently. For more information, run ``docker run --help``.
