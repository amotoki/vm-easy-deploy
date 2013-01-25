#!/bin/bash -x

NBD_DEV=/dev/nbd0
MOUNT_PATH=/mnt

if [ -z "$2" ]; then
  echo "Usage: $0 <image-file> <vm-name>"
  exit 1
fi
IMAGE=$1
NAME=$2

#-------------------

lsmod | grep nbd >/dev/null || modprobe nbd

# Check whether NBD_DEV is already used.
if ps auxw | grep -v grep | grep $NBD_DEV >/dev/null; then
  echo "$NBD_DEV is already used."
  exit 2
fi

#-------------------
# Mount VM image
#-------------------
if ! echo $IMAGE | grep -E '^/'; then
  DIR=`/bin/pwd`
  IMAGE=$DIR/$IMAGE
fi
/usr/bin/qemu-nbd -c $NBD_DEV $IMAGE

if fdisk -l $NBD_DEV | grep 'Linux LVM'; then
  # LVM
  TYPE=lvm
  NBD_PART=`fdisk -l $NBD_DEV | grep 'Linux LVM' | head -1 | awk '{print $1;}'`
  # refresh Volume Information
  #/sbin/vgscan
  /sbin/pvscan
  VG=`/sbin/pvs --noheadings $NBD_PART | awk '{print $2;}'`
  if [ -z "$VG" ]; then
    echo "$NBD_PART has no volume group."
    exit 10
  fi
  /sbin/vgchange -ay $VG
  ROOT_LV=`ls -1 /dev/$VG | grep root`
  mount /dev/$VG/$ROOT_LV $MOUNT_PATH
else
  # non-LVM
  TYPE=normal
  # It is true for Ubuntu 12.04 but need to check other distros.
  NBD_PART=${NBD_DEV}p5
  mount $NBD_PART $MOUNT_PATH
fi

#-------------------
# Modify VM Image
#-------------------
if [ -f $MOUNT_PATH/etc/debian_version ]; then
  HOSTNAME_FILE=$MOUNT_PATH/etc/hostname
  if [ -f $HOSTNAME_FILE ]; then
    OLD_HOSTNAME=`cat $HOSTNAME_FILE`
    sed -i -e "s|$OLD_HOSTNAME|$NAME|g" $HOSTNAME_FILE
    sed -i -e "s|$OLD_HOSTNAME|$NAME|g" $MOUNT_PATH/etc/hosts
  fi
elif [ -f $MOUNT_PATH/etc/redhat-release ]; then
  HOSTNAME_FILE=$MOUNT_PATH/etc/sysconfig/network
  if [ -f $HOSTNAME_FILE ]; then
    OLD_HOSTNAME=`grep HOSTNAME $HOSTNAME_FILE | cut -d = -f 2`
    sed -i -e "s|$OLD_HOSTNAME|$NAME|g" $HOSTNAME_FILE
    sed -i -e "s|$OLD_HOSTNAME|$NAME|g" $MOUNT_PATH/etc/hosts
  fi
fi

#-------------------
# Finishing stage
#-------------------
umount $MOUNT_PATH
if [ -n "$VG" ]; then
  /sbin/vgchange -an $VG
fi
/usr/bin/qemu-nbd -d $NBD_DEV
# refresh Volume Group Information
/sbin/pvscan
