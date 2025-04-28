.. _local-install:

Local Docker Instance
=====================

.. note::

   If you used another method to access AiiDAlab, you may proceed to :doc:`learn about AiiDAlab's features <../home>`.

AiiDAlab is available as a Docker image, a blueprint for a self-contained, pre-configured environment including all the necessary software to access the AiiDAlab platform. The following sections will guide you through the necessary steps to create a local AiiDAlab instance (Docker container) from this image.

.. _install-docker:

Installing Docker
*****************

.. important::

   If you already have Docker installed, **please ensure that your user account is part of** the ``docker`` or ``docker-users`` **group** (system-dependent). If you are unsure, please follow the instructions in the **important** box corresponding to your operating system.

Windows/Mac
-----------

.. raw:: html

   We recommend to install  <a href="https://docs.docker.com/get-docker" target="_blank">Docker Desktop</a>, a convenient graphical user interface (GUI) for Docker, which simplifies the process of managing containers.

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

.. raw:: html

   Though Docker Desktop is available for Linux, we recommend the simpler option of installing the <a href="https://docs.docker.com/engine/install" target="_blank">Docker Engine</a>.

.. important::

   .. raw:: html

      <p>
         <b>For Linux users</b>, please follow the <a href="https://docs.docker.com/engine/install/linux-postinstall/" target="_blank">post-installation steps for Docker Engine</a>.
      </p>

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
