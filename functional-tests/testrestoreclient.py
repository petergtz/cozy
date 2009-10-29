#/usr/bin/python

# Cozy Backup Solution
# Copyright (C) 2009  peter
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

import unittest

import threading
import dbus
import dbus.service
import cozy.restoreclientproxy
from dbus.mainloop.glib import DBusGMainLoop
import gobject

import time

class RestoreBackend(object):
    def get_equivalent_path_for_different_version(self, path, version):
        return '/my/path/version' + str(version)

class SampleRestoreClient(dbus.service.Object):
    current_path = '/my/current/path'

    def __init__(self, session_bus, mainloop):
        dbus.service.Object.__init__(self, session_bus, '/org/freedesktop/SampleRestoreClient')
        self.session_bus = session_bus
        self.mainloop = mainloop

#        session_bus.add_signal_receiver(self.__on_enter_restore_mode, 'enter_restore_mode_event',
#                                        'org.freedesktop.Cozy.RestoreControlCenter', 'org.freedesktop.Cozy',
#                                        '/org/freedesktop/Cozy/RestoreControlCenter')
        session_bus.add_signal_receiver(self.on_enter_restore_mode, 'enter_restore_mode_event',
                                        None, None, None)
        session_bus.add_signal_receiver(self.on_exit_restore_mode, 'exit_restore_mode_event',
                                        None, None, None)
        self.restore_control_center = None

    def __reply_handler(self):
        pass

    def __error_handler(self):
        raise Exception("Error")

    def on_enter_restore_mode(self):
        print "enter"
        self.restore_control_center = self.session_bus.get_object('org.freedesktop.Cozy', '/org/freedesktop/Cozy/RestoreControlCenter')
        self.restore_control_center.register_me('/org/freedesktop/SampleRestoreClient', dbus_interface='org.freedesktop.Cozy.RestoreControlCenter',
                                           reply_handler=self.__reply_handler, error_handler=self.__error_handler)
    def on_exit_restore_mode(self):
        self.restore_control_center = None

    def __get_path_in_the_past_reply(self, path):
        self.current_path = path

    def __get_path_in_the_past_error(self, e):
        raise Exception(str(e))

    @dbus.service.method(dbus_interface='org.freedesktop.Cozy.RestoreClient',
                         in_signature='i')
    def go_to_version(self, version):
        self.restore_control_center.get_path_in_the_past(self.current_path, version,
                                                         reply_handler=self.__get_path_in_the_past_reply,
                                                         error_handler=self.__get_path_in_the_past_error)

class SampleRestoreClientProcess(threading.Thread):
    def __init__(self, session_bus, mainloop):
        threading.Thread.__init__(self)
        self.mainloop = mainloop
        self.session_bus = session_bus

    def run(self):
        self.sample_restore_client = SampleRestoreClient(self.session_bus, self.mainloop)


class RestoreControlCenterProcess(threading.Thread):
    def __init__(self, mainloop, session_bus):
        threading.Thread.__init__(self)
        self.session_bus = session_bus
        self.mainloop = mainloop

    def __wait_until_mainloop_is_running(self):
        while not self.mainloop.is_running():
            pass

    def run(self):
        restore_backend = RestoreBackend()
        self.restore_client_proxy = cozy.restoreclientproxy.RestoreClientProxy(self.session_bus, restore_backend)

        self.__wait_until_mainloop_is_running()
        self.restore_client_proxy.enter_restore_mode_event()

        time.sleep(1)
        self.restore_client_proxy.go_to_version(3)
        time.sleep(1)

        self.mainloop.quit()


class TestRestoreClient(unittest.TestCase):

    def test_restore_client(self):
        gobject.threads_init()

        DBusGMainLoop(set_as_default=True)
        session_bus = dbus.SessionBus()
        bus_name = dbus.service.BusName('org.freedesktop.Cozy', session_bus)
        mainloop = gobject.MainLoop()

        sample_restore_client_process = SampleRestoreClientProcess(session_bus, mainloop)
        restore_control_center_process = RestoreControlCenterProcess(mainloop, session_bus)

        sample_restore_client_process.start()
        restore_control_center_process.start()

        mainloop.run()

        self.assertEquals(sample_restore_client_process.sample_restore_client.current_path, '/my/path/version3')


if __name__ == "__main__":
    unittest.main()
