.. _aiidalab-launch:

AiiDAlab launch
***************

.. important::

   The following steps require a local installation of Docker. You can verify your Docker installation by running ``docker run hello-world`` in the terminal.

`AiiDAlab launch`_ is a thin Docker wrapper which takes care of all the prerequisites to run the AiiDAlab Docker image.
It helps to manage multiple AiiDAlab profiles, each with its own home directory for persistent storage, and allows to easily switch between them.
To use AiiDAlab launch, make sure to first **install Python** (if not already available), then

#. Install AiiDAlab launch with `pipx <https://pypa.github.io/pipx/installation/>`_ (**recommended**):

   .. code-block:: console

      pipx install aiidalab-launch

   or directly with pip

   .. code-block:: console

      pip install aiidalab-launch

   .. note::

      If you install via `pipx` and run into issues using `aiidalab-launch`, try using `pip` directly.

#. Set up a new profile using one of the following images:

   * AiiDAlab pre-configured with the `Quantum ESPRESSO app <https://aiidalab-qe.readthedocs.io/index.html>`_ (**recommended**)

     .. code-block:: console

      aiidalab-launch profile add --image aiidalab/qe:latest aiidalab

   * Bare AiiDAlab

     .. code-block:: console

      aiidalab-launch profile add --image aiidalab/full-stack:latest aiidalab

   At the prompt, enter `n` to skip editing the profile settings.

#. Start AiiDAlab with

   .. code-block:: console

       aiidalab-launch start -p aiidalab

#. Follow the URL on the screen to open AiiDAlab in the browser

.. tip::

   For more detailed help, run

   .. code-block:: console

      aiidalab-launch --help

Profile Management
^^^^^^^^^^^^^^^^^^

As shown above, you can manage multiple profiles in AiiDAlab launch, e.g., with different home directories or ports. For more information, run

.. code-block:: console

   aiidalab-launch profile --help

You can inspect the status of all configured AiiDAlab profiles with

.. code-block:: console

   aiidalab-launch status

.. _`AiiDAlab launch`: https://github.com/aiidalab/aiidalab-launch
