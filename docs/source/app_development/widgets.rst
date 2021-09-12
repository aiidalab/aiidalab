.. _develop-apps:widgets:

####################
Use AiiDAlab widgets
####################

AiiDAlab largely relies on `Jupyter widgets <https://ipywidgets.readthedocs.io/en/latest/>`_, also known as ``ipywidgets``, for the graphical user interface (GUI).
We have created a collection of reusable widgets that are already integrated with AiiDA and help you accomplish common tasks.

****************
AiiDAlab widgets
****************

AiiDAlab apps typically involve some of the following steps:

 * prepare the input for a calculation (e.g. an atomic structure)
 * select computational resources and submit a calculation to AiiDA
 * monitor a running calculation
 * find and analyze the results of a calculation

The AiiDAlab widgets help with these common tasks and are preinstalled in the AiiDAlab environment.
Please see `https://aiidalab-widgets-base.readthedocs.io <https://aiidalab-widgets-base.readthedocs.io/>`_ for documentation on the individual widgets.

.. image:: ./include/aiidalab-widgets-base.gif
    :width: 600px
    :align: center
    :alt: text


.. _develop-apps:widgets:more-widgets:

************
More widgets
************

* `ipywidgets`_: basic GUI components, such as a text, sliders, buttons, progress bars, drowdowns, etc.
* `widget-periodictable <https://github.com/osscar-org/widget-periodictable>`_ : interactive periodic table for element selection
* `widget-bandsplot <https://github.com/osscar-org/widget-bandsplot>`_ : plot electronic bandstructure and density of states
* `widget-jsmol <https://github.com/osscar-org/widget-jsmol>`_ : use the JSmol molecular visualizer inside a Jupyter notebook


**************************
Terminology and background
**************************

Widgets and traitlets
======================

Widgets are eventful Python objects that display GUI components, such as a sliders, buttons, progress bars, drowdowns, etc.
`ipywidgets`_ is a Python package that provides interactive widgets for the use in Jupyter notebooks.

Widgets can have one or more attributes, whose value can be _ovserved_ and accessed from Python such that we can react to changes to their values.
This is implemented using `traitlets <https://traitlets.readthedocs.io/>`_.

For example, try the following code in a Jupyter notebook:

.. code-block:: python

    from ipywidgets import FloatSlider

    # slider widget that has a `value` traitlet attribute
    slider = FloatSlider(value=273.0, min=100.0, max=500.0, description="Temperature [K]");

    # Access the slider value as `slider.value`
    # print(slider.value)

    def slider_change(change):
        """Handle slider changes.

        This function is called when the slider value is changed by the user.
        """
        print(change["old"])
        print(change["new"])
        if change["new"] > 373.0:
            print("Boiling now!")

    slider.observe(slider_change, names="value")

Creating your own widgets
=========================

Each widget consists of a Python component that defines how to interact with the widget from Python,
and a Javascript (or TypeScript) component that is responsible for the graphical representation of the widget and communicates updates back to the Jupyter kernel.

If the goal is to combine existing widgets into new, reusable components, this can be done in Python without touching the Javascript component.
See for example the `implementation of the AiiDAlab widgets <https://github.com/aiidalab/aiidalab-widgets-base>`_, most of which are of this type.

To modify the appearance of an existing widget or to create an entirely new visualization, one needs to write Javascript/TypeScript.
See the detailed `tutorial <https://ipywidgets.readthedocs.io/en/stable/examples/Widget%20Custom.html>`_ on how to develop a custom widget or have a look at some of the examples from :ref:`develop-apps:widgets:more-widgets`.

.. _ipywidgets: https://ipywidgets.readthedocs.io
