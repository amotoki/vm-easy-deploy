#!/bin/bash

if [ -z "$2" ]; then
  echo "Usage: $0 IMAGE_DIR NAME"
  exit 1
fi

IMAGE_DIR=$1
NAME=$2

/bin/ls ${IMAGE_DIR}/${NAME} >/dev/null 2>&1
exit $?
