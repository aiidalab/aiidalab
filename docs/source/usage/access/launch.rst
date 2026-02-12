.. _aiidalab-launch:

AiiDAlab launch
***************

.. important::

   The following steps require a local installation of Docker. You can verify your Docker installation by running ``docker run hello-world`` in the terminal.

.. raw:: html

   <p>
      <a href="https://github.com/aiidalab/aiidalab-launch" target="_blank">AiiDAlab launch</a> is a thin Docker wrapper which takes care of all the prerequisites to run the AiiDAlab Docker image.
      It helps to manage multiple AiiDAlab profiles, each with its own home directory for persistent storage, and allows to easily switch between them.
      To use AiiDAlab launch, please follow these steps:
   </p>

#. Install AiiDAlab launch using one of the following methods:

   * ``pipx`` (**recommended**)

     .. raw:: html

         <ul>
            <li>
               <a href="https://pipx.pypa.io/stable/" target="_blank">Install pipx</a>, then run
               <pre>pipx install aiidalab-launch</pre>
            </li>
         </ul>

     .. note::

         We recommend using ``pipx`` to install AiiDAlab launch, as it creates an isolated environment for the application, avoiding potential conflicts with other Python packages. If you run into issues, please use ``pip`` (see below).

   * ``pip`` (requires a Python installation)

     .. raw:: html

         <ul>
            <li>
               <a href="https://www.python.org/" target="_blank">Install Python</a> if not already available, then run
               <pre>pip install aiidalab-launch</pre>
            </li>
         </ul>

#. Set up a new profile using one of the following images:

   * AiiDAlab pre-configured with the Quantum ESPRESSO app (**recommended**)

     .. code-block:: console

      aiidalab-launch profile add --image aiidalab/qe:latest aiidalab

     .. tip::

         .. raw:: html

            <p>
               We recommend this pre-configured image, as it includes much of the mechanics necessary to run a calculation on AiiDAlab.
               To learn more about the app, please visit the <a href="https://aiidalab-qe.readthedocs.io/index.html" target="_blank">AiiDAlab Quantum ESPRESSO app documentations</a>.
            </p>

   * Bare AiiDAlab (no pre-installed apps)

     .. code-block:: console

      aiidalab-launch profile add --image aiidalab/full-stack:latest aiidalab

   At the prompt, enter ``n`` to skip editing the profile settings.

#. Start AiiDAlab with

   .. code-block:: console

       aiidalab-launch start -p aiidalab

#. Follow the URL on the screen to open AiiDAlab in the browser

Profile Management
^^^^^^^^^^^^^^^^^^

As shown above, you can manage multiple profiles in AiiDAlab launch, e.g., with different home directories or ports. For more information, run

.. code-block:: console

   aiidalab-launch profile --help

You can inspect the status of all configured AiiDAlab profiles with

.. code-block:: console

   aiidalab-launch status

.. tip::

   For more detailed help, run

   .. code-block:: console

      aiidalab-launch --help
