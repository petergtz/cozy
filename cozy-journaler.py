#! /usr/bin/python

import os
from pyinotify import WatchManager, Notifier, ThreadedNotifier, EventsCodes, ProcessEvent

wm = WatchManager()


mask = 0
mask |= EventsCodes.IN_MOVED_FROM
mask |= EventsCodes.IN_MOVED_TO
mask |= EventsCodes.IN_CLOSE_WRITE
mask |= EventsCodes.IN_DELETE
mask |= EventsCodes.IN_CREATE
mask |= EventsCodes.IN_MODIFY
mask |= EventsCodes.IN_CLOSE_NOWRITE
mask |= EventsCodes.IN_OPEN

class PTmp(ProcessEvent):
    def process_IN_CREATE(self, event):
        print "Create: %s" %  os.path.join(event.path, event.name)

    def process_IN_DELETE(self, event):
        print "Remove: %s" %  os.path.join(event.path, event.name)

    def process_IN_ACCESS(self, event):
        print "Access: %s" %  os.path.join(event.path, event.name)

    def process_IN_CLOSE_WRITE(self, event):
        print "Close Write: %s" %  os.path.join(event.path, event.name)

    def process_IN_MOVED_FROM(self, event):
        print "Moved from: %s" %  os.path.join(event.path, event.name)

    def process_IN_MOVED_TO(self, event):
        print "Moved to: %s" %  os.path.join(event.path, event.name)

    def process_IN_MODIFY(self, event):
        print "Modify to: %s" %  os.path.join(event.path, event.name)

    def process_IN_CLOSE_NOWRITE(self, event):
        print "Close Nowrite: %s" %  os.path.join(event.path, event.name)

    def process_IN_OPEN(self, event):
        print "Open: %s" %  os.path.join(event.path, event.name)



notifier = Notifier(wm, PTmp())
wdd = wm.add_watch('/home/peter', mask, rec=True)

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
