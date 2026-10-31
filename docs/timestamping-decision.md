# External timestamping research and first protocol test

Date: October 31, 2026.

## Decision and scope

Keep blockchain out of the core MVP. Use established RFC 3161 mechanisms rather
than building a timestamp network. M-013 is in progress, not complete.

The first implementation is a manually invoked, single-authority experiment.
FreeTSA was selected for this test because its published usage policy explicitly
permits commercial incorporation and documents public-service limits. No paid
service, account, server, or subscription was created.

## Provider comparison

| Candidate | Evidence reviewed | Decision |
| --- | --- | --- |
| FreeTSA | Public commercial use permitted; maximum one request/second/IP; best-effort availability without SLA | Suitable for a small protocol experiment |
| DigiCert | Official RFC 3161 endpoint and certificate-chain documentation | General Rootproof usage permission, costs, limits, and applicable policy remain unconfirmed |
| Sectigo | Official timestamp guidance; document-signing policy disclaims warranty/liability outside signing with a Sectigo certificate | Obtain clarity on this use and terms before integration |

Sources:

- [FreeTSA usage policy](https://freetsa.org/freetsa.html).
- [FreeTSA protocol and certificate publication](https://www.freetsa.org/index_en.php).
- [DigiCert RFC 3161 documentation](https://knowledge.digicert.com/general-information/rfc3161-compliant-time-stamp-authority-server).
- [Sectigo timestamp guidance](https://www.sectigo.com/resource-library/time-stamping-server).
- [Sectigo document-signing policy](https://www.sectigo.com/uploads/files/Sectigo_CP-CPS_Document_Signing_v1_0_4.pdf), section 6.8.

Do not infer general permission, guaranteed capacity, or a price merely from a
public endpoint. Multiple endpoints operated by one organization count as one
operator for our intended independence requirement.

## Experimental commitment format

Use RFC 8785 canonical UTF-8 JSON with exactly these fields:

| Field | Value |
| --- | --- |
| type | rootproof.batch-commitment |
| format_version | Integer 1 |
| batch_id | Canonical batch UUID string |
| root | Lowercase hexadecimal Merkle root |
| tree_size | Batch entry count |
| merkle_version | Versioned Merkle construction identifier |

The source receipt must pass strict inclusion-consistency checks first. That
check does not authenticate the receipt root's history. The timestamp request
contains SHA-256 of this canonical context, a random nonce, and certificate-request
protocol information. Original file contents, names, registration metadata, and
commitment JSON are not transmitted. The provider can observe the caller's IP and
the submitted digest. Hash-only submissions are still external disclosures.

The authority attests to observing the imprint at its token time. It does not
validate an earlier server receipt time or prove authorship or measurement accuracy.

## Implementation and verification

Run from the repository root:

```powershell
# Explicit external operation; the example uses synthetic public data only.
.\.venv\Scripts\python.exe -m clients.timestamp stamp tests/fixtures/timestamp-demo-receipt.json .local/timestamps/new-public-demo

# Offline: makes no requests and does not update evidence files.
.\.venv\Scripts\python.exe -m clients.timestamp verify tests/fixtures/timestamp-demo-receipt.json tests/fixtures/freetsa-public-demo
```

The stamp output directory must not already exist. Each invocation makes at most
one timestamp request, uses HTTPS with certificate validation, bounded responses,
and explicit timeouts, and does not follow redirects or automatically retry. The
prototype has no shared rate scheduler: do not run parallel stamp commands or
loops; keep requests below FreeTSA's one-request/second/IP limit. Scheduled use
must implement a shared rate limit and retry policy before deployment.

The separately acquired CA and signer certificates are pinned in trust/freetsa.
The receipt/token cannot replace the trust roots. The protocol uses
rfc3161-client >=1.0.9, above its published certificate/signature verification
security fixes. Cryptography and RFC serialization are delegated to that library.

- [RFC 3161](https://www.rfc-editor.org/rfc/rfc3161.html).
- [RFC client documentation](https://github.com/trailofbits/rfc3161-client).
- [Certificate validation advisory](https://github.com/trailofbits/rfc3161-client/security/advisories/GHSA-3xxc-pwj6-jgrj).
- [Signature verification advisory](https://github.com/trailofbits/rfc3161-client/security/advisories/GHSA-6qhv-4h7r-2g9m).

The verifier checks the actual token signature, explicit trust chain and signer,
timestamping use, certificate validity at token time, SHA-256 message imprint, and
saved nonce. The original DER query is archived, while the saved nonce is used
directly by the offline verifier. Local request metadata is not signed evidence of
when Rootproof sent a request. Token time comes from the verified authority token.

The prototype intentionally reports:

- status: single_authority_signature_valid.
- authority_count: 1.
- quorum_met: false.
- revocation_checked: false.
- timing_accuracy_policy_approved: false.

It does not modify registrations, batches, receipt v1, or the core offline
verifier's valid_unwitnessed result. It does not claim regulatory qualification,
independent operator agreement, or approved clock accuracy.

## Live result and fixture

A request using only fixed synthetic public test data succeeded. Its actual signed
response and query are retained in tests/fixtures/freetsa-public-demo. They can be
verified offline under the pinned experimental trust configuration. The token
reports policy OID 1.2.3.4.1; its suitability and time accuracy remain for review.
No actual user batch was sent in this experiment.

## Work required to complete M-013

1. Select a second genuinely separate operator with suitable permitted use,
   capacity, costs, and explicit trust material.
2. Review each authority's timing policy and supported uncertainty. Define what
   timing conclusion follows from multiple attestations and how disagreements are
   handled; do not average clocks or call signatures a consensus protocol.
3. Define a versioned verifier trust policy supplied outside the evidence itself.
   A proposed starting threshold is both approved operators; it is not implemented.
4. Define revocation evidence, certificate rotation, historical verification, and
   long-term evidence retention/renewal behavior.
5. Add PostgreSQL-backed request/attestation state with bounded retry/rate limiting,
   without holding database transactions open during external requests.
6. Export a versioned evidence package and extend offline verification to enforce
   the approved witness policy, root context, threshold, and failure states.
7. Test unavailable authorities, wrong signers/roots, stale or mismatched responses,
   policy failures, conflicts, and insufficient confirmations end to end.

Until these are complete, the multiple-witness core MVP requirement remains open.
