import subprocess
import time
import sys
import os
from pathlib import Path

LOG = Path(__file__).resolve().parents[1] / 'logs' / 'run_short.log'
LOG.parent.mkdir(parents=True, exist_ok=True)

def main():
    start_time = time.time()
    timeout = int(os.getenv("SOAK_SECONDS", "600"))
    with LOG.open('a', encoding='utf-8') as f:
        f.write(f"SOAK_SHORT_STARTED: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
        f.flush()
        proc = subprocess.Popen([sys.executable, '-u', 'atlas/scripts/full_autonomous_cycle.py'], stdout=f, stderr=subprocess.STDOUT)
        try:
            while True:
                time.sleep(1)
                if proc.poll() is not None:
                    f.write(f"SOUPROC_EXITED: returncode={proc.returncode} at {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
                    break
                if time.time() - start_time >= timeout:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    try:
                        proc.wait(timeout=10)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                    f.write(f"SOAK_SHORT_COMPLETE: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
                    break
        except Exception as e:
            f.write(f"SOAK_SHORT_ERROR: {e!r}\n")
            try:
                proc.kill()
            except Exception:
                pass
            raise

if __name__ == '__main__':
    main()
