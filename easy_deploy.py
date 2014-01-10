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
from virtinst import util as virtutils
from virtinst.util import randomMAC

BASEDIR = '/usr/local/share/libvirt'
IMAGE_DIR = '/var/lib/libvirt/images'

# bridge interface directly connected to the Internet (or your intranet)
PUBLIC_BRIDGE = os.environ.get('EASY_DEPLOY_PUBLIC_BRIDGE', 'br0')
# mac address list of public hosts
PUBLIC_MAC_FILE = os.environ.get('EASY_DEPLOY_MAC_FILE',
                                 os.path.join(BASEDIR, 'mac.json'))

DEFAULT_TEMPLATE = os.path.join(BASEDIR, 'templates/libvirt.xml')
DEFAULT_NUM_CPU = 2
DEFAULT_MEMORY = 4  # GB
BASE_SLOT = 0x07
BASEIMAGE_DIR = os.path.join(BASEDIR, 'images')
CMD_SET_VMNAME = os.path.join(BASEDIR, 'subcmds', 'set-vm-name.sh')
CMD_COPY_IMAGE = os.path.join(BASEDIR, 'subcmds', 'copy_image.sh')
CMD_CHECK_IMAGE = os.path.join(BASEDIR, 'subcmds', 'check_image.sh')

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
    ret = callCmdAsRoot(CMD_CHECK_IMAGE, IMAGE_DIR, image, suppress=True)
    if not ret:
        print "%s exists." % image_path
        sys.exit(3)
    return image_path


def checkBaseImage(image):
    if os.path.isabs(image):
        image_path = image
    else:
        image_path = os.path.join(BASEIMAGE_DIR, image)
    if not os.path.exists(image_path):
        print "Base image %s does not exist." % image
        sys.exit(3)
    return image_path


def getImageFormat(image):
    output = callCmd('qemu-img', 'info', image, capture=True)
    fmtlines = [line for line in output.split('\n') if line.startswith('file format')]
    if fmtlines:
        fmt = fmtlines[0]
    else:
        print "Image format for %s is unknown." % image
        sys.exit(3)
    return fmt.split(': ')[1]


def copyImage(base, image):
    src_path = os.path.join(BASEIMAGE_DIR, base)
    dst_path = os.path.join(IMAGE_DIR, image)
    print 'Copying %s -> %s...' % (os.path.basename(base),
                                   os.path.basename(image))
    callCmdAsRoot(CMD_COPY_IMAGE, src_path, dst_path, direct_stderr=True)


def setHostnameToImage(image, name):
    print 'Setting Hostname to the image...'
    dst_path = os.path.join(IMAGE_DIR, image)
    cmd = '%s %s %s' % (CMD_SET_VMNAME, dst_path, name)
    args = cmd.split()
    ret = callCmdAsRoot(*args)
    if ret:
        print "setHostnameToImage failed (%s, %s)" % (image, name)
        sys.exit(5)
    print 'Done'


def defineDomain(xml):
    ret = callVirshCmd('define', xml)
    if ret:
        sys.exit(4)


def startDomain(name):
    ret = callVirshCmd('start', name)
    if ret:
        sys.exit(6)
    print 'Start VM %s' % name


def callCmd(*args, **kwargs):
    suppress = kwargs.get('suppress')
    if kwargs.get('direct_stderr'):
        stderr_dst = subprocess.STDOUT
    else:
        stderr_dst = subprocess.PIPE
    subproc_args = {'stdin': subprocess.PIPE,
                    'stdout': subprocess.PIPE,
                    'stderr': stderr_dst,
                    'close_fds': True, }
    p = subprocess.Popen(args, **subproc_args)
    ret = p.wait()
    stdout = p.stdout.read()
    if 'direct_stderr' not in kwargs:
        stderr = p.stderr.read()
    if ret and not suppress:
        print stdout
        print stderr
    if kwargs.get('capture'):
        if ret:
            raise RuntimeError(ret)
        return stdout
    else:
        return ret


def callCmdAsRoot(*args, **kwargs):
    args = ('sudo',) + args
    return callCmd(*args, **kwargs)


