#! /usr/bin/env python3
import csv, json

from argparse import ArgumentParser
from getpass import getpass
from itertools import chain

import pymysql
from openpyxl import load_workbook
from more_itertools import first

from asnake.logging import setup_logging, get_logger

ap = ArgumentParser(description="Script to determine green barcode locations")
ap.add_argument('spreadsheet', type=load_workbook, help="Spreadsheet of location barcodes")
ap.add_argument('--host', default='localhost', help="host of ASpace database")
ap.add_argument('--user', default='pobocks', help='MySQL user to run as when connecting to ASpace database')
ap.add_argument('--database', default='tuftschivesspace', help="Name of MySQL database")
ap.add_argument('--logfile', default='barcodes_report.log', help='path to print log to')

if __name__ == "__main__":
    args = ap.parse_args()
    setup_logging(filename=args.logfile)
    log = get_logger('barcodes_report')

    log.info('start')

    conn = pymysql.connect(host=args.host, user=args.user, database=args.database, cursorclass=pymysql.cursors.DictCursor,
                           password=getpass("Please enter MySQL password for {}: ".format(args.user)))

    log.info('mysql_connect')

    with open('barcode_report.csv', 'w') as barcode_report, conn:
        db = conn.cursor()
        db.execute("""SELECT barcode FROM top_container WHERE barcode REGEXP '[0-9]+[gG]$'""")

        # Green barcodes, either from explicit list OR from matching the "digits with G as last character" format
        green_barcodes = sorted(set(chain((first(row) for row in args.spreadsheet.worksheets[0].values), (row['barcode'] for row in db.fetchall()))))

        # hash of all extant barcodes. Assumes no duplicates which is not safe in principle
        # due to lack of unique index on barcode but is safe in practice across Tufts data
        db.execute("""SELECT id, barcode FROM location WHERE barcode IS NOT NULL""")
        bc_to_loc = {row['barcode']:int(row['id']) for row in db.fetchall()}

        db.execute("""SELECT r.id,
                             concat('["', group_concat(DISTINCT substr(ao.component_id, 7,3) SEPARATOR '","'), '"]') as series
                      FROM resource r
                      JOIN archival_object ao
                        ON ao.root_record_id = r.id
                  GROUP BY r.id""")
        rid_to_series = {row['id']:json.loads(row['series']) for row in db.fetchall()}

    from ipdb import set_trace;set_trace()
