.. _develop-apps:widgets:

###########################
Use/create AiiDAlab widgets
###########################

AiiDAlab largely relies on `Jupyter widgets <https://ipywidgets.readthedocs.io/en/latest/>`_, also known as ``ipywidgets``, to build interactive graphical user interfaces (GUIs).
Widgets provide a convenient way to combine Python logic with browser-based controls and visualizations.

AiiDAlab provides a collection of reusable widgets integrated with AiiDA to help developers implement common scientific workflows.


****************
AiiDAlab widgets
****************

AiiDAlab apps typically involve some of the following steps:

* Prepare calculation inputs, such as an atomic structure.
* Select computational resources and submit calculations through AiiDA.
* Monitor running calculations.
* Find, visualize, and analyze calculation results.

The `AiiDAlab widgets <https://aiidalab-widgets-base.readthedocs.io/>`_ provide reusable components for these tasks and are preinstalled in the AiiDAlab environment.
Refer to their documentation for individual widgets and their APIs.

.. image:: ./include/aiidalab-widgets-base.gif
    :width: 600px
    :align: center
    :alt: Demonstration of AiiDAlab widgets


.. _develop-apps:widgets:more-widgets:

************
More widgets
************

Several additional widget libraries are available for building interactive scientific applications:

* `ipywidgets`_: General-purpose GUI components, such as text inputs, sliders, buttons, progress bars, and dropdowns.
* `widget-periodictable <https://github.com/osscar-org/widget-periodictable>`_: Interactive periodic table for selecting chemical elements.
* `widget-bandsplot <https://github.com/osscar-org/widget-bandsplot>`_: Interactive plots of electronic band structures and densities of states.
* `widget-jsmol <https://github.com/osscar-org/widget-jsmol>`_: JSmol molecular visualization in Jupyter notebooks.


**************************
Terminology and background
**************************

Widgets and traitlets
=====================

Widgets are Python objects connected to graphical components displayed in the browser.
The `ipywidgets`_ package provides a collection of interactive widgets for use in Jupyter notebooks.

Widget state is typically exposed through attributes called *traits*, implemented using `traitlets <https://traitlets.readthedocs.io/>`_.
Python code can access these attributes and observe changes, allowing the application to react to user interactions.

For example, try the following code in a Jupyter notebook:

.. code-block:: python

    from ipywidgets import FloatSlider

    slider = FloatSlider(
        value=273.0,
        min=100.0,
        max=500.0,
        description="Temperature [K]",
    )

    def slider_change(change):
        """React to changes in the slider value."""
        if change["new"] > 373.0:
            print("Boiling now!")

    slider.observe(slider_change, names="value")

    # The current value is available as slider.value.
    display(slider)

The ``value`` trait is synchronized between Python and the browser.
Whenever the user changes the slider value, the registered observer is called.

Observers remain registered until explicitly removed or their associated objects are destroyed.
When an observer is no longer needed, unregister it using:

.. code-block:: python

    slider.unobserve(slider_change, names="value")


Creating your own widgets
=========================

Widgets generally consist of two components:

* **Python:** Defines the widget's API, state, and interactions with Python code.
* **JavaScript or TypeScript:** Renders the graphical interface in the browser and communicates state changes with the Jupyter kernel.

When combining existing widgets into new, reusable components, development can often be done entirely in Python without writing JavaScript.

Many widgets in the `aiidalab-widgets-base repository <https://github.com/aiidalab/aiidalab-widgets-base>`_ follow this approach.

For custom visualizations, integration with JavaScript libraries, or more sophisticated frontend interactions, developers may need to implement their own JavaScript or TypeScript components.

We recommend considering `AnyWidget <https://anywidget.dev/>`_ for this purpose.


.. _develop-apps:widgets:anywidget:

Developing custom widgets with AnyWidget
========================================

`AnyWidget <https://anywidget.dev/>`_ simplifies the development of custom Jupyter widgets by eliminating much of the configuration and boilerplate traditionally required to build and distribute them.

AnyWidget builds on the existing Jupyter widgets ecosystem and uses traitlets to synchronize state between Python and JavaScript.

It offers several advantages:

* **Simpler development:** Create custom widgets without configuring a dedicated JupyterLab extension or complex build system.
* **Modern frontend technologies:** Use JavaScript, TypeScript, or frameworks such as React to develop sophisticated interactive components.
* **Hot module reloading:** Update frontend code during development without restarting the kernel.
* **Easy distribution:** Package and distribute widgets as ordinary Python packages.
* **Broad compatibility:** Use widgets across supported environments, including JupyterLab, Jupyter Notebook, and VS Code.


