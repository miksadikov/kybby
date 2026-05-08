from __future__ import annotations

from typing import Dict, Literal

from pydantic import BaseModel, Field

PaletteRole = Literal["primary", "secondary", "accent", "tertiary", "neutral", "extra"]
PaletteVariantName = Literal["soft", "balanced", "contrast"]


class PaletteSuggestRequest(BaseModel):
    seed_color: str = Field(..., min_length=4, max_length=9)
    seed_role: PaletteRole = "primary"


class PaletteVariant(BaseModel):
    primary: str
    secondary: str
    accent: str
    tertiary: str
    neutral: str
    extra: str


class PaletteSuggestResponse(BaseModel):
    ok: bool = True
    seed_color: str
    seed_role: PaletteRole
    variants: Dict[PaletteVariantName, PaletteVariant]
