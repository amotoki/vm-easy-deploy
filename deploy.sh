#!/bin/sh

if [ -z "$1" ]; then
    echo "Usage: $0 <host>"
    exit 1
fi
HOST=$1

IMAGE=ubuntu1404.img

./easy_deploy.py --no-hostname -c 4 -m 8 -i pub $HOST $IMAGE
