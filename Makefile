PREFIX = /usr

all : 
	@echo "No build required. Directly use \"make PREFIX=/usr install\""

install : 
	cp cozy-backup $(PREFIX)/bin
	cp cozy-backup-applet $(PREFIX)/bin
	mkdir -p $(PREFIX)/lib/cozy
	cp -r lib/* $(PREFIX)/lib/cozy
	cp cozyfs/cozyfs.py $(PREFIX)/bin
	cp cozyfs/cozyfssnapshot.py $(PREFIX)/bin
	cp cozyfs/mkfs.cozyfs.py $(PREFIX)/bin
	mkdir -p $(PREFIX)/lib/python2.6/dist-packages/cozyutils
	cp cozyutils/*.py $(PREFIX)/lib/python2.6/dist-packages/cozyutils
	mkdir -p $(PREFIX)/share/pixmaps
	cp pixmaps/cozy.svg $(PREFIX)/share/pixmaps
	cp pixmaps/cozy-unavailable.svg $(PREFIX)/share/pixmaps
	@echo "Make sure you have a version of Nautilus installed that has DBus support for Cozy."
	@echo "See README file for more information."

uninstall :
	-rm -rf $(PREFIX)/bin/cozy-backup $(PREFIX)/bin/cozy-backup-applet $(PREFIX)/lib/cozy $(PREFIX)/bin/cozyfs.py $(PREFIX)/bin/cozyfssnapshot.py $(PREFIX)/bin/mkfs.cozyfs.py $(PREFIX)/lib/python2.6/dist-packages/cozyutils $(PREFIX)/share/pixmaps/cozy.svg $(PREFIX)/share/pixmaps/cozy-unavailable.svg

.PHONY : clean
clean :

