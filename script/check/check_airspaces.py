#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
from aerofiles.openair.reader import Reader as OpenAirReader

openairfile = OpenAirReader()
openairfile.read(open(str(sys.argv[1])))
