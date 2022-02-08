#!/usr/bin/python

import sys, getopt
import aerofiles.openair

from aerofiles.openair.reader import Reader as OpenAirReader

openairfile = OpenAirReader()
openairfile.read(open(str(sys.argv[1])))
