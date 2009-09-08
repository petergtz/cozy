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
