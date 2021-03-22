.. _develop-apps:publish-app:

*****************************************
Publish your app on the AiiDAlab registry
*****************************************

To make your app available to other AiiDAlab users, please register it on the `AiiDAlab registry`_.

How to register
===============

.. warning::

    To be sure to have the latest information on the ``metadata.json`` JSON schema, see `the registry's repository README <https://github.com/aiidalab/aiidalab-registry/blob/master/README.md>`__.

In preparation of registering your AiiDAlab app in the `AiiDAlab registry`_, ensure you have a valid and updated ``metadata.json`` file in the root of your app's repository.
To see a full list of valid keys, go to `this README section <https://github.com/aiidalab/aiidalab-registry/blob/master/README.md#valid-keys-for-metadatajson>`__.

You should fork the `AiiDAlab registry`_ repository (click `here to fork <https://github.com/aiidalab/aiidalab-registry/fork>`__ or click the "Fork" button in the upper right corner of the repository's webpage.
To learn more about forking a GitHub repository, see their documentation `here <https://docs.github.com/en/github/getting-started-with-github/fork-a-repo>`__.

In your forked repository, you can create a new git branch and update the ``apps.json`` file found in the root of the repository.
The update consists of an addition to the JSON file, e.g.:

.. code:: json

    "my-app": {
        "git_url": "https://github.com/me/my-aiidalab-app.git",
        "meta_url": "https://raw.githubusercontent.com/me/my-aiidalab-app/main/metadata.json",
        "categories": ["quantum"]
    }

This example is for an AiiDAlab existing on GitHub under the user or organization named ``me`` called ``my-aiidalab-app``.

The ``meta_url`` value should be a URL pointing to the raw content of your valid and updated ``metadata.json`` file.

The complete list of categories that can be added to the ``categories`` list of values is available in the `AiiDAlab registry`_'s ``categories.json`` file.
You can find this either in the root of your forked repository or on GitHub `here <https://github.com/aiidalab/aiidalab-registry/blob/master/categories.json>`__.
Note, if in doubt, the linked online version is the source of truth for the categories and their description.

Here follows an overview of the categories (as of `commit 3b0627b <https://github.com/aiidalab/aiidalab-registry/blob/3b0627b5dcdb55cbe010438013a3091e8f8cbea9/categories.json>`__):

.. TODO: Make this auto-generated when building the documentation

=========  ===========================================================================
  Title                                    Description
=========  ===========================================================================
Classical  Apps for performing calculations based on classical/empirical force fields.
Quantum    Apps for performing quantum-mechanical calculations.
Setup      Apps for setting up and configuring your AiiDAlab environment.
Tutorials  Apps suitable for getting to know AiiDA and the AiiDAlab.
Utilities  Utility apps for everyday tasks.
=========  ===========================================================================

Finally, you ``git push`` your branch with the updated ``apps.json`` to your fork on GitHub and `create a pull request (PR) https://github.com/aiidalab/aiidalab-registry/compare>`__ against the ``master`` branch of `AiiDAlab registry`_.

The PR will be reviewed by the AiiDAlab developers, which may result in you having to make changes, and when it is finally merged with the `AiiDAlab registry`_ repository, it will shortly become available on the `AiiDAlab registry webpage`_, as well as in the AiiDAlab app store.

.. image:: https://raw.githubusercontent.com/aiidalab/aiidalab-registry/master/make_ghpages/static/gotobutton.svg
    :alt: Go to AiiDAlab app registry
    :align: center
    :target: `AiiDAlab registry webpage`_

About the AiiDAlab registry
===========================

.. TODO: Insert reference to section on AiiDAlab App Registry

.. _AiiDAlab registry: https://github.com/aiidalab/aiidalab-registry
.. _AiiDAlab registry webpage: http://aiidalab.github.io/aiidalab-registry
