#!/bin/sh

mkdir -p ~/.nautilus/python-extensions
ln -s $PWD/nautilus-restore-extension/cozy-restore-nautilus-extension.py ~/.nautilus/python-extensions/
mkdir -p ~/.icons/hicolor/scalable/actions
ln -s $PWD/pixmaps/cozy.svg ~/.icons/hicolor/scalable/actions/cozy.svg
ln -s $PWD/pixmaps/close-cozy.svg ~/.icons/hicolor/scalable/actions/close-cozy.svg
