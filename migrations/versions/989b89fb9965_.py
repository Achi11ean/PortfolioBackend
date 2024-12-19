"""empty message

Revision ID: 989b89fb9965
Revises: f3de0500f896
Create Date: 2024-12-17 23:53:14.202576

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '989b89fb9965'
down_revision = 'f3de0500f896'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('contact', schema=None) as batch_op:
        batch_op.add_column(sa.Column('price', sa.Float(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('contact', schema=None) as batch_op:
        batch_op.drop_column('price')

    # ### end Alembic commands ###
