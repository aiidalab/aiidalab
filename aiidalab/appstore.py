# -*- coding: utf-8 -*-
"""AiiDA lab app store."""

import ipywidgets as ipw
from IPython.display import display
from jinja2 import Template

from .app import AiidaLabApp, AppManagerWidget
from .config import AIIDALAB_APPS
from .utils import load_app_registry


class AiidaLabAppStore(ipw.HBox):
    """Class to manage AiiDA lab app store."""

    def __init__(self):
        requested_dict = load_app_registry()
        if requested_dict:
            self.registry_sorted_list = sorted(requested_dict['apps'].items())
            categories_dict = requested_dict['categories']
        else:
            self.registry_sorted_list = []
        self.app_corresponding_categories = []
        self.output = ipw.Output()

        # Apps per page.
        self.items_per_page = ipw.BoundedIntText(
            value=10,
            min=5,
            max=40,
            step=5,
            description='Apps per page:',
            disabled=False,
            style={'description_width': 'initial'},
            layout={'width': '150px'},
        )
        self.items_per_page.observe(self.update_page_selector, names='value')

        # Page selector.
        self.page_selector = ipw.ToggleButtons(
            options=[],
            description='Page:',
            disabled=False,
            style={'button_width': '30px'},
        )
        self.page_selector.observe(self.render, names='value')

        # Only installed filter.
        self.only_installed = ipw.Checkbox(value=False, description='Show only installed', disabled=False)
        self.only_installed.observe(self.change_vis_list, names='value')

        # Category filter.
        self.category_filter = ipw.SelectMultiple(
            options=[],
            value=[],
            #rows=10,
            description='Filter categories',
            style={'description_width': 'initial'},
            disabled=False)
        apply_category_filter = ipw.Button(description="apply filter")
        apply_category_filter.on_click(self.change_vis_list)
        clear_category_filter = ipw.Button(description='clear selection')
        clear_category_filter.on_click(self._clear_category_filter)
        self.category_title_key_mapping = {
            categories_dict[key]['title'] if key in categories_dict else key: key for key in categories_dict
        }
        self.category_filter.options = list(self.category_title_key_mapping)

        # Define the apps that are going to be displayed.
        self.apps_to_display = [AiidaLabApp(name, app, AIIDALAB_APPS) for name, app in self.registry_sorted_list]

        self.update_page_selector()
        super().__init__([
            self.only_installed,
            ipw.VBox([self.category_filter,
                      ipw.HBox([apply_category_filter, clear_category_filter])])
        ])

    def _clear_category_filter(self, _):
        self.category_filter.value = ()
        self.change_vis_list()

    def update_page_selector(self, _=None):
        """This function changes the current page value and makes sure that the page is re-rendered."""
        initial_page = self.page_selector.value
        self.page_selector.options = list(range(1, int(len(self.apps_to_display) / self.items_per_page.value + 2)))

        # this parts makes sure that render function will always run one time only:
        # if page number changed in the previous step - the render was run automatically already
        # if not -it needs to be done manually
        if initial_page == self.page_selector.value:
            self.render()

    def change_vis_list(self, _=None):
        """This function creates a list of apps to be displayed. Moreover, it creates a parallel list of categories.
        After this the page selector update is called."""
        self.apps_to_display = [AiidaLabApp(name, app, AIIDALAB_APPS) for name, app in self.registry_sorted_list]

        if self.only_installed.value:
            self.apps_to_display = [app for app in self.apps_to_display if app.is_installed()]

        if self.category_filter.value:
            all_apps = self.apps_to_display
            self.apps_to_display = []  # clear the array that contains all the apps to be displayed
            self.app_corresponding_categories = []  # create a parallel array that contains corresponding category names
            # iterate over all categories
            for category in self.category_filter.value:
                category_key = self.category_title_key_mapping[category]
                apps_belonging_to_category = [app for app in all_apps if app.in_category(category_key)]
                self.apps_to_display += apps_belonging_to_category
                if apps_belonging_to_category:
                    self.app_corresponding_categories += [category] + [None] * (len(apps_belonging_to_category) - 1)

        # As the list of apps to be shown is changed, it is essential to update the page selector also
        self.update_page_selector()

    def render(self, _=None):
        """Show all the available apps."""
        self.output.clear_output()
        page = self.page_selector.value - 1
        start = page * self.items_per_page.value
        end = (page + 1) * self.items_per_page.value
        with self.output:
            for number, app_base in enumerate(self.apps_to_display[start:end]):
                if self.category_filter.value and self.app_corresponding_categories[start:end][number]:
                    display(ipw.HTML("<h1>{}</h1>".format(
                        self.app_corresponding_categories[start:end][number].title())))

                widget = AppStoreAppManagerWidget(app_base)
                display(ipw.HTML('<hr>'))  # horizontal line
                display(widget)

        return self.output


class AppStoreAppManagerWidget(AppManagerWidget):

    TEMPLATE = Template("""<h2 style="text-align:center;">{{ app.title }}</h2>
    <div style="font-size: 15px; font-style: italic">Description: {{ app.description | truncate(200) }}</div>
    <br>
    <div style="text-align:right;"><a href=./single_app.ipynb?app={{ app.name }}>Manage App</a>""")
