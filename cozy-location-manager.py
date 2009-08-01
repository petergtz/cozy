#!/usr/bin/python

from dbus.mainloop.glib import DBusGMainLoop

import gobject

import sys

import dbus

from cozy.configuration import Configuration
import utils.daemon

from cozy.locationmanager import LocationManager


class LocationDaemon(utils.daemon.Daemon):
    def run(self):

        DBusGMainLoop(set_as_default=True)

        config = Configuration()

        session_bus = dbus.SessionBus()
        system_bus = dbus.SystemBus()

#        name = dbus.service.BusName("org.freedesktop.Cozy.LocationManager", session_bus)
        location_manager = LocationManager(config, session_bus, system_bus)


        mainloop = gobject.MainLoop()
        mainloop.run()


if __name__ == '__main__':
    daemon = LocationDaemon('/tmp/cozy-location-manager.pid', stdout='/tmp/cozy-location-manager-stdout', stderr='/tmp/cozy-location-manager-stderr')
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
