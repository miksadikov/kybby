# BrandKit OpenRouter FLUX.2 [flex] CLI (MVP)

Минимальный CLI-генератор бренд‑артефактов через OpenRouter API и модель `black-forest-labs/flux.2-flex`.

Генерирует **растровые** ассеты (обычно PNG) и сохраняет их в:
- `out/<brand_id>/icons/`
- `out/<brand_id>/patterns/`
- `out/<brand_id>/illustrations/`

> FLUX — image‑only модель в OpenRouter, поэтому запрос идёт в `/api/v1/chat/completions` с `modalities: ["image"]`.

## Требования
- Python 3.10+
- API ключ OpenRouter

## Установка
```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Переменные окружения
```bash
# обязательно
set OPENROUTER_API_KEY=YOUR_KEY

# опционально (для лидеров/атрибуции OpenRouter)
set OPENROUTER_REFERER=http://localhost
set OPENROUTER_TITLE=BrandKit CLI
```

## Пример запуска
```bash
python src/main.py \
  --tokens config/tokens.example.json \
  --out out \
  --brand-id Brand123 \
  --icons 8 --patterns 4 --illustrations 4 \
  --aspect-ratio 1:1 --image-size 1K \
  --steps 20 --guidance 3.5
```

## Параметры качества/размера
OpenRouter поддерживает `image_config` (если модель совместима):
- `aspect_ratio`: `1:1`, `16:9`, `9:16`, `4:5`, ...
- `image_size`: `1K` (default), `2K`, `4K`

Вы можете задать это в `tokens.json -> openrouter.image_config` или через CLI флаги.

Дополнительно (best-effort passthrough — зависит от провайдера, которого выберет роутер OpenRouter):
- `--steps` (передаётся как `num_inference_steps`)
- `--guidance` (передаётся как `guidance_scale`)

## Важно про negative prompt
Для FLUX.2 Flex negative prompts обычно **не работают** — лучше описывать, что *нужно* получить (например: “clean background”), а не “no clutter”. Поэтому по умолчанию мы **не** добавляем `style.negative` в запрос; включить можно флагом `--append-negative`.

## Формат tokens.json (минимум)
Смотри `config/tokens.example.json`.
