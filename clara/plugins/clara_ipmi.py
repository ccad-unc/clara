#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#  Copyright (C) 2014 EDF SA                                                 #
#                                                                            #
#  This file is part of Clara                                                #
#                                                                            #
#  This software is governed by the CeCILL-C license under French law and    #
#  abiding by the rules of distribution of free software. You can use,       #
#  modify and/ or redistribute the software under the terms of the CeCILL-C  #
#  license as circulated by CEA, CNRS and INRIA at the following URL         #
#  "http://www.cecill.info".                                                 #
#                                                                            #
#  As a counterpart to the access to the source code and rights to copy,     #
#  modify and redistribute granted by the license, users are provided only   #
#  with a limited warranty and the software's author, the holder of the      #
#  economic rights, and the successive licensors have only limited           #
#  liability.                                                                #
#                                                                            #
#  In this respect, the user's attention is drawn to the risks associated    #
#  with loading, using, modifying and/or developing or reproducing the       #
#  software by the user in light of its specific status of free software,    #
#  that may mean that it is complicated to manipulate, and that also         #
#  therefore means that it is reserved for developers and experienced        #
#  professionals having in-depth computer knowledge. Users are therefore     #
#  encouraged to load and test the software's suitability as regards their   #
#  requirements in conditions enabling the security of their systems and/or  #
#  data to be ensured and, more generally, to use and operate it in the      #
#  same conditions as regards security.                                      #
#                                                                            #
#  The fact that you are presently reading this means that you have had      #
#  knowledge of the CeCILL-C license and that you accept its terms.          #
#                                                                            #
##############################################################################
"""
Manages and get the status from the nodes of a cluster.

Usage:
    clara ipmi connect <host>
    clara ipmi deconnect <hostlist>
    clara ipmi (on|off|reboot) <hostlist>
    clara ipmi status <hostlist>
    clara ipmi setpwd <hostlist>
    clara ipmi getmac <hostlist>
    clara ipmi pxe <hostlist>
    clara ipmi disk <hostlist>
    clara ipmi ping <hostlist>
    clara ipmi blink <hostlist>
    clara ipmi immdhcp <hostlist>
    clara ipmi bios <hostlist>
    clara ipmi -h | --help
Alternative:
    clara ipmi <host> connect
    clara ipmi <hostlist> deconnect
    clara ipmi <hostlist> (on|off|reboot)
    clara ipmi <hostlist> status
    clara ipmi <hostlist> setpwd
    clara ipmi <hostlist> getmac
    clara ipmi <hostlist> pxe
    clara ipmi <hostlist> disk
    clara ipmi <hostlist> ping
    clara ipmi <hostlist> blink
    clara ipmi <hostlist> immdhcp
    clara ipmi <hostlist> bios
"""

import errno
import logging
import os
import re
import subprocess
import sys

import ClusterShell
import docopt
from clara.utils import clara_exit, run, get_from_config, value_from_file


