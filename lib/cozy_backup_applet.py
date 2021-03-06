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

import os
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

        self.notification_service = notification_service
        self.mainloop = mainloop

        self.config = config
        self.restore_client_connector = restore_client_connector
        self.restore_control_center = restore_control_center
        self.location_manager = location_manager

        self.restore_backend = restore_backend
        self.restore_backend.connect_to_signal('available', self.__on_backup_location_available)
        self.restore_backend.connect_to_signal('unavailable', self.__on_backup_location_unavailable)

        self.config_dialog = None
        self.restore_frontend = None

        self.__create_settings_and_exit_menu()

        self.__update_backup_availability()
        self.connect_object("popup-menu", CozyIcon.__on_popup_right_click_menu, self)
        self.connect_object("activate", CozyIcon.__on_popup_left_click_menu, self)

        if not self.config.backup_enabled:
            self.on_show_config_dialog(None)

    def __update_backup_availability(self):
        if self.restore_backend.is_backup_location_available():
            self.__on_backup_location_available()
        else:
            self.__on_backup_location_unavailable()

    def __on_backup_location_available(self):
        self.set_from_icon_name(COZY_ICON_NAME)
        self.__create_available_menu()

    def __on_backup_location_unavailable(self):
        self.set_from_icon_name(COZY_ICON_NAME_UNAVAILABLE)
        self.__create_unavailable_menu()

    def __create_available_menu(self):
        self.left_click_menu = gtk.Menu()

        menu_item = gtk.MenuItem('Start Backup')
        self.left_click_menu.append(menu_item)
        menu_item.connect_object("activate", CozyIcon.on_start_backup, self)
        menu_item.show()

        menu_item = gtk.MenuItem('Start Restore Session...')
        self.left_click_menu.append(menu_item)
        menu_item.connect_object("activate", CozyIcon.on_start_restore_session, self)
        menu_item.show()

    def __create_unavailable_menu(self):
        self.left_click_menu = gtk.Menu()

        menu_item = gtk.MenuItem('Start Backup')
        self.left_click_menu.append(menu_item)
        menu_item.set_sensitive(False)
        menu_item.show()

        menu_item = gtk.MenuItem('Start Restore Session...')
        self.left_click_menu.append(menu_item)
        menu_item.set_sensitive(False)
        menu_item.show()

    def __create_settings_and_exit_menu(self):
        self.right_click_menu = gtk.Menu()

        menu_item = gtk.MenuItem('Settings...')
        self.right_click_menu.append(menu_item)
        menu_item.connect_object("activate", CozyIcon.on_show_config_dialog, self, 'Settings')
        menu_item.show()

        menu_item = gtk.MenuItem('About')
        self.right_click_menu.append(menu_item)
        menu_item.connect_object("activate", CozyIcon.on_about, self, 'About')
        menu_item.show()

        menu_item = gtk.MenuItem('Exit')
        self.right_click_menu.append(menu_item)
        menu_item.connect_object("activate", CozyIcon.on_exit, self, 'Exit')
        menu_item.show()


    def __show_message(self, title, message):
        menu = gtk.Menu()
        (x, y, p) = gtk.status_icon_position_menu(menu, self)
        self.notification_service.Notify("", 12, "", title, message, list(), {'x': x, 'y': y}, -1)

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
            if self.config.backup_location_type == 'absolute_path':
                message = "Your data will backed up automatically every full hour. " + \
                "Whenever you would like to back up your data manually, click on the Symbol."
            else:
                message = "Whenever you would like to back up your data, click on the Symbol."
            self.__show_message("Finished Cozy Configuration", message)

    def on_about(self, widget):
        print 'FIXME: make about dialog'

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

    def __on_popup_left_click_menu(self):
        self.left_click_menu.popup(None, None, gtk.status_icon_position_menu, 0, gtk.get_current_event_time(), self)

    def __on_popup_right_click_menu(self, button, activate_time):
        self.right_click_menu.popup(None, None, gtk.status_icon_position_menu, 0, gtk.get_current_event_time(), self)

def main():
    gobject.threads_init() #@UndefinedVariable
    gtk.gdk.threads_init() #@UndefinedVariable
    DBusGMainLoop(set_as_default=True)

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

