#!/usr/bin/env python3
import configparser
from datetime import datetime
import json
import logging
import os
import re
import time
import uuid
import xml.etree.ElementTree as ET

from stravalib.client import Client, exc
from stravalib.util.limiter import RateLimiter


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
                        logging.error("Daily Rate limit exceeded - exiting program")
                        exit(1)
                    logging.warning("Rate limit exceeded in connecting - "
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


    def upload_gpx(self, gpxfile, strava_activity_type, name, description):
        filename = os.path.basename(gpxfile)
        if not os.path.isfile(gpxfile):
            logging.warning("No file found for %s!", gpxfile)
            return False

        try:
            upload = self._upload(gpxfile, name, strava_activity_type, description)
            up_result = self._wait_for_upload(upload)
        except exc.ActivityUploadFailed as err:
            # deal with duplicate type of error, if duplicate then continue with next file, stop otherwise
            if str(err).find('duplicate of activity'):
                substrings = re.findall(r"href='(.*?)'", str(err))
                logging.warning("Duplicate File %s; duplicate activity: https://www.strava.com%s", filename, substrings[0])
                return True
            else:
                logging.error(f"Another ActivityUploadFailed error: {err}")
                exit(1)
        except Exception as err:
            try:
                logging.error(f"Exception raised: {err}. Exiting...")
            except:
                logging.error("Unexpected exception. Exiting...")
            exit(1)

        logging.info(f"Uploaded {filename} - Activity id: {up_result.id}")
        return True

    def _upload(self, gpxfile, strava_activity_type, name, description):
        prefix = DRY_RUN_PREFIX if self.dry_run else ""
        logging.debug(f"{prefix}Uploading {os.path.basename(gpxfile)}")
        upload = self._upload_activity(gpxfile, name, strava_activity_type, description)
        logging.debug(f"{prefix}Upload succeeded. Waiting for response...")
        return upload

    @rate_limited()
    def _upload_activity(self, gpx_file, activity_type, name, description):
        if self.dry_run:
            logging.debug(
                f"{DRY_RUN_PREFIX}Uploading activity from GPX file: {os.path.basename(gpx_file)}, activity type: {activity_type}, notes: {name}"
            )
            return FakeUpload()

        logging.debug(f"Uploading activity from GPX file: {os.path.basename(gpx_file)}, name: {name}")
        with open(gpx_file, "r") as f:
            return self.client.upload_activity(
                activity_file=f,
                data_type='gpx',
                name=name,
                description=description,
                activity_type=activity_type,
            )

    @rate_limited()
    def _wait_for_upload(self, upload):
        return upload.wait()

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

    def _get_activity_type(self, name):
        if name == 'Andere Wintersportarten':
            return 'NordicSki'
        elif name == 'Drinnen Radfahren':
            return 'VirtualRide'
        elif name == 'Gehen':
            return 'Walk'
        elif name == 'Kajakfahren':
            return 'Kayaking'
        elif name == 'Kitesurfen':
            return 'Kitesurf'
        elif name == 'Laufband':
            return 'VirtualRun'
        elif name in ['Laufen im Freien', 'Trail-Lauf']:
            return 'Run'
        elif name in ['Offenes Gewässer', 'Freistil', 'Beckenschwimmen']:
            return 'Swim'
        elif name == 'Paddelboarden':
            return 'StandUpPaddling'
        elif name == 'Radfahren im Freien':
            return 'Ride'
        elif name == 'Ruderer':
            return 'Rowing'
        elif name == 'Segeln':
            return 'Sail'
        elif name in ['Wandern', 'Trekking']:
            return 'Hike'
        elif name == 'Yoga':
            return 'Yoga'
        return 'Workout'

    def _get_name_and_activity(self, gpx):
        tree = ET.parse(gpx)
        root = tree.getroot()
        namespaces = {'': 'http://www.topografix.com/GPX/1/1'}
        name = root.find('.//name', namespaces).text
        activity = self._get_activity_type(name)

        date_string = root.find('.//trkseg/trkpt/time', namespaces).text
        if date_string is None:
            return name, activity, name

        # 2025-08-27T06:08:01Z
        date = datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%S%z").astimezone(datetime.now().tzinfo)
        return f'{self._get_part_of_day(date.hour)} {activity}', activity, name

    def _upload_files_from_directory(self, directory):
        last_file = None
        if 'Data' in self.config and 'LastFile' in self.config['Data']:
            last_file = self.config['Data']['LastFile']
        for filename in sorted(os.listdir(directory)):
            if filename.endswith(".gpx"):
                if last_file is not None and filename <= last_file:
                    logging.debug('Processing %s - skipped as it is older than the last processed file', filename)
                    continue
                logging.info('Processing %s', filename)
                gpx_path = os.path.join(directory, filename)
                name, activity, original_name = self._get_name_and_activity(gpx_path)
                self.upload_gpx(gpx_path, activity, name, original_name)
                last_file = filename
        if last_file is not None:
            if 'Data' not in self.config:
                self.config['Data'] = {}
            self.config['Data']['LastFile'] = last_file
            with open('config.ini', 'w') as configfile:
                self.config.write(configfile)

    def run(self):
        if 'Config' not in self.config or 'workpath' not in self.config['Config']:
            logging.error("No workpath found in config.ini - please create the file")
            exit(1)

        self._upload_files_from_directory(os.path.join(self.config['Config']['workpath'], 'Gadgetbridge', 'files'))


class FakeUpload:
    def wait(self):
        class Object(object):
            pass

        obj = Object()
        obj.id = uuid.uuid4()
        return obj
