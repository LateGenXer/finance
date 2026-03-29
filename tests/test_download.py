#
# Copyright (c) 2023-2025 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import os
import pytest
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.error


from download import download


@pytest.fixture(scope="session")
def httpbun(worker_id):
    try:
        yield os.environ['HTTPBUN']
    except KeyError:
        pass
    else:
        return

    if sys.platform != 'linux' or os.path.exists('/.dockerenv'):
        yield 'https://httpbun.com'
        return

    host = '127.0.0.1'

    port = 8000 + (hash(worker_id) % 100)

    container_id = subprocess.check_output(['docker', 'run', '--rm', '--detach', '--publish', f'{host}:{port}:80', 'ghcr.io/sharat87/httpbun'])

    try:
        # https://stackoverflow.com/a/19196218
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tries = 3000  # 30 secs
        result = sock.connect_ex((host, port))
        while result != 0 and tries > 0:
            tries -= 1
            time.sleep(0.010)
            result = sock.connect_ex((host, port))
        sock.close()
        if result != 0:
            raise TimeoutError

        yield f'http://{host}:{port}'
    finally:
        subprocess.check_call(['docker', 'stop', container_id.strip()])


def test_static(httpbun:str, tmp_path) -> None:
    url = httpbun + '/cache'
    filename = tmp_path / 'test_download_static.bin'

    # Download
    download(url, filename)
    assert filename.is_file()

    # Newer
    mtime = filename.stat().st_mtime
    download(url, filename)
    assert filename.stat().st_mtime == mtime


def test_dynamic(httpbun:str, tmp_path) -> None:
    url = httpbun + '/range/128'
    filename = tmp_path / 'test_download_dynamic.bin'

    # Download
    download(url, filename)
    assert filename.is_file()

    # Newer
    mtime = filename.stat().st_mtime
    download(url, filename)
    assert filename.stat().st_mtime > mtime


def test_ttl(httpbun:str, tmp_path) -> None:
    url = httpbun + '/range/128'
    filename = tmp_path / 'test_download_ttl.bin'

    # Download
    download(url, filename, 0)
    assert filename.is_file()

    # Over TTL
    mtime = filename.stat().st_mtime
    time.sleep(1)
    download(url, filename, ttl=1)
    assert filename.stat().st_mtime > mtime

    # Under TTL
    mtime = filename.stat().st_mtime
    time.sleep(1)
    download(url, filename, ttl=60)
    assert filename.stat().st_mtime == mtime


def test_content_type(httpbun:str, tmp_path) -> None:
    filename = tmp_path / 'test_download_content_type.bin'

    # Download
    download(httpbun + '/range/128', filename, content_type='application/octet-stream')
    assert filename.is_file()

    with pytest.raises(ValueError):
        download(httpbun + '/html', filename, content_type='application/xml')


def test_content_length(httpbun:str, tmp_path) -> None:
    last_modfiied = 'Fri, 08 Dec 2023 20:03:24 GMT'
    url = httpbun + '/response-headers?Last-modified=' + urllib.parse.quote_plus(last_modfiied)
    filename = tmp_path / 'test_download_content_length.bin'

    download(url, filename)
    assert filename.is_file()
    mtime = filename.stat().st_mtime

    download(url, filename)
    assert filename.is_file()
    assert filename.stat().st_mtime == mtime


def test_404(httpbun:str, tmp_path) -> None:
    url = httpbun + '/status/404'
    filename = tmp_path / 'test_download_404.bin'

    with pytest.raises(urllib.error.HTTPError):
        download(url, filename)
    assert not filename.exists()


def test_filename(httpbun:str, tmp_path, monkeypatch) -> None:
    filename = 'test_download_filename.bin'
    url = httpbun + '/anything/' + filename

    monkeypatch.chdir(tmp_path)
    download(url)
    assert (tmp_path / filename).is_file()


def test_main(httpbun:str, tmp_path) -> None:
    url = httpbun + '/range/128'
    filename = tmp_path / 'test_download_main.bin'

    from download import __file__ as download_path

    subprocess.check_call([sys.executable, download_path, url, filename])
    assert filename.is_file()
