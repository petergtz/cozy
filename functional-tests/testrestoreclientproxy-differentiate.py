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
            return re.sub('\/my\/tmp\/mountpath\/.', '/my/tmp/mountpath/', path) + str(version)

        return ''

class RestoreSimulationThread(threading.Thread):

    def __init__(self, mainloop, restore_client_proxy):
        threading.Thread.__init__(self)
        self.mainloop = mainloop
        self.restore_client_proxy = restore_client_proxy

    def run(self):
        try:
            self.__setUp()
            self._test()
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
        raise NotImplementedError()

    def __tearDown(self):
        time.sleep(0.5)
        self.restore_client_proxy.exit_restore_mode_event()
        time.sleep(0.5)
        self.mainloop.quit()

class RestoreSimulationThreadGoToVersion3(RestoreSimulationThread):
    def __init__(self, mainloop, restore_client_proxy):
        RestoreSimulationThread.__init__(self, mainloop, restore_client_proxy)

    def _test(self):
        self.restore_client_proxy.go_to_version(3)

class RestoreSimulationThreadGoToVersion32(RestoreSimulationThread):
    def __init__(self, mainloop, restore_client_proxy):
        RestoreSimulationThread.__init__(self, mainloop, restore_client_proxy)

    def _test(self):
        self.restore_client_proxy.go_to_version(3)
        self.restore_client_proxy.go_to_version(2)



EXCPECTED_OUTPUT_FROM_GO_TO_VERSION_3 = \
'''received an enter restore mode event
go_to_version(3)
Got past in the past reply: /my/tmp/mountpath/3/my_file
received an exit restore mode event
'''

EXCPECTED_OUTPUT_FROM_GO_TO_VERSION_32 = \
'''received an enter restore mode event
go_to_version(3)
Got past in the past reply: /my/tmp/mountpath/3/my_file
go_to_version(2)
Got past in the past reply: /my/tmp/mountpath/2/my_file
received an exit restore mode event
'''

class TestRestoreClientProxy(unittest.TestCase):

    def __init__(self, mthodname):
        unittest.TestCase.__init__(self, mthodname)
        gobject.threads_init()

        DBusGMainLoop(set_as_default=True)
        self.session_bus = dbus.SessionBus()
        self.bus_name = dbus.service.BusName('org.freedesktop.Cozy', self.session_bus)
        self.mainloop = gobject.MainLoop()


    def setUp(self):

        self.process = subprocess.Popen([SAMPLE_RESTORE_CLIENT], stderr=subprocess.PIPE)
        time.sleep(0.5)

        fake_restore_backend = FakeRestoreBackend()
        self.restore_client_proxy = cozy.restoreclientproxy.RestoreClientProxy(self.session_bus, fake_restore_backend)

    def tearDown(self):
#        del self.bus_name
#        del self.mainloop
 #       del self.process
        del self.restore_client_proxy
        time.sleep(1)


    def __run(self, restore_simulation_thread):
        restore_simulation_thread.start()

        self.mainloop.run()

#        process.kill()
        subprocess.call(['kill', str(self.process.pid)])
        (stdoutdata, stderrdata) = self.process.communicate()
        return stderrdata


    def test_restore_client_go_to_version_3(self):
        restore_simulation_thread = RestoreSimulationThreadGoToVersion3(self.mainloop, self.restore_client_proxy)

        output = self.__run(restore_simulation_thread)

        self.assertEquals(output, EXCPECTED_OUTPUT_FROM_GO_TO_VERSION_3)

    def test_restore_client_go_to_version_32(self):
        restore_simulation_thread = RestoreSimulationThreadGoToVersion32(self.mainloop, self.restore_client_proxy)

        output = self.__run(restore_simulation_thread)

        self.assertEquals(output, EXCPECTED_OUTPUT_FROM_GO_TO_VERSION_32)


if __name__ == "__main__":
    unittest.main()
