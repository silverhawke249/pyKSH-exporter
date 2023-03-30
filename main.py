import sys

from ksh2vox.reader.ksh import read_ksh

with open(sys.argv[1], 'r') as f:
    read_ksh(f)
