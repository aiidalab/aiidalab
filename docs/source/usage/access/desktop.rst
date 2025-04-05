.. _docker-desktop:

Docker Desktop
**************

.. important::

   The following steps require Docker Desktop. If you have yet to install it, please follow the instructions to :ref:`install Docker Desktop <install-docker>`.

Open the Docker Desktop app and follow these instructions to spin up an AiiDAlab container:

Fetch the AiiDAlab image
========================

#. On the left sidebar, click on **Images**

      .. image:: include/docker-images.png
         :width: 100%
         :align: center
         :alt: Docker images

#. In the search bar at the top of the app

   * Enter one of the following AiiDAlab images:
      * ``aiidalab/qe`` - pre-configured with the `Quantum ESPRESSO app <https://aiidalab-qe.readthedocs.io/index.html>`_ (**recommended**)
      * ``aiidalab/full-stack`` - bare image

   * Select ``latest`` from the **Tag** dropdown menu
   * Click **Pull** to download the image

      .. image:: include/image-search.png
         :width: 100%
         :align: center
         :alt: Image search

   * Once downloaded, the image will appear as a new line in the list of images

      .. image:: include/image-row.png
         :width: 100%
         :align: center
         :alt: Image row

#. Exit the search menu when done

Create a persistent volume
==========================

.. important::

   To avoid losing your work when the container shuts down (manually, or when the machine is turned off), it is important to mount a volume (a local storage) on the container. Associating the volume with the user directory ensures the persistence of all user data.

#. On the left sidebar, click on **Volumes**

      .. image:: include/docker-volumes.png
         :width: 100%
         :align: center
         :alt: Docker volumes

#. Click on **Create**
#. Name your volume (e.g. ``aiidalab_home``) and click **Create**

      .. image:: include/new-volume.png
         :width: 100%
         :align: center
         :alt: New volume

#. Repeat the process to create a second volume (e.g. ``aiidalab_conda``) for the conda environment
#. Return to the **Images** panel

Create an AiiDAlab container
============================

#. From the new image line, under actions, click ▶️ to start a container instance

      .. image:: include/run-image.png
         :width: 100%
         :align: center
         :alt: Run image

#. In the pop-up window, expand **Optional settings**

      .. image:: include/run-container.png
         :width: 100%
         :align: center
         :alt: Run container

#. You may choose to name the container for easy reference (randomly generated otherwise)
#. Choose a local port from which to communicate with the container's 8888 port (e.g. ``8888``)
#. Associate your new volumes with the corresponding container directories

   * ``aiidalab_home`` --> ``/home/jovyan``
   * ``aiidalab_conda`` --> ``/home/jovyan/.conda``

#. Click **Run** to start the container

Launch AiiDAlab
===============

#. On the left sidebar, click on **Containers**

      .. image:: include/docker-containers.png
         :width: 100%
         :align: center
         :alt: Docker containers

#. Click on the name of your newly-created container in the list of containers
#. Wait for the container build process to finish
#. When done, the log will show the following message

      .. image:: include/log-message.png
         :width: 100%
         :align: center
         :alt: Log message

#. Click the ``http://127.0.0.1:8888`` link at the top of the app to open AiiDAlab in the browser

   .. note::

      If you selected a port other than ``8888``, you can change the port in the URL

#. You will now be redirected to the :doc:`AiiDAlab home page <../home>`
