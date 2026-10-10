# Video generation benchmark — 2026-10-07 12:55

Wall-clock per task, warmup (model load) excluded. Speedup vs the 'baseline' task of the same suite.

## Suite `redgraft`

| task | resolution | frames | time (s) | speedup | status |
|---|---|---|---|---|---|
| warmup (excluded) | 1280x704 | 121 | 141.6 |  | ok |
| baseline: 1280x704, 8st (your default) | 1280x704 | 121 | 64.2 | x1.00 | ok |
| lowres: 832x480, 8st | 832x480 | 121 | 32.2 | x1.99 | ok |
| lowres + LTX2.3 Pixel Upscaler x2 (ComfyUI workflow method) | 832x480 | 121 | 1059.5 | x0.06 | error |
| lowres + LTX2.5 Pixel Upscaler x2 | 832x480 | 121 | 505.1 | x0.13 | ok |
| lowres + LTX2.5 Detail Refiner x1.5 | 832x480 | 121 | 319.6 | x0.20 | ok |

