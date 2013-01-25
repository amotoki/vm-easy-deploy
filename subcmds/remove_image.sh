#!/bin/bash

if [ -z "$2" ]; then
  echo "Usage: $0 IMAGE_DIR NAME"
  exit 1
fi

IMAGE_DIR=$1
NAME=$2

/bin/rm -v ${IMAGE_DIR}/${NAME}
