#!/usr/bin/env python3
import csv, json, sys
csv.field_size_limit(sys.maxsize)

from argparse import ArgumentParser, FileType
from itertools import tee, chain, islice

import regex as re
import pymysql
from getpass import getpass
from more_itertools import peekable, one
from openpyxl import load_workbook

from asnake.logging import setup_logging, get_logger
from asnake.aspace import ASpace
from asnake.jsonmodel import JM


ap = ArgumentParser(description="Script to map box numbers to containers based on AO component names")
ap.add_argument('--host', default='localhost', help="MySQL host with ASpace database")
ap.add_argument('--user', default='pobocks', help='MySQL user to run as when connecting to ASpace database')
ap.add_argument('--database', default='tuftschivesspace')
ap.add_argument('--commit', action='store_true', help='actually make changes to ASpace')
ap.add_argument('--logfile', default='map_box_numbers.log')

def sniff_box_number(component_id):
    if '-' in component_id:
        return "probable Green Barcode"
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

shared_idx = 1
def box_no_or_bust(row):
    global shared_idx
    indicator_prefix = ''
    if row['barcode'].endswith('g'):
        return 'Green Barcode'
    if row['shared']:
        indicator = "Shared {shared_idx}".format(shared_idx=shared_idx)
        shared_idx += 1
        return indicator
    if row['barcode'].endswith('b'):
        indicator_prefix = 'Volume '

    potential_numbers = set(map(sniff_box_number, row['component_ids']))
    try:
        box_no = one(potential_numbers)
        return indicator_prefix + box_no
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

def convert_container_to_digital_object(container_info):
    '''Take a row representing a DGB (Digital Green Barcode) container and it's archival objects
and transform it into a digital object linked to the correct AO.'''
    # QUESTIONS:
    # - is_representative value for instance?
    # - really make a dummy file_version?
    ao_id = one(container_info['ao_ids'])
    cid = one(container_info['component_ids'])
    ao = repo.archival_objects(ao_id).json()
    del ao['position'] # updating AO with position set causes issues

    digital_object = JM.digital_object(
        digital_object_id = 'tufts:{cid}'.format(cid=cid),
        title= ao['title'],
        user_defined = JM.user_defined(
            string_1 = 'Digital object location',
            text_1 = container_info['barcode']
        ),
        linked_instances = [{'ref': '/repositories/2/archival_objects/{ao_id}'.format(ao_id=ao_id)}]
    )

    d_obj_res = aspace.post('repositories/2/digital_objects', json=digital_object)
    if d_obj_res.status_code == 200:
        do_uri = d_obj_res.json()['uri']
        log.info('created_digital_object', component_id=cid, digital_object_uri=do_uri)
        instance = JM.instance(
            instance_type='digital_object',
            digital_object={'ref': do_uri},
            is_representative=True
        )
        ao['instances'].append(instance)
        ao_res = aspace.client.post(ao['uri'], json=ao)
        if ao_res.status_code == 200:
            log.info('updated_ao', component_id=cid, digital_object_uri=do_uri)
            del_res = aspace.client.delete('/repositories/2/top_containers/{container_id}'.format(container_info))
            if del_res.status_code == 200:
                log.info('cleanup_dgb_container', **container_info)
            else:
                log.error('FAIL cleanup_dgb_container', result=del_res.json(), **container_info)
        else:
            log.error('FAIL updated_ao', component_id=cid, digital_object_uri=do_uri, result=ao_res.json())
            del_res = aspace.client.delete(do_uri)
            if del_res.status_code == 200:
                log.info('digital_object_cleanup', deleted=do_uri)
            else:
                log.error('FAIL digital_object_cleanup', deleted=do_uri, result=del_res.json())
    else:
        log.error('FAIL created_digital_object', component_id=cid, result=d_obj_res.json())

def map_rows(cursor):
    '''Transform JSON columns and boolean columns in resultset from MySQL'''
    for row in cursor:
        row['component_ids'] = json.loads(row['component_ids'])
        row['ao_ids'] = json.loads(row['ao_ids'])
        row['shared'] = True if row['shared'] > 1 else False
        yield row

def unmap_row(row):
    '''Transform python -> JSON for aggregate columns'''
    for field in 'ao_ids', 'component_ids':
        row[field] = json.dumps(row[field])
    return row

if __name__ == '__main__':
    args = ap.parse_args()

    setup_logging(filename=args.logfile)
    log = get_logger('map_box_numbers')

    log.info('start')

    aspace = ASpace()
    log.info('aspace_connect')
    repo = aspace.repositories(2) # Tufts only uses repo 2

    # note: fields match up to fields in MySQL query plus additional field for
    in_fields = ['container_id', 'barcode', 'component_ids', 'ao_ids', 'shared']
    out_fields = (*in_fields[0:2], 'proposed_box_number', *in_fields[2:],)

    conn = pymysql.connect(host=args.host, user=args.user, database=args.database, cursorclass=pymysql.cursors.DictCursor, password=
                           getpass("Please enter MySQL password for {}: ".format(args.user)))
    log.info('mysql_connect')

    with open('proposed_box_numbers.csv', 'w') as pbn,\
         open('digital_object_conversion.csv', 'w') as dgb,\
         conn.cursor() as db:

        w_pbn = csv.DictWriter(pbn, dialect='excel-tab', fieldnames=out_fields)
        w_pbn.writeheader()

        w_dgb = csv.DictWriter(dgb, dialect='excel-tab', fieldnames=in_fields)
        w_dgb.writeheader()

        shared_idx = 1

        db.execute('''SET group_concat_max_len=995000''')
        db.execute(
            '''SELECT tc.id as container_id,
                      tc.barcode as barcode,
                      concat('[', group_concat(concat('"', ao.component_id, '"')), ']') as component_ids,
                      concat('[', group_concat(ao.id), ']') as ao_ids,
                      count(DISTINCT ao.root_record_id) as shared
               FROM top_container tc
               JOIN top_container_link_rlshp tclr
                 ON tclr.top_container_id = tc.id
               JOIN sub_container s
                 ON s.id = tclr.sub_container_id
               JOIN instance i
                 ON s.instance_id = i.id
               JOIN archival_object ao
                 ON ao.id = i.archival_object_id
               WHERE tc.indicator LIKE 'data_value_missing%'
               GROUP BY tc.indicator
               ORDER BY tc.id, tc.barcode, ao.component_id''')
        data = map_rows(db)
        log.info('data_retrieved')

        for row in data:
            if row['barcode'].startswith('DGB'):
                log.info('process_digital_barcode')
                # handle things that ought to be digital barcodes
                w_dgb.writerow(unmap_row(row))
                if args.commit:
                    convert_container_to_digital_object(row)
            else:
                log.info('process_real_container')
                row['proposed_box_number'] = box_no_or_bust(row)

                w_pbn.writerow(unmap_row(row))
                if args.commit:
                    # do the dang thing for common case
                    pass

        log.info('end')
