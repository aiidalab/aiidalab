# -*- coding: utf-8 -*-
"""AiiDA lab basic widgets."""

from threading import Thread
from time import sleep, time

import traitlets
import ipywidgets as ipw


class _StatusWidgetMixin:
    """Show temporary messages for example for status updates."""

    def __init__(self, *args, **kwargs):
        self._clear_timer = 0
        super().__init__(*args, **kwargs)

    def _clear_value_after_delay(self, delay):
        self._clear_timer = time() + delay  # reset timer
        sleep(delay)
        if time() > self._clear_timer:
            self.value = ''

    def show_temporary_message(self, value, clear_after=3):
        self.value = value
        if clear_after > 0:
            Thread(target=self._clear_value_after_delay, args=(clear_after,)).start()


class StatusLabel(_StatusWidgetMixin, ipw.Label):
    """Show temporary messages for example for status updates."""


class StatusHTML(_StatusWidgetMixin, ipw.HTML):
    """Show temporary HTML messages for example for status updates."""


class UpdateAvailableInfoWidget(ipw.HTML):
    """Widget that indicates whether an update is available."""

    updates_available = traitlets.Bool(allow_none=True)

    MESSAGES = {
        None:
            """<font color="#D8000C"><i class='fa fa-times-circle'></i> """\
            """Unable to determine availability of updates.</font>""",
        True:
            """<font color="#9F6000"><i class='fa fa-warning'></i> Update Available</font>""",
        False:
            """<font color="#270"><i class='fa fa-check'></i> Latest Version</font>""",
    }

    def __init__(self, updates_available=None, **kwargs):
        super().__init__(updates_available=None, **kwargs)
        self._observe_updates_available(dict(new=updates_available))  # initialize

    @traitlets.observe('updates_available')
    def _observe_updates_available(self, change):
        self.value = self.MESSAGES[change['new']]
