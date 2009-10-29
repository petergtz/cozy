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

class StandardFallbackRestoreClientLoader(object):
    def __init__(self, data_path):
        self.data_path = data_path

    def load_and_register(self, restore_client_connector):
        session_bus = dbus.SessionBus()
        nautilus_app = session_bus.get_object('org.gnome.Nautilus', '/NautilusApplication')
        object_path = nautilus_app.create_navigation_window()
        nautilus_window = session_bus.get_object('org.gnome.Nautilus', object_path)
        nautilus_window.go_to('file://' + self.data_path, dbus_interface='org.gnome.NautilusWindow')
        restore_client_connector.register_me(object_path, 'org.gnome.NautilusWindow', 'go_to', 'get_location_uri', 'org.gnome.Nautilus')

