import itertools
import sys

from pprint import pprint

from ksh2vox.reader.ksh import read_ksh

with open(sys.argv[1], 'r') as f:
    chart = read_ksh(f)

    slam_ctr_l = 0
    slam_ctr_r = 0
    print('=== VOL L ===')
    for when, vol_info in chart.note_data.vol_l.items():
        pprint(when)
        print(vol_info)
        slam_ctr_l += int(vol_info.start != vol_info.end)
    print()
    print('=== VOL R ===')
    for when, vol_info in chart.note_data.vol_r.items():
        pprint(when)
        print(vol_info)
        slam_ctr_r += int(vol_info.start != vol_info.end)
    print()
    print(slam_ctr_l, slam_ctr_r)

    # pprint(chart.note_data)
