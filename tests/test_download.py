#
# Copyright (c) 2023-2025 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import os.path
import pytest
import subprocess
import sys
import time
import urllib.parse
import urllib.error


from download import download


@pytest.fixture(scope="session")
def httpbun():
    yield os.environ.get('HTTPBUN', 'https://httpbun.com')


def test_static(httpbun:str) -> None:
    url = httpbun + '/cache'
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


def test_dynamic(httpbun:str) -> None:
    url = httpbun + '/range/128'
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


def test_ttl(httpbun:str) -> None:
    url = httpbun + '/range/128'
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


def test_content_type(httpbun:str) -> None:
    filename = 'test_download_content_type.bin'

    # Download
    if os.path.exists(filename):
        os.unlink(filename)
    download(httpbun + '/range/128', filename, content_type='application/octet-stream')
    assert os.path.isfile(filename)
    os.unlink(filename)

    with pytest.raises(ValueError):
        download(httpbun + '/html', filename, content_type='application/xml')
    assert not os.path.isfile(filename)


def test_content_length(httpbun:str) -> None:
    last_modfiied = 'Fri, 08 Dec 2023 20:03:24 GMT'
    url = httpbun + '/response-headers?Last-modified=' + urllib.parse.quote_plus(last_modfiied)
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


def test_404(httpbun:str) -> None:
    url = httpbun + '/status/404'
    filename = 'test_download_404.bin'

    assert not os.path.isfile(filename)
    with pytest.raises(urllib.error.HTTPError):
        download(url, filename)
    assert not os.path.isfile(filename)


def test_filename(httpbun:str) -> None:
    filename = 'test_download_filename.bin'
    url = httpbun + '/anything/' + filename

    if os.path.exists(filename):
        os.unlink(filename)
    download(url)
    assert os.path.isfile(filename)
    os.unlink(filename)


def test_main(httpbun:str) -> None:
    url = httpbun + '/range/128'
    filename = 'test_download_main.bin'

    from download import __file__ as download_path

    if os.path.exists(filename):
        os.unlink(filename)
    subprocess.check_call([sys.executable, download_path, url, filename])
    assert os.path.isfile(filename)
    os.unlink(filename)
