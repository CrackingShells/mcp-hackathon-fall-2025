from mcp.server.fastmcp import FastMCP
import implementation
import sys

# Parse arguments early to configure server
import argparse
parser = argparse.ArgumentParser(description="MCP Autotune Server")
parser.add_argument("--transport", choices=["stdio", "http"], default="stdio",
                    help="Transport type: stdio for local, http for HTTP")
parser.add_argument("--host", default="0.0.0.0",
                    help="Host to bind to (for SSE transport)")
parser.add_argument("--port", type=int, default=8000,
                    help="Port to bind to (for SSE transport)")
args = parser.parse_args()

# Initialize the MCP server for the autotune hackathon
mcp = FastMCP("autotune_hackathon", host=args.host, port=args.port,
              json_response=True)

@mcp.tool()
async def make_stream_benchmark(CC: str, CFLAGS: str, LDFLAGS: str):
    """
    Compile the STREAM memory bandwidth benchmark.

    Args:
        CC (str): C compiler (e.g., "gcc", "clang")
        CFLAGS (str): Compiler flags (e.g., "-O3 -march=native")
        LDFLAGS (str): Linker flags (e.g., "-lm")

    Returns:
        bool: True if compilation succeeds, False otherwise
    """
    success = implementation.make_stream_benchmark(CC, CFLAGS, LDFLAGS)
    return success

@mcp.tool()
async def test_correctness():
    """
    Verify benchmark correctness against reference implementation.

    Returns:
        str: JSON with correctness result {"correctness": "PASS"} or {"correctness": "FAIL"}
    """
    success = implementation.test_correctness()
    return success

@mcp.tool()
async def make_clean():
    """
    Clean up compiled artifacts and temporary files.

    This removes the compiled benchmark executable and any object files
    created during compilation, allowing for a fresh build.

    Returns:
        str: Success message indicating cleanup completion

    Example use case:
        Call this before trying a new set of compiler flags to ensure
        a clean compilation environment
    """
    success = implementation.make_clean()
    return success

@mcp.tool()
async def test_speed():
    """
    Measure memory bandwidth.

    Returns:
        str: JSON with bandwidth in GB/s for each kernel: {"copy_GB_s": ..., "scale_GB_s": ..., "add_GB_s": ..., "triad_GB_s": ...}
    """
    result = implementation.test_speed()
    return result

@mcp.tool()
async def get_source_code():
    """
    Get the default STREAM benchmark source code.

    This returns the current implementation which you can use as a reference
    when creating custom kernel implementations.

    Returns:
        str: Complete C source code of stream_benchmark.c
    """
    result = implementation.get_source_code()
    return result

@mcp.tool()
async def make_custom_benchmark(CC: str, CFLAGS: str, LDFLAGS: str,
                                allocation_code: str = "",
                                copy_code: str = "",
                                scale_code: str = "",
                                add_code: str = "",
                                triad_code: str = ""):
    """
    Compile STREAM benchmark with custom kernel implementations.

    Allows you to provide optimized implementations for any of the kernels or allocation.
    Use get_source_code() first to see the default implementations and required function signatures.

    IMPORTANT: You must match these exact function signatures:

    For allocation_code (if provided):
        double *a, *b, *c;  // Global pointers
        void allocate_arrays() {
            // Your allocation code here
        }
        void free_arrays() {
            // Your deallocation code here
        }

    For copy_code (if provided):
        void copy_kernel(double *a, double *b, int n) {
            // Implement: a[i] = b[i] for all i
        }

    For scale_code (if provided):
        void scale_kernel(double *b, double *a, int n) {
            // Implement: b[i] = 2.0 * a[i] for all i
        }

    For add_code (if provided):
        void add_kernel(double *c, double *a, double *b, int n) {
            // Implement: c[i] = a[i] + b[i] for all i
        }

    For triad_code (if provided):
        void triad_kernel(double *a, double *b, double *c, int n) {
            // Implement: a[i] = b[i] + 3.0 * c[i] for all i
        }

    Args:
        CC (str): C compiler (e.g., "gcc", "clang")
        CFLAGS (str): Compiler flags (e.g., "-O3 -march=native -fopenmp")
        LDFLAGS (str): Linker flags (e.g., "-lm")
        allocation_code (str): Custom allocation implementation (optional)
        copy_code (str): Custom copy kernel implementation (optional)
        scale_code (str): Custom scale kernel implementation (optional)
        add_code (str): Custom add kernel implementation (optional)
        triad_code (str): Custom triad kernel implementation (optional)

    Returns:
        bool or str: True if compilation succeeds, error message otherwise

    Example:
        make_custom_benchmark(
            CC="gcc",
            CFLAGS="-O3 -march=native",
            LDFLAGS="-lm",
            copy_code='''void copy_kernel(double * restrict a, double * restrict b, int n) {
    for (int i = 0; i < n; i += 4) {
        a[i] = b[i];
        a[i+1] = b[i+1];
        a[i+2] = b[i+2];
        a[i+3] = b[i+3];
    }
}'''
        )
    """
    result = implementation.make_custom_benchmark(
        CC, CFLAGS, LDFLAGS,
        allocation_code if allocation_code else None,
        copy_code if copy_code else None,
        scale_code if scale_code else None,
        add_code if add_code else None,
        triad_code if triad_code else None
    )
    return result


@mcp.tool()
async def list_cpu_info():
    """
    Retrieve basic CPU and operating system information from the current machine.

    Returns:
        dict: A JSON-serializable dictionary containing:
            - architecture (str): CPU architecture reported by the system.
            - processor (str): Processor model name or identifier.
            - system (str): Operating system type (e.g., Windows, Linux, Darwin).
            - release (str): OS kernel release version.
            - version (str): Full OS version string.
            - machine (str): Machine hardware type.
            - cores_logical (int): Number of logical CPU cores (includes hyperthreading).

    This tool takes no input parameters.
    """
    cpu_info = implementation.list_cpu_info()
    return cpu_info

if __name__ == "__main__":
    if args.transport == "http":
        print(f"Starting MCP server on http://{args.host}:{args.port}")
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")
