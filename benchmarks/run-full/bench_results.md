# Video generation benchmark — 2026-10-07 09:07

Wall-clock per task, warmup (model load) excluded. Speedup vs the 'baseline' task of the same suite.

## Suite `ltx25`

| task | resolution | frames | time (s) | speedup | status |
|---|---|---|---|---|---|
| warmup (excluded) | 1280x704 | 121 | 543.0 |  | unknown |
| baseline: 1280x704, 8st, guidance5x2ph (current default) | 1280x704 | 121 | 75.6 | x1.00 | unknown |
| fast recipe: 1280x704, 8st, guidance1 1ph | 1280x704 | 121 | 83.8 | x0.90 | unknown |
| lowres: 832x480, 8st, guidance1 | 832x480 | 121 | 39.9 | x1.89 | unknown |
| lowres + LTX2.5 Pixel Upscaler x2 | 832x480 | 121 | 82.2 | x0.92 | unknown |

## Suite `h3`

| task | resolution | frames | time (s) | speedup | status |
|---|---|---|---|---|---|
| warmup (excluded) | 832x480 | 124 | 174.8 |  | unknown |
| baseline: 832x480, 8st res_multistep | 832x480 | 124 | 95.7 | x1.00 | unknown |
| 6 steps | 832x480 | 124 | 80.2 | x1.19 | unknown |
| 832x480 + MiniMax H3 VAE x2 | 832x480 | 124 | 219.5 | x0.44 | unknown |
| 248 frames | 832x480 | 248 | 263.2 | x0.36 | unknown |
| 124 frames + RIFE x2 | 832x480 | 124 | 112.3 | x0.85 | unknown |

## Suite `wan13b`

| task | resolution | frames | time (s) | speedup | status |
|---|---|---|---|---|---|
| warmup (excluded) | 832x480 | 81 | 97.0 |  | unknown |
| baseline: 832x480, 4st | 832x480 | 81 | 34.9 | x1.00 | unknown |
| 1280x720, 4st | 1280x720 | 81 | 94.7 | x0.37 | unknown |
| 162 frames + RIFE x2 | 832x480 | 162 | 90.4 | x0.39 | unknown |

