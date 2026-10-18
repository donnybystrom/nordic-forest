"""Start/reuse the local bridge without changing login items or global settings."""
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = 'http://127.0.0.1:8765'


def healthy():
    try:
        with urllib.request.urlopen(URL + '/health', timeout=1) as response:
            return json.load(response).get('service') == 'nordic-forest-bridge'
    except OSError:
        return False


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {'start', 'status', 'stop', 'restart'}:
        raise SystemExit('Usage: manage_bridge.py start|status|stop|restart')
    if sys.argv[1] in {'stop', 'restart'} and healthy():
        config = json.loads((ROOT / 'runs/control/client.json').read_text())
        request = urllib.request.Request(URL + '/control/stop', data=b'{}', headers={'Authorization': 'Bearer ' + config['token'], 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=3):
                pass
        except OSError:
            raise SystemExit('Stop rejected; finish or cancel active jobs first')
        for _ in range(30):
            if not healthy():
                break
            time.sleep(.2)
        if healthy():
            raise SystemExit('Stop not acknowledged; no replacement started')
    if sys.argv[1] == 'stop':
        print('Bridge stopped')
        return
    if healthy():
        print('Bridge running: ' + URL)
        return
    if sys.argv[1] == 'status':
        raise SystemExit('Bridge stopped')
    dest = ROOT / 'runs/control'
    dest.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (dest / 'service.log').open('ab') as log:
        proc = subprocess.Popen([sys.executable, '-u', '-m', 'forest_agents.bridge_server'], cwd=ROOT,
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(30):
        if healthy():
            print('Bridge started: ' + URL)
            return
        if proc.poll() is not None:
            raise SystemExit('Bridge startup failed; inspect runs/control/service.log')
        time.sleep(.2)
    raise SystemExit('Bridge startup timeout; inspect service.log before retrying')


if __name__ == '__main__':
    main()
