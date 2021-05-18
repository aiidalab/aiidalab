===============
Deploy AiiDAlab
===============

There are several ways one can deploy AiiDAlab: locally for oneself, on a server for multiple users, or on a Kubernetes cluster for many users and high availability and scalability.
All these approaches rely on the fact that AiiDAlab is served as a Docker image.


***********************
Deploy AiiDAlab locally
***********************

This is by far the easiest way of getting started with AiiDAlab.
First, you need to make sure that Docker is installed on your machine, otherwise, go to `Get Started with Docker <https://www.docker.com/get-started>`__ page and follow the instructions for your operating system.
Once the Docker is installed, clone the `AiiDAlab Docker Stack <https://github.com/aiidalab/aiidalab-docker-stack>`__ repository and enter it.

   .. code-block: console

       $ git clone https://github.com/aiidalab/aiidalab-docker-stack
       $ cd aiidalab-docker-stack

Then, start AiiDAlab by running:

   .. code-block:: console

       $ ./run.sh 8888 ~/aiidalab

Feel free to choose a different port and directory.

You should wait until the start-up procedure is completed.
Once it is done, you can open the link that has been prompted for you at the end of the execution in your browser.


*************************
Deploy an AiiDAlab server
*************************

Deploying an AiiDAlab server requires installing several packages such as `JupyterHub <https://jupyter.org/hub>`__, `DockerSpawner <https://github.com/jupyterhub/dockerspawner>`__, `Apache HTTP Server <https://www.apache.org/>`__, and `Docker <http://www.docker.com>`__.
Further, one needs to configure the interactions between those services.
The final step is to download the `aiidalab-docker-stack <https://hub.docker.com/repository/docker/aiidalab/aiidalab-docker-stack>`__ Docker image and tag it as `aiidalab-docker-stack:latest`.
All of these steps can be either done manually or one could employ `Ansible <https://www.ansible.com/>`__ for these purposes.
We have prepared an automated `Ansible role <https://github.com/aiidalab/ansible-role-aiidalab-server>`__ for you to use, which does all the aforementioned steps automatically.


***************************************
Deploy AiiDAlab on a Kubernetes cluster
***************************************

If you are expecting to have a big number of users users, a good idea would be to deploy AiiDAlab on a scalable Kubernetes cluster.
To deploy AiiDAlab in a Kubernetes environment, you might want to follow the `instructions <https://github.com/aiidalab/aiidalab-k8s>`__ that we have prepared to simplify the setup process.
