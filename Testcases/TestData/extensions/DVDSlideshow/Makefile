all: DVDSlideshowExporter.dll

PACKAGES = \
	-pkg:f-spot \
	-pkg:glade-sharp-2.0 \
	-pkg:gnome-vfs-sharp-2.0 \
	-pkg:gtk-sharp-2.0

ASSEMBLIES = \
	-r:Mono.Posix

RESOURCES = \
	-resource:dvd_slideshow_exporter_dialog.glade \
	-resource:DVDSlideshowExporter.addin.xml

SOURCES = \
	DVDSlideshowExporter.cs

install: all
	cp *.dll ~/Sonstiges/fspotbase/addins/

mpack: DVDSlideshowExporter.dll
	mautil p DVDSlideshowExporter.dll

%.dll: $(SOURCES) DVDSlideshowExporter.addin.xml
	gmcs -target:library $(SOURCES) $(PACKAGES) $(ASSEMBLIES) $(RESOURCES)

clean:
	rm -f *.dll *~ *.bak .mpack

PHONY:
	install clean all mpack
