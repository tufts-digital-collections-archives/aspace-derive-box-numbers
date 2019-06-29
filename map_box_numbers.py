#!/usr/bin/env python3
import csv, json, sys
csv.field_size_limit(sys.maxsize)

from argparse import ArgumentParser, FileType
from itertools import tee, chain, islice
from more_itertools import peekable, one

from openpyxl import load_workbook

ap = ArgumentParser(description="Script to map box numbers to containers based on AO component names")
ap.add_argument('csv', type=FileType('r'), help='tab-delimited csv database dump of container information')

def sniff_box_number(component_id):
    if '-' in component_id:
        return "Green Barcode"
    cid = component_id.split('.')
    if len(cid[-1]) != 5 or\
       not cid[-1].isnumeric() or\
       len(cid) < 4:
        return "Cannot Assign"
    it = peekable(cid)
    next(it) # skip collection id

    curr = None
    while len(it.peek()) < 5:
        curr = next(it)
    return curr

def split(string, sep="."):
    return str.split(string, sep)

def box_no_or_bust(component_ids):
    potential_numbers = set(map(sniff_box_number, component_ids))
    try:
        box_no = one(potential_numbers)
        return box_no
    except ValueError:
        return "Cannot Assign"

def common_prefix(component_ids):
    pref = []
    for segments in zip(map(split, component_ids)):
        if len(set(segments)) == 1:
            pref.append(segments[0])
        else:
            break
    return pref


def detect_oversized(component_ids):
    pass

if __name__ == '__main__':
    args = ap.parse_args()
    with args.csv as f:
        for_dict, for_chain = tee(csv.reader(f, dialect='excel-tab'), 2)
        data = [(a[0], a[1], json.loads(a[2]), int(a[3])) for a in for_dict]

        aos = list(chain(*(json.loads(a[2]) for a in for_chain)))

        with open('proposed_box_numbers.csv', 'w') as f:
            w = csv.writer(f, dialect='excel-tab')
            w.writerow(('ASpace Container ID', 'barcode', 'proposed box no', 'component IDs', 'shared'),)
            for x in data:
                w.writerow((*x[0], x[1], box_no_or_bust(x[2]), json.dumps(x[2]), x[3] > 1))
