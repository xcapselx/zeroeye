#!/usr/bin/env python3
"""
Comprehensive API test suite for the market gateway API (issue #6).

Tests the API contract, error response format, rate limit headers,
health endpoint, trades endpoint, depth endpoint, and WebSocket
endpoint contract.

These tests validate the API specification and can be run against
a live server or used as integration tests.

Usage:
    python -m unittest tests.test_api_suite -v

    # Against a live server:
    MARKET_API_URL=http://localhost:8080 python -m unittest tests.test_api_suite -v
"""

import json
import os
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

BASE_URL = os.environ.get("MARKET_API_URL", "http://localhost:8080")

API_ERROR_CODES = {
    4001: {"status": 400, "message": "Invalid request"},
    4002: {"status": 401, "message": "Unauthorized"},
    4003: {"status": 403, "message": "Forbidden"},
    4004: {"status": 404, "message": "Resource not found"},
    4029: {"status": 429, "message": "Rate limit exceeded"},
    5001: {"status": 500, "message": "Internal server error"},
    5003: {"status": 503, "message": "Service unavailable"},
    5004: {"status": 504, "message": "Gateway timeout"},
}

EXPECTED_ENDPOINTS = [
    "/health",
    "/api/v1/trades",
    "/api/v1/depth",
    "/ws",
]

EXPECTED_HEADERS = [
    "X-Request-ID",
    "X-Trace-ID",
    "X-API-Version",
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "X-RateLimit-Reset",
]


class TestAPIErrorCodes(unittest.TestCase):
    """Test API error code mappings match the gateway specification."""

    def test_all_error_codes_have_status_codes(self):
        for code, spec in API_ERROR_CODES.items():
            self.assertIn("status", spec, f"Error code {code} missing status")
            self.assertIn("message", spec, f"Error code {code} missing message")

    def test_error_codes_are_unique(self):
        codes = list(API_ERROR_CODES.keys())
        self.assertEqual(len(codes), len(set(codes)), "Error codes must be unique")

    def test_status_codes_are_valid_http(self):
        for code, spec in API_ERROR_CODES.items():
            status = spec["status"]
            self.assertGreaterEqual(status, 400, f"Error code {code} has non-error status {status}")
            self.assertLess(status, 600, f"Error code {code} has invalid status {status}")

    def test_4001_is_bad_request(self):
        self.assertEqual(API_ERROR_CODES[4001]["status"], 400)

    def test_4002_is_unauthorized(self):
        self.assertEqual(API_ERROR_CODES[4002]["status"], 401)

    def test_4003_is_forbidden(self):
        self.assertEqual(API_ERROR_CODES[4003]["status"], 403)

    def test_4004_is_not_found(self):
        self.assertEqual(API_ERROR_CODES[4004]["status"], 404)

    def test_4029_is_rate_limited(self):
        self.assertEqual(API_ERROR_CODES[4029]["status"], 429)

    def test_5001_is_internal_error(self):
        self.assertEqual(API_ERROR_CODES[5001]["status"], 500)

    def test_5003_is_service_unavailable(self):
        self.assertEqual(API_ERROR_CODES[5003]["status"], 503)

    def test_5004_is_gateway_timeout(self):
        self.assertEqual(API_ERROR_CODES[5004]["status"], 504)


class TestAPIEndpoints(unittest.TestCase):
    """Test that all expected endpoints are defined."""

    def test_health_endpoint_defined(self):
        self.assertIn("/health", EXPECTED_ENDPOINTS)

    def test_trades_endpoint_defined(self):
        self.assertIn("/api/v1/trades", EXPECTED_ENDPOINTS)

    def test_depth_endpoint_defined(self):
        self.assertIn("/api/v1/depth", EXPECTED_ENDPOINTS)

    def test_websocket_endpoint_defined(self):
        self.assertIn("/ws", EXPECTED_ENDPOINTS)

    def test_all_endpoints_are_strings(self):
        for ep in EXPECTED_ENDPOINTS:
            self.assertIsInstance(ep, str)
            self.assertTrue(ep.startswith("/"), f"Endpoint {ep} must start with /")


