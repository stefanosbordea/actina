# Final competition pack

From the repository root:

```sh
python3 -B -m unittest discover -s app/tests -p test_review_pack.py -v
python3 -B app/tools/package_review_pack.py --check
python3 -B app/tools/package_review_pack.py
```

The builder requires the current offline build, verified PowerPoint and matching
source notes, the technical-summary source, three earlier proposal sources, all four forecast QR assets and the verified silent video. Current forecast HTML, scripts, style and packaged rows are required.
It rejects stale or changed inputs and never overwrites a previous pack. For a
new revision, pass `--output app/delivery/Aktina-Competition-Pack-REVISION.zip`.

The ZIP contains its run order and per-file SHA-256 manifest; the adjacent
`.manifest.json` identifies the complete archive. It includes no PDFs, private messages, team-setting captures, private screenshots, superseded videos or research datasets. The current technical summary is included as LaTeX source only. The earlier proposal sources are explicitly identified as review drafts that predate the current model comparison. The 44-second video is historical screenshot footage, not a current forecast demonstration.

Native LaTeX compilation and the separate deck/video receipts remain the checks for those artifacts. Packaging never exports a PDF. QR bytes must match their verification notes. Private screenshot directories are rejected rather than silently packaged. The existing public workspace preview images remain offline site dependencies.
