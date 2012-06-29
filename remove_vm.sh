#!/bin/sh

IMAGE_DIR=/var/lib/libvirt/images

export LANG=C
export LC_ALL=C

if [ `whoami` != "root" ]; then
  echo "Please use 'sudo'. This command requires root priviledge."
  exit 1
fi

if [ -z "$1" ]; then
  echo "Usage: $0 NAME"
  exit 1
fi
NAME=$1

virsh domstate $NAME | grep running > /dev/null
if [ $? -eq 0 ]; then
  virsh destroy $NAME
fi

virsh undefine $NAME
rm -v ${IMAGE_DIR}/${NAME}.img
