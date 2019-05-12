#!/usr/bin/env python3
import json, csv, sys
from collections import Counter
from itertools import chain
from more_itertools import peekable
from argparse import ArgumentParser, FileType

csv.field_size_limit(sys.maxsize)

ap = ArgumentParser(description="Parse output of 'container_id_and_barcode2component_identifiers.sql' into a report on patterns found")
ap.add_argument('input_file', type=FileType('r'), help='Tab delimited CSV of: component ids, barcodes, and JSON arrays of component identifiers')

def countify(pattern):
    '''Turn pattern into regexp'''
    p = peekable(pattern)

    output = ""
    while p.peek(None):
        if p.peek('') == '.':
            output += '\.'
            next(p)
        elif not p.peek().isdigit():
            output += next(p)
        else:
            count = 1
            while p.peek('').isdigit():
                next(p) # discard
                count += 1
            output += r'\d{{{}}}'.format(count)
    return output

if __name__ == '__main__':
    args = ap.parse_args()
    report = Counter()
    out = csv.writer(sys.stdout, dialect='excel-tab')
    with args.input_file as f:
        aos = chain(*(json.loads(a[2]) for a in csv.reader(f, dialect='excel-tab')))
        for x in aos:
            report[countify(x)] += 1
        total = sum(report.values())
        rows = sorted(report.items(), key=lambda pair: pair[1])

        out.writerow(['component_id pattern', 'count', '% matching'])
        for row in rows:
            percent = "{:.1%}".format(report[row[0]]/total)
            out.writerow((row[0].replace('.', '\.'), *row[1:], percent,))
