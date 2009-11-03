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

from dbus.mainloop.glib import DBusGMainLoop

from  cozy.configuration import Configuration
import pygtk
pygtk.require('2.0')
import gtk

from cozy.configurationdialog import ConfigMediator


def main(program_paths):
    DBusGMainLoop(set_as_default=True)


    config = Configuration()
    mediator = ConfigMediator(program_paths, config)
    mediator.show_all()
    gtk.main()

if __name__ == "__main__":
    class ProgramPaths(object):
        def __init__(self):
            self.COZY_BACKUP_APPLET_PATH = 'cozy-backup-applet'
            self.COZY_BACKUP_PATH = 'cozy-backup'
    main(ProgramPaths())