def callVirshCmd(*args, **kwargs):
    args = ('virsh',) + args
    return callCmd(*args, **kwargs)


def listImages():
    for f in sorted(os.listdir(BASEIMAGE_DIR)):
        if f.startswith('.'):
            continue
        print f


def parseArgs():
    parser = argparse.ArgumentParser(description='VM easy deployment tool')
    parser.add_argument('NAME', help='VM name to be defined')
    parser.add_argument('BASEIMAGE',
                        help=('baseimage name or LIST '
                              '(which lists available baseimages)'))
    parser.add_argument('-t', '--template', help='template file',
                        default=DEFAULT_TEMPLATE)
    parser.add_argument('--nostart', action='store_true',
                        help='Do not start after define')
    parser.add_argument('-c', '--cpu', help='number of vcpus', type=int,
                        default=DEFAULT_NUM_CPU)
    parser.add_argument('-m', '--memory', help='memory size [GB]', type=int,
                        default=DEFAULT_MEMORY)
    parser.add_argument('-i', '--nic', action='append', default=[],
                        help='NIC (bridge_name or "NAT").'
                        ' Specify multiple times if you want multiple vNICs.')
    parser.add_argument('--no-hostname', action='store_false',
                        dest='set_hostname',
                        help='Do not set hostname of VM.')
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
            print 'Load mac_address file %s' % PUBLIC_MAC_FILE


def randomMAC():
    return virtutils.randomMAC("qemu")


def getMacAddress(network, name):
    global mac_dict
    if (network == PUBLIC_BRIDGE and
        os.path.exists(PUBLIC_MAC_FILE) and name in mac_dict):
        mac = mac_dict[name]
        print 'Use %s for nic connected to %s' % (mac, network)
    else:
        mac = randomMAC()
    return mac


def getDeviceName(domname, index):
    # from linux IF_NAMESIZE
    # In recent Linux this is 16 (in older unix 14)
    DEV_NAME_LEN = 16

    devname = '%s-eth%s' % (domname, index)
    if len(devname) > DEV_NAME_LEN:
        devname = ''
    return devname


def generateLibvirtXML(args, libvirt_xml):
    params = {'name': args.NAME,
              'cpu': args.cpu,
              'memory': args.memory * 1024 * 1024,
              'nics': [],
              'format': args.fmt,
             }

    if len(args.nic) == 0:
        args.nic.append('NAT')
    for i, network in enumerate(args.nic):
        mac = getMacAddress(network, args.NAME)
        targetdev = getDeviceName(args.NAME, i)
        slot = '0x%02x' % (BASE_SLOT + i)
        param = {'network': network, 'mac': mac, 'slot': slot}
        if targetdev:
            param['targetdev'] = targetdev
        params['nics'].append(param)

    with open(args.template) as f:
        tmpl = Template(f.read())

    with open(libvirt_xml, 'w') as f:
        f.write(tmpl.render(params))

    for m in params['nics']:
        msg = "%s: %s" % (m['network'], m['mac'])
        if m.get('targetdev'):
            msg += ' (%s)' % m['targetdev']
        print msg


def getTempFile():
    f = tempfile.NamedTemporaryFile(delete=False)
    f.close()
    return f.name


def deleteLibvirtXML(libvirt_xml):
    os.remove(libvirt_xml)


def main():
    args = parseArgs()

    #checkUser()
    loadMacAddress()

    base_path = args.BASEIMAGE
    dest_path = args.NAME + ".img"
    #libvirt_xml = args.NAME + ".xml"
    libvirt_xml = getTempFile()

    dest_abspath = checkImage(dest_path)
    checkDomain(args.NAME)
    base_abspath = checkBaseImage(base_path)
    image_fmt = getImageFormat(base_abspath)
    args.fmt = image_fmt

    generateLibvirtXML(args, libvirt_xml)
    defineDomain(libvirt_xml)
    copyImage(base_abspath, dest_abspath)
    if args.set_hostname and image_fmt != 'raw':
        setHostnameToImage(dest_abspath, args.NAME)
    deleteLibvirtXML(libvirt_xml)

    if not args.nostart:
        startDomain(args.NAME)

if __name__ == '__main__':
    main()
