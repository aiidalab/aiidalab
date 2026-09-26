Background work and kernel lifecycle in AiiDAlab apps
=======================================================

A Jupyter app has two distinct lifecycles: the browser page and its Python
kernel. An AiiDA workchain submitted with ``aiida.engine.submit()`` has a third:
it runs through the AiiDA daemon and does not need the notebook kernel to remain
open. Design background work around those boundaries.

Keep process execution separate from observation
------------------------------------------------

Submit long-running AiiDA processes to the daemon. Use notebook threads only
to observe process state, fetch output, or update the interface. Closing an app
should end its observers, not cancel a submitted workchain. Conversely, a
calculation started with ``aiida.engine.run()`` executes in the local interpreter;
do not use it for work that must survive kernel shutdown.

Give every background task a lifecycle
--------------------------------------

Before starting a thread, decide:

* What starts it, and can that action accidentally start it twice?
* What condition ends it?
* How is it stopped when the user changes the selected process or closes the
  widget?
* Can a network request, subprocess, or queue operation wait indefinitely?
* What happens if the kernel shuts down during the operation?

For polling and UI-only work, use a stop event and a daemon thread. Waiting on
the event makes shutdown prompt, even when the polling interval is long:

.. code-block:: python

	import threading


	class Poller:
		def __init__(self, poll, interval=5):
			self._poll = poll
			self._interval = interval
			self._stop = threading.Event()
			self._thread = None

		def start(self):
			if self._thread is not None and self._thread.is_alive():
				return
			self._stop.clear()
			self._thread = threading.Thread(target=self._run, daemon=True)
			self._thread.start()

		def _run(self):
			while not self._stop.wait(self._interval):
				self._poll()

		def stop(self):
			self._stop.set()
			if self._thread is not None:
				self._thread.join(timeout=2)
				if not self._thread.is_alive():
					self._thread = None

Call ``stop()`` during explicit widget teardown or when changing the process
being observed. Closing a browser tab does not necessarily call a Python widget
method: the frontend may disappear without notifying the kernel.

A daemon thread is a shutdown backstop, not a substitute for a stop condition.
Python may end daemon threads abruptly when the kernel exits. Do not depend on
them to finish writes, installations, exports, or other work requiring cleanup.
Give those tasks explicit completion and cancellation behavior, or run durable
work outside the notebook kernel.

Avoid blocked and unbounded threads
-----------------------------------

Do not use ``while True`` with ``time.sleep()`` for a poller without a stop path.
Bound network calls and subprocess waits; a timeout on one read does not
necessarily bound the entire operation. Keep track of running threads, prevent
duplicate starts, and avoid accumulating ``threading.Timer`` instances. An
unbounded ``join()`` can itself block shutdown when a worker gets stuck.

Keep widget updates from workers infrequent and bounded. Prefer scheduling UI
changes on the kernel's event loop where appropriate rather than modifying
widgets concurrently from multiple threads. Do not repeatedly publish
unchanged state or unbounded output.

Browser cleanup and server memory
---------------------------------

Appmode asks the Jupyter server to remove an app's session and kernel when the
page leaves. Use ``pagehide`` rather than relying on ``unload``, which browsers may
skip. Neither event is guaranteed when a browser crashes or connectivity is
lost, so server-side kernel culling remains a necessary backstop.

With ``MappingKernelManager.buffer_offline_messages=True``, Jupyter buffers
kernel messages while no frontend is connected. An orphaned kernel that keeps
printing or changing widget traits can therefore grow the *server's* memory
even if its own memory stays stable. Making the threads daemon does not stop
this growth while the kernel remains alive. Stop observers where possible,
throttle updates, and review buffering and culling settings for the deployment.
Ongoing kernel activity can also prevent idle-time culling.

Verify the lifecycle
--------------------

Test shutdown and disconnection separately:

#. Submit a workchain, close its app, and confirm that the notebook kernel exits
   while the AiiDA process continues under the daemon.
#. Disconnect the browser without successful page cleanup. Check the server's
   session and connection lists, kernel activity, and *server* memory over time.
   Confirm that the configured culler removes a quiet orphan.

Also test switching processes, repeated starts, explicit stops, and shutdown
while a worker is blocked. A thread being marked ``daemon=True`` is not, by
itself, evidence that these cases are handled.
