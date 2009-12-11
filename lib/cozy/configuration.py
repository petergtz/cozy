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
import ConfigParser

import random

class Configuration(object):

    def __init__(self, filename=None):
        self.filename = filename
        self.__init()

    def write(self):
        with open(os.path.expanduser('~/.cozy'), 'w') as fp:
            self.parser.write(fp)
            self.__set_unchanged()

    def forget_changes(self):
        self.__init()

    def __init(self):
        self.parser = ConfigParser.SafeConfigParser()
        if self.filename is None:
            result = self.parser.read(os.path.expanduser('~/.cozy'))
        else:
            result = self.parser.read(self.filename)
        if len(result) == 0:
            self.parser.add_section('globals')
            self.parser.add_section('backup_location')
            self.parser.add_section('backup')
            self.backup_id = random.randint(1, 100000)
        self.__set_unchanged()


    def __set_unchanged(self):
        self.backup_id_changed = False
        self.backup_enabled_changed = False
        self.data_path_changed = False
        self.backup_location_type_changed = False
        self.backup_location_identifier_changed = False
        self.backup_type_changed = False

    def __get_backup_enabled(self):
        try:
            return self.parser.getboolean('globals', 'backup_enabled')
        except ConfigParser.Error:
            return None

    def __set_backup_enabled(self, enable):
        self.backup_enabled_changed = self.backup_enabled != enable
        self.parser.set('globals', 'backup_enabled', str(enable))

    def __get_data_path(self):
        try:
            return self.parser.get('globals', 'data_path').rstrip('/')
        except ConfigParser.Error:
            return None

    def __set_data_path(self, data_path):
        self.data_path_changed = self.data_path != data_path
        self.parser.set('globals', 'data_path', data_path)

    def __get_backup_id(self):
        try:
            return self.parser.getint('backup', 'backup_id')
        except ConfigParser.Error:
            None

    def __set_backup_id(self, backup_id):
        self.backup_id_changed = self.backup_id != backup_id
        if not isinstance(backup_id, int):
            raise TypeError()
        self.parser.set('backup', 'backup_id', str(backup_id))

    def __get_backup_type(self):
        try:
            return self.parser.get('backup', 'type')
        except ConfigParser.Error:
            None

    def __set_backup_type(self, value):
        self.backup_type_changed = self.backup_type != value
        self.parser.set('backup', 'type', value)

    def __get_backup_location_identifier(self):
        try:
            return self.parser.get('backup_location', 'location_identifier')
        except ConfigParser.Error:
            None

    def __set_backup_location_identifier(self, value):
        self.backup_location_identifier_changed = self.backup_location_identifier != value
        self.parser.set('backup_location', 'location_identifier', value)


    def __get_backup_location_type(self):
        try:
            return self.parser.get('backup_location', 'location_type')
        except ConfigParser.Error:
            None

    def __set_backup_location_type(self, value):
        self.backup_location_type_changed = self.backup_location_type != value
        self.parser.set('backup_location', 'location_type', value)

    def changed(self):
        return (self.backup_id_changed or self.backup_enabled_changed or self.data_path_changed or
            self.backup_location_type_changed or self.backup_location_identifier_changed or
            self.backup_type_changed)

    backup_enabled = property(__get_backup_enabled, __set_backup_enabled)
    data_path = property(__get_data_path, __set_data_path)
    backup_id = property(__get_backup_id, __set_backup_id)
    backup_type = property(__get_backup_type, __set_backup_type)

    backup_location_type = property(__get_backup_location_type, __set_backup_location_type)
    backup_location_identifier = property(__get_backup_location_identifier, __set_backup_location_identifier)
