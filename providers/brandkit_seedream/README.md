# BrandKit OpenRouter Seedream CLI (MVP)

Минимальный CLI-генератор бренд-артефактов через OpenRouter API и модель `bytedance-seed/seedream-4.5`.

Генерирует **растровые** ассеты (PNG/JPEG/WEBP — как вернёт модель) и сохраняет их в папки:
- `out/<brand_id>/icons/`
- `out/<brand_id>/patterns/`
- `out/<brand_id>/illustrations/`

## Требования
- Python 3.10+ (Ubuntu 22.04 ок)
- API ключ OpenRouter

## Установка
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Переменные окружения
```bash
export OPENROUTER_API_KEY="YOUR_KEY"
# опционально
export OPENROUTER_REFERER="http://localhost"
export OPENROUTER_TITLE="BrandKit CLI"
```

## Пример запуска
```bash
python3 src/main.py \
  --tokens config/tokens.example.json \
  --out out \
  --brand-id Brand123 \
  --icons 8 --patterns 4 --illustrations 4
```

### Важно про иконки
Seedream (как и большинство image-gen моделей через OpenRouter) выдаёт **картинки**, а не SVG.
То есть иконки будут PNG/JPG/WEBP “в стиле иконок”.

## Формат tokens.json (минимум)
Смотри `config/tokens.example.json`.