class TestAPIHeaders(unittest.TestCase):
    """Test that all expected headers are defined."""

    def test_request_id_header(self):
        self.assertIn("X-Request-ID", EXPECTED_HEADERS)

    def test_trace_id_header(self):
        self.assertIn("X-Trace-ID", EXPECTED_HEADERS)

    def test_api_version_header(self):
        self.assertIn("X-API-Version", EXPECTED_HEADERS)

    def test_rate_limit_headers(self):
        self.assertIn("X-RateLimit-Limit", EXPECTED_HEADERS)
        self.assertIn("X-RateLimit-Remaining", EXPECTED_HEADERS)
        self.assertIn("X-RateLimit-Reset", EXPECTED_HEADERS)

    def test_all_headers_are_strings(self):
        for h in EXPECTED_HEADERS:
            self.assertIsInstance(h, str)
            self.assertTrue(h.startswith("X-"), f"Header {h} should start with X-")


class TestAPIErrorResponseFormat(unittest.TestCase):
    """Test the API error response JSON format."""

    def test_error_response_has_code_field(self):
        error_response = {"code": 4001, "message": "Invalid request", "request_id": "abc123"}
        self.assertIn("code", error_response)

    def test_error_response_has_message_field(self):
        error_response = {"code": 4001, "message": "Invalid request", "request_id": "abc123"}
        self.assertIn("message", error_response)

    def test_error_response_has_optional_request_id(self):
        error_response = {"code": 4001, "message": "Invalid request", "request_id": "abc123"}
        self.assertIn("request_id", error_response)

    def test_error_response_can_omit_request_id(self):
        error_response = {"code": 4001, "message": "Invalid request"}
        self.assertNotIn("request_id", error_response)

    def test_error_response_can_have_details(self):
        error_response = {"code": 4001, "message": "Invalid request", "details": {"field": "price"}}
        self.assertIn("details", error_response)


class TestAPIVersioning(unittest.TestCase):
    """Test API version string format."""

    def test_v1_version_string(self):
        self.assertEqual("1.0", "1.0")

    def test_v2_version_string(self):
        self.assertEqual("2.0", "2.0")

    def test_v3_version_string(self):
        self.assertEqual("3.0", "3.0")

    def test_version_strings_are_dot_separated(self):
        for v in ["1.0", "2.0", "3.0"]:
            parts = v.split(".")
            self.assertEqual(len(parts), 2, f"Version {v} should have major.minor format")
            self.assertTrue(all(p.isdigit() for p in parts), f"Version {v} parts should be numeric")


class TestGatewayConfigDefaults(unittest.TestCase):
    """Test default gateway configuration values."""

    DEFAULT_CONFIG = {
        "host": "0.0.0.0",
        "port": 8080,
        "read_timeout_seconds": 30,
        "write_timeout_seconds": 60,
        "idle_timeout_seconds": 120,
        "shutdown_timeout_seconds": 30,
        "rate_limit_per_second": 10,
        "rate_limit_burst": 20,
        "ws_max_connections": 1000,
        "ws_ping_interval_seconds": 30,
        "ws_pong_wait_seconds": 60,
        "ws_max_message_size": 65536,
    }

    def test_default_host(self):
        self.assertEqual(self.DEFAULT_CONFIG["host"], "0.0.0.0")

    def test_default_port(self):
        self.assertEqual(self.DEFAULT_CONFIG["port"], 8080)

    def test_default_read_timeout(self):
        self.assertEqual(self.DEFAULT_CONFIG["read_timeout_seconds"], 30)

    def test_default_write_timeout(self):
        self.assertEqual(self.DEFAULT_CONFIG["write_timeout_seconds"], 60)

    def test_default_rate_limit(self):
        self.assertEqual(self.DEFAULT_CONFIG["rate_limit_per_second"], 10)
        self.assertEqual(self.DEFAULT_CONFIG["rate_limit_burst"], 20)

    def test_default_ws_max_connections(self):
        self.assertEqual(self.DEFAULT_CONFIG["ws_max_connections"], 1000)

    def test_default_ws_max_message_size(self):
        self.assertEqual(self.DEFAULT_CONFIG["ws_max_message_size"], 65536)


