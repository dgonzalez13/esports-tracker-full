"""Retry the same commit on temporary GitHub push failures; never force push."""
import re
import subprocess
import time


TRANSIENT = re.compile(
    r'internal server error|http (?:error )?(?:408|429|500|502|503|504)\b|'
    r'requested url returned error: (?:408|429|500|502|503|504)\b|'
    r'connection (?:reset|timed out)|operation timed out|'
    r'remote end hung up unexpectedly|temporary failure in name resolution',
    re.IGNORECASE,
)


def push_with_retry(run=None, sleep=None):
    run = run or subprocess.run
    sleep = sleep or time.sleep
    delays = (5, 10, 20, 30)
    for attempt in range(5):
        result = run(['git', 'push'], capture_output=True, text=True)
        output = (result.stdout or '') + (result.stderr or '')
        print(output, end='' if output.endswith('\n') else '\n', flush=True)
        if result.returncode == 0:
            return 0
        # A different branch tip or permissions error needs attention, not retries.
        if (attempt == 4 or not TRANSIENT.search(output)
                or re.search(r'non-fast-forward|fetch first|permission denied|authentication failed|GH006|GH013',
                             output, re.IGNORECASE)):
            print('Push failed; generated changes remain in the local checkout.', flush=True)
            return result.returncode
        print(f'Temporary push failure. Retrying in {delays[attempt]} seconds '
              f'(attempt {attempt+2}/5).', flush=True)
        sleep(delays[attempt])


if __name__ == '__main__':
    raise SystemExit(push_with_retry())
