"""update3

Revision ID: 93b865e121f4
Revises: b06e6f50e96c
Create Date: 2024-02-20 05:52:30.060676

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '93b865e121f4'
down_revision: Union[str, None] = 'b06e6f50e96c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('collection',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('href', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('sold_percentage', sa.Float(), nullable=True),
    sa.Column('total_stock', sa.Integer(), nullable=True),
    sa.Column('sold_stock', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('href')
    )
    op.create_table('tracking',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('time', sa.DateTime(), nullable=True),
    sa.Column('sold_to_time', sa.Integer(), nullable=True),
    sa.Column('collection_href', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['collection_href'], ['collection.href'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('tracking')
    op.drop_table('collection')
    # ### end Alembic commands ###
