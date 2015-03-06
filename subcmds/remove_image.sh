#!/bin/bash

if [ -z "$2" ]; then
  echo "Usage: $0 IMAGE_DIR NAME"
  exit 1
fi

IMAGE_DIR=$1
NAME=$2
RAMDISK_DIR=$3

/bin/rm -v ${IMAGE_DIR}/${NAME}

if [ -n "$RAMDISK_DIR" ]; then
  RAM_IMAGE=$RAMDISK_DIR/$NAME
  if [ -f "$RAM_IMAGE" ]; then
    /bin/rm -v $RAM_IMAGE
  fi
fi
