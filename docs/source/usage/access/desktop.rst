.. _docker-desktop:

Docker Desktop
**************

Follow these instructions to spin up an AiiDAlab container:

#. Open the Docker Desktop app
#. On the left sidebar, click on *Images*
#. In the search bar at the top of the app, type ``aiidalab/full-stack``
#. Select ``latest`` from the *tag* dropdown menu
#. Click *Pull* to download the image

   * Once downloaded, the image will appear as a new line in the list of images
   * Exit the search menu when done

#. At the far right column of the new image line, under actions, click ▶️ to start a container instance
#. In the pop-up window, expand *optional settings*
#. You may choose to name the container for easy reference (randomly generated otherwise)
#. Choose a local port from which to communicate with the container's 8888 port
#. Set up the following local volumes:

   .. important::

      To avoid losing your work when the container shuts down (manually, or when the machine is turned off), it is important to associate the container with a volume - a local directory - with which the container data's is mirrored. When set up, the container will restart from this mirrored volume.

   * ``<local-docker-volumes-dir>\aiidalab_home`` --> ``/home/jovyan``
   * ``<local-docker-volumes-dir>\aiidalab_conda`` --> ``/home/jovyan/.conda``

   .. note::

      ``local-docker-volumes-dir`` can be any local directory in which to store Docker volumes, for example, on a Windows machine, this could be ``C:\Users\<username>\Docker\``


#. Click *Run* to start the container
#. On the left sidebar, click on *Containers*
#. Click on the name of your newly-created container
#. Wait for the container build process to finish

   * The log will show a line ``To access the notebook, open this file in a browser:``

#. Click on the ``<port>:8888`` link at the top of the app to open AiiDAlab in the browser
#. Copy and paste the container's token to the browser and submit to open AiiDAlab

   * The token can be found at the bottom of the log in a line similar to ``...?token=<long-hash>``

   .. note::

      Subsequent connections to the port in the browser will not prompt for a token for some time. If and when it does, you may again retrieve the token from the log.
