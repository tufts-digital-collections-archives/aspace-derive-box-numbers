#!/usr/bin/env python3
import csv, json, sys, os
csv.field_size_limit(sys.maxsize)

from argparse import ArgumentParser
from collections import OrderedDict
from getpass import getpass

from openpyxl import load_workbook
import pymysql

from asnake.logging import setup_logging, get_logger

ap = ArgumentParser(description="Script to report out green barcode container ids, barcode, and component identifiers")
ap.add_argument('--host', default='localhost', help="host of ASpace database")
ap.add_argument('--user', default='pobocks', help='MySQL user to run as when connecting to ASpace database')
ap.add_argument('--database', default='tuftschivesspace', help="Name of MySQL database")
ap.add_argument('--logfile', default='green_barcode_cid_2_barcode_and_components.log', help='path to print log to')
ap.add_argument('--green_containers', help="Excel file with container barcodes of interest")

def top_container_barcodes(excel_filename):
    xl = load_workbook(excel_filename)
    rows = iter(xl.worksheets[0])
    next(rows) # skip header
    return ",".join(f"'{row[0].value}'" for row in rows)

if __name__ == '__main__':
    args = ap.parse_args()
    setup_logging(filename=args.logfile)
    log = get_logger('green_barcodes_cid2bc_and_components')

    log.info('start')

    conn = pymysql.connect(host=args.host, user=args.user, database=args.database, cursorclass=pymysql.cursors.DictCursor,
                password=getpass("Please enter MySQL password for {}: ".format(args.user)))
    log.info('mysql_connect')

    with open('green_cid2bc_and_components.csv', 'w') as gc2bac_report, conn:
        db = conn.cursor()

        db.execute('''SET group_concat_max_len=995000''')
        db.execute(f'''
SELECT tc.id,
       tc.indicator,
       tc.barcode,
       concat('[', group_concat(concat('"', ao.component_id, '"')), ']') as component_ids,
       concat('[', group_concat(ao.id), ']') as ao_ids,
       count(DISTINCT ao.root_record_id) as resources_attached_to
FROM top_container tc
JOIN top_container_link_rlshp tclr
  ON tclr.top_container_id = tc.id
JOIN sub_container s
  ON s.id = tclr.sub_container_id
JOIN instance i
  ON s.instance_id = i.id
JOIN archival_object ao
  ON ao.id = i.archival_object_id
WHERE tc.barcode IN ({top_container_barcodes(args.green_containers)})
GROUP BY tc.id
ORDER BY tc.id, tc.barcode, ao.component_id
        ''')

        data = db.fetchall()
        writer = csv.DictWriter(gc2bac_report, fieldnames=data[0].keys(), dialect='excel-tab')
        for row in data:
            writer.writerow(row)

    log.info('end')
