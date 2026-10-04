# Final competition pack

From the repository root:

```sh
python3 -B -m unittest discover -s app/tests -p test_review_pack.py -v
python3 -B app/tools/package_review_pack.py --check
python3 -B app/tools/package_review_pack.py
```

The builder requires the current offline build, verified PowerPoint and matching
source notes, three current LaTeX sources, and the verified silent final video.
It rejects stale or changed inputs and never overwrites a previous pack. For a
new revision, pass `--output app/delivery/Aktina-Competition-Pack-REVISION.zip`.

The ZIP contains its run order and per-file SHA-256 manifest; the adjacent
`.manifest.json` identifies the complete archive. It includes no historical
PDF exports, old videos, drafts, or research datasets. Native LaTeX compilation
and the separate deck/video receipts remain the checks for those artifacts.
