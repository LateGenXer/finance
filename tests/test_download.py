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
import urllib.request

from filelock import FileLock

from download import download


def _start_httpbun(host: str, port: int):
    container_id = subprocess.check_output(['docker', 'run', '--rm', '--detach', '--publish', f'{host}:{port}:80', 'ghcr.io/sharat87/httpbun'])
    try:
        # Poll with an actual HTTP request: Docker's port-forwarding proxy accepts
        # TCP connections before the container's server is ready, so a socket-level
        # check gives a false positive.
        deadline = time.monotonic() + 30
        url = f'http://{host}:{port}/status/200'
        while True:
            try:
                r = urllib.request.urlopen(url, timeout=0.1)
            except urllib.error.URLError as e:
                if not isinstance(e.reason, (ConnectionRefusedError, ConnectionResetError)):
                    raise
            except (ConnectionRefusedError, ConnectionResetError):
                pass
            else:
                assert r.status == 200
                break
            if time.monotonic() >= deadline:
                raise TimeoutError
            time.sleep(0.010)
        yield f'http://{host}:{port}'
    finally:
        subprocess.check_call(['docker', 'stop', container_id.decode('ascii').strip()])
    return


@pytest.fixture(scope="session")
def httpbun(tmp_path_factory, worker_id):
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
    port = 8080

    # https://pytest-xdist.readthedocs.io/en/stable/how-to.html#making-session-scoped-fixtures-execute-only-once

    if worker_id == 'master':
        yield from _start_httpbun(host, port)
        return

    root_tmp_dir = tmp_path_factory.getbasetemp().parent

    with FileLock(str(root_tmp_dir / 'httpbun.lock')):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        already_running = sock.connect_ex((host, port)) == 0
        sock.close()
        if already_running:
            yield f'http://{host}:{port}'
            return
        else:
            yield from _start_httpbun(host, port)


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
