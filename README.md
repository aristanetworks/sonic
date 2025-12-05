Arista platform support for SONiC
=================================

Copyright (C) 2016 Arista Networks, Inc.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

## License

All linux kernel code is licensed under the GPLv2. All other code is
licensed under the GPLv3. Please see the LICENSE file for copies of
both licenses.

## Purpose

This package provides open source hardware support for Arista products.
It is mainly targeted at SONiC OS (debian based) though this repository should
build and work on any operating system.
For more details visit the [SONiC website](https://azure.github.io/SONiC/)

During normal operations, the platform is initialized at boot time via a set of
systemd services. These services invoke commands using the `arista` tool.

This tool detects the platform on which it is running before loading and
initializing the appropriate drivers.
Once the initialization is complete, the system exposes various
components through the sysfs such as fans, leds, xcvrs, ...

## API

The primary means to interact with the library is through the `sonic_platform`
library. This is SONiC's API for switch vendors to manage the platform.
The base classes of this API can be found in the
[sonic-platform-common repository](https://github.com/Azure/sonic-platform-common)

Internal APIs of this repository are subject to change without notice.
We try to avoid breaking the CLI but it can happen.

## Supported platforms

The following platforms are currently supported,

 - CCS-720DT-48S
 - DCS-7050QX-32
 - DCS-7050QX-32S
 - DCS-7050CX3-32S
 - DCS-7060CX-32
 - DCS-7060CX2-32
 - DCS-7060PX4-32 and DCS-7060DX4-32
 - DCS-7060DX5-32
 - DCS-7060PX5-64 and DCS-7060DX5-64
 - DCS-7060DX5-64S
 - DCS-7170-32C
 - DCS-7170-32CD
 - DCS-7170-64C
 - DCS-7170B-64C
 - DCS-7260CX3-64
 - DCS-7280CR3-32P4 and DCS-7280CR3-32D4

Note that the support in this package does not necessarily means that the
dataplane is working in SONiC.
Though most should be, some could face some ASIC/PHY bringup challenges.

SONiC's [list of supported devices](https://sonic-net.github.io/SONiC/Supported-Devices-and-Platforms.html)
should be crossed referenced though it might not be up to date either.

Some product variants were omitted in the previous list but might be supported
see `arista platforms` for a detailed list of supported SKUs.

Some platforms might require custom kernel patches and configs.
A working configuration is maintained under the [SONiC kernel repository](https://github.com/Azure/sonic-linux-kernel).

## Packaging

The current debian packaging mechanism creates 4 packages.
 - sonic-platform-arista : system configuration files
 - sonic-platform-arista-libs : shared libraries
 - drivers-sonic-platform-arista : kernel modules and drivers
 - python3-sonic-platform-arista : python3 library to manage the hardware

## Usage

At boot time the systemd services under `systemd/` are loaded. When runnable they
will perform the platform initialization.

The central piece of the platform support is the `arista` entry point.
It is a python script that load the arista platform library to perform actions.
This library is python3 only, python2 support is now deprecated.

For more details on the available commands see the help message
```
arista --help
```

The arista python library also exposes other entry points for APIs.
SONiC uses a few like `sonic_platform`, `sfputil`, `sonic_eeprom`, ...

## Documentation

 - [More details about the sysfs on Arista devices](./README.sysfs.md)
 - [Download Portal for SONiC Images](https://sonic-build.azurewebsites.net/ui/sonic/pipelines)
 - [SONiC Main page](https://azure.github.io/SONiC/)
 - [SONiC Wiki](https://github.com/Azure/SONiC/wiki)
 - [SONiC Documentation](https://github.com/Azure/SONiC/tree/master/doc)
 - [SONiC Build Repository](https://github.com/Azure/sonic-buildimage)

