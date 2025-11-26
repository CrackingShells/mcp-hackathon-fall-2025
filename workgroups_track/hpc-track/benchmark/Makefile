CC = gcc
CFLAGS ?= -O2 -Wall
LDFLAGS = 

all: stream_benchmark

stream_benchmark: stream_benchmark.c
	$(CC) $(CFLAGS) -o stream_benchmark stream_benchmark.c $(LDFLAGS)

custom: stream_benchmark_custom.c
	$(CC) $(CFLAGS) -o stream_benchmark stream_benchmark_custom.c $(LDFLAGS)

test-correctness:
	@if [ ! -f stream_benchmark ]; then echo "Error: stream_benchmark not found"; exit 1; fi
	@if [ ! -x stream_benchmark ]; then echo "Error: stream_benchmark not executable"; chmod +x stream_benchmark; fi
	./stream_benchmark

test-speed:
	@if [ ! -f stream_benchmark ]; then echo "Error: stream_benchmark not found"; exit 1; fi
	@if [ ! -x stream_benchmark ]; then echo "Error: stream_benchmark not executable"; chmod +x stream_benchmark; fi
	./stream_benchmark

test: test-correctness test-speed

clean:
	rm -f stream_benchmark stream_benchmark_custom.c

.PHONY: all test test-correctness test-speed clean custom
