#!/usr/bin/python

from cozy.backupprovider import BackupProvider
from dbus.mainloop.glib import DBusGMainLoop

import gobject

import sys

import dbus
import dbus.service

from cozy.configuration import Configuration
import utils.daemon

from cozy.restorebackend import RestoreBackend
from cozy.locationmanager import LocationManager

class ManagerDaemon(utils.daemon.Daemon):
    def run(self):

        DBusGMainLoop(set_as_default=True)

        config = Configuration()

        backup_provider = BackupProvider()

        session_bus = dbus.SessionBus()
        system_bus = dbus.SystemBus()

        name = dbus.service.BusName('org.freedesktop.Cozy.RestoreBackend', session_bus)

        location_manager = LocationManager(config, system_bus)

#        location_manager = session_bus.get_object('org.freedesktop.Cozy.LocationManager', '/org/freedesktop/Cozy/LocationManager')

#        backup_location_object = session_bus.get_object('org.freedesktop.Cozy.LocationManager', location_manager.get_backup_location(dbus_interface='org.freedesktop.Cozy.LocationManager'))
#        backup_location = dbus.Interface(backup_location_object, dbus_interface='org.freedesktop.Cozy.BackupLocation')

        restore_backend = RestoreBackend(config, backup_provider, session_bus, location_manager)

        mainloop = gobject.MainLoop()
        mainloop.run()


if __name__ == '__main__':
    daemon = ManagerDaemon('/tmp/cozy-restore-backend.pid', stdout='/tmp/cozy-restore-backend-stdout', stderr='/tmp/cozy-restore-backend-stderr')
    if len(sys.argv) == 2:
        if 'start' == sys.argv[1]:
            daemon.start()
        elif 'stop' == sys.argv[1]:
            daemon.stop()
        elif 'restart' == sys.argv[1]:
            daemon.restart()
        elif 'nodaemon' == sys.argv[1]:
            daemon.run()
        else:
            print "Unknown command"
            sys.exit(2)
        sys.exit(0)
    else:
        print "usage: %s start|stop|restart|nodaemon" % sys.argv[0]
        sys.exit(2)
