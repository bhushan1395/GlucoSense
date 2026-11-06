from datetime import datetime, timezone
from typing import Optional, List, Literal
import math

from pydantic import BaseModel, Field, ConfigDict, field_validator


class ReadingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=1, max_length=80)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    channels: List[float] = Field(min_length=1, max_length=24)

    led_850_raw: Optional[float] = None
    led_940_raw: Optional[float] = None
    pulse_bpm: Optional[float] = Field(default=None, ge=20, le=250)

    # MLX90614 readings, stored separately from any skin-temperature field.
    object_temp_c: Optional[float] = Field(default=None, ge=-70, le=380)
    ambient_temp_c: Optional[float] = Field(default=None, ge=-40, le=125)
    skin_temp_c: Optional[float] = Field(default=None, ge=10, le=50)

    signal_quality: Literal["unassessed", "poor", "fair", "good"] = "unassessed"
    reference_glucose_mg_dl: Optional[float] = Field(default=None, ge=20, le=700)
    session_id: Optional[str] = Field(default=None, max_length=100)
    participant_code: Optional[str] = Field(default=None, max_length=100)
    metadata: dict = Field(default_factory=dict)

    @field_validator("channels")
    @classmethod
    def finite_channels(cls, values):
        if not all(math.isfinite(v) and v >= 0 for v in values):
            raise ValueError("channels must be finite and non-negative")
        return values


class ReferenceIn(BaseModel):
    reference_glucose_mg_dl: float = Field(ge=20, le=700)
    reference_method: str = Field(min_length=2, max_length=120)
    measured_at: datetime
    notes: Optional[str] = Field(default=None, max_length=500)
