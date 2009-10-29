#!/usr/bin/python

from __future__ import with_statement

from dbus.mainloop.glib import DBusGMainLoop
import gobject

import pygtk
pygtk.require('2.0')
import gtk

import os

import dbus
import dbus.service
import time

import threading

from cozy.restorebackend import RestoreBackend
from cozy.locationmanager import LocationManager
from cozy.restorecontrolcenter import RestoreControlCenter
from cozy.configuration import Configuration
from cozy.backupprovider import BackupProvider
from cozy.restoreclientconnector import RestoreClientConnector
from cozy.standardfallbackrestoreclientloader import StandardFallbackRestoreClientLoader
from cozy.restorefrontend import RestoreFrontend


class WaitUntilEventLoopIsRunningThread(threading.Thread):

    def __init__(self, mainloop, restore_control_center, standard_fallback_restore_client_loader):
        threading.Thread.__init__(self)
        self.mainloop = mainloop
        self.restore_control_center = restore_control_center
        self.standard_fallback_restore_client_loader = standard_fallback_restore_client_loader

    def __wait_until_mainloop_is_running(self):
        while not self.mainloop.is_running():
            pass

    def run(self):
        self.__wait_until_mainloop_is_running()

        session_bus = dbus.SessionBus()
        restore_client_connector = RestoreClientConnector(session_bus, self.standard_fallback_restore_client_loader)
        restore_client = restore_client_connector.get_restore_client()
        self.restore_control_center.set_restore_client(restore_client)



def main():

    gobject.threads_init()
    gtk.threads_init()
    DBusGMainLoop(set_as_default=True)

    session_bus = dbus.SessionBus()
    system_bus = dbus.SystemBus()

    name = dbus.service.BusName('org.freedesktop.Cozy', session_bus)

    mainloop = gobject.MainLoop()

    config = Configuration()

    backup_provider = BackupProvider()

    location_manager = LocationManager(config, system_bus)
    backup_location = location_manager.get_backup_location()

    with RestoreBackend(config, backup_provider, backup_location) as restore_backend:

        standard_fallback_restore_client_loader = StandardFallbackRestoreClientLoader(config.data_path)

        restore_control_center = RestoreControlCenter(restore_backend)

        wait_until_event_loop_is_running_thread = WaitUntilEventLoopIsRunningThread(mainloop, restore_control_center, standard_fallback_restore_client_loader)
        wait_until_event_loop_is_running_thread.start()

        restore_frontend = RestoreFrontend(restore_control_center, mainloop)

        mainloop.run()



if __name__ == "__main__":
    main()
