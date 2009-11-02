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

import dbus
import dbus.service
import time

class RestoreClient(object):
    pass

class RestoreClientConnector(dbus.service.Object):
    def __init__(self, session_bus, standard_fallback_restore_client_loader):
        dbus.service.Object.__init__(self, session_bus, '/org/freedesktop/Cozy/RestoreControlCenter')
        self.standard_fallback_restore_client_loader = standard_fallback_restore_client_loader
        self.session_bus = session_bus
        self.restore_client = None

    def get_restore_client(self):
        self.restore_client = None
        self.enter_restore_mode_event()
        time.sleep(1)
        if not self.__has_restore_client():
            self.standard_fallback_restore_client_loader.load_and_register(self)
        if self.__has_restore_client():
            return self.restore_client
        else:
            raise Exception('Error: Could not load the standard fallback restore client')

    @dbus.service.signal(dbus_interface='org.freedesktop.Cozy.RestoreControlCenter',
                         signature='')
    def enter_restore_mode_event(self):
        print 'enter_restore_mode_event'
        pass

    @dbus.service.method(dbus_interface='org.freedesktop.Cozy.RestoreControlCenter',
                         in_signature='ssss', sender_keyword='restore_client_bus_name')
    def register_me(self,
                    restore_client_object_path,
                    restore_client_interface_name,
                    restore_client_go_to_path_method_name,
                    restore_client_get_path_method_name,
                    restore_client_bus_name=None):
        print 'register_me'
        restore_client_object = self.session_bus.get_object(restore_client_bus_name,
                                                       restore_client_object_path)
        restore_client = dbus.Interface(restore_client_object, dbus_interface=restore_client_interface_name)
        self.restore_client = RestoreClient()
        self.restore_client.go_to_path = \
                restore_client.get_dbus_method(restore_client_go_to_path_method_name)
        self.restore_client.get_path = \
                restore_client.get_dbus_method(restore_client_get_path_method_name)

    def __has_restore_client(self):
        return self.restore_client is not None

