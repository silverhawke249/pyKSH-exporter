import sys

from pprint import pprint

from ksh2vox.parser.ksh import KSHParser

with open(sys.argv[1], 'r') as f:
    parser = KSHParser(f)

    pprint(parser)

    with open('test.xml', 'w') as f:
        parser.write_xml(f)

    with open('test.vox', 'w') as f:
        parser.write_vox(f)

    # chart = read_ksh(f)

    # slam_ctr_l = 0
    # slam_ctr_r = 0
    # print('=== VOL L ===')
    # for when, vol_info in chart.note_data.vol_l.items():
    #     pprint(when)
    #     pprint(vol_info)
    #     slam_ctr_l += int(vol_info.start != vol_info.end)
    # print()
    # print('=== VOL R ===')
    # for when, vol_info in chart.note_data.vol_r.items():
    #     pprint(when)
    #     pprint(vol_info)
    #     slam_ctr_r += int(vol_info.start != vol_info.end)
    # print()
    # print(slam_ctr_l, slam_ctr_r)

    # pprint(chart.note_data.fx_l)
    # print()
    # pprint(chart.note_data.fx_r)
