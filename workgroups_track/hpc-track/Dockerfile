FROM ubuntu:22.04

# Avoid interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    make \
    valgrind \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip3 install fastmcp

# Set working directory
WORKDIR /app

# Copy Python files
COPY server.py .
COPY implementation.py .

# Copy benchmark files to benchmark subdirectory
COPY benchmark/ benchmark/

# Ensure all files in /app are writable (important for Singularity sandbox)
RUN chmod -R 777 /app

# Expose port for HTTP/SSE transport (optional)
EXPOSE 8000

# Default command runs the MCP server with stdio
CMD ["python3", "server.py"]
