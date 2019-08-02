# ASpace Derive Box-numbers

A script for deriving box-numbers from archival object component identifiers, and some associated scripts and SQL queries.  This readme covers the `map_box_numbers.py` script exclusively, the SQL statements and other scripts are ephemera and left as an excercise to the reader.

This script's operation is specifically keyed to details of Tufts University's data, and should not be taken as a general means of mapping component IDs to box numbers.

## Requirements

The requirements for this script are listed in [Pipfile].  If you're using [Pipenv](https://docs.pipenv.org/en/latest/) to manage dependencies, you can install them by running:

```shell
pipenv install
```

And run the script as:

```shell
pipenv run map_box_numbers.py ARGUMENTS
```

Additionally, you will need to configure ArchivesSnake via a yaml configuration file as per instructions [here](https://github.com/archivesspace-labs/ArchivesSnake/#configuration), providing a baseurl and a username and password for a user with the ability to edit and create records in your repository (the script assumes a single repository with id = 2).  You will also need to provide database access to the MySQL database of your ArchivesSpace instance.  Hostname, user, and database name can be passed in as arguments to the script, but you will be prompted to input the password, as it is not secure to include it in the command.

## Operation

If run without the `--commit` argument, the script will produce two files, a report on the disposition of top_containers in `proposed_box_numbers.csv`, and a report on containers converted to digital objects in `digital_object_conversion.csv`, but will not actually make changes to the data in ArchivesSpace.  With `--commit`, the reports will be generated AND the indicators of boxes will be changed, AND boxes whose barcodes indicate they are supposed to be digital objects will be converted.  Additionally, a log will be produced, by default at `map_box_numbers.log`  This log is formatted as line-oriented JSON, i.e. a single JSON object per line.

## Usage Instructions

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

Produced for Tufts University by Dave Mayo ([pobocks](/pobocks))

Copyright Language Pending but it's copyright Tufts