A simple example
----------------

An AnyWidget consists of a Python class defining its state and a JavaScript module defining its appearance and behavior.

The following example implements a simple counter widget:

.. code-block:: python

    import anywidget
    import traitlets


    class CounterWidget(anywidget.AnyWidget):
        _esm = """
        function render({ model, el }) {
            const button = document.createElement("button");

            const update = () => {
                button.textContent = `Count: ${model.get("count")}`;
            };

            button.addEventListener("click", () => {
                model.set("count", model.get("count") + 1);
                model.save_changes();
            });

            model.on("change:count", update);
            update();
            el.appendChild(button);

            return () => {
                model.off("change:count", update);
            };
        }

        export default { render };
        """

        count = traitlets.Int(0).tag(sync=True)


    CounterWidget()

The ``count`` trait is synchronized between Python and JavaScript.
Changes made in either environment are reflected in the other.

The JavaScript ``render`` function creates the interface and registers event handlers.
Its returned cleanup function unregisters the model observer when the widget view is removed.

For more information, see the `AnyWidget getting started guide <https://anywidget.dev/en/getting-started/>`_.


Organizing and packaging larger widgets
---------------------------------------

For simple widgets, embedding JavaScript directly in the Python class is convenient.
However, as a widget grows in complexity, we recommend separating its Python, JavaScript, and CSS code into dedicated files.

AnyWidget supports loading frontend assets from external files, making it straightforward to organize a widget as a small Python package.

For example:

.. code-block:: text

    my-widget/
    ├── pyproject.toml
    └── src/
        └── my_widget/
            ├── __init__.py
            ├── widget.py
            └── static/
                ├── widget.js
                └── widget.css

The Python widget class can then reference these files:

.. code-block:: python

    from pathlib import Path

    import anywidget
    import traitlets


    HERE = Path(__file__).parent


    class MyWidget(anywidget.AnyWidget):
        _esm = HERE / "static" / "widget.js"
        _css = HERE / "static" / "widget.css"

        value = traitlets.Unicode("").tag(sync=True)

The JavaScript module must export an AnyWidget-compatible ``render`` function, as demonstrated in the previous example.

Make sure that the JavaScript and CSS files are included in the Python package when building distributions.

For widgets with more sophisticated frontend requirements, such as React components or TypeScript, consider maintaining a dedicated frontend source directory and build process that produces the JavaScript and CSS assets distributed with the Python package.

AnyWidget supports modern frontend build tools such as Vite and esbuild.
See the `AnyWidget bundling guide <https://anywidget.dev/en/bundling/>`_ for further information.

When developing with external JavaScript files, AnyWidget also supports hot module reloading (HMR).
Enable it by setting the environment variable ``ANYWIDGET_HMR=1`` before starting Jupyter.


Maintaining widgets in separate repositories
--------------------------------------------

We recommend developing larger, reusable widgets in their own repositories, rather than embedding them directly in an AiiDAlab app.

This offers several benefits:

* **Reusability:** Widgets can be shared across multiple AiiDAlab apps and other Jupyter-based projects.
* **Independent development:** Widgets can evolve without being tied to the development cycle of a particular app.
* **Testing and maintenance:** Each widget can have its own tests, documentation, and continuous integration workflows.
* **Versioning and distribution:** Widgets can be released independently and installed as Python dependencies.
* **Separation of concerns:** Apps focus on scientific workflows and application logic, while widgets provide reusable interface components.

Not every custom widget needs its own package or repository.
Small, app-specific components can remain within the app's codebase.

However, once a widget becomes sufficiently complex or has potential for reuse, extracting it into a standalone package and repository is generally preferable.


Choosing the right approach
---------------------------

The choice of widget development approach depends on the complexity and intended reuse of the component:

* **Compose existing ipywidgets** when standard controls and Python callbacks provide the required functionality.
* **Use AnyWidget** when developing custom visualizations, integrating JavaScript libraries, or implementing sophisticated frontend behavior.
* **Create a standalone package** when a widget grows beyond a simple component or requires dedicated JavaScript and CSS files.
* **Maintain a separate repository** when a widget is sufficiently complex, reusable, or requires independent development and releases.

Regardless of the approach, remember to manage widget lifecycles carefully.
Event listeners, observers, timers, and background tasks should be cleaned up when they are no longer needed.

For additional guidance on custom widget development, see the `ipywidgets custom widget tutorial <https://ipywidgets.readthedocs.io/en/stable/examples/Widget%20Custom.html>`_ and the `AnyWidget documentation <https://anywidget.dev/>`_.


.. _ipywidgets: https://ipywidgets.readthedocs.io/
