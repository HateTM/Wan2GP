# Video generation benchmark — 2026-10-07 11:03

Wall-clock per task, warmup (model load) excluded. Speedup vs the 'baseline' task of the same suite.

## Suite `redgraft`

| task | resolution | frames | time (s) | speedup | status |
|---|---|---|---|---|---|
| warmup (excluded) | 1280x704 | 121 | 138.4 |  | ok |
| baseline: 1280x704, 8st (your default) | 1280x704 | 121 | 64.5 | x1.00 | ok |
| lowres: 832x480, 8st | 832x480 | 121 | 33.1 | x1.95 | ok |
| lowres + LTX2.3 Pixel Upscaler x2 (ComfyUI workflow method) | 832x480 | 121 | 5.9 | x10.93 | error |
| lowres + LTX2.5 Pixel Upscaler x2 | 832x480 | 121 | 501.8 | x0.13 | ok |
| lowres + LTX2.5 Detail Refiner x1.5 | 832x480 | 121 | 16.9 | x3.82 | error |

