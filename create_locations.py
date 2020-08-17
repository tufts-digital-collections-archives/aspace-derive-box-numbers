import json
from argparse import ArgumentParser
from getpass import getpass

import pymysql

from openpyxl import load_workbook
from more_itertools import first

from asnake.aspace import ASpace
from asnake.logging import setup_logging, get_logger
from asnake.aspace import ASpace
from asnake.jsonmodel import JM

ap = ArgumentParser(description="Script to create locations from spreadsheet")
ap.add_argument('spreadsheet', type=load_workbook, help="Spreadsheet of location attrs")
ap.add_argument('--host', default='localhost', help="host of ASpace database")
ap.add_argument('--user', default='pobocks', help='MySQL user to run as when connecting to ASpace database')
ap.add_argument('--database', default='tuftschivesspace', help="Name of MySQL database")
ap.add_argument('--logfile', default='create_locations.log', help='path to print log to')

if __name__ == "__main__":
    args = ap.parse_args()
    setup_logging(filename=args.logfile)
    log = get_logger('create_locations')

    log.info('start')

    aspace = ASpace()
    log.info('aspace_connect')

    log.info('process_spreadsheet')
    rows = args.spreadsheet.worksheets[0].values
    headers = dict(enumerate(first(rows)))
    JSONS = []

    conn = pymysql.connect(host=args.host, user=args.user, database=args.database, cursorclass=pymysql.cursors.DictCursor,
                           password=getpass("Please enter MySQL password for {}: ".format(args.user)))
    log.info('mysql_connect')

    for row in rows:
        row_dict = {headers[idx]:str(field) for idx, field in enumerate(row)}
        profile_uri = row_dict.pop('location_profile_URI')
        row_dict['location_profile'] = {'ref': '/' + profile_uri }
        JSONS.append(row_dict)


        with conn:
            db = conn.cursor()
            db.execute('SELECT DISTINCT barcode FROM location')
            existing_barcodes = set(row['barcode'] for row in db.fetchall())

    log.info('create_locations')
    for location in JSONS:
        log.info('create_start', barcode=location['barcode'])
        if location['barcode'] in existing_barcodes:
            log.info('location_already_exists', barcode=location['barcode'])
            continue
        res = aspace.client.post('locations', json=location)
        if res.status_code == 200:
            log.info('create_success', result=res.json())
        else:
            log.info('create_error', result=res.json(), status_code=res.status_code)
    log.info('end')
