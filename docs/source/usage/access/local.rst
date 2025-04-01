.. _local-install:

Local Docker Instance
=====================

.. note::

   If you used another method to access AiiDAlab, you may proceed to :doc:`learn about AiiDAlab's features <../home>`.

AiiDAlab is available as a Docker container, a self-contained, pre-configured environment including all the necessary software to access the AiiDAlab platform. To run the container, you will first need to :ref:`install Docker <install-docker>` on your local machine.

.. _install-docker:

Installing Docker
*****************

Windows/Mac
-----------

We recommend to install `Docker Desktop <https://docs.docker.com/get-docker>`_, a convenient graphical user interface (GUI) for Docker, which simplifies the process of managing containers.

.. important::

   **For Windows users**, if your admin account is different to your user account, you must add the user to the **docker-users** group.

   From a Windows terminal

   .. code::

      net localgroup docker-users <username> /add

   or, if using WSL, from a bash terminal

   .. code::

      sudo usermod -aG docker <username>

Linux
-----

Though Docker Desktop is available for Linux, we recommend the simpler option of installing the `Docker Engine <https://docs.docker.com/engine/install/>`_.

.. important::

   **For Linux users**, please follow the `post-installation steps for Docker Engine <https://docs.docker.com/engine/install/linux-postinstall/>`_.

Launching AiiDAlab
******************

Once Docker is installed, you can create and launch the container by using the following options:

.. tip::

   Regardless of the option chosen here to create the AiiDAlab container, you can always use the Docker Desktop GUI to conveniently view and manage all images, containers, and volumes.

.. grid:: 1 1 3 3
   :gutter: 3
   :margin: 0
   :padding: 0

   .. grid-item-card:: AiiDAlab Launch CLI
      :text-align: center

      .. raw:: html

         <span style="color: #459db9;"><b>Linux/Mac users</b></span>
         <hr>

      Automate container setup with our handy *aiidalab-launch* CLI.

      ++++

      .. button-ref:: launch
         :ref-type: doc
         :click-parent:
         :expand:
         :color: primary
         :outline:

         Instructions

   .. grid-item-card:: Docker Desktop GUI
      :text-align: center

      .. raw:: html

         <span style="color: #459db9;"><b>Windows users</b></span>
         <hr>

      Use the graphical interface to configure the container, including ports, mounts, environment variable, etc.

      ++++

      .. button-ref:: desktop
         :ref-type: doc
         :click-parent:
         :expand:
         :color: primary
         :outline:

         Instructions

   .. grid-item-card:: Docker CLI
      :text-align: center

      .. raw:: html

         <span style="color: #459db9;"><b>Advanced users</b></span>
         <hr>

      Manually set up a container using the Docker CLI. Most flexible, but requires prior knowledge of Docker.

      ++++

      .. button-ref:: direct
         :ref-type: doc
         :click-parent:
         :expand:
         :color: primary
         :outline:

         Instructions

.. toctree::
   :maxdepth: 1
   :hidden:

   launch
   desktop
   direct
