#!/usr/bin/python

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
from dbus.mainloop.glib import DBusGMainLoop
import gobject
import dbus
import dbus.service
import sys


class SampleRestoreClient(dbus.service.Object):
    def __init__(self, current_path, session_bus):
        dbus.service.Object.__init__(self, session_bus, '/org/freedesktop/SampleRestoreClient')

        self.current_path = current_path

        self.session_bus = session_bus

        session_bus.add_signal_receiver(self.on_enter_restore_mode, 'enter_restore_mode_event',
                                        None, None, None)
        session_bus.add_signal_receiver(self.on_exit_restore_mode, 'exit_restore_mode_event',
                                        None, None, None)
        self.restore_control_center = None

    def on_enter_restore_mode(self):
        sys.stderr.write("received an enter restore mode event\n")
        self.restore_control_center = self.session_bus.get_object('org.freedesktop.Cozy', '/org/freedesktop/Cozy/RestoreControlCenter')
        self.restore_control_center.register_me('/org/freedesktop/SampleRestoreClient', dbus_interface='org.freedesktop.Cozy.RestoreControlCenter',
                                           reply_handler=self.__reply_handler, error_handler=self.__error_handler)

    def __reply_handler(self):
        pass

    def __error_handler(self, e):
        raise Exception(str(e))

    def on_exit_restore_mode(self):
        sys.stderr.write("received an exit restore mode event\n")
        self.go_to_version(-1)

        self.restore_control_center = None

    @dbus.service.method(dbus_interface='org.freedesktop.Cozy.RestoreClient',
                         in_signature='i')
    def go_to_version(self, version):
        sys.stderr.write("go_to_version(" + str(version) + ')\n')
        if self.restore_control_center.is_path_in_backup_data(self.current_path):
            self.restore_control_center.get_path_in_the_past(self.current_path, version,
                     reply_handler=self.__get_path_in_the_past_reply,
                     error_handler=self.__get_path_in_the_past_error)
        else:
            raise Exception("jkjh")


    def __get_path_in_the_past_reply(self, path):
        self.current_path = path
        sys.stderr.write('Got past in the past reply: ' + self.current_path + '\n')
#        if self.restore_control_center is not None:
#            self.restore_control_center.go_to_version_reply_real_handler(
#                reply_handler=self.__reply_handler,
#                error_handler=self.__error_handler)


    def __get_path_in_the_past_error(self, e):
#        if self.restore_control_center is not None:
#            self.restore_control_center.go_to_version_error_real_handler(
#                reply_handler=self.__reply_handler,
#                error_handler=self.__error_handler)
        pass


def main():
    DBusGMainLoop(set_as_default=True)
    session_bus = dbus.SessionBus()
    bus_name = dbus.service.BusName('org.freedesktop.SampleRestoreClient', session_bus)
    mainloop = gobject.MainLoop()

    sample_restore_client = SampleRestoreClient(sys.argv[1], session_bus)

    mainloop.run()

if __name__ == '__main__':
    main()
