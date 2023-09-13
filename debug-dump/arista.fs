#!/bin/bash

source $(dirname "$0")/arista-debug-helpers.sh

runcmd losetup -l
runcmd lsblk -o NAME,LABEL,FSTYPE,FSSIZE,FSUSED,FSAVAIL,SIZE,RO,TYPE,VENDOR,MODEL,SERIAL,ALIGNMENT,MOUNTPOINT
runcmd fdisk -l "/dev/$(lsblk -no pkname "$(df | awk '/\/host$/ {print $1}')")"
