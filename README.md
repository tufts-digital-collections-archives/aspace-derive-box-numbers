# ASpace Derive Box-numbers

A script for deriving box-numbers from archival object component identifiers, and some associated scripts and SQL queries.  This README covers the `map_box_numbers.py`, `map_green_barcode_box_numbers.py` and `report_duplicates.py` scripts; the SQL docs in `db_queries` and any other scripts are ephemera, left as an excercise to the reader.

This script's operation is specifically keyed to details of Tufts University's data, and should not be taken as a general means of mapping component IDs to box numbers.

## Requirements

These scripts require Python 3.5 or higher and several Python packages, and a working instance of ArchivesSpace version 2.5.1.

The Python packages required for this script are listed in [Pipfile](https://github.com/tufts-digital-collections-archives/aspace-derive-box-numbers/blob/master/Pipfile).  If you're using [Pipenv](https://docs.pipenv.org/en/latest/) to manage dependencies, you can install them by running:

```
pipenv install
```

And run the script as:

```
pipenv run map_box_numbers.py ARGUMENTS
```

Alternatively, you can also install dependencies with pip from the provided `requirements.txt` file:

```
pip install -r requirements.txt
```

Additionally, you will need to configure ArchivesSnake via a YAML configuration file as per the instructions [here](https://github.com/archivesspace-labs/ArchivesSnake/#configuration), providing a base url, username, and password for a user that has the ability to edit and create repository records. (The script assumes a single repository with id = 2.)  You will also need to provide database access to the MySQL database of your ArchivesSpace instance.  Host name, user, and database name can be passed in as arguments to the script, but you will be prompted to input the password, as it is not secure to include it within the command.

## `map_box_numbers.py`

### Operation

If run without the `--commit` argument, the script will produce two files: a report on the disposition of top_containers (`proposed_box_numbers.csv`) and a report on containers converted to digital objects (`digital_object_conversion.csv`); no changes will be made to your ArchivesSpace data.  By adding `--commit`, the script will:

When run, the script will produce the following:

1. A report of proposed indicators or else failure/omission notices ("Cannot Assign", "Green Barcode", "Omitted") for top containers to be processed (`proposed_box_numbers.csv`)
2. a report on containers converted to digital objects (`digital_object_conversion.csv`)

No changes will be made to the data in ArchivesSpace.

If the `--commit` argument is passed, the script will also:

3. Change the indicators of boxes
4. Convert boxes whose barcodes indicate they are supposed to be digital objects into digital objects.

Additionally, a log will be produced, by default at `map_box_numbers.log`. This log is formatted as JSON Lines, i.e. a single JSON object per line.

### Usage Instructions

```
usage: map_box_numbers.py [-h] [--host HOST] [--user USER]
                          [--database DATABASE] [--omissions OMISSIONS]
                          [--manual_mappings MANUAL_MAPPINGS] [--commit]
                          [--logfile LOGFILE] [--cached_aos CACHED_AOS]
                          [--cached_aos_save CACHED_AOS_SAVE]
                          [--cached_containers CACHED_CONTAINERS]
                          [--cached_containers_save CACHED_CONTAINERS_SAVE]

Script to map box numbers to containers based on AO component names

optional arguments:
  -h, --help            show this help message and exit
  --host HOST           host of ASpace database
  --user USER           MySQL user to run as when connecting to ASpace
                        database
  --database DATABASE   Name of MySQL database
  --omissions OMISSIONS
                        Single column Excel file with list of container
                        barcodes to ignore
  --manual_mappings MANUAL_MAPPINGS
                        two column Excel file with mapping from barcode to
                        indicator
  --commit              actually make changes to ASpace
  --logfile LOGFILE     path to print log to
  --cached_aos CACHED_AOS
                        source of cached archival object jsons
  --cached_aos_save CACHED_AOS_SAVE
                        place to store cached archival object jsons
  --cached_containers CACHED_CONTAINERS
                        source of cached container jsons
  --cached_containers_save CACHED_CONTAINERS_SAVE
                        place to store cached container jsons
```

## `map_green_barcode_box_numbers.py`

### Operation

When run, this script will process two Excel spreadsheets, both of which are expected to contain one worksheet with no headers, with all data consisting of barcodes:

1. top container barcodes for containers that are being used as pseudo-locations (i.e. that represent a shelf rather than an actual container)
2. new barcodes to assign to newly created top containers

It will then:

1. create real locations with the same barcodes
2. take the archival objects in these containers, group them by CUID-indicated box number where possible, and create new top containers, associating them with the correct locations.
3. Remove the pseudo-locations IF AND ONLY IF there were no errors in steps 1 and 2.

This script will change values in ArchivesSpace; note that there is not a "no-commit" mode, because the changes to be made depend on each other enough that running the analytical parts alone isn't really coherent.  It will also output a report (by default `barcodes_report.csv`) which archivists should then use to apply the proper barcode to the proper physical container.  It also produces a log of actions taken (by default `barcodes_report.log`).  These will be emitted in the directory the script is run from.

### Usage

```
usage: map_green_barcode_box_numbers.py [-h] [--host HOST] [--user USER]
                                        [--database DATABASE]
                                        [--logfile LOGFILE]
                                        [--reportfile REPORTFILE]
                                        spreadsheet barcode_source

Script to convert green barcode pseudo-locations (containers) into proper
locations, deriving and assigning box numbers.

positional arguments:
  spreadsheet               Spreadsheet of pseudo-location barcodes
  barcode_source            Spreadsheet of new barcodes to be assigned

optional arguments:
  -h, --help                show this help message and exit
  --host HOST               host of ASpace database
  --user USER               MySQL user to run as when connecting to ASpace database
  --database DATABASE       Name of MySQL database
  --logfile LOGFILE         path to print log to
  --reportfile REPORTFILE   path to print CSV report to
```

## Report Duplicates

Additionally, this repository contains a script for creating a report of duplicated box numbers, `report_duplicates.py`.

### Operation

Running the script will produce a report in the same directory as the script, with the filename `dupe_report.csv`.

### Usage

```
usage: report_duplicates.py [-h] [--host HOST] [--user USER]
                            [--database DATABASE] [--logfile LOGFILE]

Script to detect duplicate indicators by series based on AO component names

optional arguments:
  -h, --help           show this help message and exit
  --host HOST          host of ASpace database
  --user USER          MySQL user to run as when connecting to ASpace database
  --database DATABASE  Name of MySQL database
  --logfile LOGFILE    path to print log to
```

## Create Locations

There's a small script for creating locations from a spreadsheet. This spreadsheet is expected to consist of a first row of headers that match the fields in the location object,
and an additional field `location_profile_URI` which has the URI of a location profile, WITHOUT a leading '/'.

## Operation

Running the script will create the locations, and leave a log in the same directory as the script, with the filename `create_locations.log`

## Usage

```
usage: create_locations.py [-h] [--logfile LOGFILE] spreadsheet

Script to create locations from spreadsheet

positional arguments:
  spreadsheet        Spreadsheet of location attrs

optional arguments:
  -h, --help         show this help message and exit
  --logfile LOGFILE  path to print log to
```

## Copyright

Produced for Tufts University by Dave Mayo ([pobocks](https://github.com/pobocks)).

Copyright language pending, but basically, it's copyright Tufts.
