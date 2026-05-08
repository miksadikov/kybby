"""Общие клиенты для внешних сервисов (провайдеры генерации и др.)."""

from app.integrations.provider_http import request_with_retries

__all__ = ['request_with_retries']
