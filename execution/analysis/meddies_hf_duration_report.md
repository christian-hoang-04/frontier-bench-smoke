# Meddies HF Audio Duration Report

Dataset:
- `Meddies/Meddies-ASR-Raw-Audios`
- `https://huggingface.co/datasets/Meddies/Meddies-ASR-Raw-Audios/tree/main`

Snapshot date:
- `2026-07-01`

Method:
- Enumerate nested WAV files remotely under `processed/audio` with authenticated `HfFileSystem().glob(...)`.
- Fetch only WAV header bytes with authenticated HTTP range reads.
- Parse RIFF/WAVE `fmt ` and `data` chunks and compute duration as `data_size / byte_rate`.
- Use low concurrency and retry/backoff to survive HF `429` rate limits.
- Verify with two independent passes; both matched exactly.

Totals:
- Remote WAV files: `6633`
- Total duration seconds: `8520147.71775`
- Total duration hours: `2366.707699`
- Zero-duration files: `0`
- Duration parse errors: `0`

Per-source durations:

| Source | Remote WAV files | Duration seconds | Duration hours |
| --- | ---: | ---: | ---: |
| CafeF | 1 | 29.205313 | 0.008113 |
| Duong_Hay_Xam | 29 | 88588.266562 | 24.607852 |
| HTV_Tin_Tuc | 3427 | 3534094.189312 | 981.692830 |
| Khanh_Vy_Official | 22 | 27187.264000 | 7.552018 |
| Spiderum_Podcast | 11 | 28777.258687 | 7.993683 |
| The_First_Step | 11 | 25101.331250 | 6.972592 |
| The_Tri_Way | 54 | 135386.258188 | 37.607294 |
| VIETSUCCESS | 408 | 1364364.020125 | 378.990006 |
| VTV10 | 533 | 430836.373375 | 119.676770 |
| VTV4 | 1122 | 600849.857438 | 166.902738 |
| Vat_Vo_Studio_Podcasts | 1 | 1644.778687 | 0.456883 |
| Vietcetera | 975 | 2156766.845438 | 599.101902 |
| unlock_fm | 39 | 126522.069375 | 35.145019 |

Caveat:
- These values describe the current HF `main` snapshot.
- They should not be blindly joined onto older local manifests with different file counts.
- Known mismatches seen during verification:
  - `HTV_Tin_Tuc`: local `4416` vs current HF remote `3427`
  - `VIETSUCCESS`: local `675` vs current HF remote `408`
  - `Vietcetera`: local `945` vs current HF remote `975`
