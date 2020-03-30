# -*- coding: utf-8 -*-
"""AiiDA lab basic widgets."""

from threading import Timer

import traitlets
import ipywidgets as ipw


class _StatusWidgetMixin:
    """Show temporary messages for example for status updates.

    This is a mixin class that is meant to be part of an inheritance
    tree of an actual widget with a 'value' traitlet that is used
    to convey a status message. See the non-private classes below
    for examples.
    """

    def __init__(self, *args, **kwargs):
        self._clear_timer = None
        super().__init__(*args, **kwargs)

    def _clear_value(self):
        """Set widget .value to be an empty string."""
        self.value = ''

    def show_temporary_message(self, value, clear_after=3):
        """Show a temporary message and clear it after the given interval."""
        if self._clear_timer is not None:
            # Cancel previous timer; has no effect if it already timed out.
            self._clear_timer.cancel()

        self.value = value

        # Start new timer that will clear the value after the specified interval.
        self._clear_timer = Timer(clear_after, self._clear_value)
        self._clear_timer.start()


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


class Spinner(ipw.HTML):
    """Widget that shows a simple spinner if enabled."""

    enabled = traitlets.Bool()

    def __init__(self, spinner_style=None):
        self.spinner_style = f' style="{spinner_style}"' if spinner_style else ''
        super().__init__()

    @traitlets.default('enabled')
    def _default_enabled(self):  # pylint: disable=no-self-use
        return False

    @traitlets.observe('enabled')
    def _observe_enabled(self, change):
        """Show spinner if enabled, otherwise nothing."""
        if change['new']:
            self.value = f"""<i class="fa fa-spinner fa-pulse"{self.spinner_style}></i>"""
        else:
            self.value = ""
