#!/usr/bin/env python3
import csv, json

from argparse import ArgumentParser
from collections import OrderedDict
from getpass import getpass

import pymysql

from asnake.logging import setup_logging, get_logger
from asnake.aspace import ASpace

ap = ArgumentParser(description="Script to detect duplicate indicators by series based on AO component names")
ap.add_argument('--host', default='localhost', help="host of ASpace database")
ap.add_argument('--user', default='pobocks', help='MySQL user to run as when connecting to ASpace database')
ap.add_argument('--database', default='tuftschivesspace', help="Name of MySQL database")
ap.add_argument('--logfile', default='dupe_report.log', help='path to print log to')

if __name__ == '__main__':
    args = ap.parse_args()
    setup_logging(filename=args.logfile)
    log = get_logger('report_duplicates')

    log.info('start')

    aspace = ASpace()
    log.info('aspace_connect')

    log.info('end')

    conn = pymysql.connect(host=args.host, user=args.user, database=args.database, cursorclass=pymysql.cursors.DictCursor,
                           password=getpass("Please enter MySQL password for {}: ".format(args.user)))
    log.info('mysql_connect')

    with open('dupe_report.csv', 'w') as dupe_report, conn:
        db = conn.cursor()
        db.execute('''SET group_concat_max_len=995000''')
        db.execute('''SELECT r.id,
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

        db.execute('''SELECT r.id,
                              substr(r.identifier, 3, 5) as identifier,
                              substr(ao.component_id, 7, 3) as series,
                              tc.indicator,
                              concat('{', group_concat(DISTINCT concat('"', tc.id, '": "', tc.barcode, '"')), '}') AS id2bc
                       FROM resource r
                       JOIN archival_object ao ON ao.root_record_id = r.id
                       JOIN instance i ON i.archival_object_id = ao.id
                       JOIN sub_container sc ON i.id = sc.instance_id
                       JOIN top_container_link_rlshp tclr ON tclr.sub_container_id = sc.id
                       JOIN top_container tc ON tc.id = tclr.top_container_id
                       GROUP BY r.id, series, tc.indicator
                       HAVING count(DISTINCT tc.id) > 1 ORDER BY r.id, series, tc.id''')

        w_dupe = csv.DictWriter(dupe_report, dialect='excel-tab', fieldnames=['resource_id', 'identifier_and_series', 'container_id', 'barcode', 'original_box_number', 'suggested_box_number'])
        w_dupe.writeheader()

        dupe_id2indicator = {}
        for row in db.fetchall():
            try:
                dupes = iter(json.loads(row['id2bc'].replace('\\', '\\\\'), object_pairs_hook=OrderedDict).items())
            except json.decoder.JSONDecodeError as e:
                log.error('FAILED to process dupes for resource', data=row)
                continue
            for cid, bc in dupes:
                res = aspace.client.get('repositories/2/top_containers/{}'.format(cid))
                if res.status_code == 200:
                    container = res.json()
                    if not container['indicator'].isnumeric():
                        log.warning('FAILED duplicate_indicator is not numeric', container_id=cid, indicator=container['indicator'])
                else:
                    log.warning('FAILED to fetch duplicate top container {}'.format(cid), status=res.status_code, response=ress.json())
                    continue
                s2i_key = "{}.{}".format(row['id'], row['series'])
                if not s2i_key in series2idx:
                    log.warning('FAILED to find series2idx', key=s2i_key, container_id=cid, barcode=bc)
                    indicator = "could not find reliable maximum box number, cannot guess"
                elif not container['indicator'].isnumeric():
                    indicator = "non-numeric box number, cannot guess"
                else:
                    series2idx[s2i_key] += 1
                    indicator = series2idx[s2i_key]
                dupe_id2indicator[cid] = indicator
                w_dupe.writerow({"resource_id": row['id'], "identifier_and_series": s2i_key, "container_id": cid, "barcode": bc, "original_box_number": container['indicator'],  "suggested_box_number": indicator})

        log.info('end')
