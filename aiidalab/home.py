"""Module to generate AiiDA lab home page."""
from os import path
from glob import glob
from functools import wraps

import json
import traitlets
import ipywidgets as ipw
from IPython.display import display

# AiiDA lab imports.
from .app import AiidaLabApp
from .config import AIIDALAB_APPS
from .utils import load_widget, load_app_registry
from .widgets import UpdateAvailableInfoWidget


def create_app_widget_move_buttons(name):
    """Make buttons to move the app widget up or down."""
    layout = ipw.Layout(width="40px")
    app_widget_move_buttons = ipw.HTML("""
    <a href=./start.ipynb?move_up={name} title="Move it up"><i class='fa fa-arrow-up' style='color:#337ab7;font-size:2em;' ></i></a>
    <a href=./start.ipynb?move_down={name} title="Move it down"><i class='fa fa-arrow-down' style='color:#337ab7;font-size:2em;' ></i></a>
    """.format(name=name),
                                       layout=layout)
    app_widget_move_buttons.layout.margin = "50px 0px 0px 0px"

    return app_widget_move_buttons


def _workaround_property_lock_issue(func):
    """Work-around for issue with the ipw.Accordion widget.

    The widget does not report changes to the .selected_index trait when displayed
    within a custom ipw.Output instance. However, the change is somewhat cryptic reported
    by a change to the private '_property_lock' trait. We observe changes to that trait
    and convert the change argument into a form that is more like the one expected by
    downstream handlers.
    """

    @wraps(func)
    def _inner(self, change):
        if change['name'] == '_property_lock':
            if 'selected_index' in change['old']:
                fixed_change = change.copy()
                fixed_change['name'] = 'selected_index'
                fixed_change['new'] = change['old']['selected_index']
                del fixed_change['old']
                return func(self, fixed_change)

        return func(self, change)

    return _inner


class AiidaLabHome:
    """Class that mananges the appearance of the AiiDA lab home page."""

    def __init__(self):
        self.config_fn = ".launcher.json"
        self.output = ipw.Output()
        self.app_registry = load_app_registry()['apps']
        self._app_widgets = dict()

    def _create_app_widget(self, name):
        """Create the widget representing the app on the home screen."""
        config = self.read_config()
        app_data = self.app_registry.get(name, None)
        app = AiidaLabApp(name, app_data, AIIDALAB_APPS)

        if name == 'home':
            app_widget = AppWidget(app, allow_move=False)
        else:
            app_widget = CollapsableAppWidget(app, allow_move=True)
            app_widget.hidden = name in config['hidden']
            app_widget.observe(self._on_app_widget_change_hidden, names=['hidden'])

        return app_widget

    def _on_app_widget_change_hidden(self, change):
        """Record whether a app widget is hidden on the home screen in the config file."""
        config = self.read_config()
        hidden = set(config['hidden'])
        if change['new']:  # hidden
            hidden.add(change['owner'].app.name)
        else:  # visible
            hidden.discard(change['owner'].app.name)
        config['hidden'] = list(hidden)
        self.write_config(config)

    def write_config(self, config):
        json.dump(config, open(self.config_fn, 'w'), indent=2)

    def read_config(self):
        if path.exists(self.config_fn):
            return json.load(open(self.config_fn, 'r'))
        return {'order': [], 'hidden': []}  #default config

    def render(self):
        """Rendering all apps."""
        self.output.clear_output()
        apps = self.load_apps()

        with self.output:
            for name in apps:

                # Create app widget if it has not been created yet.
                if name not in self._app_widgets:
                    self._app_widgets[name] = self._create_app_widget(name)

                display(self._app_widgets[name])

        return self.output

    def load_apps(self):
        """Load apps according to the order defined in the config file."""
        apps = [
            path.basename(fn)
            for fn in glob(path.join(AIIDALAB_APPS, '*'))
            if path.isdir(fn) and not fn.endswith('home') and not fn.endswith('__pycache__')
        ]
        config = self.read_config()
        order = config['order']
        apps.sort(key=lambda x: order.index(x) if x in order else -1)
        config['order'] = apps
        self.write_config(config)
        return ['home'] + apps

    def move_updown(self, name, delta):
        """Move the app up/down on the start page."""
        config = self.read_config()
        order = config['order']
        i = order.index(name)
        del order[i]
        j = min(len(order), max(0, i + delta))
        order.insert(j, name)
        config['order'] = order
        self.write_config(config)


class AppWidget(ipw.VBox):
    """Widget that represents an app as part of the home page."""

    def __init__(self, app, allow_move=False):
        self.app = app

        launcher = load_widget(app.name)
        launcher.layout = ipw.Layout(width="900px")

        update_info = UpdateAvailableInfoWidget()
        ipw.dlink((app, 'updates_available'), (update_info, 'updates_available'))
        update_info.layout.margin = "0px 0px 0px 800px"

        if allow_move:
            app_widget_move_buttons = create_app_widget_move_buttons(app.name)
            body = ipw.HBox([launcher, app_widget_move_buttons])
        else:
            body = launcher

        footer = ipw.HTML("<a href=./single_app.ipynb?app={}><button>Manage App</button></a>".format(app.name),
                          layout={'width': 'initial'})
        if app.url:
            footer.value += ' <a href="{}"><button>URL</button></a>'.format(app.url)
        footer.layout.margin = "0px 0px 0px 700px"

        super().__init__(children=[update_info, body, footer])


class CollapsableAppWidget(ipw.Accordion):
    """Widget that represents a collapsable app as part of the home page."""

    hidden = traitlets.Bool()

    def __init__(self, app, **kwargs):
        self.app = app
        app_widget = AppWidget(app, **kwargs)
        super().__init__(children=[app_widget])
        self.set_title(0, app.title)
        # Need to observe all names here due to unidentified issue:
        self.observe(self._observe_accordion_selected_index)  # , names=['selected_index'])

    @_workaround_property_lock_issue
    def _observe_accordion_selected_index(self, change):
        if change['name'] == 'selected_index':  # Observing all names due to unidentified issue.
            self.hidden = change['new'] is None

    @traitlets.observe('hidden')
    def _observe_hidden(self, change):
        self.selected_index = None if change['new'] else 0
