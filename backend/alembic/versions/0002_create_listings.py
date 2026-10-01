"""create listings and price snapshots

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-01
"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "listings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("condition", sa.String(length=16), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_listings")),
        sa.UniqueConstraint("source", "external_id", name=op.f("uq_listings_source")),
    )
    op.create_table(
        "price_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("in_stock", sa.Boolean(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["listings.id"],
            name=op.f("fk_price_snapshots_listing_id_listings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_price_snapshots")),
    )
    op.create_index(
        "ix_price_snapshots_listing_captured", "price_snapshots", ["listing_id", "captured_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_price_snapshots_listing_captured", table_name="price_snapshots")
    op.drop_table("price_snapshots")
    op.drop_table("listings")
