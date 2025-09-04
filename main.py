#!/usr/bin/env python3

import argparse
import logging
import logging.config
import os
import sys

from uploader import UploadToStrava


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
        logLevel = logging.DEBUG
    elif args.quiet:
        logLevel = logging.WARNING
    else:
        logLevel = logging.INFO

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
    argparser.add_argument('-q', '--quiet', action='store_true', help='quiet logging - only show warnings and errors')
    args = argparser.parse_args()

    init_logging()

    os.environ['SILENCE_TOKEN_WARNINGS'] = '1'

    logging.info("--------------------------------------------------------")
    print("Starting Strava Uploader...")

    uploader = UploadToStrava()
    uploader.run()

    print("Finished Strava Uploader")
