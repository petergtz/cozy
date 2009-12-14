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

import os
import pygtk
pygtk.require('2.0')
import gtk

from cozy.pathbasedbackuplocation import PathBasedBackupLocation
from cozy.removeablebackuplocation import RemoveableBackupLocation
from cozy.locationmanager import LocationManager

import dbus



import subprocess

import re
import xdg.BaseDirectory, xdg.DesktopEntry

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

COZY_MKFS_PATH = 'mkfs.cozyfs.py'

BUILDER_XML_PATH = os.path.join(BASE_DIR, 'configuration_dialog.xml')


class ConfigMediator:
    def __init__(self, program_paths, config, return_func):
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

        self.config = config
        self.return_func = return_func

        self.__setup_controls()

    def __setup_controls(self):
        if self.config.backup_enabled is not None:
            self.enable_checkbox.set_active(self.config.backup_enabled)
        else:
            print "No configuration found. Creating new one with backup disabled."
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
                    backup_location = RemoveableBackupLocation(dbus.SystemBus(), uuid, rel_path)
                    self.volume_name_label.set_text(backup_location.volume_label())
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
            backup_location = RemoveableBackupLocation(dbus.SystemBus(), arbitrary_path=dlg.get_filename())
            self.config.backup_location_identifier = backup_location.serialize()
            self.volume_name_label.set_text(backup_location.volume_label())
            self.relative_path_label.set_text(backup_location.rel_path)
        dlg.destroy()

    def on_radio_cozyfs_changed(self, widget, data=None):
        if widget.get_active():
            self.config.backup_type = 'CozyFS'

    def on_radio_plainfs_changed(self, widget, data=None):
        if widget.get_active():
            self.config.backup_type = 'PlainFS'

    def on_reset(self, widget, data=None):
        self.config.forget_changes()
        self.__setup_controls()

    def on_close(self, widget, data=None):
        if self.__can_close():
            self.destroy(widget, data)

    def delete_event(self, widget, event, data=None):
        return not self.__can_close()

    def __can_close(self):
        if self.config.changed():
            return self.__can_close_although_changed()
        else:
            return True

    def __can_close_although_changed(self):
        if self.config.backup_enabled:
            if self.__config_is_incomplete():
                result = self.__handle_incomplete_config()
                if result == 'cannot_close':
                    return False
        return True


    def __config_is_incomplete(self):
        return self.config.backup_location_identifier is None or self.config.data_path is None

    def __handle_incomplete_config(self):
        result = self.__show_confirmation_dailog_and_return_result()
        if result == 2:
            return 'cannot_close'
        else:
            self.config.backup_enabled = False
            return 'can_close'

    def __show_confirmation_dailog_and_return_result(self):
        dialog = self.builder.get_object("config_not_complete_confirmation_dialog")
        result = dialog.run()
        dialog.hide()
        return result

    def destroy(self, widget, data=None):
        self.configuration_window.hide()
        if self.config.changed():
            self.config.write()
            self.__react_on_config_changes()

        self.return_func()


    def __react_on_config_changes(self):
        if self.config.backup_enabled:
            self.__create_filestructure_in_backup_location()
            self.__add_backup_applet_autostart()
            if self.config.backup_location_type == 'absolute_path':
                self.__add_crontab_entry()
            else:
                self.__remove_crontab_entry()
        else:
            self.__remove_crontab_entry()
            self.__remove_backup_applet_autostart()

    def __create_filestructure_in_backup_location(self):
        system_bus = dbus.SystemBus()
        location_manager = LocationManager(system_bus)
        backup_location = location_manager.get_backup_location(self.config)
        backup_path = backup_location.get_path()
        if self.config.backup_type == 'CozyFS':
            subprocess.check_call([COZY_MKFS_PATH, '--no-version', backup_path, str(self.config.backup_id)])
        elif self.config.backup_type == 'PlainFS':
            os.makedirs(os.path.join(backup_path, str(self.config.backup_id), '0'))
        elif self.config.backup_type == 'HardlinkedFS':
            pass

    def present(self):
        self.configuration_window.present()

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

    def __add_backup_applet_autostart(self):
        entry = xdg.DesktopEntry.DesktopEntry(os.path.join(xdg.BaseDirectory.xdg_config_home, 'autostart', 'cozy-backup-applet.desktop'))
        entry.set("Type", "Application")
        entry.set("Name", "Cozy Backup Applet")
        entry.set("Exec", self.program_paths.COZY_BACKUP_APPLET_PATH)
        entry.set("Icon", "cozy")
        entry.write()

    def __remove_backup_applet_autostart(self):
        if os.path.exists(os.path.join(xdg.BaseDirectory.xdg_config_home, 'cozy-backup-applet.desktop')):
            os.remove(os.path.join(xdg.BaseDirectory.xdg_config_home, 'cozy-backup-applet.desktop'))


    def show_all(self):
        self.configuration_window.show_all()
