#! /usr/bin/python

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

import os.path
import os

import pygtk
pygtk.require('2.0')
import gtk

from dbus.mainloop.glib import DBusGMainLoop

from  cozy.configuration import Configuration

import subprocess
import time

import re

from cozy.pathbasedbackuplocation import PathBasedBackupLocation
from cozy.removeablebackuplocation import RemoveableBackupLocation
from cozy.locationmanager import LocationManager
import dbus

import xdg.BaseDirectory, xdg.DesktopEntry

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

COZY_MKFS_PATH = 'mkfs.cozyfs.py'

BUILDER_XML_PATH = os.path.join(BASE_DIR, 'configuration_dialog.xml')

class ConfigMediator:
    def __init__(self, program_paths=None):

#        self.parent = parent
        self.builder = gtk.Builder()
        self.builder.add_from_file(BUILDER_XML_PATH)

        self.program_paths = program_paths

        self.configuration_window = self.builder.get_object('configuration_window')
        self.enable_checkbox = self.builder.get_object('enable_checkbox')
        self.global_sections = self.builder.get_object('global_sections')
        self.temp_radio = self.builder.get_object('temp_radio')
        self.permanent_radio = self.builder.get_object('permanent_radio')
        self.source_path_label = self.builder.get_object('source_path_label')
        self.absolute_path_label = self.builder.get_object('absolute_path_label')
        self.volume_name_label = self.builder.get_object('volume_name_label')
        self.relative_path_label = self.builder.get_object('relative_path_label')
        self.permanent_group = self.builder.get_object('permanent_group')
        self.temp_group = self.builder.get_object('temp_group')

        self.cozyfs_radio = self.builder.get_object('radio_cozyfs')
        self.plainfs_radio = self.builder.get_object('radio_plainfs')

        self.builder.connect_signals(self)

        self.config = Configuration()

        self.__setup_controls()

    def __setup_controls(self):
        if self.config.backup_enabled is not None:
            self.enable_checkbox.set_active(self.config.backup_enabled)
        else:
            print "Warning: Cozy backup is not configured properly"
            print "Disabling backup."
            self.enable_checkbox.set_active(False)

        self.global_sections.set_sensitive(self.enable_checkbox.get_active())

        if self.config.data_path is not None:
            self.source_path_label.set_text(self.config.data_path)
        else:
            self.source_path_label.set_text('Not configured')

        identifier = self.config.backup_location_identifier
        if self.config.backup_location_type is not None:
            if self.config.backup_location_type == 'removeable_volume':
                self.temp_radio.set_active(True)
                if identifier is not None:
                    uuid, rel_path = identifier.split(':')
                    self.volume_name_label.set_text(uuid)
                    self.relative_path_label.set_text(rel_path)
                else:
                    self.volume_name_label.set_text('Not configured')
                    self.relative_path_label.set_text('Not configured')
            else:
                self.permanent_radio.set_active(True)
                if identifier is not None:
                    self.absolute_path_label.set_text(identifier)
                else:
                    self.absolute_path_label.set_text('Not configured')
        else:
            self.permanent_radio.set_active(True)
            self.absolute_path_label.set_text('Not configured')

        self.on_permanent_mode_changed(self.permanent_radio)
        self.on_temporary_mode_changed(self.temp_radio)

        if self.config.backup_type is not None:
            if self.config.backup_type == 'CozyFS':
                self.cozyfs_radio.set_active(True)
            elif self.config.backup_type == 'PlainFS':
                self.plainfs_radio.set_active(True)

        self.on_radio_cozyfs_changed(self.cozyfs_radio)
        self.on_radio_plainfs_changed(self.plainfs_radio)

    def on_backup_enable(self, widget, data=None):
        self.global_sections.set_sensitive(widget.get_active())
        self.config.backup_enabled = widget.get_active()

    def on_choose_source_btn_clicked(self, widget, data=None):
        dlg = gtk.FileChooserDialog(action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                                    buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        if dlg.run() == gtk.RESPONSE_OK:
            self.config.data_path = dlg.get_filename()
            self.source_path_label.set_text(self.config.data_path)
        dlg.destroy()

    def on_permanent_mode_changed(self, widget, data=None):
        if widget.get_active():
            self.config.backup_location_type = 'absolute_path'
            self.permanent_group.set_sensitive(True)
        else:
            self.permanent_group.set_sensitive(False)

    def on_temporary_mode_changed(self, widget, data=None):
        if widget.get_active():
            self.config.backup_location_type = 'removeable_volume'
            self.temp_group.set_sensitive(True)
        else:
            self.temp_group.set_sensitive(False)

    def on_choose_permanent_target_btn_clicked(self, widget, data=None):
        dlg = gtk.FileChooserDialog(action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                                    buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        if dlg.run() == gtk.RESPONSE_OK:
            backup_location = PathBasedBackupLocation(dlg.get_filename())
            self.config.backup_location_identifier = backup_location.serialize()
            self.absolute_path_label.set_text(backup_location.path)
        dlg.destroy()


    def on_choose_temp_target_btn_clicked(self, widget, data=None):
        dlg = gtk.FileChooserDialog(action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                                    buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        if dlg.run() == gtk.RESPONSE_OK:
            backup_location = RemoveableBackupLocation(arbitrary_path=dlg.get_filename())
            self.config.backup_location_identifier = backup_location.serialize()
            self.volume_name_label.set_text(backup_location.uuid)
            self.relative_path_label.set_text(backup_location.rel_path)
        dlg.destroy()

    def on_radio_cozyfs_changed(self, widget, data=None):
        if widget.get_active():
            self.config.backup_type = 'CozyFS'

    def on_radio_plainfs_changed(self, widget, data=None):
        if widget.get_active():
            self.config.backup_type = 'PlainFS'

    def on_reset(self, widget, data=None):
        self.config = Configuration()
        self.__setup_controls()

    def on_close(self, widget, data=None):
        if not self.delete_event(widget, None):
           self.destroy(widget, data)

    def __applet_running(self):
        a = os.system("ps -ef | grep -v grep | grep " +
                            os.path.basename(self.program_paths.COZY_BACKUP_APPLET_PATH))
        if a != 0:
            return False
        return True

    def __start_applet_if_not_running(self):
        if not self.__applet_running():
            subprocess.Popen([self.program_paths.COZY_BACKUP_APPLET_PATH])

    def __stop_applet_if_running(self):
        if self.__applet_running():
            subprocess.call(['killall', os.path.basename(self.program_paths.COZY_BACKUP_APPLET_PATH)])

    def __add_restore_backend_autostart(self):
        entry = xdg.DesktopEntry.DesktopEntry(os.path.join(xdg.BaseDirectory.xdg_config_home, 'autostart', 'cozy-restore-backend.desktop'))
        entry.set("Type", "Application")
        entry.set("Name", "Cozy Restore Backend")
        entry.set("Exec", self.program_paths.COZY_RESTORE_BACKEND_PATH + " start")
        entry.set("Icon", "cozy")
        entry.write()


    def __add_backup_applet_autostart(self):
        entry = xdg.DesktopEntry.DesktopEntry(os.path.join(xdg.BaseDirectory.xdg_config_home, 'autostart', 'cozy-backup-applet.desktop'))
        entry.set("Type", "Application")
        entry.set("Name", "Cozy Backup Applet")
        entry.set("Exec", self.program_paths.COZY_BACKUP_APPLET_PATH)
        entry.set("Icon", "cozy")
        entry.write()


    def __remove_restore_backend_autostart(self):
        if os.path.exists(os.path.join(xdg.BaseDirectory.xdg_config_home, 'cozy-restore-backend.desktop')):
            os.remove(os.path.join(xdg.BaseDirectory.xdg_config_home, 'cozy-restore-backend.desktop'))

    def __remove_backup_applet_autostart(self):
        if os.path.exists(os.path.join(xdg.BaseDirectory.xdg_config_home, 'cozy-backup-applet.desktop')):
            os.remove(os.path.join(xdg.BaseDirectory.xdg_config_home, 'cozy-backup-applet.desktop'))

    def delete_event(self, widget, event, data=None):
        if self.config.changed():
            self.config.write()
            if not self.config.backup_enabled:
                self.__stop_applet_if_running()
                self.__stop_restore_backend()
                self.__remove_crontab_entry()
                self.__remove_backup_applet_autostart()
                self.__remove_restore_backend_autostart()
                return False

            if self.config.backup_location_identifier is None or self.config.data_path is None:
                dialog = self.builder.get_object("config_not_complete_confirmation_dialog")
                result = dialog.run()
                dialog.hide()

                if result == 2:
                    return True
                else:
                    self.config.backup_enabled = False
                    return self.delete_event(widget, event, data)

            location_manager = LocationManager(self.config, dbus.SystemBus())
            backup_location = location_manager.get_backup_location()
            subprocess.call([COZY_MKFS_PATH, backup_location.get_path(), str(self.config.backup_id)])
            if self.permanent_radio.get_active():
                self.__add_crontab_entry()
                self.__stop_applet_if_running()
                self.__remove_backup_applet_autostart()
            else:
                self.__remove_crontab_entry()
                self.__start_applet_if_not_running()
                self.__add_backup_applet_autostart()
            self.__restart_restore_backend()
            self.__add_restore_backend_autostart()
        return False

    def destroy(self, widget, data=None):
        self.configuration_window.hide()
#        if self.parent is None:
        gtk.main_quit()


    def __restart_restore_backend(self):
        os.system(self.program_paths.COZY_RESTORE_BACKEND_PATH + ' restart')
        time.sleep(2)

    def __stop_restore_backend(self):
        os.system(self.program_paths.COZY_RESTORE_BACKEND_PATH + ' stop')
        time.sleep(2)

#        if process.poll() is not None:
#            if process.poll() == 1:
#                print 'Could not start cozy-manager due do disabled or incomplete configuration. cozy-applet will not work properly. TODO: should be a popup-window.'
#            elif process.poll() == 2:
#                print 'Could not start cozy-manager. cozy-applet will not work properly. TODO: should be a popup-window.'
#            else:
#                print 'Could not start cozy-manager due to unknown reasons. cozy-applet will not work properly. TODO: should be a popup-window.'

    def __add_crontab_entry(self):
        pid = subprocess.Popen(['crontab', '-l'], stdout=subprocess.PIPE)
        crontab = pid.stdout.read()
        new_crontab = re.sub('(?m)^.*cozy-backup -s\n', '', crontab)
        new_crontab += '*/60 * * * * ' + self.program_paths.COZY_BACKUP_PATH + ' -s\n'
        pid = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE)
        pid.stdin.write(new_crontab)
        pid.stdin.close()

    def __remove_crontab_entry(self):
        pid = subprocess.Popen(['crontab', '-l'], stdout=subprocess.PIPE)
        crontab = pid.stdout.read()
        new_crontab = re.sub('(?m)^.*cozy-backup -s\n', '', crontab)
        pid = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE)
        pid.stdin.write(new_crontab)
        pid.stdin.close()


    def show_all(self):
        self.configuration_window.show_all()

def main(program_paths):
    DBusGMainLoop(set_as_default=True)

    mediator = ConfigMediator(program_paths)
    mediator.show_all()
    gtk.main()

if __name__ == "__main__":
    class ProgramPaths(object):
        def __init__(self):
            self.COZY_RESTORE_BACKEND_PATH = 'cozy-restore-backend'
            self.COZY_BACKUP_APPLET_PATH = 'cozy-backup-applet'
            self.COZY_BACKUP_PATH = 'cozy-backup'
    main(ProgramPaths())

