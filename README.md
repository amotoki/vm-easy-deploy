vm-easy-deploy
==============

Template-based VM deployment tool on a VM environment using libvirt.

This tool is intended to use on a single host.
If you want tools like this, I recomment to use IaaS stack such as OpenStack.

## Prerequites

* python 2.7 (vm-easy-deploy uses "argparse")
* libvirt-bin
* virtinst
* python-jinja2
* lvm2

Note that I tested it under Ubuntu 12.04 server.

## Installation

1. You can install vm-easy-deploy into an arbitrary directory you want.
   The default install path is */usr/local/share/libvirt*.
2. Set the install diretory to BASEDIR in easy_deploy.py.
3. Set IMAGE_DIR depending on your libvirt cofiguration.

## Usage

### Define VM

*easy_deploy.py* defines a libvirt VM definition and copies a VM image from
a specified base image. When VM image copy, set a hostname into the VM image
if possible.
(sudo privilege is required to copy a VM image.)

    sudo /usr/local/share/libvirt/easy_deploy.py [-h] [-t TEMPLATE] [-m MEMORY] [-i NIC] NAME BASEIMAGE

* **NAME**:
  VM name to be created. Choose a name which is not used.
  You can check which names are already used by *virsh list --all*.
* **BASEIMAGE**:
  Template image name.
  Select from images in /usr/local/share/libvirt/images/.
  By specifying "LIST" as BASENAME, you can get image list available.
* **NIC**:
  Specify a bridge name that a NIC is connected to.
  (You need to create bridges in advance.)
  Reserved word "NAT" can be specified. "NAT" means that a NIC connects to
  a NAT bridge "virbr0" prepared by libvirt.
  You can specify NICs multiple times as you need.
  If no NIC is specified, "-i NAT" is assumed.

#### Examples

Create a VM with a default NIC

    % sudo /usr/local/share/libvirt/easy_deploy.py testvm ubuntu1204.img

Create a VM with three NICs (connected to NAT, br100 and br101)

    % sudo /usr/local/share/libvirt/easy_deploy.py -i NAT -i br100 -i br101 testvm ubuntu1204.img

If you want to list available VM images, pass "LIST" to BASEIMAGE.

    % sudo /usr/local/share/libvirt/easy_deploy.py testvm list
    ubuntu1104.img
    ubuntu1204.img
    ubuntu1110.img

### Remove VM

*remove_vm.sh* undefines libvirt VM definition and removes a related VM image.
If the specified VM is running, it first force stops the VM.
(sudo privilege is required to remove a VM image.)

    % sudo /usr/local/share/libvirt/remove_vm.sh <vm_name>

