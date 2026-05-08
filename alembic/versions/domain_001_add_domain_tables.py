"""Таблицы style_profiles, assets, asset_manifests, error_logs.

Создаёт только отсутствующие таблицы — совместимо с тем, что приложение уже
могло поднять схему через SQLAlchemy create_all.

Revision ID: domain_001
Revises:
Create Date: 2026-05-04

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'domain_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if 'style_profiles' not in tables:
        op.create_table(
            'style_profiles',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('project_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('version', sa.Integer(), server_default='1', nullable=False),
            sa.Column('payload', sa.JSON(), nullable=True),
            sa.Column('snapshot_path', sa.Text(), nullable=True),
            sa.Column('created_at', sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(
            'ix_style_profiles_project_created',
            'style_profiles',
            ['project_id', 'created_at'],
            unique=False,
        )

    if 'assets' not in tables:
        op.create_table(
            'assets',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('project_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('kind', sa.Text(), nullable=False),
            sa.Column('provider', sa.Text(), nullable=False),
            sa.Column('storage_path', sa.Text(), nullable=False),
            sa.Column('filename', sa.Text(), nullable=True),
            sa.Column('meta', sa.JSON(), nullable=True),
            sa.Column('generation_job_id', sa.Text(), nullable=True),
            sa.Column('created_at', sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(
            'ix_assets_project_kind',
            'assets',
            ['project_id', 'kind'],
            unique=False,
        )

    if 'asset_manifests' not in tables:
        op.create_table(
            'asset_manifests',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('project_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('kind', sa.Text(), nullable=False),
            sa.Column('payload', sa.JSON(), nullable=True),
            sa.Column('storage_path', sa.Text(), nullable=True),
            sa.Column('generation_job_id', sa.Text(), nullable=True),
            sa.Column('created_at', sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(
            'ix_asset_manifests_project_kind',
            'asset_manifests',
            ['project_id', 'kind'],
            unique=False,
        )

    if 'error_logs' not in tables:
        op.create_table(
            'error_logs',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('project_id', sa.Integer(), nullable=True),
            sa.Column('generation_job_id', sa.Text(), nullable=True),
            sa.Column('source', sa.Text(), nullable=False),
            sa.Column('code', sa.Text(), nullable=True),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('detail', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_error_logs_created', 'error_logs', ['created_at'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    for name in ('error_logs', 'asset_manifests', 'assets', 'style_profiles'):
        if name in tables:
            op.drop_table(name)
