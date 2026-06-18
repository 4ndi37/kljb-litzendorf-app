"""Convert tag weekday names to ISO dates

Revision ID: 91619d5f7491
Revises: 8606f0e25c34
Create Date: 2026-04-20 14:57:54.580216

"""
from alembic import op
import sqlalchemy as sa
from datetime import date, timedelta

# revision identifiers, used by Alembic.
revision = '91619d5f7491'
down_revision = '8606f0e25c34'
branch_labels = None
depends_on = None

TAGE_DE = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']


def _wochentag_zu_iso(tag_name, termin_start_str):
    """Converts a German weekday name to the ISO date within the event's week."""
    if not tag_name or not termin_start_str:
        return tag_name
    if len(tag_name) == 10 and tag_name[4] == '-':
        return tag_name  # already ISO
    try:
        target_wd = TAGE_DE.index(tag_name)
    except ValueError:
        return tag_name
    try:
        start = date.fromisoformat(str(termin_start_str)[:10])
    except ValueError:
        return tag_name
    days_ahead = (target_wd - start.weekday()) % 7
    return (start + timedelta(days=days_ahead)).isoformat()


def _iso_zu_wochentag(iso_str):
    """Converts ISO date string back to German weekday name."""
    try:
        d = date.fromisoformat(str(iso_str)[:10])
        return TAGE_DE[d.weekday()]
    except (ValueError, TypeError):
        return iso_str


def upgrade():
    conn = op.get_bind()

    rows = conn.execute(sa.text(
        "SELECT pp.id, pp.tag, t.start FROM programmpunkt pp "
        "JOIN termin t ON pp.termin_id = t.id"
    )).fetchall()
    for row_id, tag, termin_start in rows:
        new_tag = _wochentag_zu_iso(tag, termin_start)
        if new_tag != tag:
            conn.execute(sa.text("UPDATE programmpunkt SET tag = :t WHERE id = :i"),
                         {"t": new_tag, "i": row_id})

    rows = conn.execute(sa.text(
        "SELECT pb.id, pb.tag, t.start FROM programmblock pb "
        "JOIN termin t ON pb.termin_id = t.id"
    )).fetchall()
    for row_id, tag, termin_start in rows:
        new_tag = _wochentag_zu_iso(tag, termin_start)
        if new_tag != tag:
            conn.execute(sa.text("UPDATE programmblock SET tag = :t WHERE id = :i"),
                         {"t": new_tag, "i": row_id})


def downgrade():
    conn = op.get_bind()

    for table in ('programmpunkt', 'programmblock'):
        rows = conn.execute(sa.text(f"SELECT id, tag FROM {table}")).fetchall()
        for row_id, tag in rows:
            old_tag = _iso_zu_wochentag(tag)
            if old_tag != tag:
                conn.execute(sa.text(f"UPDATE {table} SET tag = :t WHERE id = :i"),
                             {"t": old_tag, "i": row_id})
