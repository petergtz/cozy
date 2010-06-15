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

import os
from pyinotify import WatchManager, Notifier, ThreadedNotifier, EventsCodes, ProcessEvent
import pyinotify

wm = WatchManager()


mask = 0
FLAGS = EventsCodes.ALL_FLAGS

mask |= FLAGS['IN_MOVED_FROM']
mask |= FLAGS['IN_MOVED_TO']
mask |= FLAGS['IN_CLOSE_WRITE']
mask |= FLAGS['IN_DELETE']
mask |= FLAGS['IN_CREATE']
mask |= FLAGS['IN_MODIFY']
mask |= FLAGS['IN_CLOSE_NOWRITE']
mask |= FLAGS['IN_OPEN']

class PTmp(ProcessEvent):
    def process_IN_CREATE(self, event):
        print "Create: %s" % os.path.join(event.path, event.name)

    def process_IN_DELETE(self, event):
        print "Remove: %s" % os.path.join(event.path, event.name)

    def process_IN_ACCESS(self, event):
        print "Access: %s" % os.path.join(event.path, event.name)

    def process_IN_CLOSE_WRITE(self, event):
        print "Close Write: %s" % os.path.join(event.path, event.name)

    def process_IN_MOVED_FROM(self, event):
        print "Moved from: %s" % os.path.join(event.path, event.name)

    def process_IN_MOVED_TO(self, event):
        print "Moved to: %s" % os.path.join(event.path, event.name)

    def process_IN_MODIFY(self, event):
        print "Modify to: %s" % os.path.join(event.path, event.name)

    def process_IN_CLOSE_NOWRITE(self, event):
        print "Close Nowrite: %s" % os.path.join(event.path, event.name)

    def process_IN_OPEN(self, event):
        print "Open: %s" % os.path.join(event.path, event.name)



notifier = Notifier(wm, PTmp())
wdd = wm.add_watch('/ext4-Space/home/peter/Desktop', mask, rec=True)

while True:  # loop forever
    try:
        # process the queue of events as explained above
        notifier.process_events()
        if notifier.check_events():
            # read notified events and enqeue them
            notifier.read_events()
        # you can do some tasks here...
    except KeyboardInterrupt:
        # destroy the inotify's instance on this interrupt (stop monitoring)
        notifier.stop()
        break
