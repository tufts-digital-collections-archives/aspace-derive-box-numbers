#! /usr/bin/env python3
from argparse import ArgumentParser
from getpass import getpass

import pymysql
from openpyxl import load_workbook

if __name__ == "__main__":
    ap = ArgumentParser(description="Script to determine green barcode locations")
    ap.add_argument('spreadsheet', type=load_workbook, help="Spreadsheet of location barcodes")
    ap.add_argument('--host', default='localhost', help="host of ASpace database")
    ap.add_argument('--user', default='pobocks', help='MySQL user to run as when connecting to ASpace database')
    ap.add_argument('--database', default='tuftschivesspace', help="Name of MySQL database")
