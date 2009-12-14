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

from cozy.pathbasedbackuplocation import PathBasedBackupLocation
from cozy.removeablebackuplocation import RemoveableBackupLocation
from cozy.backuplocation import BackupLocation

class NoneBackupLocation(BackupLocation):
    def get_path(self):
        assert False, 'A NoneBackupLocation has no path. Logical Error!'

    def is_available(self):
        return False

    def serialize(self):
        return 'None'


class LocationManager(object):

    def __init__(self, system_bus):
        self.system_bus = system_bus

    def get_backup_location(self, config):
        if config.backup_location_identifier is None:
            return NoneBackupLocation()

        if config.backup_location_type == 'absolute_path':
            return PathBasedBackupLocation(config.backup_location_identifier)
        elif config.backup_location_type == 'removeable_volume':
            uuid, rel_path = config.backup_location_identifier.split(':')
            return RemoveableBackupLocation(self.system_bus, uuid, rel_path)
        elif config.backup_location_type is None:
            return NoneBackupLocation()
        else:
            raise Exception('Unknown location type.')

