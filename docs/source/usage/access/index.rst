===============
Access AiiDAlab
===============

We provide several options for accessing AiiDAlab, depending on your needs and technical background.

Demo server
-----------

We provide the `AiiDAlab demo server <https://demo.aiidalab.io/>`_, a temporary instance hosted online for demonstration purposes.
The server comes with the `Quantum ESPRESSO app <https://aiidalab-qe.readthedocs.io/>`_ pre-installed, including example workflows and tutorials, to help you get started with AiiDAlab.

.. important::

   The demo server is **reset periodically**, and any data you upload or create will be lost after a certain period.
   Therefore, it is recommended to use the demo server **only for testing and exploration**, and not for storing important data.

Local instance
--------------

Please select one of the following options for accessing AiiDAlab.

.. grid:: 1 1 2 2
   :gutter: 3
   :margin: 0
   :padding: 0

   .. grid-item-card:: Local Docker Instance
      :text-align: center
      :shadow: md

      Install Docker locally and run an instance of the AiiDAlab image. No prior knowledge of Docker necessary!

      ++++

      .. button-ref:: local
         :ref-type: doc
         :click-parent:
         :expand:
         :color: primary
         :outline:

         To the guide

   .. grid-item-card:: Virtual Machine Image
      :text-align: center
      :shadow: md

      Download a virtual machine image for AiiDAlab based on Quantum Mobile, *pre-configured** with everything you need to run AiiDAlab.

      ++++

      .. button-link:: https://quantum-mobile.readthedocs.io/
         :click-parent:
         :expand:
         :color: primary
         :outline:

         To the download page

Deployed server
---------------

You can also ask your group or institutional admin to install an AiiDAlab server for you (refer to the :doc:`deployment guide <../../admin/index>`).

.. toctree::
   :maxdepth: 1
   :hidden:

   local
