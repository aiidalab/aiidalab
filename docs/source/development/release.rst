:orphan:

****************************
Release definition and guide
****************************

The AiiDAlab in general definition is not a single tool but an infrustructure contains multiple componets. 
It is run or deployed on an tengible machine. 
We don't have a version tag for AiiDAlab specificly which cause the problem that it is hard to measure the progress of development.

All base dependencies have their version tag and developed incrementally.
Once there are breaking features or important fixes, we shouldn't wait and postpone the release of the new version.

Base dependencies
=================

Defined in ``https://github.com/aiidalab/aiidalab-docker-stack/blob/main/build.json``, the full-stack which we used for all production deployment and as the default stack of aiidalab-launch, contain the base dependencies that when new version relesae, the `aiidalab-docker-stack` required version bump with the corresponding package version bump. 

These dependencies are:
- aiida-core will influent the plugin compatibilities, the frequencies are 2~3 months and we only follow the update of:
    - the minor version update
    - the patch version bumper with crucial bugfix that cause server issue to AiiDAlab ecosystem. (See the real-world example we just encountered: https://github.com/aiidalab/aiidalab-docker-stack/pull/362)
- aiidalab which contain the tools for app management and for app register. I personally think this show not be in the list but the version is deduct from `aiidalab-home`. 
- `aiidalab-home` is the app that not provide the app entry point in the index page but ensential for the tools show in the index page and also the app management widgets. 
- python version showed be less aggressive to keep the most tested version. To bring the new features of programing without bring burden to developers. The princeple is following the python version of `aiida-core`, and use the second latest version defined in `aiida-core`. For example, when `3.11` is supported by `aiida-core`, we then start to support `3.10` for aiidalab ecosystem.
    - pgsql version bump require involving with the database migrate which influence all users in all deployment include also the localhost container running. Therefore, we need to conservative to update this version. (Every year we have a discussion.) But the migration will be much easier if we have the home tool to allow user to migrate by themself, thanks to @yakutovicha work on database migration.

All version bump of the packages above will eventually lead to the version update of the `aiidalab-docker-stack`. 
The version of ``aiidalab`` and ``aiidalab-home`` is later introduced to the `build.json` file. 
It means if as defined above, we keep the aiidalab-home in the list, we better to have a tag for it as well. 
This is a good practice in my opinion. 
Because the backend python version and aiida-core version are more reveal in background which means users have no intuitive feeling how the AiiDAlab is changing. 
But the aiidalab-home have potential to bring new layout, new tools to the index page which will be highlight for the updates.

Production deployments
======================

The new release of the aiidalab-docker-stack will create new docker stacks to be used in deployments. 
We now have following core maintained deployments that required to having either the stable deployment for users running production and robust calculation or the edge deployment where we want to have all the edge features. The edge deployment is very important for us to show the progress quickly to the project reviews. 
It also enssential for developers to have an integrated pack of packges to run and test the edge features.

- aiidalab.materialscloud.net (Production, need to be robust and conservativly update)
- dev-aiidalab.materialscloud.net (staging, edge deployment and used to display the newest feature to public). It is currently deployed by ansible, we plan to using the standard z2jh k8s deployment with the help from CSCS.
- theospc7.epfl.ch (THEOS AiiDAlab test server, staging and the QeApp is the essential to be the latest)
- dev-aiidalab.psi.ch (psi server, which is for test purpose at the moment.)
- localhost running through `aiidalab-launch`, need to have latest image supported and backward for running the old images (Now, we support to run `aiidalab/aiidalab-docker-stack` images.).


The definition of AiiDAlab relase
=================================

Based on time, just like ubuntu version 23-04, 24-10 for next two releases.

The AiiDAlab team can keep its own pace on making the progress and anouncement. 
However, we have encountered the issue that to support the AiiDA 2.x we delay a lot for having the release annouce since plenty of unexpected issues appread and achitecture of docker stacks cahnges.
Now we introduce the concept of core dependencies, which is designed for apps that if the core dependencies are not meet, the app manager will prevent it from installing. This relieve the issuet that the core developers need to coordinates with app developers to wait the new app support. 
Meanwhile the empty list of the app is a very good reminder for app developers to priorities there work on support the new AiiDAlab. 

At the moment, we only have `aiida-core` in the core dependencies. 
Which means that once the app support the aiida-core version of new AiiDAlab, the app will have the newly supported version show in the app manager.

The break design change and important AWB interface change
----------------------------------------------------------

This can always go in slow but stady pace and make the anouncement in half year base.
The problem is the breaking changes are hard to measure the working load since sometime the changes tangle in between varias core packages.