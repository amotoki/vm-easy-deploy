#!/usr/bin/env python
import argparse
import ConfigParser
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
ALIAS_FILE = os.environ.get('EASY_DEPLOY_ALIAS_FILE', '')

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


def checkDomainOne(name, alias=False):
    ret = callVirshCmd('domstate', name, suppress=True)
    if ret == 0:
        if alias:
            name = 'Alias "%s"' % name
        print "%s is already defined." % name
        sys.exit(2)


def checkDomain(name):
    checkDomainOne(name)
    aliases = getAliasNames(name)
    for n in aliases:
        checkDomainOne(n, alias=True)


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


def loadConfig():
    global mac_dict
    conf_file = os.path.join(os.environ.get('HOME'), '.easydeployrc')
    conf = ConfigParser.SafeConfigParser()
    conf.read(conf_file)
    if conf.has_section('mac'):
        mac_dict.update(dict(conf.items('mac')))
    if conf.has_section('alias'):
        alias_dict = dict(conf.items('alias'))
        for alias, name in alias_dict.items():
            if name in mac_dict:
                mac_dict[alias] = mac_dict[name]
            else:
                print ('Alias "%(alias)s" has no corresponding '
                       'entry "%(name)s"') % locals()
    if conf.has_section('default'):
        if conf.has_option('default', 'public_bridge'):
            global PUBLIC_BRIDGE
            PUBLIC_BRIDGE = conf.get('default', 'public_bridge')


def loadMacAddress():
    global mac_dict
    if os.path.exists(PUBLIC_MAC_FILE):
        print 'Loading mac_address file %s' % PUBLIC_MAC_FILE
        with open(PUBLIC_MAC_FILE) as f:
            mac_dict = json.load(f)
    # Alias
    if os.path.exists(ALIAS_FILE):
        print 'Loading alias file %s' % ALIAS_FILE
        with open(ALIAS_FILE) as f:
            alias_dict = json.load(f)
        for alias, name in alias_dict.items():
            if name in mac_dict:
                mac_dict[alias] = mac_dict[name]
            else:
                print ('Alias "%(alias)s" has no corresponding '
                       'entry "%(name)s"') % locals()


def getAliasNames(name):
    global mac_dict
    if name not in mac_dict:
        return []
    mac = mac_dict[name]
    return [k for k, v in mac_dict.items()
            if v == mac and k != name]


def randomMAC():
    return virtutils.randomMAC("qemu")


def getMacAddress(network, name):
    global mac_dict
    if (network == PUBLIC_BRIDGE and name in mac_dict):
        mac = mac_dict[name]
        print 'Use %s for nic connected to %s' % (mac, network)
    else:
        mac = randomMAC()
        print 'Generate random MAC address %s for network %s' % (mac, network)
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
    loadConfig()
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
