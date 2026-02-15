// Shared demo flow: load samples, run tinyformer_encode(), classify, print pred/exp.
// Used by all baseline and accelerated main_*.c variants.

#ifndef DEMO_RUNNER_H
#define DEMO_RUNNER_H

#ifdef __cplusplus
extern "C" {
#endif

// Print a single line to UART (e.g. "MODE: BASELINE\r\n"). Used by each main for the banner.
void demo_print_banner(const char *line);

// Run the full TinyFormer UCI HAR demo: iterate demo samples, encode, mean-pool,
// classifier, argmax; print "Sample i: pred=X exp=Y" per sample via UART.
void demo_run(void);

#ifdef __cplusplus
}
#endif

#endif /* DEMO_RUNNER_H */
