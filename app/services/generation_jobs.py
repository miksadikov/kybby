from __future__ import annotations

import threading
import traceback
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.project_service import ProjectService

from app.services.generation_error_summary import ProviderGenerationError, summarize_generation_failure
from app.services.generation_service import GenerationCancelledError

TERMINAL_JOB_STATUSES = ('completed', 'completed_with_errors', 'failed', 'cancelled')


class GenerationJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _stamp(self) -> str:
        return datetime.now().strftime('%H:%M:%S')

    def create_job(self, *, user_id: int, project_slug: str) -> dict[str, Any]:
        job_id = uuid.uuid4().hex[:12]
        provider_map = {
            'recraft': 'pending',
            'seedream': 'pending',
            'flux': 'pending',
        }
        job = {
            'id': job_id,
            'user_id': user_id,
            'project_slug': project_slug,
            'status': 'pending',
            'progress': 0,
            'message': 'Ожидание запуска',
            'error': None,
            'error_hint': None,
            'logs': [f'[{self._stamp()}] Задача создана'],
            'result': None,
            'providers': dict(provider_map),
            'provider_statuses': dict(provider_map),
            'provider_errors': {
                'recraft': None,
                'seedream': None,
                'flux': None,
            },
            'current_provider': None,
            'failed_provider': None,
            'cancel_requested': False,
        }
        with self._lock:
            self._jobs[job_id] = job
        return dict(job)

    def append_log(self, job_id: str, message: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job['logs'].append(f'[{self._stamp()}] {message}')

    def update(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return

            providers = changes.pop('providers', None)
            provider_statuses = changes.pop('provider_statuses', None)
            merged_statuses = providers or provider_statuses
            if merged_statuses:
                job['providers'].update(merged_statuses)
                job['provider_statuses'].update(merged_statuses)

            provider_errors = changes.pop('provider_errors', None)
            if provider_errors:
                job['provider_errors'].update(provider_errors)

            job.update(changes)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def get_active_job_for_project(self, *, user_id: int, project_slug: str) -> dict[str, Any] | None:
        with self._lock:
            candidates = [
                j for j in self._jobs.values()
                if int(j.get('user_id') or 0) == int(user_id)
                and str(j.get('project_slug') or '') == project_slug
                and str(j.get('status') or '') not in TERMINAL_JOB_STATUSES
            ]
            if not candidates:
                return None
            return dict(candidates[-1])

    def is_cancel_requested(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            return bool(job and job.get('cancel_requested'))

    def request_cancel(self, job_id: str, user_id: int) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or int(job.get('user_id') or 0) != int(user_id):
                return False
            if job.get('status') in TERMINAL_JOB_STATUSES:
                return False
            job['cancel_requested'] = True
            if job.get('status') in ('pending', 'running'):
                job['status'] = 'cancelling'
                job['message'] = 'Прерывание генерации...'
            job['logs'].append(f'[{self._stamp()}] Запрошено прерывание генерации пользователем')
            return True

    def start_generation(
        self,
        *,
        job_id: str,
        generation_service,
        user_id: int,
        project_slug: str,
        payload: dict[str, Any],
        base_host: str,
        project_service: 'ProjectService | None' = None,
    ) -> None:
        def runner() -> None:
            if project_service is not None:
                project_service.set_generation_job_running(job_id)
            self.update(job_id, status='running', progress=3, message='Инициализация генерации')
            self.append_log(job_id, 'Инициализация генерации...')

            def report(
                progress: int,
                message: str,
                provider: str | None = None,
                provider_status: str | None = None,
                provider_error: dict[str, Any] | None = None,
            ) -> None:
                changes: dict[str, Any] = {'progress': progress, 'message': message}

                if provider and provider_status:
                    changes['providers'] = {provider: provider_status}
                    if provider_status == 'running':
                        changes['current_provider'] = provider
                    elif provider_status == 'error':
                        changes['failed_provider'] = provider

                if provider and provider_error:
                    changes['provider_errors'] = {provider: provider_error}
                    if provider_error.get('message'):
                        changes['error'] = provider_error.get('message')
                    if provider_error.get('hint'):
                        changes['error_hint'] = provider_error.get('hint')

                self.update(job_id, **changes)
                self.append_log(job_id, message)

            try:
                result = generation_service.generate_assets(
                    user_id,
                    project_slug,
                    payload,
                    base_host,
                    progress_callback=report,
                    should_cancel=lambda: self.is_cancel_requested(job_id),
                    generation_job_id=job_id,
                )
                if self.is_cancel_requested(job_id):
                    raise GenerationCancelledError('Генерация прервана пользователем.')
                has_errors = bool(result.get('has_errors'))
                final_status = 'completed_with_errors' if has_errors else 'completed'
                final_message = 'Завершено с ошибками' if has_errors else 'Завершено'
                self.update(
                    job_id,
                    status=final_status,
                    progress=100,
                    message=final_message,
                    error=result.get('error'),
                    error_hint=result.get('error_hint'),
                    result=result,
                    current_provider=None,
                )
                self.append_log(job_id, 'Генерация завершена с ошибками провайдеров.' if has_errors else 'Генерация завершена успешно!')
                if project_service is not None:
                    project_service.finalize_generation_job_record(
                        job_id,
                        'success',
                        error_message=(result.get('error') or None) if has_errors else None,
                        error_hint=(result.get('error_hint') or None) if has_errors else None,
                    )
                    if has_errors:
                        project_service.record_error_log(
                            user_id=int(user_id),
                            project_slug=str(project_slug),
                            job_id=job_id,
                            source='generation:partial',
                            message=str(result.get('error') or 'Часть провайдеров завершилась с ошибкой'),
                            detail={
                                'hint': result.get('error_hint'),
                                'provider_errors': result.get('provider_errors'),
                            },
                        )
            except Exception as exc:
                if isinstance(exc, GenerationCancelledError):
                    self.update(
                        job_id,
                        status='cancelled',
                        progress=100,
                        message='Генерация прервана',
                        error=None,
                        error_hint=None,
                        current_provider=None,
                    )
                    self.append_log(job_id, 'Генерация прервана пользователем')
                    if project_service is not None:
                        project_service.finalize_generation_job_record(
                            job_id,
                            'failed',
                            error_message='Генерация прервана пользователем.',
                            error_hint='Откройте проект, исправьте параметры и запустите генерацию снова.',
                        )
                        project_service.record_error_log(
                            user_id=int(user_id),
                            project_slug=str(project_slug),
                            job_id=job_id,
                            source='generation:cancel',
                            message='Генерация прервана пользователем.',
                            detail={
                                'hint': 'Откройте проект, исправьте параметры и запустите генерацию снова.',
                            },
                        )
                    return
                tb = traceback.format_exc()
                snapshot = self.get_job(job_id) or {}

                failed_provider = (
                    getattr(exc, 'provider', None)
                    or snapshot.get('failed_provider')
                    or snapshot.get('current_provider')
                )

                if isinstance(exc, ProviderGenerationError):
                    user_msg = exc.user_message
                    hint = exc.hint
                else:
                    user_msg, hint = summarize_generation_failure(exc, provider=failed_provider)

                changes: dict[str, Any] = {
                    'status': 'failed',
                    'progress': 100,
                    'message': 'Ошибка генерации',
                    'error': user_msg,
                    'error_hint': hint,
                    'result': {'traceback': tb},
                    'current_provider': None,
                    'failed_provider': failed_provider,
                }

                if failed_provider:
                    changes['providers'] = {failed_provider: 'error'}
                    changes['provider_errors'] = {
                        failed_provider: {
                            'message': user_msg,
                            'hint': hint,
                        }
                    }

                self.update(job_id, **changes)
                self.append_log(job_id, user_msg or 'Ошибка генерации')
                if hint:
                    self.append_log(job_id, hint)
                if project_service is not None:
                    project_service.finalize_generation_job_record(
                        job_id,
                        'failed',
                        error_message=user_msg or 'Ошибка генерации',
                        error_hint=hint,
                    )
                    fp = str(failed_provider).strip() if failed_provider else 'unknown'
                    project_service.record_error_log(
                        user_id=int(user_id),
                        project_slug=str(project_slug),
                        job_id=job_id,
                        source=f'generation:{fp}',
                        message=user_msg or 'Ошибка генерации',
                        detail={'hint': hint, 'traceback': tb[-4000:]},
                    )

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()


generation_jobs = GenerationJobStore()
