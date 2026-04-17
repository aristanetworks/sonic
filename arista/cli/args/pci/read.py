from argparse import ArgumentParser
from functools import partial

from . import pciParser
from .. import registerParser

@registerParser('read', parent=pciParser,
                help='read PCIe resource memory')
def readParser(parser: ArgumentParser) -> None:
   parser.add_argument('--size', '-s', type=int, default=32, choices=[8, 16, 32],
                       help='Size of memory value to read')
   parser.add_argument('--resource', '-r', type=int, default=0,
                       help='BAR resource to read')
   parser.add_argument('--binary', '-b', action="store_true", default=False,
                       help='Display value in binary')
   parser.add_argument('device', type=str,
                       help='PCIe device to read')
   parser.add_argument('address', type=partial(int, base=0),
                       help='Address to read')
