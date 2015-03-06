#!/bin/sh -x

SRC_PATH=$1
DST_PATH=$2
RAMDISK_DIR=$3

if [ -n "$RAMDISK_DIR" ]; then
  mkdir -p $RAMDISK_DIR
  DST_IMAGE=$RAMDISK_DIR/$(basename $DST_PATH)
  /bin/cp -v $1 $DST_IMAGE
  ln -s $DST_IMAGE $DST_PATH
else
  #/usr/bin/pv < $1 > $2
  /bin/cp -v $1 $2
fi
