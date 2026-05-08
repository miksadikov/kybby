from __future__ import annotations

import colorsys
import re
from dataclasses import dataclass

PALETTE_KEYS = ("primary", "secondary", "accent", "tertiary", "neutral", "extra")
HEX_RE = re.compile(r"^#?(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")


@dataclass(frozen=True)
class VariantTuning:
    secondary_hue: float
    secondary_sat_scale: float
    secondary_lightness_shift: float
    accent_hue: float
    accent_sat_scale: float
    accent_lightness_shift: float
    tertiary_hue: float
    tertiary_sat_scale: float
    tertiary_lightness_shift: float
    neutral_sat: float
    neutral_lightness: float
    extra_sat_scale: float
    extra_lightness: float


VARIANT_TUNINGS: dict[str, VariantTuning] = {
    "soft": VariantTuning(
        secondary_hue=14,
        secondary_sat_scale=0.52,
        secondary_lightness_shift=0.17,
        accent_hue=172,
        accent_sat_scale=0.84,
        accent_lightness_shift=-0.02,
        tertiary_hue=-26,
        tertiary_sat_scale=0.68,
        tertiary_lightness_shift=0.10,
        neutral_sat=0.08,
        neutral_lightness=0.90,
        extra_sat_scale=0.55,
        extra_lightness=0.24,
    ),
    "balanced": VariantTuning(
        secondary_hue=18,
        secondary_sat_scale=0.60,
        secondary_lightness_shift=0.13,
        accent_hue=182,
        accent_sat_scale=0.96,
        accent_lightness_shift=-0.06,
        tertiary_hue=-34,
        tertiary_sat_scale=0.78,
        tertiary_lightness_shift=0.06,
        neutral_sat=0.10,
        neutral_lightness=0.91,
        extra_sat_scale=0.62,
        extra_lightness=0.18,
    ),
    "contrast": VariantTuning(
        secondary_hue=22,
        secondary_sat_scale=0.66,
        secondary_lightness_shift=0.10,
        accent_hue=196,
        accent_sat_scale=1.12,
        accent_lightness_shift=-0.12,
        tertiary_hue=-44,
        tertiary_sat_scale=0.90,
        tertiary_lightness_shift=0.02,
        neutral_sat=0.11,
        neutral_lightness=0.89,
        extra_sat_scale=0.68,
        extra_lightness=0.14,
    ),
}


class PaletteService:
    def normalize_hex(self, color: str) -> str:
        value = str(color or "").strip()
        if not HEX_RE.match(value):
            raise ValueError("Передан некорректный цвет. Используйте формат #RRGGBB.")
        value = value.lstrip("#")
        if len(value) == 3:
            value = "".join(ch * 2 for ch in value)
        return f"#{value.upper()}"

    def suggest_variants(self, seed_color: str) -> dict[str, dict[str, str]]:
        seed = self.normalize_hex(seed_color)
        return {name: self._build_variant(seed, tuning) for name, tuning in VARIANT_TUNINGS.items()}

    def _build_variant(self, seed_hex: str, tuning: VariantTuning) -> dict[str, str]:
        r, g, b = self._hex_to_rgb(seed_hex)
        hue, lightness, saturation = colorsys.rgb_to_hls(r, g, b)
        hue_deg = hue * 360.0

        seed_lightness = self._clamp(lightness, 0.22, 0.72)
        seed_saturation = self._clamp(saturation, 0.18, 0.88)
        primary = seed_hex

        secondary = self._from_hls(
            hue_deg + tuning.secondary_hue,
            seed_lightness + tuning.secondary_lightness_shift,
            self._clamp(seed_saturation * tuning.secondary_sat_scale, 0.10, 0.42),
        )
        accent = self._from_hls(
            hue_deg + tuning.accent_hue,
            seed_lightness + tuning.accent_lightness_shift,
            self._clamp(max(seed_saturation, 0.45) * tuning.accent_sat_scale, 0.40, 0.84),
        )
        tertiary = self._from_hls(
            hue_deg + tuning.tertiary_hue,
            seed_lightness + tuning.tertiary_lightness_shift,
            self._clamp(max(seed_saturation, 0.28) * tuning.tertiary_sat_scale, 0.18, 0.58),
        )
        neutral = self._from_hls(
            hue_deg + 4,
            tuning.neutral_lightness,
            tuning.neutral_sat,
        )
        extra = self._from_hls(
            hue_deg - 6,
            tuning.extra_lightness,
            self._clamp(max(seed_saturation, 0.18) * tuning.extra_sat_scale, 0.12, 0.45),
        )

        palette = {
            "primary": primary,
            "secondary": secondary,
            "accent": accent,
            "tertiary": tertiary,
            "neutral": neutral,
            "extra": extra,
        }
        return self._ensure_distinct(palette)

    def _ensure_distinct(self, palette: dict[str, str]) -> dict[str, str]:
        pairs = (("secondary", "primary"), ("accent", "primary"), ("tertiary", "secondary"), ("tertiary", "accent"))
        normalized = dict(palette)
        for current, other in pairs:
            if self._hex_distance(normalized[current], normalized[other]) < 44:
                normalized[current] = self._nudge_color(normalized[current], current)
        if self._hex_distance(normalized["neutral"], normalized["extra"]) < 70:
            normalized["extra"] = self._nudge_color(normalized["extra"], "extra")
        return normalized

    def _nudge_color(self, color: str, role: str) -> str:
        r, g, b = self._hex_to_rgb(color)
        hue, lightness, saturation = colorsys.rgb_to_hls(r, g, b)
        hue_deg = hue * 360.0
        if role == "extra":
            return self._from_hls(hue_deg - 12, max(0.10, lightness - 0.06), min(0.48, saturation + 0.06))
        if role == "accent":
            return self._from_hls(hue_deg + 18, self._clamp(lightness - 0.04, 0.18, 0.68), min(0.90, saturation + 0.08))
        return self._from_hls(hue_deg + 14, self._clamp(lightness + 0.04, 0.20, 0.86), self._clamp(saturation + 0.03, 0.12, 0.66))

    def _from_hls(self, hue_deg: float, lightness: float, saturation: float) -> str:
        hue = (hue_deg % 360.0) / 360.0
        lightness = self._clamp(lightness, 0.08, 0.94)
        saturation = self._clamp(saturation, 0.0, 1.0)
        r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
        return self._rgb_to_hex(r, g, b)

    def _hex_distance(self, first: str, second: str) -> float:
        r1, g1, b1 = self._hex_to_rgb(first)
        r2, g2, b2 = self._hex_to_rgb(second)
        dr = (r1 - r2) * 255.0
        dg = (g1 - g2) * 255.0
        db = (b1 - b2) * 255.0
        return (dr * dr + dg * dg + db * db) ** 0.5

    def _hex_to_rgb(self, value: str) -> tuple[float, float, float]:
        raw = value.lstrip("#")
        return tuple(int(raw[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

    def _rgb_to_hex(self, r: float, g: float, b: float) -> str:
        return "#{:02X}{:02X}{:02X}".format(
            int(round(self._clamp(r, 0.0, 1.0) * 255)),
            int(round(self._clamp(g, 0.0, 1.0) * 255)),
            int(round(self._clamp(b, 0.0, 1.0) * 255)),
        )

    def _clamp(self, value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))
