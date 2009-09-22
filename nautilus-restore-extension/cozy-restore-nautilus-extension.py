#!/usr/bin/python

# Cozy Backup Solution
# Copyright (C) 2009  Peter Goetz
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as published by
# the Free Software Foundation.
#  
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#    
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import subprocess
import nautilus
import sys

import dbus

import urllib
import urlparse

class CozyRestoreNautilusExtension(nautilus.MenuProvider):

    def __init__(self):
        self.is_in_restore_mode = False
        self.service_unknown_msg_shown = False

# FIXME: seems like the destructor gets never called by nautilus. So automatic cleanup is impossible
    def __del__(self):
        print "Cozy's Destructor was CALLED"


    def go_to_previous_version(self, menu, file, window):
        location = self.manager.get_previous_version_path(file)
        cmdline = ['nautilus', location]
        subprocess.Popen(cmdline)
        window.destroy()

    def go_to_next_version(self, menu, file, window):
        location = self.manager.get_next_version_path(file)
        cmdline = ['nautilus', location]
        subprocess.Popen(cmdline)
        window.destroy()

    def go_to_newest_version(self, menu, file, window):
        location = self.manager.get_newest_version_path(file)
        cmdline = ['nautilus', location]
        subprocess.Popen(cmdline)
        window.destroy()

    def go_to_restore_mode(self, menu, file, window):
        try:
            self.manager_object = self.session_bus.get_object('org.freedesktop.Cozy.RestoreBackend', '/org/freedesktop/Cozy/RestoreBackend')
            self.manager = dbus.Interface(self.manager_object, dbus_interface='org.freedesktop.Cozy.RestoreBackend')

            if not self.manager.backup_location_available():
                notifications = self.session_bus.get_object('org.freedesktop.Notifications', '/org/freedesktop/Notifications')
                notifications.Notify("", 0, "", "Warning in Cozy Nautilus Extension", 'Backup location is not available', list(), {}, 12000, dbus_interface='org.freedesktop.Notifications')
            else:
                cmdline = ['nautilus', file]
                subprocess.Popen(cmdline)
                self.is_in_restore_mode = True
                window.destroy()
        except Exception, e: # This must be something like a DBus object not existing exception
            notifications = self.session_bus.get_object('org.freedesktop.Notifications', '/org/freedesktop/Notifications')
            notifications.Notify("", 0, "", "Error in Cozy Nautilus Extension", str(e), list(), {}, 12000, dbus_interface='org.freedesktop.Notifications')
            items = []

    def close_restore_mode(self, menu, file, window):
        location = self.manager.get_newest_version_path(file)
        cmdline = ['nautilus', location]
        subprocess.Popen(cmdline)
        self.is_in_restore_mode = False
        window.destroy()
        self.manager.close_restore_mode()


    def get_toolbar_items(self, window, path):
        self.session_bus = dbus.SessionBus()
        notifications = self.session_bus.get_object('org.freedesktop.Notifications', '/org/freedesktop/Notifications')
        notifications_iface = dbus.Interface(notifications, dbus_interface='org.freedesktop.Notifications')

        return self.__get_toolbar_items(window, path, notifications_iface)

    def __get_toolbar_items(self, window, uri, notifications_target):
        items = []

        path = urlparse.urlsplit(urllib.unquote(uri.get_uri()))[2]

        try:
            if not self.is_in_restore_mode:
                item = nautilus.MenuItem(name="NautilusPython::restoremode", icon='cozy', label="Enter Restore Mode", tip="Switches Nautilus into Restore Mode to discover older versions of files and folders")
                item.connect("activate", self.go_to_restore_mode, path, window)
                items.append(item)
            else:
                item = nautilus.MenuItem(name="NautilusPython::closerestoremode", label="Exit Restore Mode", tip="Exits from Restore Mode and goes back to normal mode", icon='close-cozy')
                item.connect("activate", self.close_restore_mode, path, window)
                items.append(item)

                if self.manager.get_previous_version_path(path) != '':
                    item = nautilus.MenuItem(name="NautilusPython::prev", label="Previous Version", tip="Go to previous Version of current location", icon='go-previous')
                    item.connect("activate", self.go_to_previous_version, path, window)
                    items.append(item)
                if self.manager.get_next_version_path(path) != '':
                    item = nautilus.MenuItem(name="NautilusPython::next", label="Next Version", tip="Go to next Version of current location", icon='go-next')
                    item.connect("activate", self.go_to_next_version, path, window)
                    items.append(item)
        except Exception, e: # This must be something like a DBus object not existing exception
            notifications_target.Notify("", 0, "", "Error in Cozy Nautilus Extension", str(e), list(), {}, 12000)
            items = []

        return items

