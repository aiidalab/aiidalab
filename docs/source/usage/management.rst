.. _app-management:

=============
Managing apps
=============

You can manage apps in AiiDAlab from the **Terminal**.
We also provide a graphical user interface for app management.
You can access it by clicking on **Manage App** in the home page container of an app.

.. _app-management:upgrade:

Upgrade/downgrade an app
************************

.. tab-set::

   .. tab-item:: App Manager

      .. grid:: 1
         :gutter: 3
         :margin: 0
         :padding: 0

         .. grid-item-card:: Step 1: Find the app you would like to upgrade on the start page

            On the home app start page, simply look for the app you would like to upgrade.

            .. image:: ../_static/app-management-start-page-upgrade-available.png

            Click on the **Manage App** button to open the app manager.

         .. grid-item-card:: Step 2: Open the App Management page

            The green :fa:`arrow-circle-up` **Update** button indicates that there is a newer version of the app available.

            .. image:: ../_static/app-management-upgrade-available.png

            Click on the :fa:`arrow-circle-up` **Update** button to upgrade the app.

            By default, the app will be upgraded to the latest available version, however you can alternatively select any available version, including a version that is lower than the currently installed one.

   .. tab-item:: Terminal

      Within the :fa:`terminal` Terminal, execute the following command to upgrade:

      .. code-block:: console

         $ aiidalab install <app-name>

      This will install the most recent version of an app, regardless of whether it is already installed or not.
      You will be prompted to confirm the operation.

      You can install a specific version, by using standard `PEP 440 version specifiers`_, for example:

      .. code-block:: console

         $ aiidalab install quantum-espresso==v22.01.0

.. _uninstall-app:uninstall:

Uninstall an app
****************

.. tab-set::

   .. tab-item:: App Manager

      .. grid:: 1
         :gutter: 3
         :margin: 0
         :padding: 0

         .. grid-item-card:: Step 1: Find the app you would like to uninstall on the start page

            On the home app start page, simply look for the app you would like to uninstall.

            .. image:: ../_static/app-management-start-page.png

            Click on the **Manage App** button to open the app manager.

         .. grid-item-card:: Step 2: Uninstall

            The app manager allows you to uninstall the app or to install a different version.

            .. image:: ../_static/app-management-app-installed.png

            Click on the :fa:`trash` **Uninstall** button to uninstall the app.

            .. note::

               In some cases you will see a warning that uninstalling the app might lead to data loss.
               That warning indicates that there are local modifications to the app source code.
               You can safely ignore this warning and click on the "Ignore" check box in case that you are sure that any local modifications are safe to delete.

   .. tab-item:: Terminal

      Within the :fa:`terminal` Terminal, execute the following command to uninstall an app:

      .. code-block:: console

         $ aiidalab uninstall <app-name>

      You will be prompted to confirm the operation.

.. _PEP 440 version specifiers: https://www.python.org/dev/peps/pep-0440/#version-specifiers
