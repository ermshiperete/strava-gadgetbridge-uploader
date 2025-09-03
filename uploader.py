#!/usr/bin/env python3
import argparse
import configparser
from datetime import datetime
import json
import logging
import logging.config
import os
import sys
import time
import uuid
import xml.etree.ElementTree as ET

from stravalib.client import Client, exc
from stravalib.util.limiter import RateLimiter

os.environ['SILENCE_TOKEN_WARNINGS'] = '1'


logger: logging.Logger = logging.getLogger(__name__)
DRY_RUN_PREFIX = "[DRY RUN] "
DRY_RUN = False


# This list can be expanded
# @see https://developers.strava.com/docs/uploads/#upload-an-activity
# @see https://github.com/hozn/stravalib/blob/master/stravalib/model.py#L723
activity_translations = {
    'running': 'run',
    'cycling': 'ride',
    'mountain biking': 'ride',
    'hiking': 'hike',
    'walking': 'walk',
    'swimming': 'swim',
    'downhill skiing': 'alpineski'
}


def rate_limited(retries=2, sleep=900):
    def deco_retry(f):
        def f_retry(*args, **kwargs):
            for i in range(retries):
                try:
                    if hasattr(f, "__func__"):
                        # staticmethod or classmethod
                        return f.__func__(*args, **kwargs)
                    else:
                        return f(*args, **kwargs)
                except exc.RateLimitExceeded:
                    if i > 0:
                        logger.error("Daily Rate limit exceeded - exiting program")
                        exit(1)
                    logger.warning("Rate limit exceeded in connecting - "
                                   "Retrying strava connection in %d seconds", sleep)
                    time.sleep(sleep)
        return f_retry  # true decorator
    return deco_retry


class UploadToStrava:
    def __init__(self):
        self.dry_run = DRY_RUN
        self.config = configparser.ConfigParser()
        if os.path.exists('config.ini'):
            self.config.read('config.ini')

        self.client = Client()
        with open("client_secrets.txt") as f:
            client_id_str, client_secret = f.read().strip().split(",")
            client_id = int(client_id_str)

        # Open the token JSON file that you saved earlier
        with open('tokens.json', "r") as f:
            token_response_refresh = json.load(f)

        self.client.access_token = token_response_refresh['access_token']

        refresh_response = self.client.refresh_access_token(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=token_response_refresh['refresh_token'],
        )


    def upload_gpx(self, gpxfile, strava_activity_type, notes):
        if not os.path.isfile(gpxfile):
            logger.warning("No file found for %s!", gpxfile)
            return False

        try:
            upload = self._upload(gpxfile, notes, strava_activity_type)
            up_result = self._wait_for_upload(upload)
        except exc.ActivityUploadFailed as err:
            # deal with duplicate type of error, if duplicate then continue with next file, stop otherwise
            if str(err).find('duplicate of activity'):
                # FileUtils.archive_file(gpxfile, dry_run=self.dry_run)
                logger.debug("Duplicate File %s", gpxfile)
                return True
            else:
                logger.error("Another ActivityUploadFailed error: {}".format(err))
                exit(1)
        except Exception as err:
            try:
                logger.error("Exception raised: {}. Exiting...".format(err))
            except:
                logger.error("Unexpected exception. Exiting...")
            exit(1)

        logger.info("Uploaded %s - Activity id: %s", gpxfile, str(up_result.id))
        # FileUtils.archive_file(gpxfile, dry_run=self.dry_run)
        return True

    def _upload(self, gpxfile, notes, strava_activity_type):
        prefix = DRY_RUN_PREFIX if self.dry_run else ""
        logger.info(prefix + "Uploading %s", gpxfile)
        upload = self._upload_activity(gpxfile, notes, strava_activity_type)
        logger.info(prefix + "Upload succeeded. Waiting for response...")
        return upload

    @rate_limited()
    def _upload_activity(self, gpx_file, notes, activity_type):
        if self.dry_run:
            logger.info(DRY_RUN_PREFIX + "Uploading activity from GPX file: %s, activity type: %s, notes: %s",
                        gpx_file, activity_type, notes)
            return FakeUpload()

        logging.debug("Uploading activity from GPX file: %s, name: %s",
                      gpx_file, notes)
        with open(gpx_file, "r") as f:
            upload = self.client.upload_activity(
                activity_file=f,
                data_type='gpx',
                name=notes,
                description=notes,
                activity_type=activity_type
            )
            return upload

    @rate_limited()
    def _wait_for_upload(self, upload):
        up_result = upload.wait()
        return up_result

    def _get_part_of_day(self, x):
        if (x >= 6) and (x < 11):
            return 'Morning'
        elif (x >= 11) and (x < 14 ):
            return 'Lunch'
        elif (x >= 14) and (x < 18):
            return'Afternoon'
        elif (x >= 18) and (x < 22) :
            return 'Evening'
        elif (x >= 22) or (x <= 6):
            return'Night'

    def _get_name(self, gpx):
        tree = ET.parse(gpx)
        root = tree.getroot()
        namespaces = {'': 'http://www.topografix.com/GPX/1/1'}
        old_name = root.find('.//name', namespaces).text
        if old_name != 'Radfahren im Freien':
            return old_name
        date_string = root.find('.//trkseg/trkpt/time', namespaces).text
        if date_string is None:
            return old_name

        # 2025-08-27T06:08:01Z
        date = datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%S%z").astimezone(datetime.now().tzinfo)
        return f'{self._get_part_of_day(date.hour)} Ride'

    def _upload_files_from_directory(self, directory):
        last_file = None
        if 'Data' in self.config:
            if 'LastFile' in self.config['Data']:
                last_file = self.config['Data']['LastFile']
        for filename in sorted(os.listdir(directory)):
            if filename.endswith(".gpx"):
                logging.info('Processing %s', filename)
                if last_file is not None and filename <= last_file:
                    logging.debug('Skipping %s as it is older than the last processed file', filename)
                    continue
                gpx_path = os.path.join(directory, filename)
                self.upload_gpx(gpx_path, 'ride', self._get_name(gpx_path))
                last_file = filename
        if last_file is not None:
            if 'Data' not in self.config:
                self.config['Data'] = {}
            self.config['Data']['LastFile'] = last_file
            with open('config.ini', 'w') as configfile:
                self.config.write(configfile)

    def run(self):
        if not 'Config' in self.config or not 'SyncPath' in self.config['Config']:
            logger.error("No SyncPath found in config.ini - please create the file")
            exit(1)

        self._upload_files_from_directory(os.path.join(self.config['Config']['SyncPath'], 'Gadgetbridge', 'files'))


