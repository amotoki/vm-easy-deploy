#!/usr/bin/env python

import random

def randomMAC():
    oui = [ 0x52, 0x54, 0x00 ]  # qemu
    # oui = [ 0x00, 0x16, 0x3E ]  # xen
    mac = oui + [
            random.randint(0x00, 0xff),
            random.randint(0x00, 0xff),
            random.randint(0x00, 0xff)]
    return ':'.join(map(lambda x: "%02x" % x, mac))

if __name__ == '__main__':
    print randomMAC()
