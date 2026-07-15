# Vendored whisper.cpp model download script

- Upstream project: `ggml-org/whisper.cpp`
- Upstream repository: <https://github.com/ggml-org/whisper.cpp>
- Upstream commit: `8443cf05e3fa8ce1b32348e1bcbcf8fc31f7f3ae`
- Original path: `models/download-ggml-model.sh`
- Vendored path: `vendor/whisper.cpp/download-ggml-model.sh`
- Upstream license: MIT; see `LICENSE` in this directory.

To update this resource, check out the intended upstream commit in a clean
`ggml-org/whisper.cpp` clone, copy `models/download-ggml-model.sh` and `LICENSE`
into this directory, preserve the script's executable bit, update the commit
above, and verify both copies with `cmp` or SHA-256 before committing.

This directory contains only the stable resources required for model download.
It does not contain the complete whisper.cpp source tree, build artifacts,
runtime libraries, `whisper-cli`, or model files.
