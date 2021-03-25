#######
Widgets
#######

AiiDAlab largely dependents on Jupyter widgets for the graphical user interface (GUI).
More specifically, the `Ipywidgets <https://ipywidgets.readthedocs.io/>`_ package is the primary tool for creating AiiDAlab apps. 
We have also created the `aiidalab-widgets-base <https://github.com/aiidalab/aiidalab-widgets-base>`_ that is based on `Ipywidgets` and provides tools to interact with AiiDA.

**********
Ipywidgets
**********

`Ipywidgets <https://ipywidgets.readthedocs.io/>`_ is a python package that provides interactive widgets to be used in Jupyter notebooks. 
Widgets are eventful python objects, which shows GUI components such as a slider, button, etc.

Ipywidgets provides base widgets like sliders, progressbar, buttons, checkbox, dropdown, radio buttons, text, textarea, label, etc. 
The widgets have properties and value, which can be connected to the python codes and upated dynamically.
For a simple example, one can use a slider to control the value of a variable.

.. code-block:: python

    from ipywidgets import FloatSlider

    w = FloatSlider(value=0.0, min=0.0, max=10.0, description="b:");
    a = 0.0;

    def slider_change(change):
        global a

        print(change["old"])
        print(change["new"])

        a = a + w.value

    a.obersve(slider_change, names="value")

In this example, the ``slider_change`` function will be called each time the slider' value being updated.

Traitlets
=================

In ipywidgets, all the widgets are using the `traitlets <https://traitlets.readthedocs.io/>`_ types for the parameters.
As shown in the example above, the value of the FloatSlider is a Float trait type.
One can not only show the current value ``value["new"]`` but also the old value ``value["old"]``.
Traits can emit change events when the attributes are upated. This is very useful for creating custom widgets.

Custom widgets
==============

Ipywidgets package also supports developers in creating their own widgets.
There is a detailed `tutorial <https://ipywidgets.readthedocs.io/en/stable/examples/Widget%20Custom.html>`_ to show how to develop a custom widget.
In the ipywidgets framework is based on the Comm framework.
In the Comm framework, the change events of the traits leads to send a json massage to the Jupyter kernel.
Then, the frontend will update accordingly. 

Develop the custom widgets mainly involve two parts:

* **Python**: in the Python part, one needs to define the APIs of the widgets.
  For instance, the color of the widget's background. 
  The traits types should be initialized as:
  

.. code-block:: python

    from traitlets import Unicode

    color = Unicode('').tag(sync=True)

* **Javascript** (or TypeScript): the javascript part is for the frontend of the widgets.
  The frontend uses the `backbone.js <https://backbonejs.org/>`_ framework. 
  The communications between the Python and Javascript parts are from the set and get functions of the traits.

.. code-block:: javascript

    let color = this.model.get('color');

    this.model.set('color', 'red');

The change of the traits can be monitored and triggle javascript function.

.. code-block:: javascript

    this.model.on('change:color', this._color_change);

Here is a list for some useful custom widgets:

* `widget-periodictable <https://github.com/osscar-org/widget-periodictable>`_ : A interactive periodic table.
* `widget-bandsplot <https://github.com/osscar-org/widget-bandsplot>`_ : A widget to plot bandstructure and density of states.
* `widget-jsmol <https://github.com/osscar-org/widget-jsmol>`_ : A widget to use the molecular visualizer Jmol inside the Jupyter.

*********************
AiiDAlab base widgets
*********************

Molecular and material simulations always need database parser, molecular visulizer and editor, image render tools etc.
Here, we privde the `aiidalab-widgets-base <https://github.com/aiidalab/aiidalab-widgets-base>`_ , which is a collection of these tools.
Developers can easily reuse it to develop AiiDAlab apps. 
Read more information at `https://aiidalab-widgets-base.readthedocs.io <https://aiidalab-widgets-base.readthedocs.io/>`_ .

.. image:: aiidalab-widgets-base.gif
    :width: 600px
    :align: center
    :alt: text
