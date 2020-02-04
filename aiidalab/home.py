"""Module to generate AiiDA lab home page."""

from os import path
from glob import glob
from importlib import import_module

import json
import requests
import ipywidgets as ipw
from IPython.display import display
from IPython.lib import backgroundjobs as bg
from markdown import markdown

# try-except is a fix for Quantum Mobile release v19.03.0 that does not have requests_cache installed
try:
    import requests_cache
except ImportError:
    pass

# AiiDA lab imports.
from .app import AiidalabApp
from .config import AIIDALAB_APPS, AIIDALAB_REGISTRY


def mk_buttons(name):
    """Make buttons to move the app up or down."""
    layout = ipw.Layout(width="40px")
    btn_box = ipw.HTML("""
    <a href=./start.ipynb?move_up={name} title="Move it up"><i class='fa fa-arrow-up' style='color:#337ab7;font-size:2em;' ></i></a>
    <a href=./start.ipynb?move_down={name} title="Move it down"><i class='fa fa-arrow-down' style='color:#337ab7;font-size:2em;' ></i></a>
    """.format(name=name),
                       layout=layout)
    btn_box.layout.margin = "50px 0px 0px 0px"

    return btn_box


def load_widget(name):
    if path.exists(path.join(AIIDALAB_APPS, name, 'start.py')):
        return load_start_py(name)
    return load_start_md(name)


def load_start_py(name):
    """Load app appearance from a Python file."""
    try:
        mod = import_module('apps.%s.start' % name)
        appbase = "../" + name
        jupbase = "../../.."
        notebase = jupbase + "/notebooks/apps/" + name
        try:
            return mod.get_start_widget(appbase=appbase, jupbase=jupbase, notebase=notebase)
        except Exception:
            return mod.get_start_widget(appbase=appbase, jupbase=jupbase)
    except Exception as exc:
        return ipw.HTML("<pre>{}</pre>".format(str(exc)))


def load_start_md(name):
    """Load app appearance from a Markdown file."""
    fname = path.join(AIIDALAB_APPS, name, 'start.md')
    try:

        md_src = open(fname).read()
        md_src = md_src.replace("](./", "](../%s/" % name)
        html = markdown(md_src)

        # open links in new window/tab
        html = html.replace('<a ', '<a target="_blank" ')

        # downsize headings
        html = html.replace("<h3", "<h4")
        return ipw.HTML(html)

    except Exception:
        return ipw.HTML("Could not load start.md")


class AiidalabHome:
    """Class that mananges the appearance of the AiiDA lab home page."""

    def __init__(self):

        self.config_fn = ".launcher.json"

        def update_cache():
            """Run this process asynchronously."""
            requests_cache.install_cache(cache_name='apps_meta',
                                         backend='sqlite',
                                         expire_after=3600,
                                         old_data_on_error=True)
            requests.get(AIIDALAB_REGISTRY)
            requests_cache.install_cache(cache_name='apps_meta', backend='sqlite')

        # try-except is a fix for Quantum Mobile release v19.03.0 that does not have requests_cache installed
        try:
            requests_cache.install_cache(cache_name='apps_meta', backend='sqlite')  # at start getting data from cache
            update_cache_background = bg.BackgroundJobFunc(update_cache)  # if requests_cache is installed, the
            # update_cache_background variable will be present
        except NameError:
            pass

        try:
            self.app_registry = requests.get(AIIDALAB_REGISTRY).json()['apps']
            if 'update_cache_background' in globals():
                update_cache_background.start()
        except ValueError:
            print("Registry server is unavailable! Can't check for the updates")
            self.app_registry = {}

        self.output = ipw.Output()

    def write_config(self, config):
        json.dump(config, open(self.config_fn, 'w'), indent=2)

    def read_config(self):
        if path.exists(self.config_fn):
            return json.load(open(self.config_fn, 'r'))
        return {'order': [], 'hidden': []}  #default config

    def render(self):
        """Rendering all apps."""
        self.output.clear_output()
        self.render_home()
        apps = self.load_apps()
        config = self.read_config()
        with self.output:
            for name in apps:
                accordion = self.mk_accordion(name)
                accordion.selected_index = None if name in config['hidden'] else 0
                display(accordion)

        return self.output

    def record_showhide(self, name, visible):
        """Store the information about displayed/hidden status of an app."""
        config = self.read_config()
        hidden = set(config['hidden'])
        if visible:
            hidden.discard(name)
        else:
            hidden.add(name)
        config['hidden'] = list(hidden)
        self.write_config(config)

    def render_home(self):
        """Rendering home app."""
        launcher = load_widget('home')
        launcher.layout = ipw.Layout(width="900px", padding="20px", color='gray')
        app = AiidalabApp('home', self.app_registry.get('home', None), AIIDALAB_APPS)
        update_info = ipw.HTML("{}".format(app.update_info))
        update_info.layout.margin = "0px 0px 0px 800px"
        description_box = ipw.HTML("<a href=./single_app.ipynb?app=home><button>Manage App</button></a> {}".format(
            app.git_hidden_url),
                                   layout={'width': 'initial'})
        description_box.layout.margin = "0px 0px 0px 700px"
        display(update_info, launcher, description_box, app.install_info)

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
        return apps

    def mk_accordion(self, name):
        """Make per-app accordion widget to put on the home page."""
        launcher = load_widget(name)
        launcher.layout = ipw.Layout(width="900px")
        btn_box = mk_buttons(name)
        app_data = self.app_registry.get(name, None)
        app = AiidalabApp(name, app_data, AIIDALAB_APPS)
        update_info = ipw.HTML("{}".format(app.update_info))
        update_info.layout.margin = "0px 0px 0px 800px"
        run_line = ipw.HBox([launcher, btn_box])
        description_box = ipw.HTML("<a href=./single_app.ipynb?app={}><button>Manage App</button></a> {}".format(
            name, app.git_hidden_url),
                                   layout={'width': 'initial'})
        description_box.layout.margin = "0px 0px 0px 700px"
        box = ipw.VBox([update_info, run_line, description_box])
        accordion = ipw.Accordion(children=[box])
        accordion.set_title(0, app.title)
        accordion.observe(lambda c: self.record_showhide(name, accordion.selected_index == 0), names="selected_index")
        return accordion

    def move_updown(self, name, delta):
        """Move the app up/down on the start page."""
        config = self.read_config()
        order = config['order']
        i = order.index(name)
        del order[i]
        j = min(len(order) - 1, max(0, i + delta))
        order.insert(j, name)
        config['order'] = order
        self.write_config(config)
