import threading
import time
import requests
import os
import socket

from main import ServerManager


def run_test():
    folder = os.path.abspath("test_upload")
    if not os.path.isdir(folder):
        os.makedirs(folder)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.connect(("8.8.8.8", 80))
    ip = sock.getsockname()[0]
    sock.close()
    port = 8001

    mgr = ServerManager(folder, port, print)
    mgr.start()
    url = f"http://{ip}:{port}"
    print("server url", url)

    time.sleep(1)
    r = requests.get(url)
    print("GET / status", r.status_code)

    files = {'file': ('foo.txt', b'hello world')}
    r = requests.post(url, files=files)
    print("upload status", r.status_code, r.headers.get('Location'))

    print("saved files", os.listdir(folder))

    r2 = requests.get(url + "/files/foo.txt")
    print("download status", r2.status_code, r2.content)

    mgr.stop()

if __name__ == '__main__':
    run_test()
