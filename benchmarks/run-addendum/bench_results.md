# Video generation benchmark — 2026-10-07 09:35

Wall-clock per task, warmup (model load) excluded. Speedup vs the 'baseline' task of the same suite.

## Suite `h3`

| task | resolution | frames | time (s) | speedup | status |
|---|---|---|---|---|---|
| warmup (excluded) | 832x480 | 124 | 178.4 |  | ok |
| baseline: 832x480, 8st res_multistep | 832x480 | 124 | 97.4 | x1.00 | ok |
| 6 steps | 832x480 | 124 | 76.0 | x1.28 | ok |
| 4 steps (Civitai ultra-fast recipe) | 832x480 | 124 | 60.0 | x1.62 | ok |
| 832x480 + MiniMax H3 VAE x2 | 832x480 | 124 | 162.9 | x0.60 | ok |
| 248 frames | 832x480 | 248 | 261.0 | x0.37 | ok |
| 124 frames + RIFE x2 | 832x480 | 124 | 109.6 | x0.89 | ok |

## Suite `ltx25`

| task | resolution | frames | time (s) | speedup | status |
|---|---|---|---|---|---|
| warmup (excluded) | 1280x704 | 121 | 146.4 |  | ok |
| baseline: 1280x704, 8st, guidance5x2ph (current default) | 1280x704 | 121 | 71.7 | x1.00 | ok |
| fast recipe: 1280x704, 8st, guidance1 1ph | 1280x704 | 121 | 83.6 | x0.86 | ok |
| lowres: 832x480, 8st, guidance1 | 832x480 | 121 | 41.1 | x1.74 | ok |
| lowres: 832x480, 8st, guidance5 (quality-preserving) | 832x480 | 121 | 39.7 | x1.81 | ok |
| lowres + LTX2.5 Pixel Upscaler x2 | 832x480 | 121 | 76.5 | x0.94 | ok |

