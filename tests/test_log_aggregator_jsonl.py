#!/usr/bin/env python3
"""
Tests for log_aggregator JSONL output (issue #185).

Covers JSON and text log formats, unparseable line warnings,
and timestamp ordering.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from log_aggregator import LogAggregator


SAMPLE_JSON_LOGS = [
    '{"timestamp": "2024-01-15T10:30:00Z", "level": "ERROR", "service": "api", "message": "Database connection failed"}',
    '{"timestamp": "2024-01-15T10:31:00Z", "level": "INFO", "service": "api", "message": "Retry succeeded"}',
    '{"timestamp": "2024-01-15T10:29:00Z", "level": "WARN", "service": "worker", "message": "Queue depth high"}',
]

SAMPLE_TEXT_LOGS = [
    '2024-01-15 10:30:00 [api] ERROR: Database connection failed',
    '2024-01-15 10:31:00 [api] INFO: Retry succeeded',
    '2024-01-15 10:29:00 [worker] WARN: Queue depth high',
]

UNPARSEABLE_LINE = '<<<this is not a recognizable log format>>>'


class TestJSONLOutput(unittest.TestCase):

    def _write_temp_file(self, lines, suffix=".log"):
        fd, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, 'w') as f:
            for line in lines:
                f.write(line + '\n')
        return path

    def _temp_output_path(self, suffix=".jsonl"):
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        os.unlink(path)
        return path

    def _read_jsonl(self, path):
        records = []
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def test_jsonl_output_with_json_logs(self):
        agg = LogAggregator()
        path = self._write_temp_file(SAMPLE_JSON_LOGS)
        try:
            agg.process_file(path)
            out = self._temp_output_path()
            agg.export_jsonl(out)
            records = self._read_jsonl(out)
            self.assertEqual(len(records), 3)
            for r in records:
                self.assertIn('timestamp', r)
                self.assertIn('level', r)
                self.assertIn('source', r)
                self.assertIn('message', r)
                self.assertIn('metadata', r)
            os.unlink(out)
        finally:
            os.unlink(path)

    def test_jsonl_output_with_text_logs(self):
        agg = LogAggregator()
        path = self._write_temp_file(SAMPLE_TEXT_LOGS)
        try:
            agg.process_file(path)
            out = self._temp_output_path()
            agg.export_jsonl(out)
            records = self._read_jsonl(out)
            self.assertEqual(len(records), 3)
            for r in records:
                self.assertIn('timestamp', r)
                self.assertIn('level', r)
                self.assertIn('source', r)
                self.assertIn('message', r)
                self.assertIn('metadata', r)
            os.unlink(out)
        finally:
            os.unlink(path)

    def test_jsonl_sorted_by_timestamp(self):
        agg = LogAggregator()
        path = self._write_temp_file(SAMPLE_JSON_LOGS)
        try:
            agg.process_file(path)
            out = self._temp_output_path()
            agg.export_jsonl(out)
            records = self._read_jsonl(out)
            timestamps = [r['timestamp'] for r in records if r['timestamp'] is not None]
            self.assertEqual(timestamps, sorted(timestamps))
            self.assertEqual(timestamps[0], '2024-01-15T10:29:00+00:00')
            os.unlink(out)
        finally:
            os.unlink(path)

    def test_unparseable_lines_produce_warning_records(self):
        agg = LogAggregator()
        lines = SAMPLE_JSON_LOGS + [UNPARSEABLE_LINE]
        path = self._write_temp_file(lines)
        try:
            agg.process_file(path)
            out = self._temp_output_path()
            agg.export_jsonl(out)
            records = self._read_jsonl(out)
            warnings = [r for r in records if r['level'] == 'warn' and r['source'] == 'log_aggregator']
            self.assertEqual(len(warnings), 1)
            self.assertIn('raw_line', warnings[0]['metadata'])
            os.unlink(out)
        finally:
            os.unlink(path)

    def test_text_format_is_default(self):
        import argparse
        from log_aggregator import parse_args
        original_argv = sys.argv
        sys.argv = ['log_aggregator.py', '--input', 'dummy.log']
        try:
            args = parse_args()
            self.assertEqual(args.format, 'text')
        finally:
            sys.argv = original_argv

    def test_jsonl_format_choice_exists(self):
        import argparse
        from log_aggregator import parse_args
        original_argv = sys.argv
        sys.argv = ['log_aggregator.py', '--input', 'dummy.log', '--format', 'jsonl']
        try:
            args = parse_args()
            self.assertEqual(args.format, 'jsonl')
        finally:
            sys.argv = original_argv


if __name__ == '__main__':
    unittest.main()
