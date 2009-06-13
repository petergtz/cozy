#!/usr/bin/python
'''
Created on 11.05.2009

@author: peter
'''


import pygtk
pygtk.require('2.0')
import gtk

from dbus.mainloop.glib import DBusGMainLoop

import dbus
import gobject

import subprocess

#import cozy.configdialog

import sys
import os
import time

class CozyIcon(gtk.StatusIcon):
    '''
    classdocs
    '''

    def on_activate(self):
        dlg = gtk.MessageDialog(buttons=gtk.BUTTONS_YES_NO,
                                message_format="Do you want to backup your data now?")
        result = dlg.run()
        dlg.destroy()
        if result == gtk.RESPONSE_YES:
            process = subprocess.Popen(['./cozy-backup.py', '-f'])

    def on_popup_menu(self, button, activate_time):
        menu = gtk.Menu()
        menu_item = gtk.MenuItem('Settings...')
        menu.append(menu_item)
        menu_item.connect_object("activate", CozyIcon.on_show_configuration_dlg, self, 'Settings')
        menu_item.show()

        menu_item = gtk.MenuItem('Exit')
        menu.append(menu_item)
        menu_item.connect_object("activate", CozyIcon.on_exit, self, 'Exit')
        menu_item.show()

        menu.popup(None, None, gtk.status_icon_position_menu, button, activate_time, self)

    def __init__(self):
        gtk.StatusIcon.__init__(self)
        self.make_invisible()



        self.connect_object("activate", CozyIcon.on_activate, self)
        self.connect_object("popup-menu", CozyIcon.on_popup_menu, self)
        self.set_from_file("cozy.svg")

        session_bus = dbus.SessionBus()
        session_bus.add_signal_receiver(self.make_visible, 'removeable_volume_connected_signal', 'org.freedesktop.Cozy.Manager', 'org.freedesktop.Cozy', '/org/freedesktop/Cozy/Manager')
        session_bus.add_signal_receiver(self.make_invisible, 'removeable_volume_disconnected_signal', 'org.freedesktop.Cozy.Manager', 'org.freedesktop.Cozy', '/org/freedesktop/Cozy/Manager')

        # if manager not started
        #     start manager
        #     if manager start not successful due to incomplete configuration
        #         run configuration dialog
        #            if dialog finished with complete configuration
        #                start manager
        #                if manager start still not successful
        #                    show error message and abort 
        #            else
        #                abort
        #        

        os.system('./cozy-manager.py start')
        time.sleep(2)
        try:
            manager = session_bus.get_object('org.freedesktop.Cozy', '/org/freedesktop/Cozy/Manager')
        except dbus.exceptions.DBusException, e:
            self.on_show_configuration_dlg(self)
            return
#            if process.poll() == 1:
#                self.on_show_configuration_dlg(self)
#                return
#            elif process.poll() == 2:
#                print 'Could not start cozy-manager. cozy-applet will not work properly. TODO: should be a popup-window.'
#                return # returning. But we're still starting the applet.
#            else:
#                print 'Could not start cozy-manager due to unknown reasons. cozy-applet will not work properly. TODO: should be a popup-window.'
#                return # returning. But we're still starting the applet.


            # actually applet should start even if manager is not running. but it should somehow tell the user that it is not running
            # or it should give the possiblity to start it. think about a good solution.

        manager = session_bus.get_object('org.freedesktop.Cozy', '/org/freedesktop/Cozy/Manager')
        self.set_visible(manager.is_backup_volume_connected(dbus_interface='org.freedesktop.Cozy.Manager'))

    def make_visible(self):
        self.set_visible(True)

    def make_invisible(self):
        self.set_visible(False)

    def set_visible(self, visible):
        gtk.StatusIcon.set_visible(self, visible)
        if visible:
            time.sleep(1)
            self.notify()

    def notify(self):
        nbus = dbus.SessionBus()
        notifications = nbus.get_object('org.freedesktop.Notifications', '/org/freedesktop/Notifications')
        menu = gtk.Menu()
#        menu_item = gtk.MenuItem('Settings...')
#        menu.append(menu_item)
        (x, y, p) = gtk.status_icon_position_menu(menu, self)
        notifications.Notify("", 0, "", "Backup Volume Connected", "Click here if you want to back up your data now.", list(), {'x': x, 'y': y}, -1, dbus_interface='org.freedesktop.Notifications')

    def delete_event(self, widget, event):
        return False

    def on_show_configuration_dlg(self, widget):
#        mediator = None
#        mediator = cozy.configdialog.ConfigMediator(self)
#        mediator.show_all()
        process = subprocess.Popen('./configdialog.py')

    def on_exit(self, widget):
        mainloop.quit()

if __name__ == '__main__':

    DBusGMainLoop(set_as_default=True)

    builder = gtk.Builder()
    builder.add_from_file("configuration_dialog.xml")
#    cozy.configdialog.builder = builder

    icon = CozyIcon()

    mainloop = gobject.MainLoop()
    mainloop.run()

