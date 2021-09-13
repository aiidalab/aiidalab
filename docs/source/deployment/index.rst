===============
Deploy AiiDAlab
===============

There are several ways one can deploy AiiDAlab: locally for oneself, on a server for multiple users, or on a Kubernetes cluster for many users and high availability and scalability.
All these approaches rely on the fact that AiiDAlab is served as a Docker image.


***********************
Deploy AiiDAlab locally
***********************

This is by far the easiest way of getting started with AiiDAlab.


Prerequisites
-------------

Linux or MacOS with `Docker installed <https://www.docker.com/get-started>`__


Instructions
------------

Clone the `AiiDAlab Docker Stack <https://github.com/aiidalab/aiidalab-docker-stack>`__ repository and enter it:

   .. code-block:: console

       $ git clone https://github.com/aiidalab/aiidalab-docker-stack
       $ cd aiidalab-docker-stack

Then, start AiiDAlab by running:

   .. code-block:: console

       $ ./run.sh 8888 ~/aiidalab

Feel free to choose a different port and directory (path needs to be absolute).

The startup procedure can take a while, particularly when you run it for the first time.
Once it is done, open the link provided at the bottom of the console.


*************************
Deploy an AiiDAlab server
*************************

For medium-sized deployments (a handful of users), an AiiDAlab multi-user server can deployed on a single (virtual or bare-metal) machine.

Since deploying a multi-user server requires additional packages, such as `JupyterHub <https://jupyter.org/hub>`__, `DockerSpawner <https://github.com/jupyterhub/dockerspawner>`__, `Apache HTTP Server <https://www.apache.org/>`__, and `Docker <http://www.docker.com>`__, we provide the ``aiidalab-server`` `Ansible <https://www.ansible.com/>`__ role which automates the setup of the server.
Please see the `corresponding git repository <https://github.com/aiidalab/ansible-role-aiidalab-server>`__ for more information.


***************************************
Deploy AiiDAlab on a Kubernetes cluster
***************************************

If you are expecting to a large number of users (>50), consider deploying AiiDAlab on a scalable Kubernetes cluster.
To deploy AiiDAlab in a Kubernetes environment, you might want to follow the `instructions <https://github.com/aiidalab/aiidalab-k8s>`__ that we have prepared to simplify the setup process.
