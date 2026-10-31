# FreeTSA experimental trust configuration

These are public certificates, not credentials or private keys. They are used
only by the single-authority M-013 experiment. They are not silently accepted
from receipts or timestamp responses.

Retrieved on October 31, 2026 from the official HTTPS URLs:

- CA: https://freetsa.org/files/cacert.pem
- TSA signer: https://freetsa.org/files/tsa.crt
- Published file hashes: https://www.freetsa.org/index_en.php

The exact downloaded PEM file hashes match FreeTSA's published SHA-256 values:

| File | PEM file SHA-256 |
| --- | --- |
| ca.crt | 2151b61137ffa86bf664691ba67e7da0b19f98c758e3d228d5d8ebf27e044438 |
| tsa.crt | 8bfb0305bb64e2571ca507552ef3245cb1c2fee8728e0ff8689225081ea13467 |

For clarity, the certificate DER fingerprints are different:

| Certificate | DER SHA-256 |
| --- | --- |
| CA | a6379e7cecc05faa3cbf076013d745e327bbbaa38c0b9af22469d4701d18aabc |
| TSA signer | 32e841a95cc1164101ffde41298ef2fc75c1c4372ef095e88a6bbd47dfb191fc |

The client pins both files before creating a verifier with this CA and exact
signer. Initial trust is based on the provider's HTTPS publication, not an
independent audit of the operator. Certificate rotation requires deliberate
review, source verification, and updated test coverage. Do not overwrite these
files automatically when a request fails.
The repository's .gitattributes preserves the pinned PEM bytes across platforms.

The library checks the token signature, chain, timestamping certificate use,
certificate validity at token time, nonce, and message imprint. This experiment
does not check revocation or approve a timing-accuracy policy. It establishes no
multi-operator quorum. See docs/timestamping-decision.md for remaining work.
