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
    def __init__(self, restore_control_center, mainloop):
        self.restore_control_center = restore_control_center
        self.builder = gtk.Builder()
        self.builder.add_from_file(BUILDER_XML_PATH)
        self.main_window = self.builder.get_object('main_window')
        self.builder.connect_signals(self)
        self.current_point_in_time_label = self.builder.get_object('current_point_in_time')
        self.dates_listbox = self.builder.get_object('dates')

        liststore = gtk.ListStore(str)
        self.dates_listbox.set_model(liststore)
        cell = gtk.CellRendererText()
        self.dates_listbox.pack_start(cell, True)
        self.dates_listbox.add_attribute(cell, 'text', 0)

        self.version2formatted = dict()
        self.formatted2version = dict()
        for version in restore_control_center.get_all_versions():
            if version == -1:
                self.formatted2version["Now"] = -1
                self.version2formatted[-1] = 'Now'
                self.dates_listbox.append_text('Now')
            else:
                datetime = epoche2date(version)
                date, time = datetime.split('_')
                formatted = date + '  ' + time.replace('-', ':')
                self.formatted2version[formatted] = version
                self.version2formatted[version] = formatted
                self.dates_listbox.append_text(formatted)

        self.__update_point_in_time_label()

        self.mainloop = mainloop
        self.main_window.show_all()

    def __update_point_in_time_label(self):
        self.current_point_in_time_label.set_text(self.version2formatted[self.restore_control_center.current_version])


    def on_previous_button_clicked(self, widget, data=None):
        self.restore_control_center.go_to_previous_version()
        self.__update_point_in_time_label()

    def on_next_button_clicked(self, widget, data=None):
        self.restore_control_center.go_to_next_version()
        self.__update_point_in_time_label()

    def on_main_window_destroy(self, widget):
        self.mainloop.quit()

