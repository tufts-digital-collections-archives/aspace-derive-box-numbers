import json
from argparse import ArgumentParser
from getpass import getpass

from openpyxl import load_workbook
from more_itertools import first

from asnake.aspace import ASpace
from asnake.logging import setup_logging, get_logger
from asnake.aspace import ASpace
from asnake.jsonmodel import JM

ap = ArgumentParser(description="Script to create locations from spreadsheet")
ap.add_argument('spreadsheet', type=load_workbook, help="Spreadsheet of location attrs")
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
    for row in rows:
        row_dict = {headers[idx]:str(field) for idx, field in enumerate(row)}
        profile_uri = row_dict.pop('location_profile_URI')
        row_dict['location_profile'] = {'ref': '/' + profile_uri }
        JSONS.append(row_dict)

    log.info('create_locations')
    for location in JSONS:
        log.info('create_start', barcode=location['barcode'])
        res = aspace.client.post('locations', json=location)
        if res.status_code == 200:
            log.info('create_success', result=res.json())
        else:
            log.info('create_error', result=res.json(), status_code=res.status_code)
