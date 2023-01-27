#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
from aerofiles.seeyou.reader import Reader as CupFileReader

cupfile = CupFileReader()
print(sys.argv[1])
cupfile.read(open(str(sys.argv[1])))
