# -*- coding: utf-8 -*-
import requests

# Info: try-except is a fix for Quantum Mobile release v19.03.0
# that does not have requests_cache installed
try:
    import requests_cache
except:
    pass

from collections import Counter
import ipywidgets as ipw

from IPython.display import clear_output
from IPython.lib import backgroundjobs as bg

from .app import AiidalabApp
from .config import aiidalab_apps

class AiidalabAppStore(ipw.HBox):
    def __init__(self):
        def update_cache():
            """Run this process asynchronously"""
            requests_cache.install_cache(cache_name='apps_meta', backend='sqlite',
                                         expire_after=3600, old_data_on_error=True)
            requests.get(registry_url)
            requests_cache.install_cache(cache_name='apps_meta', backend='sqlite')

        # try-except is a fix for Quantum Mobile release v19.03.0 that does not have requests_cache installed
        try:
            requests_cache.install_cache(cache_name='apps_meta', backend='sqlite')
            update_cache_background = bg.BackgroundJobFunc(update_cache) # if requests_cache is installed, the
                                                                 # update_cache_background variable will be present
        except NameError:
            pass
        registry_url = 'https://aiidalab.materialscloud.org/appsdata/apps_meta.json'
        try:
            requested_dict = requests.get(registry_url).json()
            if 'update_cache_background' in locals():
                update_cache_background.start()
            self.registry_sorted_list = sorted(requested_dict['apps'].items())
            self.categories_dict = requested_dict['categories']
        except ValueError:
            print("Registry server is unavailable! Can't load the apps")
            self.registry_sorted_list = []

        self.output = ipw.Output()
        self.items_per_page = ipw.BoundedIntText(value=10,
                                                 min=5,
                                                 max=40,
                                                 step=5,
                                                 description='Apps per page:',
                                                 disabled=False,
                                                 style = {'description_width': 'initial'},
                                                 layout={'width': '150px'},
                                                )
        self.category_filter = ipw.SelectMultiple(
            options=[],
            value=[],
            #rows=10,
            description='Filter categories',
            style = {'description_width': 'initial'},
            disabled=False
        )
        self.apply_category_filter = ipw.Button(description="apply filter")
        self.apply_category_filter.on_click(self.change_vis_list)
        self.clear_category_filter = ipw.Button(description='clear selection')
        self.clear_category_filter.on_click(self._clear_category_filter)
        self.items_per_page.observe(self.update_page_selector, names='value')
        self.page_selector = ipw.ToggleButtons(
            options=[],
            description='Page:',
            disabled=False,
            style={'button_width' : '30px'},
        )
        self.page_selector.observe(self.render, names='value')
        
        self.only_installed = ipw.Checkbox(
            value=False,
            description='Show only installed',
            disabled=False)
        self.only_installed.observe(self.change_vis_list, names='value')
        self.apps_to_display = [ AiidalabApp(name, app, aiidalab_apps) for name, app in self.registry_sorted_list ]
        
        self.categorys_counter = Counter([category for app in self.apps_to_display for category in app.categories])
        self.category_title_key_mapping = { self.categories_dict[key]['title'] if key in self.categories_dict else key:key
                             for key in self.categories_dict }
        self.category_filter.options =  [ key for key in self.category_title_key_mapping]
        self.update_page_selector()
        return super().__init__(
            [self.only_installed, ipw.VBox([self.category_filter,
                                            ipw.HBox([self.apply_category_filter, self.clear_category_filter])
                                           ])])
    def _clear_category_filter(self, b):
        self.category_filter.value = ()
        self.change_vis_list()

    def update_page_selector(self, b=None):
        """This function changes the current page value and makes sure that the page is re-rendered"""
        initial_page = self.page_selector.value
        self.page_selector.options = range(1, int(len(self.apps_to_display) / self.items_per_page.value + 2))

        # this parts makes sure that render function will always run one time only:
        # if page number changed in the previous step - the render was run automatically already
        # if not -it needs to be done manually
        if initial_page == self.page_selector.value:
            self.render()

    def change_vis_list(self, b=None):
        """
        This function creates a list of apps to be displayed. Moreover, it creates a parallel list of categories.
        After this the page selector update is called
        
        """
        self.apps_to_display = [AiidalabApp(name, app, aiidalab_apps) for name, app
                                in self.registry_sorted_list]

        if self.only_installed.value:
            self.apps_to_display = [app for app in self.apps_to_display if app.is_installed()]

        if self.category_filter.value: 
            all_apps = self.apps_to_display
            self.apps_to_display = [] # clear the array that contains all the apps to be displayed
            self.app_corresponding_categories = [] # create a parallel array that contains corresponding category names
            # iterate over all categories
            for category in self.category_filter.value:
                category_key = self.category_title_key_mapping[category]
                apps_belonging_to_category = [app for app in all_apps if app.in_category(category_key)]
                self.apps_to_display += apps_belonging_to_category
                if apps_belonging_to_category:
                    self.app_corresponding_categories += [category] + [None] * (len(apps_belonging_to_category) - 1)

        # As the list of apps to be shown is changed, it is essential to update the page selector also
        self.update_page_selector()

    def render(self, b=None):
        max_len = 180
        self.output.clear_output()
        page = self.page_selector.value - 1
        start = page * self.items_per_page.value
        end = (page + 1) * self.items_per_page.value
        with self.output:
            for number, app_base in enumerate(self.apps_to_display[start:end]):
                if self.category_filter.value and self.app_corresponding_categories[start:end][number]:
                    display(ipw.HTML("<h1>{}</h1>".format(
                        self.app_corresponding_categories[start:end][number].title())))
                hr = ipw.HTML('<hr>')
                description = ipw.HTML("""<h2 style="text-align:center;">{}</h2>
                <div style="font-size: 15px; font-style: italic">Description: {}</div>
                <br>
                <div style="text-align:right;">{}</div>
                """.format(app_base.title,
                           app_base.description if len(app_base.description) < max_len
                           else app_base.description[:max_len] + '...',
                           app_base.more))
                description.layout = {'width': '600px'}
                description.layout.margin = "0px 0px 0px 40px"
                # TODO: put here as less widgets as possible
                result = ipw.VBox([hr,
                                   ipw.HBox([app_base.logo, description]),
                                   ipw.HBox([app_base.uninstall_button, app_base.update_button, app_base.install_button]),
                                   ipw.HBox([app_base.install_info]),
                                  ])
                display(result)
        
        return self.output
