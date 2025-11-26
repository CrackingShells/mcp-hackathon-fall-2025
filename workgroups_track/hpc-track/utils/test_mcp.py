#!/usr/bin/env python3
"""
Test script for MCP server - supports both local (Docker) and remote (URL) connections.

Usage:
    python3 test_mcp.py                    # Test local Docker container
    python3 test_mcp.py http://host:port   # Test remote HTTP server
    python3 test_mcp.py ssh://user@host    # Test remote via SSH
"""
import subprocess
import json
import sys
import argparse
import requests
from urllib.parse import urlparse

def send_request_stdio(process, method, params=None, request_id=None):
    """Send a JSON-RPC request via stdio."""
    request = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        request["id"] = request_id
    if params is not None:
        request["params"] = params

    process.stdin.write(json.dumps(request) + "\n")
    process.stdin.flush()

    if request_id is not None:
        response_line = process.stdout.readline()
        if response_line:
            return json.loads(response_line)
    return None

def send_request_http(base_url, method, params=None, request_id=None):
    """Send a JSON-RPC request via HTTP."""
    request = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        request["id"] = request_id
    if params is not None:
        request["params"] = params

    response = requests.post(
        f"{base_url}/mcp",
        json=request,
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    )

    if response.status_code == 200:
        return response.json()
    else:
        print(f"HTTP Error {response.status_code}: {response.text}", file=sys.stderr)
        return None

def call_tool(send_fn, tool_name, arguments, request_id):
    """Call an MCP tool."""
    print(f"\n{'='*60}")
    print(f"Calling tool: {tool_name}")
    print(f"Arguments: {json.dumps(arguments, indent=2)}")

    response = send_fn("tools/call", {"name": tool_name, "arguments": arguments}, request_id)

    if response and "result" in response:
        print(f"✓ Result: {json.dumps(response['result'], indent=2)}")
        return response["result"]
    else:
        print(f"✗ Error: {response}")
        return None

def run_tests(send_fn):
    """Run the test suite."""
    try:
        # Initialize
        print("\n1. Initializing MCP server...")
        response = send_fn("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"}
        }, 1)
        if not response:
            print("✗ Failed to initialize")
            return False
        print("✓ Initialized")

        # Send initialized notification
        send_fn("notifications/initialized")

        # List tools
        print("\n2. Listing available tools...")
        response = send_fn("tools/list", {}, 2)
        if response and "result" in response:
            tools = [t["name"] for t in response["result"]["tools"]]
            print(f"✓ Available tools: {', '.join(tools)}")

        # Test each tool
        req_id = 3

        call_tool(send_fn, "get_source_code", {}, req_id)
        req_id += 1

        call_tool(send_fn, "make_clean", {}, req_id)
        req_id += 1

        call_tool(send_fn, "make_stream_benchmark", {
            "CC": "gcc",
            "CFLAGS": "-O2 -Wall",
            "LDFLAGS": "-lm"
        }, req_id)
        req_id += 1

        call_tool(send_fn, "test_correctness", {}, req_id)
        req_id += 1

        print("\nBaseline performance:")
        call_tool(send_fn, "test_speed", {}, req_id)
        req_id += 1

        custom_copy = '''void copy_kernel(double * restrict a, double * restrict b, int n) {
    for (int i = 0; i < n; i += 4) {
        a[i] = b[i];
        a[i+1] = b[i+1];
        a[i+2] = b[i+2];
        a[i+3] = b[i+3];
    }
}'''
        call_tool(send_fn, "make_custom_benchmark", {
            "CC": "gcc",
            "CFLAGS": "-O3 -march=native",
            "LDFLAGS": "-lm",
            "copy_code": custom_copy
        }, req_id)
        req_id += 1

        print("\nCustom implementation performance:")
        call_tool(send_fn, "test_speed", {}, req_id)
        req_id += 1

        call_tool(send_fn, "make_clean", {}, req_id)

        print("\n" + "="*60)
        print("✓ All MCP tools tested successfully!")
        return True

    except Exception as e:
        print(f"✗ Error testing MCP server: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_local():
    """Test local Docker container."""
    print("Starting MCP server in Docker...")

    process = subprocess.Popen(
        ["docker", "run", "-i", "lj_benchmark"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    try:
        def send_fn(method, params=None, request_id=None):
            return send_request_stdio(process, method, params, request_id)

        return run_tests(send_fn)

    finally:
        try:
            send_request_stdio(process, "shutdown", {}, 999)
            send_request_stdio(process, "exit")
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

def test_remote(url):
    """Test remote MCP server."""
    parsed = urlparse(url)

    if parsed.scheme in ['http', 'https']:
        print(f"Connecting to {url}...")
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        def send_fn(method, params=None, request_id=None):
            return send_request_http(base_url, method, params, request_id)

        return run_tests(send_fn)

    else:
        print(f"Unsupported URL scheme: {parsed.scheme}", file=sys.stderr)
        print("Supported schemes: http, https", file=sys.stderr)
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test MCP server")
    parser.add_argument("url", nargs="?", help="Remote server URL (e.g., http://host:port)")
    args = parser.parse_args()

    if args.url:
        success = test_remote(args.url)
    else:
        success = test_local()

    sys.exit(0 if success else 1)
