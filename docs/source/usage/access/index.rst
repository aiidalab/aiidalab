===============
Access AiiDAlab
===============

We provide several options for accessing AiiDAlab, depending on your needs and technical background.

.. grid:: 1 1 1 1
   :gutter: 3
   :margin: 0
   :padding: 0

   .. grid-item-card:: AiiDAlab Demo Server
      :text-align: center
      :shadow: md

      Access the online demo server to explore AiiDAlab without any installation. The demo server is pre-configured with the `Quantum ESPRESSO app <https://aiidalab-qe.readthedocs.io/>`_, including example workflows and tutorials, to help you get started with AiiDAlab.

      ++++

      .. button-link:: https://demo.aiidalab.io/
         :expand:
         :color: primary
         :outline:

         To the demo server

.. important::

   The demo server is **reset periodically**, removing all user data and installed apps.
   Therefore, it is recommended to use the demo server **only for testing and exploration**, and not for storing important data.

----

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

----

You can also ask your group or institutional admin to install an AiiDAlab server for you (refer to the :doc:`deployment guide <../../admin/index>`).

.. toctree::
   :maxdepth: 1
   :hidden:

   local
