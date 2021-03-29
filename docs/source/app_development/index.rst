.. _develop-apps:

#####################
Develop AiiDAlab apps
#####################

Overview of the separate in-depth sections in this part of the documentation:

.. toctree::
    :maxdepth: 1

    create.rst
    first_app.rst
    publish.rst

To get an idea of how proper apps may be built and used, you can check out these examples:

.. toctree::
    :maxdepth: 1

    example_qebands.rst

Below is a short overview of each main section.
It is recommended to follow the sections step-by-step when creating your first AiiDAlab app.

Create app
==========

:ref:`Go directly to section<develop-apps:create-app>`

This section describes the overall steps you need to consider when developing an app for AiiDAlab.

First, to create an app, there are two conventional paths:

#. :ref:`develop-apps:create-app:variant-a_cookiecutter`
#. :ref:`develop-apps:create-app:variant-b_from-scratch`

The first utilizes the `app cookiecutter <https://github.com/aiidalab/aiidalab-app-cutter>`__, which will guide you through a series of user inputs, which together will define the app with its necessary configuration options.

The other option is to create the app from scratch.
This is more cumbersome, but provides a more in-depth understanding of how AiiDAlab interfaces with an app.

Build app
=========

:ref:`Go directly to section<develop-apps:first-app>`

A very simplistic example of how your first AiiDAlab app may be set up and built.

For more advanced examples see :ref:`develop-apps:example-qe_bands`.

Publish app
===========

:ref:`Go directly to section<develop-apps:publish-app>`

After creating the app, you need to register it with the `AiiDAlab registry <https://github.com/aiidalab/aiidalab-registry>`__ in order for other users to benefit from it.

To learn more about this, please see :ref:`develop-apps:publish-app`.
