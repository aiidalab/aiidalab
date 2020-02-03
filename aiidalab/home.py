from os import path, getenv
from glob import glob

import json
import requests

from importlib import import_module
from markdown import markdown

# try-except is a fix for Quantum Mobile release v19.03.0 that does not have requests_cache installed
try:
    import requests_cache
except ImportError:
    pass

import ipywidgets as ipw
from IPython.lib import backgroundjobs as bg

from .app import AiidalabApp
from .config import aiidalab_home, aiidalab_apps, aiidalab_registry

CONFIG_FN = ".launcher.json"

def read_config():
    if path.exists(CONFIG_FN):
        return json.load(open(CONFIG_FN,'r'))
    else:
        return {'order':[], 'hidden':[]} #default config

def write_config(config):
    json.dump(config, open(CONFIG_FN,'w'), indent=2)

def mk_buttons(name):
    layout = ipw.Layout(width="40px")
    btn_box = ipw.HTML("""
    <a href=./start.ipynb?move_up={} title="Move it up"><i class='fa fa-arrow-up' style='color:#337ab7;font-size:2em;' ></i></a>
    <a href=./start.ipynb?move_down={} title="Move it down"><i class='fa fa-arrow-down' style='color:#337ab7;font-size:2em;' ></i></a>
    """.format(name, name), layout=layout)
    btn_box.layout.margin = "50px 0px 0px 0px"

    return(btn_box)

def load_widget(name):
    if path.exists(path.join(aiidalab_apps, name, 'start.py')):
        return load_start_py(name)
    else:  # fall back
        return load_start_md(name)

def load_start_py(name):
    try:
        mod = import_module('apps.%s.start' % name)
        appbase = "../" + name
        jupbase = "../../.."
        notebase = jupbase+"/notebooks/apps/"+name
        try:
            return mod.get_start_widget(appbase=appbase, jupbase=jupbase, notebase=notebase)
        except:
            return mod.get_start_widget(appbase=appbase, jupbase=jupbase)
    except Exception as e:
        return ipw.HTML("<pre>%s</pre>" % str(e))

def record_showhide(name, visible):
    config = read_config()
    hidden = set(config['hidden'])
    if visible:
        hidden.discard(name)
    else:
        hidden.add(name)
    config['hidden'] = list(hidden)
    write_config(config)
    
    
def load_start_md(name):
    fn = path.join(aiidalab_apps, name, 'start.md')
    try:

        md_src = open(fn).read()
        md_src = md_src.replace("](./", "](../%s/"%name)
        html = markdown(md_src)

        # open links in new window/tab
        html = html.replace('<a ', '<a target="_blank" ')

        # downsize headings
        html = html.replace("<h3", "<h4")
        return ipw.HTML(html)

    except Exception as e:
        return ipw.HTML("Could not load start.md")

class AiidalabHome(ipw.HBox):
    def __init__(self):
        def update_cache():
            """Run this process asynchronously."""
            requests_cache.install_cache(cache_name='apps_meta', backend='sqlite', expire_after=3600, old_data_on_error=True)
            requests.get(aiidalab_registry)
            requests_cache.install_cache(cache_name='apps_meta', backend='sqlite')

        # try-except is a fix for Quantum Mobile release v19.03.0 that does not have requests_cache installed
        try:
            requests_cache.install_cache(cache_name='apps_meta', backend='sqlite') # at start getting data from cache
            update_cache_background = bg.BackgroundJobFunc(update_cache) # if requests_cache is installed, the
                                                                     # update_cache_background variable will be present
        except NameError:
            pass

        try:
            self.app_registry = requests.get(aiidalab_registry).json()['apps']
            if 'update_cache_background' in globals():
                update_cache_background.start()
        except ValueError:
            print("Registry server is unavailable! Can't check for the updates")
            self.app_registry = {}

        self.output = ipw.Output()
    
    def render(self):
        self.output.clear_output()
        self.render_home()
        apps = self.load_apps()
        config = read_config()
        with self.output:
            for name in apps:
                accordion = self.mk_accordion(name)
                accordion.selected_index = None if name in config['hidden'] else 0
                display(accordion)

        return self.output
    
    def render_home(self):
        launcher = load_widget('home')
        launcher.layout = ipw.Layout(width="900px", padding="20px", color='gray')
        app = AiidalabApp('home', self.app_registry.get('home', None), aiidalab_apps)
        update_info = ipw.HTML("{}".format(app.update_info))
        update_info.layout.margin = "0px 0px 0px 800px"
        description_box = ipw.HTML("<a href=./single_app.ipynb?app=home><button>Manage App</button></a> {}".format(
            app.git_hidden_url), layout={'width': 'initial'})
        description_box.layout.margin = "0px 0px 0px 700px"
        info_line = app.install_info
        display(update_info, launcher, description_box, info_line)



    def load_title(self, name):
        try:
            fn = path.join(aiidalab_apps, name, 'metadata.json')
            metadata = json.load(open(fn))
            title = metadata['title']
        except:
            title = "%s (couldn't load title)"%name
        return title
    
    def load_apps(self):
        apps = [path.basename(fn) for fn in glob(path.join(aiidalab_apps, '*')) if path.isdir(fn) and not fn.endswith('home') and
               not fn.endswith('__pycache__')]
        config = read_config()
        order = config['order']
        apps.sort(key=lambda x: order.index(x) if x in order else -1)
        config['order'] = apps
        write_config(config)
        return apps

    def mk_accordion(self, name):
        launcher = load_widget(name)
        launcher.layout = ipw.Layout(width="900px")
        btn_box = mk_buttons(name)
        app_data = self.app_registry.get(name, None)
        app = AiidalabApp(name, app_data, aiidalab_apps)
        update_info = ipw.HTML("{}".format(app.update_info))
        update_info.layout.margin = "0px 0px 0px 800px"
        run_line = ipw.HBox([launcher, btn_box])
        description_box = ipw.HTML("<a href=./single_app.ipynb?app={}><button>Manage App</button></a> {}".format(name, app.git_hidden_url),
                                   layout={'width': 'initial'})
        info_line = app.install_info
        description_box.layout.margin = "0px 0px 0px 700px"
        box = ipw.VBox([update_info, run_line, description_box])
        accordion = ipw.Accordion(children=[box])
        title = self.load_title(name)
        accordion.set_title(0, title)
        on_change = lambda c: record_showhide(name, accordion.selected_index==0)
        accordion.observe(on_change, names="selected_index")
        return accordion

    def move_updown(self, name, delta):
        config = read_config()
        order = config['order']
        n = len(order)
        i = order.index(name)
        del(order[i])
        j = min(n-1, max(0, i + delta))
        order.insert(j, name)
        config['order'] = order
        write_config(config)   
