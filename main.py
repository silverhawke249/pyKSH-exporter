import sys

from pprint import pprint

from ksh2vox.reader.ksh import read_ksh

with open(sys.argv[1], 'r') as f:
    chart = read_ksh(f)
    pprint(chart.note_data)
