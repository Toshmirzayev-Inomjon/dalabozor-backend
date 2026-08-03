"""one role per account: dedupe user_roles and enforce single role

Bitta akkaunt — bitta rol qoidasini ma'lumotlar bazasi darajasida
kafolatlaymiz: eski ko'p rolli akkauntlarni bitta rolda qoldiramiz
(eng yuqori imtiyoz saqlanadi), so'ng user_id ustuniga unique
constraint qo'shamiz.

Revision ID: a1b2c3d4e5f6
Revises: dcf3a927984b
Create Date: 2026-08-03 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "dcf3a927984b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Eski ko'p rolli akkauntlar: bir xil user uchun imtiyoz pastligi bo'yicha
    # faqat eng yuqori rol qoldiriladi (admin > collector > restaurant > farmer).
    op.execute(
        sa.text(
            """
            DELETE FROM user_roles ur
            USING user_roles keep
            WHERE ur.user_id = keep.user_id
              AND ur.id <> keep.id
              AND CASE ur.role
                    WHEN 'admin' THEN 4
                    WHEN 'collector' THEN 3
                    WHEN 'restaurant' THEN 2
                    ELSE 1
                  END
                  <
                  CASE keep.role
                    WHEN 'admin' THEN 4
                    WHEN 'collector' THEN 3
                    WHEN 'restaurant' THEN 2
                    ELSE 1
                  END
            """
        )
    )
    # Endi bitta user'da bitta qator bor — unique constraint buni kafolatlaydi.
    op.create_unique_constraint(
        "uq_user_roles_one_role_per_user", "user_roles", ["user_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_user_roles_one_role_per_user", "user_roles", type_="unique")
