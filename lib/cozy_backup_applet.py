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

from __future__ import with_statement

import pygtk
pygtk.require('2.0')
import gtk

from dbus.mainloop.glib import DBusGMainLoop

import dbus
import gobject
import glib

import subprocess
import sys
import os
import time
import threading

import cozy.back_up

from cozy.locationmanager import LocationManager

from cozy.configuration import Configuration
from cozy.configurationdialog import ConfigMediator

from cozy.backupprovider import BackupProvider

from cozy.restorefrontend import RestoreFrontend
from cozy.restorecontrolcenter import RestoreControlCenter
from cozy.restoreclientconnector import RestoreClientConnector
from cozy.restorebackend import RestoreBackend
from cozy.standardfallbackrestoreclientloader import StandardFallbackRestoreClientLoader


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
COZY_CONFIGDLG_PATH = os.path.join(BASE_DIR, 'cozy_setup.py')
COZY_ICON_NAME = 'cozy'
COZY_ICON_NAME_UNAVAILABLE = 'cozy-unavailable'

class CozyIcon(gtk.StatusIcon):

    def __init__(self, config, restore_backend, notification_service, mainloop,
                 restore_client_connector, restore_control_center, location_manager):
        gtk.StatusIcon.__init__(self)

        self.connect_object("popup-menu", CozyIcon.on_popup_menu, self)

        self.notification_service = notification_service
        self.mainloop = mainloop

        self.config = config
        self.config_dialog = None
        self.restore_frontend = None
        self.restore_client_connector = restore_client_connector
        self.restore_control_center = restore_control_center
        self.location_manager = location_manager

        self.restore_backend = restore_backend
        self.restore_backend.connect_to_signal('available', self.set_backup_location_available)
        self.restore_backend.connect_to_signal('unavailable', self.set_backup_location_unavailable)

        self.__update_backup_availability()

        if not self.config.backup_enabled:
            self.on_show_config_dialog(None)

    def __update_backup_availability(self):
        if self.restore_backend.is_backup_location_available():
            self.set_backup_location_available()
        else:
            self.set_backup_location_unavailable()

    def set_backup_location_available(self):
        self.set_from_icon_name(COZY_ICON_NAME)
        self.__show_message("Backup Volume Connected", "Click here if you want to back up your data now.")
        self.__create_available_menu()

    def set_backup_location_unavailable(self):
        self.set_from_icon_name(COZY_ICON_NAME_UNAVAILABLE)
        self.__create_unavailable_menu()



    def __create_available_menu(self):
        self.menu = gtk.Menu()

        menu_item = gtk.MenuItem('Start Backup')
        self.menu.append(menu_item)
        menu_item.connect_object("activate", CozyIcon.on_start_backup, self)
        menu_item.show()

        menu_item = gtk.MenuItem('Start Restore Session...')
        self.menu.append(menu_item)
        menu_item.connect_object("activate", CozyIcon.on_start_restore_session, self)
        menu_item.show()

        self.__create_settings_and_exit_menu_items()

    def __create_unavailable_menu(self):
        self.menu = gtk.Menu()
        self.__create_settings_and_exit_menu_items()

    def __create_settings_and_exit_menu_items(self):
        menu_item = gtk.MenuItem('Settings...')
        self.menu.append(menu_item)
        menu_item.connect_object("activate", CozyIcon.on_show_config_dialog, self, 'Settings')
        menu_item.show()

        menu_item = gtk.MenuItem('Exit')
        self.menu.append(menu_item)
        menu_item.connect_object("activate", CozyIcon.on_exit, self, 'Exit')
        menu_item.show()


    def __show_message(self, title, message):
        menu = gtk.Menu()
        (x, y, p) = gtk.status_icon_position_menu(menu, self)
        self.notification_service.Notify("", 0, "", title, message, list(), {'x': x, 'y': y}, -1)

    def delete_event(self, widget, event):
        return False

    def on_show_config_dialog(self, widget):
        if self.config_dialog is None:
            class ProgramPaths(object):
                def __init__(self):
                    self.COZY_BACKUP_APPLET_PATH = 'cozy-backup-applet'
                    self.COZY_BACKUP_PATH = 'cozy-backup'
            self.config_dialog = ConfigMediator(ProgramPaths(), self.config, self.on_config_dialog_closed)
        self.config_dialog.present()

    def on_config_dialog_closed(self):
        self.config_dialog = None
        if not self.config.backup_enabled:
            self.mainloop.quit()
        else:
            backup_location = self.location_manager.get_backup_location(self.config)
            self.restore_backend.set_backup_location(backup_location)
            self.__update_backup_availability()


    def on_exit(self, widget):
        self.mainloop.quit()

    def on_start_backup(self):
        cozy.back_up.back_up()

    def on_start_restore_session(self):
        class RestoreSessionThread(threading.Thread):
            def __init__(self, restore_client_connector, restore_control_center):
                threading.Thread.__init__(self)
                self.restore_client_connector = restore_client_connector
                self.restore_control_center = restore_control_center

            def run(self):
                    restore_client = self.restore_client_connector.get_restore_client()
                    self.restore_control_center.set_restore_client(restore_client)

        if self.restore_frontend is None:
            self.restore_frontend = RestoreFrontend(self.restore_control_center, self.on_restore_session_close)
            self.restore_session = RestoreSessionThread(self.restore_client_connector, self.restore_control_center)
            self.restore_session.start()

    def on_restore_session_close(self):
        self.restore_control_center.go_to_present()
        self.restore_frontend = None

    def on_popup_menu(self, button, activate_time):
        self.__show_popup_menu(activate_time)

    def __show_popup_menu(self, activation_time=0):
        self.menu.popup(None, None, gtk.status_icon_position_menu, 0, activation_time, self)

def alive():
    sys.stdout.write('.')
    return True

def main():
    gobject.threads_init()
    gtk.gdk.threads_init()
    DBusGMainLoop(set_as_default=True)

    gobject.timeout_add(1000, alive)
    mainloop = gobject.MainLoop()

    session_bus = dbus.SessionBus()
    notification_service_object = session_bus.get_object('org.freedesktop.Notifications', '/org/freedesktop/Notifications')
    notification_service = dbus.Interface(notification_service_object, dbus_interface='org.freedesktop.Notifications')

    name = dbus.service.BusName('org.freedesktop.Cozy', session_bus)

    backup_provider = BackupProvider()

    config = Configuration()
    system_bus = dbus.SystemBus()
    location_manager = LocationManager(system_bus)
    backup_location = location_manager.get_backup_location(config)

    standard_fallback_restore_client_loader = StandardFallbackRestoreClientLoader(config.data_path)
    restore_client_connector = RestoreClientConnector(session_bus, standard_fallback_restore_client_loader)

    with RestoreBackend(config, backup_provider, backup_location) as restore_backend:
        with RestoreControlCenter(restore_backend) as restore_control_center:
            icon = CozyIcon(config, restore_backend, notification_service, mainloop,
                            restore_client_connector, restore_control_center, location_manager)

            mainloop.run()


if __name__ == '__main__':
    main()

