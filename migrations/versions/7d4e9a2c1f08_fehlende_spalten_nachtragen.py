"""Fehlende Spalten nachtragen: termin.versteckt + gruppenleiter Login-Felder

Holt Modell-Spalten in die Migrationshistorie nach, die seinerzeit direkt in
models.py ergaenzt wurden, ohne dass eine Migration entstand:
  - termin.versteckt
  - gruppenleiter.muss_passwort_aendern
  - gruppenleiter.fehlversuche
  - gruppenleiter.gesperrt_bis

Bewusst IDEMPOTENT: In Umgebungen, in denen die Spalten bereits existieren
(lokal wie produktiv), wird nichts erneut hinzugefuegt. Damit ist
`flask db upgrade` ueberall gefahrlos. Setzt eine bestehende Online-DB voraus
(passend zum create_all-basierten Schema dieses Projekts).

Revision ID: 7d4e9a2c1f08
Revises: 91619d5f7491
Create Date: 2026-06-18

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7d4e9a2c1f08'
down_revision = '91619d5f7491'
branch_labels = None
depends_on = None


def _spalten(tabelle):
    """Namen der vorhandenen Spalten einer Tabelle (fuer Idempotenz)."""
    insp = sa.inspect(op.get_bind())
    return {c['name'] for c in insp.get_columns(tabelle)}


def upgrade():
    termin = _spalten('termin')
    if 'versteckt' not in termin:
        op.add_column('termin', sa.Column(
            'versteckt', sa.Boolean(), nullable=False, server_default='0'))

    gl = _spalten('gruppenleiter')
    if 'muss_passwort_aendern' not in gl:
        op.add_column('gruppenleiter', sa.Column(
            'muss_passwort_aendern', sa.Boolean(), nullable=True, server_default='0'))
    if 'fehlversuche' not in gl:
        op.add_column('gruppenleiter', sa.Column(
            'fehlversuche', sa.Integer(), nullable=True, server_default='0'))
    if 'gesperrt_bis' not in gl:
        op.add_column('gruppenleiter', sa.Column(
            'gesperrt_bis', sa.DateTime(), nullable=True))


def downgrade():
    # Spalten loeschen -> bei SQLite Batch-Modus (Tabelle wird neu erzeugt)
    gl = _spalten('gruppenleiter')
    drops = [c for c in ('gesperrt_bis', 'fehlversuche', 'muss_passwort_aendern') if c in gl]
    if drops:
        with op.batch_alter_table('gruppenleiter') as batch:
            for c in drops:
                batch.drop_column(c)

    if 'versteckt' in _spalten('termin'):
        with op.batch_alter_table('termin') as batch:
            batch.drop_column('versteckt')
