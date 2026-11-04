from contextlib import redirect_stdout
from io import StringIO
from subprocess import CompletedProcess
from unittest import TestCase
from unittest.mock import Mock

from push_tracker_changes import push_with_retry


class PushRetryTests(TestCase):
    def invoke(self, outputs):
        run = Mock(side_effect=[CompletedProcess(['git', 'push'], code, stdout='', stderr=output)
                                for code, output in outputs])
        sleep = Mock()
        with redirect_stdout(StringIO()):
            code = push_with_retry(run=run, sleep=sleep)
        return code, run, sleep

    def test_success_no_retry(self):
        code, run, sleep = self.invoke([(0, 'Everything up-to-date')])
        self.assertEqual(code, 0)
        self.assertEqual(run.call_count, 1)
        sleep.assert_not_called()

    def test_reported_github_error_retries_same_push(self):
        code, run, sleep = self.invoke([
            (1, 'warning: file is 55.39 MB\nremote: Internal Server Error\nremote rejected'),
            (0, 'Everything up-to-date')])
        self.assertEqual(code, 0)
        self.assertEqual(run.call_args_list[0], run.call_args_list[1])
        sleep.assert_called_once_with(5)

    def test_retry_bound_exposes_failure(self):
        code, run, sleep = self.invoke([(1, 'The requested URL returned error: 503')] * 5)
        self.assertEqual(code, 1)
        self.assertEqual(run.call_count, 5)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [5, 10, 20, 30])

    def test_permanent_errors_do_not_retry(self):
        for output in ['non-fast-forward', 'fetch first', 'Authentication failed',
                       'Permission denied', 'File exceeds maximum size of 100.00 MB',
                       'GH013: Repository rule violation\nInternal Server Error']:
            code, run, sleep = self.invoke([(1, output)])
            self.assertEqual(code, 1)
            self.assertEqual(run.call_count, 1)
            sleep.assert_not_called()
