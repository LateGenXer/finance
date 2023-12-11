#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import os.path
import posixpath
import pytest
import subprocess
import sys
import time
import urllib.parse
import urllib.error


from download import download


def test_static():
    url = 'https://httpbin.org/cache'
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
    filename = 'test_download_content_type.bin'

    # Download
    if os.path.exists(filename):
        os.unlink(filename)
    download('https://httpbin.org/xml', filename, content_type='application/xml')
    assert os.path.isfile(filename)
    os.unlink(filename)

    with pytest.raises(ValueError):
        download('https://httpbin.org/html', filename, content_type='application/xml')
    assert not os.path.isfile(filename)


def test_content_length():
    last_modfiied = 'Fri, 08 Dec 2023 20:03:24 GMT'
    url = 'https://httpbin.org/response-headers?Last-modified=' + urllib.parse.quote_plus(last_modfiied)
    filename = 'test_download_content_length.bin'

    if os.path.exists(filename):
        os.unlink(filename)
    download(url, filename)
    assert os.path.isfile(filename)
    mtime = os.path.getmtime(filename)

    download(url, filename)
    assert os.path.isfile(filename)
    assert os.path.getmtime(filename) == mtime
    os.unlink(filename)


def test_404():
    url = 'https://httpbin.org/status/404'
    filename = 'test_download_404.bin'

    assert not os.path.isfile(filename)
    with pytest.raises(urllib.error.HTTPError):
        download(url, filename)
    assert not os.path.isfile(filename)


def test_filename():
    filename = 'test_download_filename.bin'
    url = f'https://httpbin.org/anything/{filename}'

    if os.path.exists(filename):
        os.unlink(filename)
    download(url)
    assert os.path.isfile(filename)
    os.unlink(filename)


def test_main():
    url = 'https://httpbin.org/bytes/128'
    filename = 'test_download_main.bin'

    from download import __file__ as download_path

    if os.path.exists(filename):
        os.unlink(filename)
    status = subprocess.call([sys.executable, download_path, url, filename])
    assert status == 0
    assert os.path.isfile(filename)
    os.unlink(filename)
