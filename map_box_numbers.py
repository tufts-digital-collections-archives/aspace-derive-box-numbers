#!/usr/bin/env python3
import csv, json, sys
csv.field_size_limit(sys.maxsize)

from argparse import ArgumentParser, FileType
from itertools import chain, islice
from types import SimpleNamespace as NS

import regex as re
import pymysql
from getpass import getpass
from more_itertools import peekable, one, chunked
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
ap.add_argument('--cached_aos', type=FileType('r'), help='source of cached archival object jsons')
ap.add_argument('--cached_aos_save', type=FileType('w'), help='place to store cached archival object jsons')
ap.add_argument('--cached_containers', type=FileType('r'), help='source of cached container jsons')
ap.add_argument('--cached_containers_save', type=FileType('w'), help='place to store cached container jsons')


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
    try:
        ao_id = one(container_info['ao_ids'])
        cid = one(container_info['component_ids'])
    except Exception as e:
        import ipdb;ipdb.set_trace()
    ao = ao_jsons[ao_id]
    del ao['position'] # updating AO with position set causes issues

    digital_object = JM.digital_object(
        digital_object_id = 'tufts:{cid}'.format(cid=cid),
        title= ao['title'],
        file_versions = [JM.file_version(
            file_uri='example://no-url-available',
            publish=True
        )],
        user_defined = JM.user_defined(
            string_1 = 'Digital object location',
            text_1 = container_info['barcode']
        ),
        linked_instances = [{'ref': '/repositories/2/archival_objects/{ao_id}'.format(ao_id=ao_id)}]
    )
    log.info('create_digital_obj', digital_object=digital_object)
    if args.commit:
        d_obj_res = aspace.client.post('repositories/2/digital_objects', json=digital_object)
    else: d_obj_res = NS(status_code=200, json = lambda: {'uri': 'PLACEHOLDER'}) # mock object if dry-run
    if d_obj_res.status_code == 200:
        do_uri = d_obj_res.json()['uri']
        log.info('created_digital_object', component_id=cid, digital_object_uri=do_uri, for_real=args.commit)
        instance = JM.instance(
            instance_type='digital_object',
            digital_object={'ref': do_uri},
            is_representative=False
        )
        ao['instances'].append(instance)
        if args.commit:
            ao_res = aspace.client.post(ao['uri'], json=ao)
            if ao_res.status_code == 200:
                log.info('updated_ao', component_id=cid, ao=ao['uri'], digital_object_uri=do_uri)
                del_res = aspace.client.delete('/repositories/2/top_containers/{}'.format(cid))
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
            log.info('SKIP updated_ao', component_id=cid, message='Since this is a dry run, we shan\'t update the AO')

    else:
        log.error('FAIL created_digital_object', component_id=cid, result=d_obj_res.json())

def reindicate_container(row, new_indicator):
    '''Change indicator for container'''
    # container SHOULD be in jsons, but fallback to individual fetch if it's not for some reason?
    container = container_jsons.get(row['container_id'], None)
    if not container:
        log.warning('WARN single_container_fetch', container_id = row['container_id'])
        c_res = aspace.client.get('repositories/2/top_containers/{}'.format(row['container_id']))
        if c_res.status_code == 200:
            container = c_res.json()
            log.info('single_container_fetch', container_id = row['container_id'])
        else:
            log.error('FAIL single_container_fetch', container_id = row['container_id'])

    container['indicator'] = new_indicator
    container_res = aspace.client.post(container['uri'], json=container)
    if container_res.status_code == 200:
        log.info('updated_container', container_id=row['container_id'])
    else:
        log.info('FAIL updated_container', container_id=row['container_id'], data=row, error=container_res.json())

def map_rows(cursor):
    '''Transform JSON columns and boolean columns in resultset from MySQL'''
    for row in cursor:
        row['component_ids'] = json.loads(row['component_ids'])
        row['ao_ids'] = json.loads(row['ao_ids'])
        row['shared'] = True if row['shared'] > 1 else False
        yield row

def unmap_row(row):
    '''Transform python -> JSON for aggregate columns'''
    return {k:(json.dumps(v) if k in ('ao_ids', 'component_ids') else v) for k,v in row.items()}

def chain_aos(for_aos):
    for row in for_aos:
        yield from row['ao_ids']

if __name__ == '__main__':
    args = ap.parse_args()

    setup_logging(filename=args.logfile)
    log = get_logger('map_box_numbers')

    log.info('start')

    aspace = ASpace()
    log.info('aspace_connect')

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
        data = list(map_rows(db))

        log.info('fetch_ao_jsons')
        ao_jsons = {}
        if args.cached_aos:
            log.info('load_aos_from_cache')
            with args.cached_aos as f:
                ao_jsons = {int(k):v for k,v in json.load(f).items()}
        else:
            for chunk in chunked(sorted(chain_aos(data)), 250):
                log.info('fetch_ao_chunk', chunk=chunk)
                ao_res = aspace.client.get('repositories/2/archival_objects', params={'id_set': chunk})
                if ao_res.status_code == 200:
                    log.info('fetch_chunk_complete', chunk="{}-{}".format(chunk[0], chunk[-1]))
                    for ao in ao_res.json():
                        ao_id = int(ao['uri'][ao['uri'].rfind('/') + 1:])
                        ao_jsons[ao_id] = ao
            if args.cached_aos_save:
                log.info('save_aos_to_cache')
                with args.cached_aos_save as f:
                    json.dump(ao_jsons, f)

        if args.cached_containers:
            log.info('load_containers_from_cache')
            with args.cached_containers as f:
                container_jsons = {int(k):v for k,v in json.load(f).items()}
        else:
            container_jsons = {}
            for chunk in chunked(sorted(row['container_id'] for row in data), 250):
                log.info('fetch_container_chunk', chunk=chunk)
                c_res = aspace.client.get('repositories/2/archival_objects', params={'id_set': chunk})
                if c_res.status_code == 200:
                    log.info('fetch_chunk_complete', chunk="{}-{}".format(chunk[0], chunk[-1]))
                    for c in c_res.json():
                        c_id = int(c['uri'][c['uri'].rfind('/') + 1:])
                        container_jsons[c_id] = c
            if args.cached_containers_save:
                log.info('save_containers_to_cache')
                with args.cached_containers_save as f:
                    json.dump(container_jsons, f)

        log.info('data_retrieved')

        for row in data:
            if row['barcode'].startswith('DGB'):
                log.info('process_digital_barcode')
                # handle things that ought to be digital barcodes
                w_dgb.writerow(unmap_row(row))
                convert_container_to_digital_object(row)
            else:
                log.info('process_real_container')
                new_indicator = row['proposed_box_number'] = box_no_or_bust(row)

                w_pbn.writerow(unmap_row(row))
                if args.commit and new_indicator not in {'Green Barcode', 'Cannot Assign'}:
                    # do the dang thing for common case
                    reindicate_container(row, new_indicator)


        log.info('end')
