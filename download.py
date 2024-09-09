#!/usr/bin/env python3
#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import logging
import os.path
import posixpath
import shutil
import sys
import time
import threading
import urllib.error
import urllib.request
import email.message
import email.utils
import http


__all__ = [
    'download',
]


logger = logging.getLogger('download')


def download(url:str, filename:str|None=None, ttl:int=0, content_type:str|None=None, verbose:bool=False):
    if filename is None:
        filename = posixpath.basename(url)

    headers = {
        'User-Agent': 'Mozilla/5.0',
    }
    if content_type is not None:
        headers['Accept'] = content_type

    dst_exists = os.path.exists(filename)
    if dst_exists:
        dst_size = os.path.getsize(filename)
        dst_mtime = os.path.getmtime(filename)
        if dst_mtime + ttl >= time.time():
            return
        headers['If-Modified-Since'] = time.strftime('%a, %d %b %Y %H:%M:%S %Z', time.gmtime(dst_mtime))

    request = urllib.request.Request(url, headers=headers)

    try:
        src = urllib.request.urlopen(request)
    except urllib.error.HTTPError as ex:
        if ex.code == http.HTTPStatus.NOT_MODIFIED:
            return
        else:
            raise
    assert src.code != http.HTTPStatus.NOT_MODIFIED

    if verbose:
        print(src.headers)

    if content_type is not None:
        # https://stackoverflow.com/a/75727619
        msg = src.headers
        assert isinstance(msg, email.message.Message)
        params = msg.get_params()
        if params is None:
            src_content_type = None
        else:
            src_content_type = params[0][0]
        if src_content_type != content_type:
            logger.warning(f'{url}: unexpected content-type {src_content_type}')
            raise ValueError(f'Expected {content_type}, got {src_content_type}')

    src_mtime = src.headers.get('Last-Modified')
    if src_mtime is None:
        src_mtime = time.time()
    else:
        src_mtime = email.utils.parsedate_tz(src_mtime)
        src_mtime = email.utils.mktime_tz(src_mtime)

    if dst_exists:
        src_size = src.headers.get('Content-Length')
        if src_size is not None:
            src_size = int(src_size)
            if src_size == dst_size and src_mtime == dst_mtime:
                src.close()
                return

    logger.info(f'Downloading {url} to {os.path.relpath(filename)}')
    head, tail = os.path.split(filename)
    tid = threading.get_native_id()
    tmp_filename = os.path.join(head, f'.{tail}.{tid}')
    dst = open(tmp_filename, 'wb')
    shutil.copyfileobj(src, dst)
    dst.close()
    os.utime(tmp_filename, (src_mtime, src_mtime))
    src.close()
    os.replace(tmp_filename, filename)


if __name__ == '__main__':
    _, url, filename = sys.argv[:3]
    content_type = None
    if len(sys.argv) > 3:
        content_type = sys.argv[3]
    download(url, filename, content_type=content_type, verbose=True)
