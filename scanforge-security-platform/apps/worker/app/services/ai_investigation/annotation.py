from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class AIAnnotation:
    explanation: str
    remediation: str | None
    model_id: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cached: bool = False

    def to_dict(self) -> dict:
        return asdict(self)
