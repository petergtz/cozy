#!/usr/bin/python

import subprocess
import nautilus
import sys

import dbus

class CozyRestoreNautilusExtension(nautilus.MenuProvider):

	def __init__(self):
		self.dbus = None
#		try:
#			self.dbus=RestoreDBus()
#		except Exception, e:
#			sys.stderr.write(str(e))

		self.is_in_restore_mode = False

# FIXME: seems like the destructor gets never called by nautilus. So automatic cleanup is impossible
	def __del__(self):
		print "Cozy's Destructor was CALLED"
		self.dbus = None


	def go_to_previous_version(self, menu, file, window):
		location = self.manager.get_previous_version_path(file, dbus_interface='org.freedesktop.Cozy.Manager')
		cmdline = ['nautilus', location]
		subprocess.Popen(cmdline)
		window.destroy()

	def go_to_next_version(self, menu, file, window):
		location = self.manager.get_next_version_path(file, dbus_interface='org.freedesktop.Cozy.Manager')
		cmdline = ['nautilus', location]
		subprocess.Popen(cmdline)
		window.destroy()

	def go_to_newest_version(self, menu, file, window):
		location = self.manager.get_newest_version_path(file, dbus_interface='org.freedesktop.Cozy.Manager')
		cmdline = ['nautilus', location]
		subprocess.Popen(cmdline)
		window.destroy()

	def go_to_restore_mode(self, menu, file, window):
		cmdline = ['nautilus', file]
		subprocess.Popen(cmdline)
		self.is_in_restore_mode = True
		window.destroy()

	def close_restore_mode(self, menu, file, window):
		location = self.manager.get_newest_version_path(file, dbus_interface='org.freedesktop.Cozy.Manager')
		cmdline = ['nautilus', location]
		subprocess.Popen(cmdline)
		self.is_in_restore_mode = False
		window.destroy()
		self.manager.close_restore_mode(dbus_interface='org.freedesktop.Cozy.Manager')

	def get_toolbar_items(self, window, path):
		items = []

		path = path.get_uri().replace('file://', '')

		try:
			self.session_bus = dbus.SessionBus()
			self.manager = self.session_bus.get_object('org.freedesktop.Cozy', '/org/freedesktop/Cozy/Manager')
			if not self.is_in_restore_mode:
				item = nautilus.MenuItem(name="NautilusPython::restoremode", icon='cozy', label="Enter Restore Mode", tip="Switches Nautilus into Restore Mode to discover older versions of files and folders")
				item.connect("activate", self.go_to_restore_mode, path, window)
				items.append(item)
			else:
				item = nautilus.MenuItem(name="NautilusPython::closerestoremode", label="Exit Restore Mode", tip="Exits from Restore Mode and goes back to normal mode", icon='close-cozy')
				item.connect("activate", self.close_restore_mode, path, window)
				items.append(item)

				if self.manager.get_previous_version_path(path, dbus_interface='org.freedesktop.Cozy.Manager') != '':
					item = nautilus.MenuItem(name="NautilusPython::prev", label="Previous Version", tip="Go to previous Version of current location", icon='go-previous')
					item.connect("activate", self.go_to_previous_version, path, window)
					items.append(item)
				if self.manager.get_next_version_path(path, dbus_interface='org.freedesktop.Cozy.Manager') != '':
					item = nautilus.MenuItem(name="NautilusPython::next", label="Next Version", tip="Go to next Version of current location", icon='go-next')
					item.connect("activate", self.go_to_next_version, path, window)
					items.append(item)
		except Exception, e: # This must be something like a DBus object not existing exception
			sys.stderr.write('Error in Cozy Restore Nautilus Extension:\n' + str(e))
			items = []

		return items


