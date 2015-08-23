#!/bin/sh

TOP_DIR=$(cd $(dirname $0) && pwd)

if [ -z "$1" ]; then
    echo "Usage: $0 <host>"
    exit 1
fi
HOST=$1

IMAGE=ubuntu1404.img

$TOP_DIR/easy_deploy.py --no-hostname -c 4 -m 8 -i pub $HOST $IMAGE
