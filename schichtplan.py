from flask import Blueprint, redirect, render_template, url_for, flash
from flask_login import login_required, current_user
from models import db, Schicht
from push_notifications import send_push_to_all

schichtplan_bp = Blueprint('schichtplan', __name__)


@schichtplan_bp.route('/schichtplan')
@login_required
def schichtplan():
    alle_schichten = Schicht.query.order_by(Schicht.datum, Schicht.uhrzeit).all()

    return render_template('schichtplan.html', schichten=alle_schichten)

@schichtplan_bp.route('/schicht_uebernehmen/<int:id>', methods=['POST'])
@login_required
def schicht_uebernehmen(id):
    schicht = db.session.get(Schicht, id)
    if schicht and schicht.leiter_id is None:
        bereits_eingetragen = Schicht.query.filter_by(
            event_name=schicht.event_name,
            datum=schicht.datum,
            uhrzeit=schicht.uhrzeit,
            leiter_id=current_user.id
        ).first()
        if bereits_eingetragen:
            flash("Du bist bereits für diese Schicht eingetragen.", "warning")
        else:
            schicht.leiter_id = current_user.id
            db.session.commit()
            flash("Du wurdest erfolgreich eingetragen.", "success")
    else:
        flash("Schicht wurde bereits übernommen.", "danger")



    return redirect(url_for('schichtplan.schichtplan'))

@schichtplan_bp.route('/schicht_abgeben/<int:schicht_id>', methods=['POST'])
@login_required
def schicht_abgeben(schicht_id):
    schicht = db.session.get(Schicht, schicht_id)
    if schicht and (schicht.leiter_id == current_user.id or current_user.ist_admin):
        schicht.leiter_id = None
        db.session.commit()
        send_push_to_all("Schicht frei", "Eine Schicht im Schichtplan ist frei geworden.", "/schichtplan")
        flash("Du wurdest erfolgreich ausgetragen.", "info")

    return redirect(url_for('schichtplan.schichtplan'))
