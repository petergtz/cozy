#!/usr/bin/python

from __future__ import with_statement

import os.path
import ConfigParser
import dbus

import random

from  utils.md5sum import md5sum_from_string

class Configuration(object):

    def __init__(self, filename=None):
        self.parser = ConfigParser.SafeConfigParser()
        if filename is None:
            result = self.parser.read(os.path.expanduser('~/.cozy'))
        else:
            result = self.parser.read(filename)
        if len(result) == 0:
            self.parser.add_section('globals')
            self.parser.add_section('backup_location')
            self.backup_id = random.randint(1, 100000)

        self.backup_id_changed = False
        self.backup_enabled_changed = False
        self.data_path_changed = False
        self.backup_location_type_changed = False
        self.backup_location_identifier_changed = False

    def write(self):
        with open(os.path.expanduser('~/.cozy'), 'w') as fp:
            self.parser.write(fp)

    def __get_backup_enabled(self):
        try:
            return self.parser.getboolean('globals', 'backup_enabled')
        except ConfigParser.Error, e:
            return None

    def __set_backup_enabled(self, enable):
        self.backup_enabled_changed = self.backup_enabled != enable
        self.parser.set('globals', 'backup_enabled', str(enable))

    def __get_data_path(self):
        try:
            return self.parser.get('globals', 'data_path').rstrip('/')
        except ConfigParser.Error, e:
            return None

    def __set_data_path(self, data_path):
        self.data_path_changed = self.data_path != data_path
        self.parser.set('globals', 'data_path', data_path)

    def __get_backup_id(self):
        try:
            return self.parser.getint('globals', 'backup_id')
        except ConfigParser.Error, e:
            None

    def __set_backup_id(self, backup_id):
        self.backup_id_changed = self.backup_id != backup_id
        if not isinstance(backup_id, int):
            raise TypeError()
        self.parser.set('globals', 'backup_id', str(backup_id))

    def __get_backup_location_identifier(self):
        try:
            return self.parser.get('backup_location', 'location_identifier')
        except ConfigParser.Error, e:
            None

    def __set_backup_location_identifier(self, value):
        self.backup_location_identifier_changed = self.backup_location_identifier != value
        self.parser.set('backup_location', 'location_identifier', value)

#    def __get_backup_location_name(self):
#        try:
#            location_identifier = self.parser.get('backup_location', 'location_identifier')
##            return '/org/freedesktop/Cozy/BackupLocations/' + location_identifier.replace('/', '_').replace(':', '_')
#            return '/org/freedesktop/Cozy/BackupLocations/' + md5sum_from_string(location_identifier)
#        except ConfigParser.Error, e:
#            None

    def __get_backup_location_type(self):
        try:
            return self.parser.get('backup_location', 'location_type')
        except ConfigParser.Error, e:
            None

    def __set_backup_location_type(self, value):
        self.backup_location_type_changed = self.backup_location_type != value
        self.parser.set('backup_location', 'location_type', value)

    def changed(self):
        return self.backup_id_changed or self.backup_enabled_changed or self.data_path_changed or self.backup_location_type_changed or self.backup_location_identifier_changed

    backup_enabled = property(__get_backup_enabled, __set_backup_enabled)
    data_path = property(__get_data_path, __set_data_path)
    backup_id = property(__get_backup_id, __set_backup_id)

    backup_location_type = property(__get_backup_location_type, __set_backup_location_type)
#    backup_location_name = property(__get_backup_location_name)
    backup_location_identifier = property(__get_backup_location_identifier, __set_backup_location_identifier)
