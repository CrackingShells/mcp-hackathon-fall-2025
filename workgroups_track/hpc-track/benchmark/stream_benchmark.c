#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define N 200000000
#define NTIMES 20

// ALLOCATION_START
double *a, *b, *c;

void allocate_arrays() {
    a = (double*)malloc(N * sizeof(double));
    b = (double*)malloc(N * sizeof(double));
    c = (double*)malloc(N * sizeof(double));
}

void free_arrays() {
    free(a);
    free(b);
    free(c);
}
// ALLOCATION_END

// COPY_START
void copy_kernel(double *a, double *b, int n) {
    for (int i = 0; i < n; i++) {
        a[i] = b[i];
    }
}
// COPY_END

// SCALE_START
void scale_kernel(double *b, double *a, int n) {
    for (int i = 0; i < n; i++) {
        b[i] = 2.0 * a[i];
    }
}
// SCALE_END

// ADD_START
void add_kernel(double *c, double *a, double *b, int n) {
    for (int i = 0; i < n; i++) {
        c[i] = a[i] + b[i];
    }
}
// ADD_END

// TRIAD_START
void triad_kernel(double *a, double *b, double *c, int n) {
    for (int i = 0; i < n; i++) {
        a[i] = b[i] + 3.0 * c[i];
    }
}
// TRIAD_END

int main(int argc, char *argv[]) {
    allocate_arrays();

    for (int i = 0; i < N; i++) {
        a[i] = 1.0;
        b[i] = 2.0;
        c[i] = 0.0;
    }

    struct timespec start, end;
    double time;
    double sum = 0.0;

    // Copy: a[i] = b[i]
    sum = 0.0;
    clock_gettime(CLOCK_MONOTONIC, &start);
    for (int k = 0; k < NTIMES; k++) {
        copy_kernel(a, b, N);
        sum += a[N/2];
    }
    clock_gettime(CLOCK_MONOTONIC, &end);
    if (sum < 0.0) return 1;
    time = (end.tv_sec - start.tv_sec) + (end.tv_nsec - start.tv_nsec) / 1e9;
    double copy_bw = (2 * N * sizeof(double) * NTIMES / time) / 1e9;

    // Scale: b[i] = 2.0 * a[i]
    sum = 0.0;
    clock_gettime(CLOCK_MONOTONIC, &start);
    for (int k = 0; k < NTIMES; k++) {
        scale_kernel(b, a, N);
        sum += b[N/2];
    }
    clock_gettime(CLOCK_MONOTONIC, &end);
    if (sum < 0.0) return 1;
    time = (end.tv_sec - start.tv_sec) + (end.tv_nsec - start.tv_nsec) / 1e9;
    double scale_bw = (2 * N * sizeof(double) * NTIMES / time) / 1e9;

    // Add: c[i] = a[i] + b[i]
    sum = 0.0;
    clock_gettime(CLOCK_MONOTONIC, &start);
    for (int k = 0; k < NTIMES; k++) {
        add_kernel(c, a, b, N);
        sum += c[N/2];
    }
    clock_gettime(CLOCK_MONOTONIC, &end);
    if (sum < 0.0) return 1;
    time = (end.tv_sec - start.tv_sec) + (end.tv_nsec - start.tv_nsec) / 1e9;
    double add_bw = (3 * N * sizeof(double) * NTIMES / time) / 1e9;

    // Triad: a[i] = b[i] + 3.0 * c[i]
    sum = 0.0;
    clock_gettime(CLOCK_MONOTONIC, &start);
    for (int k = 0; k < NTIMES; k++) {
        triad_kernel(a, b, c, N);
        sum += a[N/2];
    }
    clock_gettime(CLOCK_MONOTONIC, &end);
    if (sum < 0.0) return 1;
    time = (end.tv_sec - start.tv_sec) + (end.tv_nsec - start.tv_nsec) / 1e9;
    double triad_bw = (3 * N * sizeof(double) * NTIMES / time) / 1e9;

    // Compute checksum
    double checksum = 0.0;
    for (int i = 0; i < N; i++) {
        checksum += a[i] + b[i] + c[i];
    }

    printf("{\"copy_GB_s\": %.2f, \"scale_GB_s\": %.2f, \"add_GB_s\": %.2f, \"triad_GB_s\": %.2f, \"checksum\": %.1f}\n",
           copy_bw, scale_bw, add_bw, triad_bw, checksum);

    free_arrays();
    return 0;
}
