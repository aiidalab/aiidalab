=============================
Develop AiiDAlab applications
=============================

############################################################
Variant A: Quickstart using the AiiDAlab application cutter
############################################################

Open the terminal from the AiiDalab home page. On the terminal type:

   .. code-block:: console

       $ cd apps
       $ cookiecutter https://github.com/aiidalab/aiidalab-app-cutter.git
       app_name [template]: 
       ...

After answering the questions asked by the app cutter, you will find a new folder inside `apps` that contains the basic structure of the app.
In order to see the rendered version of your app, simply open (or reload) the home page.

**Note** In order to start keeping track of your development using `Git <https://git-scm.com/>`__, do:

   .. code-block:: console

       $ git init       # initialize repository
       $ git add -A     # add all files
       $ git commit     # store them in git

#####################################################
Variant B: Slowstart: set-by-step creation of an app.
#####################################################

In the following, we provide instructions for how to "manually" create your own app from scratch.
This section is kept only to clarify for you what would happen if you would launch a cookie-cutter job described in the previous section. 

Step 1: create a folder
=======================

This is all you need to do in order to make your app listed on your AiiDalab home page. Go to the terminal, enter the apps folder and then type:

   .. code-block:: console

       $ mkdir my_app

Once you have done this, just update the home page and you will see that your new app is already there!
However, one could see that the app still misses some things: it is not yet managed by Git, title and content of the app are missing as well:

.. _fig_intro_workchain_graph:
.. figure:: include/new_app.png
    :scale: 60
    :align: center

    Freshly created AiiDAlab app.

Step 2: initialize a git repo
=============================
To fix the first problem we go to the command line as well. We enter the app folder and initialize the git repo:

   .. code-block:: console

       $ cd my_app
       $ git init

Once you have done this , the text "Unable to determine availability of updates." on the app will be replaced by "Modified" which means that the app is now managed by the App Manager that can check for updates/or modifications.
If you now click on the "Manage App" button -- you will be redirected to the app's "home page" that is basically showing no information about the app (title, list of authors, description are missing).
This we are going to solve in the next step.

Step 3: add `metadata.json` file
================================

Go back to the terminal, create a new file called `metadata.json` and add the following information there (adapt it for your case) and update the page to see that changes were taken into account:

   .. code-block:: json

       {
           "description": "Example app that I just created",
           "title": "Example App",
           "authors": "X.Y. Author1, A.B. Author2"
       }




If you want to add a logo to your app, the only thing you need to do is to add the following line in your `metadata.json` and add the file `logo_filename.png` in the `my_app` folder:

   .. code-block::

       "logo": "logo_filename.png"



Step 4: make the app do something.
==================================

So far we have being working on make the app look nice and recognizable by the AiiDalab.
However, it was not doing any useful things.
To fix that we first go to the AiiDalab home page and we notice that our app is still missing `start.md` file.
At this point we actually have a choice: we can either create a static `start.md` file or a dynamic `start.py`.
We will take the first approach. Here is the minimal template:

   .. code-block:: md

       - [My App](./print_hello_world.ipynb)

Once you have done this, you can close the text editor and update the AiiDalab home page.
You will notice that it now has My App link that will bring you to a NON-existing page (because we haven't create one yet).
To fix this click on the `File Manager` icon, go to the :file:`apps/my_app` folder and click on the `New` button.
Select the `Python 3` option and make the following modifications:

- Rename it to `print_hello_world`.
- add a line `print ("Hello world!")` in the code cell.
- save the notebook and close it.

Now go back to AiiDalab Home page and click on the `My App` link again - it should bring you to a page that says "Hello wrold!"


##########################################
Publish your app on the AiiDalab registry.
##########################################
To make your application available for the other AiiDAlab users, please register it on the `AiiDAlab registry <https://github.com/aiidalab/aiidalab-registry>`__.
You should first clone the repository, add the following text to the :file:`apps.json` and make a `pull request <https://github.com/aiidalab/aiidalab-registry/compare>`__ to the AiiDAlab registry:

   .. code-block:: json

       {
          "aiidalab-widgets-base": {
              "git_url": "https://github.com/path/to/your/app.git",
              "meta_url": "https://raw.githubusercontent.com/path/to/master/metadata.json",
              "categories": ["utilities"]
          }
       }