class FakeUpload:
    def wait(self):
        class Object(object):
            pass

        obj = Object()
        obj.id = uuid.uuid4()
        return obj


class StravalibLoggingFilter(logging.Filter):
    def filter(self, record):
        # return True to accept the log record, False to reject it
        return record.levelname != 'INFO' or not record.name.startswith('stravalib.protocol')


class PyWarningsFilter(logging.Filter):
    def filter(self, record):
        # return True to accept the log record, False to reject it
        return record.getMessage().find('FutureWarning') == -1


def init_logging():
    if args.verbose:
        logLevel = logging.INFO
    elif args.veryverbose:
        logLevel = logging.DEBUG
    else:
        logLevel = logging.WARNING

    config = {
        'version': 1,
        'formatters': {
            'default': {
                'format': '%(levelname)s: %(message)s',
            },
            'file': {
                'format': '%(asctime)s %(name)s (line %(lineno)s) | %(levelname)s %(message)s',
            },
        },
        'filters': {
            'stravalib_filter': {
                '()': StravalibLoggingFilter,
            },
            'pywarnings_filter': {
                '()': PyWarningsFilter,
            }
        },

        'handlers': {
            'console_stdout': {
                'class': 'logging.StreamHandler',
                'level': logLevel,
                'formatter': 'default',
                'stream': sys.stdout,
                'filters': ['stravalib_filter', 'pywarnings_filter']
            },
            'file': {
                'class': 'logging.FileHandler',
                'level': logging.DEBUG,
                'formatter': 'file',
                'filename': '/tmp/strava-uploader.log',
                'encoding': 'utf8'
            }
        },
        'root': {
            'level': logging.NOTSET,
            'handlers': ['console_stdout', 'file']
        },
    }
    logging.config.dictConfig(config)


if __name__ == '__main__':
    argparser = argparse.ArgumentParser(description='Upload GPX files to Strava.')
    argparser.add_argument('-v', '--verbose', action='store_true', help='verbose logging')
    argparser.add_argument('-vv', '--veryverbose', action='store_true', help='very verbose logging')
    args = argparser.parse_args()

    init_logging()

    logging.info("--------------------------------------------------------")
    print("Starting Strava Uploader...")

    uploader = UploadToStrava()
    uploader.run()

    print("Finished Strava Uploader")
