#!/usr/bin/env python3
"""
Tests for deterministic seed support in data_generator (issue #4).

Verifies that the same seed produces byte-for-byte identical output
across multiple runs and seeds.
"""

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from data_generator import DataGenerator


class TestDeterministicSeed(unittest.TestCase):

    def _generate_to_json(self, seed, tmpdir):
        gen = DataGenerator(seed)
        users = gen.generate_users(10)
        orders = gen.generate_orders(20)
        trades = gen.generate_trades(30)
        return json.dumps({
            "users": users,
            "orders": orders,
            "trades": trades,
        }, sort_keys=True, default=str).encode("utf-8")

    def test_same_seed_produces_identical_output(self):
        dir1 = tempfile.mkdtemp()
        dir2 = tempfile.mkdtemp()
        try:
            output1 = self._generate_to_json(42, dir1)
            output2 = self._generate_to_json(42, dir2)
            self.assertEqual(output1, output2, "Same seed should produce identical output")
        finally:
            import shutil
            shutil.rmtree(dir1, ignore_errors=True)
            shutil.rmtree(dir2, ignore_errors=True)

    def test_different_seeds_produce_different_output(self):
        dir1 = tempfile.mkdtemp()
        dir2 = tempfile.mkdtemp()
        try:
            output1 = self._generate_to_json(42, dir1)
            output2 = self._generate_to_json(99, dir2)
            self.assertNotEqual(output1, output2, "Different seeds should produce different output")
        finally:
            import shutil
            shutil.rmtree(dir1, ignore_errors=True)
            shutil.rmtree(dir2, ignore_errors=True)

    def test_deterministic_across_three_seeds(self):
        seeds = [42, 123, 999]
        for seed in seeds:
            dir_a = tempfile.mkdtemp()
            dir_b = tempfile.mkdtemp()
            try:
                output_a = self._generate_to_json(seed, dir_a)
                output_b = self._generate_to_json(seed, dir_b)
                hash_a = hashlib.sha256(output_a).hexdigest()
                hash_b = hashlib.sha256(output_b).hexdigest()
                self.assertEqual(hash_a, hash_b, f"Seed {seed} should produce identical hashes across runs")
            finally:
                import shutil
                shutil.rmtree(dir_a, ignore_errors=True)
                shutil.rmtree(dir_b, ignore_errors=True)

    def test_print_seed_flag_exists(self):
        import argparse
        from data_generator import parse_args
        original_argv = sys.argv
        sys.argv = ['data_generator.py', '--print-seed', '--seed', '42']
        try:
            args = parse_args()
            self.assertTrue(args.print_seed)
            self.assertEqual(args.seed, 42)
        finally:
            sys.argv = original_argv

    def test_seed_none_generates_random_seed(self):
        import argparse
        from data_generator import parse_args
        original_argv = sys.argv
        # Test default behavior -- no --seed flag means seed is None
        sys.argv = ['data_generator.py']
        try:
            args = parse_args()
            self.assertIsNone(args.seed)
        finally:
            sys.argv = original_argv


if __name__ == '__main__':
    unittest.main()
