#! /usr/bin/python

import os.path
import os

import pygtk
pygtk.require('2.0')
import gtk

from  cozy.configutils import Configuration

import subprocess
import time

import re

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
COZY_MKFS_PATH = os.path.join(ROOT_DIR, 'cozy-mkfs.py')
COZY_MANAGER_PATH = os.path.join(ROOT_DIR, 'cozy-manager.py')
COZY_APPLET_PATH = os.path.join(ROOT_DIR, 'cozy-applet.py')
BUILDER_XML_PATH = os.path.join(ROOT_DIR, 'configuration_dialog.xml')

class ConfigMediator:
    def __init__(self, parent=None):

        self.parent = parent

        self.configuration_window = builder.get_object('configuration_window')
        self.enable_checkbox = builder.get_object('enable_checkbox')
        self.global_sections = builder.get_object('global_sections')
        self.temp_radio = builder.get_object('temp_radio')
        self.permanent_radio = builder.get_object('permanent_radio')
        self.source_path_label = builder.get_object('source_path_label')
        self.absolute_path_label = builder.get_object('absolute_path_label')
        self.volume_name_label = builder.get_object('volume_name_label')
        self.relative_path_label = builder.get_object('relative_path_label')
        self.permanent_group = builder.get_object('permanent_group')
        self.temp_group = builder.get_object('temp_group')

        builder.connect_signals(self)

        self.config = Configuration()

        try:
            self.enable_checkbox.set_active(self.config.is_backup_enabled())
        except Configuration.ConfigFileIncompleteError, e:
            print "Warning: " + str(e)
            print "Disabling backup."
            self.enable_checkbox.set_active(False)

        self.global_sections.set_sensitive(self.enable_checkbox.get_active())

        try:
            self.source_path_label.set_text(self.config.get_source_path())
        except Configuration.ConfigFileIncompleteError, e:
            self.source_path_label.set_text(os.path.expanduser('~'))

        try:
            if self.config.is_removeable_target_volume():
                self.temp_radio.set_active(True)
                try:
                    self.volume_name_label.set_text(self.config.get_target_uuid())
                    self.relative_path_label.set_text(self.config.get_relative_target_path())
                except Configuration.ConfigFileIncompleteError, e:
                    print "Warning: " + str(e)
            else:
                self.permanent_radio.set_active(True)
                try:
                    self.absolute_path_label.set_text(self.config.get_full_target_path())
                except Configuration.ConfigFileIncompleteError, e:
                    print "Warning: " + str(e)
        except Configuration.ConfigFileIncompleteError, e:
            self.permanent_radio.set_active(True)
            self.config.set_removeable_target_volume(False)
            print "Warning: " + str(e)
            print "Setting backup mode to permanent."
        self.on_permanent_mode_changed(self.permanent_radio)
        self.on_temporary_mode_changed(self.temp_radio)

    def on_backup_enable(self, widget, data=None):
        self.global_sections.set_sensitive(widget.get_active())
        self.config.set_backup_enabled(widget.get_active())

    def on_choose_source_btn_clicked(self, widget, data=None):
        dlg = gtk.FileChooserDialog(action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                                    buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        if dlg.run() == gtk.RESPONSE_OK:
            self.source_path_label.set_text(dlg.get_filename())
            self.config.set_source_path(dlg.get_filename())
        dlg.destroy()

    def on_permanent_mode_changed(self, widget, data=None):
        if widget.get_active():
            self.config.set_removeable_target_volume(False)
#            self.config.set_full_target_path(target_chooser.get_filename())
            self.permanent_group.set_sensitive(True)
        else:
            self.permanent_group.set_sensitive(False)

    def on_temporary_mode_changed(self, widget, data=None):
        if widget.get_active():
            self.config.set_removeable_target_volume(True)
#            self.config.set_full_target_path(target_chooser.get_filename())
            self.temp_group.set_sensitive(True)
        else:
            self.temp_group.set_sensitive(False)

    def on_choose_permanent_target_btn_clicked(self, widget, data=None):
        dlg = gtk.FileChooserDialog(action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                                    buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        if dlg.run() == gtk.RESPONSE_OK:
            self.config.set_full_target_path(dlg.get_filename())
            self.absolute_path_label.set_text(dlg.get_filename())
        dlg.destroy()


    def on_choose_temp_target_btn_clicked(self, widget, data=None):
        dlg = gtk.FileChooserDialog(action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                                    buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        if dlg.run() == gtk.RESPONSE_OK:
#            self.source_path_label.set_text(dlg.get_filename())
            self.config.set_full_target_path(dlg.get_filename())
 #           self.config.set_source_path(dlg.get_filename())
            self.volume_name_label.set_text(self.config.get_target_uuid())
            self.relative_path_label.set_text(self.config.get_relative_target_path())
        dlg.destroy()


    def on_close(self, widget, data=None):
        if not self.delete_event(widget, None):
           self.destroy(widget, data)


    def delete_event(self, widget, event, data=None):
        if self.config.changed():
            self.config.write()
            subprocess.call([COZY_MKFS_PATH, self.config.get_full_target_path(), str(self.config.get_backup_id())])
            if self.permanent_radio.get_active():
                self.add_crontab_entry()
                subprocess.call(['killall', 'cozy-applet.py'])
            else:
                self.remove_crontab_entry()
                a = os.system("ps -ef | grep -v grep | grep cozy-applet.py")
                if a != 0:
                    subprocess.Popen([COZY_APPLET_PATH])
            self.restart_manager()
#        dialog = builder.get_object("confirmation_dialog")
#        result = dialog.run()
#        dialog.hide()
#
#        return result == 2
        return False

    def destroy(self, widget, data=None):
        self.configuration_window.hide()
        if self.parent is None:
            gtk.main_quit()


    def restart_manager(self):
        print 'Restarting cozy-manager.py'
        os.system(COZY_MANAGER_PATH + ' restart')
        time.sleep(2)

#        if process.poll() is not None:
#            if process.poll() == 1:
#                print 'Could not start cozy-manager due do disabled or incomplete configuration. cozy-applet will not work properly. TODO: should be a popup-window.'
#            elif process.poll() == 2:
#                print 'Could not start cozy-manager. cozy-applet will not work properly. TODO: should be a popup-window.'
#            else:
#                print 'Could not start cozy-manager due to unknown reasons. cozy-applet will not work properly. TODO: should be a popup-window.'

    def add_crontab_entry(self):
        'Adds a new entry to the users crontab.'
        pid = subprocess.Popen(['crontab', '-l'], stdout=subprocess.PIPE)
        crontab = pid.stdout.read()
        new_crontab = re.sub('\n.*cozy-backup.py', '', crontab)
        new_crontab += '\n* * * * * cozy-backup.py'
        pid = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE)
        pid.stdin.write(new_crontab)
        pid.stdin.close()

    def remove_crontab_entry(self):
        'Removes an entry from the users crontab.'
        pid = subprocess.Popen(['crontab', '-l'], stdout=subprocess.PIPE)
        crontab = pid.stdout.read()
        new_crontab = re.sub('\n.*cozy-backup.py', '', crontab)
        pid = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE)
        pid.stdin.write(new_crontab)
        pid.stdin.close()


    def show_all(self):
        self.configuration_window.show_all()


if __name__ == "__main__":
    builder = gtk.Builder()
    builder.add_from_file(BUILDER_XML_PATH)

    mediator = ConfigMediator()
    mediator.show_all()
    gtk.main()
