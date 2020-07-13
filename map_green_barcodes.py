#!/usr/bin/env python3
import csv, json

from argparse import ArgumentParser
from collections import OrderedDict
from getpass import getpass

import pymysql

from asnake.logging import setup_logging, get_logger
from asnake.aspace import ASpace

ap = ArgumentParser(description="Script to suggest new box numbers and assign barcodes to Green Barcode boxes")
ap.add_argument('--host', default='localhost', help="host of ASpace database")
ap.add_argument('--user', default='pobocks', help='MySQL user to run as when connecting to ASpace database')
ap.add_argument('--database', default='tuftschivesspace', help="Name of MySQL database")
ap.add_argument('--logfile', default='map_green_barcodes.log', help='path to print log to')

if __name__ == '__main__':
    args = ap.parse_args()
    setup_logging(filename=args.logfile)
    log = get_logger('map_green_barcodes')

    log.info('start')

    aspace = ASpace()
    log.info('aspace_connect')

    conn = pymysql.connect(host=args.host, user=args.user, database=args.database, cursorclass=pymysql.cursors.DictCursor,
                           password=getpass("Please enter MySQL password for {}: ".format(args.user)))
    log.info('mysql_connect')
    log.info('load_series2idx')
    with open('map_green_barcodes_report.csv', 'w') as gb_report, conn:
        db = conn.cursor()
        db.execute('''SET group_concat_max_len=995000''')
        db.execute('''SELECT r.id,
                             substr(r.identifier, 3, 5) as r_identifier,
                             substr(ao.component_id, 7, 3) as series,
                             max(CAST(regexp_substr(tc.indicator, '[0123456789]+$') AS integer)) AS max_indicator
                       FROM resource r
                       JOIN archival_object ao ON ao.root_record_id = r.id
                       JOIN instance i ON i.archival_object_id = ao.id
                       JOIN sub_container sc ON i.id = sc.instance_id
                       JOIN top_container_link_rlshp tclr ON tclr.sub_container_id = sc.id
                       JOIN top_container tc ON tc.id = tclr.top_container_id
                       WHERE tc.indicator REGEXP '[0123456789]+$'
                       AND tc.indicator REGEXP '^[0123456789;, -]+$'
                       GROUP BY r.id, series
                       HAVING max_indicator > 0
                       ORDER BY r.id''')

        series2idx = {"{}.{}".format(el['id'], el['series']):el['max_indicator'] for el in db.fetchall()}
        log.info('series2idx_load_complete')


        log.info('load_data')
        db.execute('''SELECT tc.id as container_id,
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
