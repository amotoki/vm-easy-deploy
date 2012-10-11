#!/usr/bin/env python
import argparse
import getpass
from jinja2 import Template
import json
import os
import shutil
import sys
import subprocess
import tempfile
from virtinst.util import randomMAC

BASEDIR = '/usr/local/share/libvirt'
IMAGE_DIR = '/var/lib/libvirt/images'

# bridge interface directly connected to the Internet (or your intranet)
PUBLIC_BRIDGE = 'br0'
# mac address list of public hosts
PUBLIC_MAC_FILE = os.path.join(BASEDIR, 'mac.json')

DEFAULT_TEMPLATE = os.path.join(BASEDIR, 'templates/libvirt.xml')
DEFAULT_MEMORY = 4 * 1024 * 1024 # KB
BASE_SLOT = 0x07
BASEIMAGE_DIR = os.path.join(BASEDIR, 'images')
CMD_SET_VMNAME= os.path.join(BASEDIR, 'set-vm-name.sh')

mac_dict = {}

def usage():
    print "Usage: %s name template" % sys.argv[0]
    sys.exit(1)

def checkUser():
    if getpass.getuser() != 'root':
        print "Please use 'sudo'. This command requires root priviledge."
        sys.exit(1)

def checkDomain(name):
    ret = callVirshCmd('domstate', name, suppress=True)
    if ret == 0:
        print "%s is already defined." % name
        sys.exit(2)

def checkImage(image):
    image_path = os.path.join(IMAGE_DIR, image)
    if os.path.exists(image_path):
        print "%s exists." % image_path
        sys.exit(3)

def checkBaseImage(image):
    image_path = os.path.join(BASEIMAGE_DIR, image)
    if not os.path.exists(image_path):
        print "Base image %s does not exist." % image
        sys.exit(3)

def copyImage(base, image):
    src_path = os.path.join(BASEIMAGE_DIR, base)
    dst_path = os.path.join(IMAGE_DIR, image)
    shutil.copyfile(src_path, dst_path)

def setHostnameToImage(image, name):
    dst_path = os.path.join(IMAGE_DIR, image)
    subproc_args = { 'stdin': subprocess.PIPE,
                     'stdout': subprocess.PIPE,
                     'stderr': subprocess.PIPE,
                     'close_fds': True, }
    cmd = '%s %s %s' % (CMD_SET_VMNAME, dst_path, name)
    args = cmd.split()
    p = subprocess.Popen(args, **subproc_args)
    ret = p.wait()
    if ret:
        print p.stdout.read()
        print p.stderr.read()
        sys.exit(5)

def defineDomain(xml):
    ret = callVirshCmd('define', xml)
    if ret:
        sys.exit(4)

def startDomain(name):
    ret = callVirshCmd('start', name)
    if ret:
        sys.exit(6)

def callVirshCmd(*args, **kwargs):
    suppress = kwargs.get('suppress')
    subproc_args = { 'stdin': subprocess.PIPE,
                     'stdout': subprocess.PIPE,
                     'stderr': subprocess.PIPE,
                     'close_fds': True, }
    args = ('virsh',) + args
    p = subprocess.Popen(args, **subproc_args)
    ret = p.wait()
    stdout = p.stdout.read()
    stderr = p.stderr.read()
    if ret and not suppress:
        print stdout
        print stderr
    return ret

def listImages():
    #print "ubuntu1204.img"
    #print "ubuntu1104.img"
    for f in os.listdir(BASEIMAGE_DIR):
        print f

def parseArgs():
    parser = argparse.ArgumentParser(description='VM easy deployment tool')
    parser.add_argument('NAME', help='VM name to be defined')
    parser.add_argument('BASEIMAGE', help='baseimage name or LIST (which lists available baseimages)')
    parser.add_argument('-t', '--template', help='template file', default=DEFAULT_TEMPLATE)
    parser.add_argument('--nostart', action='store_true', help='Do not start after define')
    parser.add_argument('-m', '--memory', help='memory size [KB]', default=DEFAULT_MEMORY)
    parser.add_argument('-i', '--nic', action='append', default=[],
                        help='NIC (bridge_name or "NAT").'
                        ' Specify multiple times if you want multiple vNICs.')
    args = parser.parse_args()

    if args.BASEIMAGE == '?' or args.BASEIMAGE.upper() == 'LIST':
        listImages()
        sys.exit(0)

    return args

def loadMacAddress():
    global mac_dict
    if os.path.exists(PUBLIC_MAC_FILE):
        with open(PUBLIC_MAC_FILE) as f:
            mac_dict = json.load(f)

def getMacAddress(nic, name):
    global mac_dict
    print '%s exists => %s' % (PUBLIC_MAC_FILE, os.path.exists(PUBLIC_MAC_FILE))
    print 'name in mac_dict %s' % (name in mac_dict)
    if (nic == PUBLIC_BRIDGE and
        os.path.exists(PUBLIC_MAC_FILE) and name in mac_dict):
        mac = mac_dict[name]
    else:
      mac = randomMAC("qemu")
    return mac

def generateLibvirtXML(args, libvirt_xml):
    params = { 'name': args.NAME,
               'memory': args.memory,
               'nics': [] }
    
    if len(args.nic) == 0:
        args.nic.append('NAT')
    for i, nic in enumerate(args.nic):
        mac = getMacAddress(nic, args.NAME)
        slot = '0x%02x' % (BASE_SLOT + i)
        params['nics'].append({'nic': nic, 'mac': mac, 'slot': slot})
    
    with open(args.template) as f:
        tmpl = Template(f.read())
    
    with open(libvirt_xml, 'w') as f:
        f.write(tmpl.render(params))
    
    #print "%s generated successfully from %s" % (libvirt_xml, args.template)
    for m in params['nics']:
        print "%s: %s" % (m['nic'], m['mac'])

def getTempFile():
    f = tempfile.NamedTemporaryFile(delete=False)
    f.close()
    return f.name

def deleteLibvirtXML(libvirt_xml):
    os.remove(libvirt_xml)

#------------------------------------------------------------

checkUser()
loadMacAddress()

args = parseArgs()

base_path = args.BASEIMAGE
dest_path = args.NAME + ".img"
#libvirt_xml = args.NAME + ".xml"
libvirt_xml = getTempFile()

checkImage(dest_path)
checkDomain(args.NAME)
checkBaseImage(base_path)

generateLibvirtXML(args, libvirt_xml)
defineDomain(libvirt_xml)
copyImage(base_path, dest_path)
setHostnameToImage(dest_path, args.NAME)
deleteLibvirtXML(libvirt_xml)

if not args.nostart:
    startDomain(args.NAME)