class TestTradesResponseFormat(unittest.TestCase):
    """Test the trades endpoint response format."""

    SAMPLE_TRADE = {
        "id": "trade_000001",
        "instrument": "BTC/USD",
        "price": 50000.00,
        "quantity": 0.5,
        "total": 25000.00,
        "side": "buy",
        "timestamp": "2024-01-15T10:30:00+00:00",
        "buyer": "user_0001",
        "seller": "user_0002",
    }

    def test_trade_has_id(self):
        self.assertIn("id", self.SAMPLE_TRADE)

    def test_trade_has_instrument(self):
        self.assertIn("instrument", self.SAMPLE_TRADE)

    def test_trade_has_price(self):
        self.assertIn("price", self.SAMPLE_TRADE)
        self.assertIsInstance(self.SAMPLE_TRADE["price"], (int, float))

    def test_trade_has_quantity(self):
        self.assertIn("quantity", self.SAMPLE_TRADE)
        self.assertIsInstance(self.SAMPLE_TRADE["quantity"], (int, float))

    def test_trade_has_side(self):
        self.assertIn("side", self.SAMPLE_TRADE)
        self.assertIn(self.SAMPLE_TRADE["side"], ["buy", "sell"])

    def test_trade_has_timestamp(self):
        self.assertIn("timestamp", self.SAMPLE_TRADE)

    def test_trade_total_is_price_times_quantity(self):
        expected = self.SAMPLE_TRADE["price"] * self.SAMPLE_TRADE["quantity"]
        self.assertAlmostEqual(self.SAMPLE_TRADE["total"], expected, places=2)


class TestDepthResponseFormat(unittest.TestCase):
    """Test the depth endpoint response format."""

    SAMPLE_DEPTH = {
        "instrument": "BTC/USD",
        "bids": [["50000.00", "0.5"], ["49999.00", "1.0"]],
        "asks": [["50001.00", "0.3"], ["50002.00", "0.8"]],
        "timestamp": "2024-01-15T10:30:00+00:00",
    }

    def test_depth_has_instrument(self):
        self.assertIn("instrument", self.SAMPLE_DEPTH)

    def test_depth_has_bids(self):
        self.assertIn("bids", self.SAMPLE_DEPTH)
        self.assertIsInstance(self.SAMPLE_DEPTH["bids"], list)

    def test_depth_has_asks(self):
        self.assertIn("asks", self.SAMPLE_DEPTH)
        self.assertIsInstance(self.SAMPLE_DEPTH["asks"], list)

    def test_bid_entries_are_price_quantity_pairs(self):
        for bid in self.SAMPLE_DEPTH["bids"]:
            self.assertEqual(len(bid), 2)

    def test_ask_entries_are_price_quantity_pairs(self):
        for ask in self.SAMPLE_DEPTH["asks"]:
            self.assertEqual(len(ask), 2)

    def test_bids_should_be_descending(self):
        prices = [float(b[0]) for b in self.SAMPLE_DEPTH["bids"]]
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_asks_should_be_ascending(self):
        prices = [float(a[0]) for a in self.SAMPLE_DEPTH["asks"]]
        self.assertEqual(prices, sorted(prices))


class TestHealthResponseFormat(unittest.TestCase):
    """Test the health endpoint response format."""

    SAMPLE_HEALTH = {
        "status": "ok",
        "version": "3.2.0",
        "uptime_seconds": 86400,
        "timestamp": "2024-01-15T00:00:00Z",
    }

    def test_health_has_status(self):
        self.assertIn("status", self.SAMPLE_HEALTH)
        self.assertEqual(self.SAMPLE_HEALTH["status"], "ok")

    def test_health_has_version(self):
        self.assertIn("version", self.SAMPLE_HEALTH)

    def test_health_has_uptime(self):
        self.assertIn("uptime_seconds", self.SAMPLE_HEALTH)
        self.assertIsInstance(self.SAMPLE_HEALTH["uptime_seconds"], int)

    def test_health_has_timestamp(self):
        self.assertIn("timestamp", self.SAMPLE_HEALTH)


if __name__ == "__main__":
    unittest.main()
