#!/usr/bin/env python

'''
Integrates Mac OS X's screenshot utility with DreamObjects for easy sharing.
'''

from contextlib import closing
import boto
import boto.s3.connection
import datetime
import json
import os
import random
import requests
import subprocess
import tempfile
import webbrowser


#### CONFIGURATION ####

# DreamObject config
dhdo_access_key = ''
dhdo_secret_key = ''
dhdo_screenshots_bucket = ''

# Automatically open the screenshot in the default browser
auto_open = True

# Copy the url to the system clipboard
copy_to_clipboard = True

# If true, URL will be random characters--otherwise it will be a datetime string
obfuscate_url = True

# Print a tiny URL using Google URL Shortener
shorten_url = False
api_key = ''                                                 # Required if shorten_url == True
goog_url = 'https://www.googleapis.com/urlshortener/v1/url'  # You probably don't need to change this


# Housekeeping
# Remove images older than the max_age or if there are more than the max_pics
trim_old_images = True
max_age = 14    # days
max_pics = 200  # number of images to keep




def dho_connect():
    '''
    Helper fuction--returns a boto S3 connection object
    '''
    return boto.connect_s3(
        aws_access_key_id=dhdo_access_key,
        aws_secret_access_key=dhdo_secret_key,
        host='objects.dreamhost.com'
    )


def shorten(long_url):
    '''
    Given a url, returns the shortened version
    '''
    url = goog_url + '?key=' + api_key

    message = json.dumps({ 'longUrl' : long_url })
    headers = { 'Content-Type' : 'application/json' }

    try:
        r = requests.post(url, data=message, headers=headers)
        contents = json.loads(r.text)
        short_url = contents['id']
    except:
        short_url = None
    return short_url


def trim_old_files(bucket, max_age, num_files):
    '''
    Deletes keys in a bucket if:
        They are older than the max_age
    Or if:
        There are more than num_files keys
        (The oldest are deleted first)
    '''
    bucket = dho_connect().get_bucket(bucket)
    keys = sorted( [ k for k in bucket.list() ], key=lambda x: x.last_modified )

    deleted = []

    for k in keys[0:-num_files]:
        deleted.append(k.name)
        k.delete()

    for k in keys[-num_files:]:
        key_age = datetime.date(
            int(k.last_modified[0:4]),
            int(k.last_modified[5:7]),
            int(k.last_modified[8:10])
        )
        if (datetime.date.today() - key_age).days > max_age:
            deleted.append(k.name)
            k.delete()

    return deleted



if __name__ == '__main__':

    with closing(tempfile.NamedTemporaryFile(mode='rb', suffix='.png')) as f:

        result = subprocess.call(['screencapture', '-i', f.name])

        print 'Screenshot captured! Copying to DreamObjects...'

        if os.path.exists(f.name):

            bucket = dho_connect().get_bucket(dhdo_screenshots_bucket)

            if obfuscate_url:
                chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
                name = ''.join(random.choice(chars) for c in range(8))
            else:
                name = datetime.datetime.strftime(datetime.datetime.now(), '%m-%d-%Y-%H-%M-%S')

            key = bucket.new_key(name + '.png')
            key.set_contents_from_filename(f.name)
            key.set_canned_acl('public-read')

            public_url = key.generate_url(0, query_auth=False, force_http=True)

            if shorten_url:
                public_url = shorten(public_url)

            print 'Screenshot available at:'
            print 'URL:    {url}'.format(url=public_url)

            if copy_to_clipboard:
                os.system('echo "%s" | pbcopy' % public_url)

            if auto_open:
                webbrowser.open(public_url)

            if trim_old_images:
                deleted = trim_old_files(dhdo_screenshots_bucket, max_age, max_pics)
                print "Deleted {count} old images".format(
                        count=str(len(deleted))
                        )
