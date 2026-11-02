# Portable single-authority evidence package

The experimental `rootproof.evidence.freetsa.v1` package combines an existing
receipt, a saved RFC 3161 response, and the request nonce in one JSON file.
It contains no original document. Receipt metadata such as a document name may
be present, so share the package deliberately.

Export and verification are offline. Neither command submits a timestamp request.
Export verifies the saved response before writing and refuses to overwrite a file.

Document Desk also accepts these packages in **Check saved evidence offline**.
Choose a document and the exported package JSON, then select **Check file and
saved evidence**. The result displays the verified authority time and the explicit
single-authority limitations. Ordinary inclusion receipts remain supported and
continue to report unwitnessed. Invalid packages do not fall back to a weaker
receipt-only check. The desktop does not yet acquire or export timestamp packages.

```powershell
.\.venv\Scripts\python.exe -m clients.evidence export tests/fixtures/timestamp-demo-receipt.json tests/fixtures/freetsa-public-demo .local/public-demo-evidence.json
.\.venv\Scripts\python.exe -m clients.evidence verify tests/fixtures/timestamp-demo.txt .local/public-demo-evidence.json
```

The output parent directory must already exist. Use a new output filename for
subsequent exports. Exit codes are 0 for successful export or successful combined
verification, 1 for a document/proof mismatch, and 2 for malformed or unverifiable
evidence or file errors. A valid authority signature does not turn a changed
document into a successful result.

The verifier uses the separately pinned certificates in `trust/freetsa`, never
certificates or verification claims supplied by the package. Retain the verifier
and reviewed trust material with archived evidence. Base64 preserves the exact
receipt and response bytes. Unknown versions, extra fields, duplicate JSON keys,
invalid base64, oversized packages, mismatched batch commitments, wrong nonces,
and invalid signatures are rejected.

The reported authority time applies to observation of the batch commitment.
Earlier database receipt and sealing times remain operator assertions. The result
reports one authority, no quorum, no revocation check, and no approved timing
accuracy policy. This remains experimental and does not complete M-013.

This first end-to-end package anchors an existing batch directly. A future
aggregation tree can commit to many batch commitments, with a second inclusion
path and a new versioned package. Append-only history claims would additionally
require consistency verification and a mechanism to detect conflicting histories.
No second tree, blockchain integration, or scheduler is implemented by this package.
