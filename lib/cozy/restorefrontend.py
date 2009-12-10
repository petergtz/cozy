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

import pygtk
pygtk.require('2.0')
import gtk

from cozyutils.date_helper import epoche2date

import os
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
BUILDER_XML_PATH = os.path.join(BASE_DIR, 'restore_window.xml')

class RestoreFrontend(object):
    def __init__(self, restore_control_center, close_func):
        self.restore_control_center = restore_control_center
        self.builder = gtk.Builder()
        self.builder.add_from_file(BUILDER_XML_PATH)
        self.main_window = self.builder.get_object('main_window')
        self.__do_stupid_fancy_window_arrangements()
        self.builder.connect_signals(self)
        self.current_point_in_time_label = self.builder.get_object('current_point_in_time')
        self.dates_listbox = self.builder.get_object('dates')

        self.__set_up_dates_listbox()

        self.__update_dates_combobox()

        self.close_func = close_func

        self.main_window.show_all()

    def __do_stupid_fancy_window_arrangements(self):
        screen = self.main_window.get_screen()
        self.main_window.move(0, screen.get_height() - 40)
        self.main_window.resize(screen.get_width(), 40)
        self.main_window.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color(60000, 40000, 15000))
        self.main_window.set_keep_above(True)

    def __set_up_dates_listbox(self):
        liststore = gtk.ListStore(str)
        self.dates_listbox.set_model(liststore)
        cell = gtk.CellRendererText()
        self.dates_listbox.pack_start(cell, True)
        self.dates_listbox.add_attribute(cell, 'text', 0)

        self.version2index = dict()
        self.index2version = dict()
        index = 0
        for version in self.restore_control_center.get_all_versions():
            if version == -1:
                formatted = 'Now'
            else:
                datetime = epoche2date(version)
                date, time = datetime.split('_')
                formatted = date + '  ' + time.replace('-', ':')

            self.index2version[index] = version
            self.version2index[version] = index
            index += 1

            self.dates_listbox.append_text(formatted)


    def __update_dates_combobox(self):
        self.dates_listbox.set_active(self.version2index[self.restore_control_center.current_version])

    def on_previous_button_clicked(self, widget, data=None):
        self.restore_control_center.go_to_previous_version()
        self.__update_dates_combobox()

    def on_next_button_clicked(self, widget, data=None):
        self.restore_control_center.go_to_next_version()
        self.__update_dates_combobox()

    def on_dates_changed(self, combobox):
        version_text = self.dates_listbox.get_active()
        self.restore_control_center.go_to_version(self.index2version[version_text])
        self.__update_dates_combobox()

    def on_main_window_destroy(self, widget):
        self.main_window.hide_all()
#        self.main_window.destroy()
        self.close_func()

