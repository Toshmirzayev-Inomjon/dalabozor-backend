"""add farmer geo coordinates

Revision ID: c7d2a91e4f63
Revises: 57d49404df32
Create Date: 2026-07-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7d2a91e4f63"
down_revision: Union[str, None] = "57d49404df32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("farmers", sa.Column("geo_lat", sa.Float(), nullable=True))
    op.add_column("farmers", sa.Column("geo_lng", sa.Float(), nullable=True))
    op.create_check_constraint(
        "ck_farmers_geo_pair",
        "farmers",
        "(geo_lat IS NULL) = (geo_lng IS NULL)",
    )
    op.create_check_constraint(
        "ck_farmers_geo_lat_range",
        "farmers",
        "geo_lat IS NULL OR geo_lat BETWEEN -90 AND 90",
    )
    op.create_check_constraint(
        "ck_farmers_geo_lng_range",
        "farmers",
        "geo_lng IS NULL OR geo_lng BETWEEN -180 AND 180",
    )
    op.create_check_constraint(
        "ck_farmers_geo_not_origin",
        "farmers",
        "geo_lat IS NULL OR NOT (geo_lat = 0 AND geo_lng = 0)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_farmers_geo_not_origin", "farmers", type_="check")
    op.drop_constraint("ck_farmers_geo_lng_range", "farmers", type_="check")
    op.drop_constraint("ck_farmers_geo_lat_range", "farmers", type_="check")
    op.drop_constraint("ck_farmers_geo_pair", "farmers", type_="check")
    op.drop_column("farmers", "geo_lng")
    op.drop_column("farmers", "geo_lat")
