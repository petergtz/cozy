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
from dbus.mainloop.glib import DBusGMainLoop
import gobject
import dbus
import dbus.service
import cozy.restoreclientproxy
import subprocess
import threading
import os
import time
import re

SAMPLE_RESTORE_CLIENT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'samplerestoreclient.py')

class FakeRestoreBackend(object):
    def get_equivalent_path_for_different_version(self, path, version):
        if path.startswith('/my/data/path'):
            return path.replace('/my/data/path', '/my/tmp/mountpath/' + str(version))
        if path.startswith('/my/tmp/mountpath/'):
            if version == -1:
                return re.sub('\/my\/tmp\/mountpath\/.', '/my/data/path', path)
            else:
                return re.sub('\/my\/tmp\/mountpath\/.', '/my/tmp/mountpath/' + str(version), path)

        raise Exception('Error: Requested path neither specifies your data nor your data in the past')

    def is_path_in_backup_data(self, path):
        if path.startswith('/my/data/path'):
            return True
        if path.startswith('/my/tmp/mountpath/'):
            return True
        return False



class RestoreSimulationThread(threading.Thread):

    def __init__(self, mainloop, restore_client_proxy):
        threading.Thread.__init__(self)
        self.mainloop = mainloop
        self.restore_client_proxy = restore_client_proxy
        self.exception_happened = False

    def run(self):
        try:
            self.__setUp()
            self._test()
        except Exception, e:
            self.exception_happened = True
        finally:
            self.__tearDown()

    def __setUp(self):
        self.__wait_until_mainloop_is_running()
        self.restore_client_proxy.enter_restore_mode_event()
        time.sleep(0.5)
        if not self.restore_client_proxy.has_restore_client():
            raise Exception('No possible restore client candidate found.')

    def __wait_until_mainloop_is_running(self):
        while not self.mainloop.is_running():
            pass

    def _test(self):
        self.restore_client_proxy.go_to_version(3)
        self.restore_client_proxy.go_to_version(2)

    def __tearDown(self):
        time.sleep(0.5)
        self.restore_client_proxy.exit_restore_mode_event()
        time.sleep(0.5)
        self.mainloop.quit()



EXCPECTED_OUTPUT = \
'''received an enter restore mode event
go_to_version(3)
Got past in the past reply: /my/tmp/mountpath/3/my_file
go_to_version(2)
Got past in the past reply: /my/tmp/mountpath/2/my_file
received an exit restore mode event
go_to_version(-1)
Got past in the past reply: /my/data/path/my_file
'''

class TestRestoreClientProxy(unittest.TestCase):

    def setUp(self):
        gobject.threads_init()

        DBusGMainLoop(set_as_default=True)
        self.session_bus = dbus.SessionBus()
        self.bus_name = dbus.service.BusName('org.freedesktop.Cozy', self.session_bus)
        self.mainloop = gobject.MainLoop()

        fake_restore_backend = FakeRestoreBackend()
        self.restore_client_proxy = cozy.restoreclientproxy.RestoreClientProxy(self.session_bus, fake_restore_backend)

        self.restore_simulation_thread = RestoreSimulationThread(self.mainloop, self.restore_client_proxy)

    def tearDown(self):
        self.restore_client_proxy.remove_from_connection(self.session_bus, '/org/freedesktop/Cozy/RestoreControlCenter')

    def test_restore_client_go_to_version(self):
        self.__start_sample_restore_client(file_location='/my/data/path/my_file')

        self.restore_simulation_thread.start()
        self.mainloop.run()

        output = self.__stop_sample_restore_client_and_return_output()

        self.assertEquals(output, EXCPECTED_OUTPUT)

    def test_restore_client_go_to_version_wrong_path(self):
        self.__start_sample_restore_client(file_location='/a/file/outside/of/the/backup/data/dir')

        self.restore_simulation_thread.start()
        self.mainloop.run()

        self.__stop_sample_restore_client_and_return_output()

        self.assertTrue(self.restore_simulation_thread.exception_happened)

    def __start_sample_restore_client(self, file_location):
        self.process = subprocess.Popen([SAMPLE_RESTORE_CLIENT, file_location], stderr=subprocess.PIPE)
        time.sleep(0.5)

    def __stop_sample_restore_client_and_return_output(self):
        subprocess.call(['kill', str(self.process.pid)])
        return self.process.communicate()[1]


if __name__ == "__main__":
    unittest.main()
