PREFIX = /usr
NAUTILUS_RELEASE = nautilus-2.28.1
NAUTILUS_TAR_GZ = $(NAUTILUS_RELEASE).tar.gz
NAUTILUS_WEB_LOCATION = http://ftp.acc.umu.se/pub/GNOME/sources/nautilus/2.28/$(NAUTILUS_TAR_GZ)

all : nautilus-patch/$(NAUTILUS_RELEASE)/src/nautilus

nautilus-patch/$(NAUTILUS_TAR_GZ) :
	cd nautilus-patch && wget $(NAUTILUS_WEB_LOCATION)
	
nautilus-patch/tar-extracted-indicator : nautilus-patch/$(NAUTILUS_TAR_GZ)
	cd nautilus-patch && tar xfz $(NAUTILUS_TAR_GZ)
	touch nautilus-patch/tar-extracted-indicator

nautilus-patch/patch-applied-indicator : nautilus-patch/tar-extracted-indicator
	cd nautilus-patch/$(NAUTILUS_RELEASE) && patch -p0 <../cozy-support.diff
	touch nautilus-patch/patch-applied-indicator

nautilus-patch/$(NAUTILUS_RELEASE)/src/nautilus : nautilus-patch/patch-applied-indicator
	cd nautilus-patch/$(NAUTILUS_RELEASE) && ./configure --prefix=$(PREFIX)
	cd nautilus-patch/$(NAUTILUS_RELEASE) && make

install : nautilus-patch/$(NAUTILUS_RELEASE)/src/nautilus
	echo "WARNING: THIS WILL OVERWRITE YOUR EXISTING NAUTILUS INSTALLATION. PRESS CTRL-C TO ABORT OR ENTER TO CONTINUE."
	read confirmation
	cd nautilus-patch/$(NAUTILUS_RELEASE) && make install
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

uninstall :
	cd nautilus-patch/$(NAUTILUS_RELEASE) && make uninstall
	-rm -rf $(PREFIX)/bin/cozy-backup $(PREFIX)/bin/cozy-backup-applet $(PREFIX)/lib/cozy $(PREFIX)/bin/cozyfs.py $(PREFIX)/bin/cozyfssnapshot.py $(PREFIX)/bin/mkfs.cozyfs.py $(PREFIX)/lib/python2.6/dist-packages/cozyutils $(PREFIX)/share/pixmaps/cozy.svg $(PREFIX)/share/pixmaps/cozy-unavailable.svg

.PHONY : clean
clean :
	-rm -rf nautilus-patch/$(NAUTILUS_RELEASE) nautilus-patch/patch-applied-indicator nautilus-patch/tar-extracted-indicator

.PHONY : distclean
distclean :
	-rm -rf nautilus-patch/$(NAUTILUS_RELEASE) nautilus-patch/$(NAUTILUS_TAR_GZ) nautilus-patch/patch-applied-indicator nautilus-patch/tar-extracted-indicator