def ipmi_do(hosts, pty=False, *cmd):
    command = []
    if not isinstance(pty, bool):
        command.append(pty)
        pty = False
    command.extend(cmd)
    imm_user = value_from_file(get_from_config("common", "master_passwd_file"), "IMMUSER")
    os.environ["IPMI_PASSWORD"] = value_from_file(get_from_config("common", "master_passwd_file"), "IMMPASSWORD")
    nodeset = ClusterShell.NodeSet.NodeSet(hosts)
    for host in nodeset:

        pat = re.compile("\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
        if not pat.match(host):
            host = "imm" + host

        ipmitool = ["ipmitool", "-I", "lanplus", "-H", host, "-U", imm_user, "-E", "-e!"]
        ipmitool.extend(command)

        logging.debug("ipmi/ipmi_do: {0}".format(" ".join(ipmitool)))

        if pty:
            run(ipmitool)
        else:
            os.system("echo -n '%s: ' ;" % host + " ".join(ipmitool))


def getmac(hosts):
    imm_user = value_from_file(get_from_config("common", "master_passwd_file"), "IMMUSER")
    os.environ["IPMI_PASSWORD"] = value_from_file(get_from_config("common", "master_passwd_file"), "IMMPASSWORD")
    nodeset = ClusterShell.NodeSet.NodeSet(hosts)
    for host in nodeset:

        pat = re.compile("\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
        if not pat.match(host):
            host = "imm" + host

        logging.info("{0}: ".format(host))
        cmd = ["ipmitool", "-I", "lanplus", "-H", host,
               "-U", imm_user, "-E", "fru", "print", "0"]

        logging.debug("ipmi/getmac: {0}".format(" ".join(cmd)))

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        # The data we want is in line 15
        lines = proc.stdout.readlines()
        if (len(lines) < 14):
            clara_exit("The host {0} can't be reached".format(host))
        full_mac = lines.split(":")[1].strip().upper()
        mac_address1 = "{0}:{1}:{2}:{3}:{4}:{5}".format(full_mac[0:2],
                                                        full_mac[2:4],
                                                        full_mac[4:6],
                                                        full_mac[6:8],
                                                        full_mac[8:10],
                                                        full_mac[10:12])

        mac_address2 = "{0}:{1}:{2}:{3}:{4}:{5}".format(full_mac[12:14],
                                                        full_mac[14:16],
                                                        full_mac[16:18],
                                                        full_mac[18:20],
                                                        full_mac[20:22],
                                                        full_mac[22:24])

        logging.info("  eth0's MAC address is {0}\n" \
                     "  eth1's MAC address is {1}".format(mac_address1, mac_address2))


def do_connect(hosts):
    nodeset = ClusterShell.NodeSet.NodeSet(hosts)
    if (len(nodeset) != 1):
        clara_exit('Only one host allowed for this command')
    else:
        try:
            cmd = ["service", "conman", "status"]
            fnull = open(os.devnull, 'wb')  # Supress output of the following call
            retcode = subprocess.call(cmd, stdout=fnull, stderr=subprocess.STDOUT)
            fnull.close()
        except OSError, e:
            if (e.errno == errno.ENOENT):
                clara_exit("Binary not found, check your path and/or retry as root."
                         "You were trying to run:\n {0}".format(" ".join(cmd)))

        if retcode == 0:  # if conman is running
            os.environ["CONMAN_ESCAPE"] = '!'
            conmand = get_from_config("ipmi", "conmand")
            run(["conman", "-d", conmand, hosts])
        elif retcode == 1 or retcode == 3:  # if conman is NOT running
            ipmi_do(hosts, True, "sol", "activate")
        else:
            clara_exit(' '.join(cmd))


def do_ping(hosts):
    nodes = ClusterShell.NodeSet.NodeSet(hosts)
    cmd = ["fping", "-r1", "-u", "-s"] + list(nodes)
    run(cmd)


def main():
    logging.debug(sys.argv)
    dargs = docopt.docopt(__doc__)

    if dargs['connect']:
        do_connect(dargs['<host>'])
    elif dargs['deconnect']:
        ipmi_do(dargs['<hostlist>'], "sol", "deactivate")
    elif dargs['status']:
        ipmi_do(dargs['<hostlist>'], "power", "status")
    elif dargs['setpwd']:
        clara_exit("Not tested!")  # TODO
        ipmi_do(dargs['<hostlist>'], "user", "set", "name", "2", "IMMUSER")
        ipmi_do(dargs['<hostlist>'], "user", "set", "password", "2", "IMMPASSWORD")
    elif dargs['getmac']:
        getmac(dargs['<hostlist>'])
    elif dargs['on']:
        ipmi_do(dargs['<hostlist>'], "power", "on")
    elif dargs['off']:
        ipmi_do(dargs['<hostlist>'], "power", "off")
    elif dargs['reboot']:
        ipmi_do(dargs['<hostlist>'], "chassis", "power", "reset")
    elif dargs['blink']:
        ipmi_do(dargs['<hostlist>'], "chassis", "identify", "1")
    elif dargs['bios']:
        ipmi_do(dargs['<hostlist>'], "chassis", "bootparam", "set", "bootflag", "force_bios")
    elif dargs['immdhcp']:
        ipmi_do(dargs['<hostlist>'], "lan", "set", "1", "ipsrc", "dhcp")
    elif dargs['pxe']:
        ipmi_do(dargs['<hostlist>'], "chassis", "bootdev", "pxe")
    elif dargs['disk']:
        ipmi_do(dargs['<hostlist>'], "chassis", "bootdev", "disk")
    elif dargs['ping']:
        do_ping(dargs['<hostlist>'])


if __name__ == '__main__':
    main()
