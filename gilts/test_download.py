#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import os.path
import posixpath
import pytest
import time


from download import download


def test_static():
    url = 'https://ajax.googleapis.com/ajax/libs/listjs/2.3.1/list.min.js'
    filename = 'test_download_static.bin'

    # Download
    if os.path.exists(filename):
        os.unlink(filename)
    download(url, filename)
    assert os.path.isfile(filename)

    # Newer
    mtime = os.path.getmtime(filename)
    download(url, filename)
    assert os.path.getmtime(filename) == mtime

    os.unlink(filename)


def test_dynamic():
    url = 'https://httpbin.org/bytes/128'
    filename = 'test_download_dynamic.bin'

    # Download
    if os.path.exists(filename):
        os.unlink(filename)
    download(url, filename)
    assert os.path.isfile(filename)

    # Newer
    mtime = os.path.getmtime(filename)
    download(url, filename)
    assert os.path.getmtime(filename) > mtime

    os.unlink(filename)


def test_ttl():
    url = 'https://httpbin.org/bytes/128'
    filename = 'test_download_ttl.bin'

    # Download
    if os.path.exists(filename):
        os.unlink(filename)
    download(url, filename, 0)
    assert os.path.isfile(filename)

    # Over TTL
    mtime = os.path.getmtime(filename)
    time.sleep(1)
    download(url, filename, ttl=1)
    assert os.path.getmtime(filename) > mtime

    # Under TTL
    mtime = os.path.getmtime(filename)
    time.sleep(1)
    download(url, filename, ttl=60)
    assert os.path.getmtime(filename) == mtime

    os.unlink(filename)


def test_content_type():
    url = 'https://httpbin.org/bytes/128'
    filename = 'test_download_content_type.bin'

    # Download
    if os.path.exists(filename):
        os.unlink(filename)
    download(url, filename, content_type='application/octet-stream')
    assert os.path.isfile(filename)
    os.unlink(filename)

    with pytest.raises(ValueError):
        download(url, filename, content_type='text/xml')
    assert not os.path.isfile(filename)
