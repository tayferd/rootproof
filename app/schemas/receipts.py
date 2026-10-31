"""Portable receipt version 1; witness confirmation is not implemented."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from integrity.merkle import MERKLE_VERSION
from integrity.proofs import PROOF_VERSION

HexDigest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ProtectedRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["rootproof.registration"]
    id: UUID
    digest: HexDigest
    hash_algorithm: Literal["sha256"]
    received_at: datetime
    registration_metadata: dict[str, Any]
    format_version: Literal[1]


class ReceiptBatch(BaseModel):
    id: UUID
    root: HexDigest
    tree_size: int = Field(ge=1, le=1000)
    merkle_version: Literal[MERKLE_VERSION]
    sealed_at: datetime


class InclusionProof(BaseModel):
    version: Literal[PROOF_VERSION] = PROOF_VERSION
    leaf_index: int = Field(ge=0, le=999)
    audit_path: list[HexDigest] = Field(max_length=10)


class Receipt(BaseModel):
    receipt_version: Literal["rootproof.receipt.v1"] = "rootproof.receipt.v1"
    registration: ProtectedRegistration
    batch: ReceiptBatch
    inclusion_proof: InclusionProof
    status: Literal["sealed_pending_witnesses"] = "sealed_pending_witnesses"
