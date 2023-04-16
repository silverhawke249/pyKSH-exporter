import sys

from ksh2vox.parser.ksh import KSHParser


with open(sys.argv[1], 'r', encoding='utf-8-sig') as f:
    parser = KSHParser(f)

    with open('test.xml', 'w') as f:
        parser.write_xml(f)

    with open('test.vox', 'w') as f:
        parser.write_vox(f)
