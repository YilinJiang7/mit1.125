"""Podcast metadata discovery with GUID identities and enclosure locations."""
from feeds_helper import collect
from lib.records import stage_main

if __name__ == '__main__':
    stage_main('fetch-podcasts', lambda run, receipt:collect(run, receipt, 'podcast'))
