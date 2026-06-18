from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Gruppenleiter, Schicht
from datetime import datetime, timedelta, date
import os
from decorators import require_role
from push_notifications import send_push_to_all

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/leiter_verwalten', methods=['GET', 'POST'])
@login_required
@require_role('admin')
def leiter_verwalten():
    alle_leiter = Gruppenleiter.query.order_by(Gruppenleiter.name).all()
    return render_template('leiter_verwalten.html', leiter=alle_leiter)

@admin_bp.route('/leiter_anlegen', methods=['POST'])
@login_required
@require_role('admin')
def leiter_anlegen():
    name = request.form.get('name', '').strip()
    passwort = request.form.get('passwort')
    rolle = request.form.get('rolle')

    if not name:
        flash("Name darf nicht leer sein.", "warning")
        return redirect(url_for('admin.leiter_verwalten'))

    if rolle not in ('leiter', 'kueche', 'admin'):
        flash("Ungültige Rolle.", "warning")
        return redirect(url_for('admin.leiter_verwalten'))

    if Gruppenleiter.query.filter_by(name=name).first():
        flash("Name existiert bereits!", "warning")
        return redirect(url_for('admin.leiter_verwalten'))

    neuer_leiter = Gruppenleiter(name=name, ist_admin=(rolle == 'admin'), ist_kueche=(rolle == 'kueche'))
    if not passwort or len(passwort) < 12:
        flash("Passwort muss mindestens 12 Zeichen haben.", "warning")
        return redirect(url_for('admin.leiter_verwalten'))
    neuer_leiter.set_password(passwort)
    neuer_leiter.muss_passwort_aendern = True
    db.session.add(neuer_leiter)
    db.session.commit()
    flash(f"Leiter '{name}' wurde angelegt.", "success")
    return redirect(url_for('admin.leiter_verwalten'))

@admin_bp.route('/leiter_rolle_aendern/<int:id>', methods=['POST'])
@login_required
@require_role('admin')
def leiter_rolle_aendern(id):
    leiter = db.session.get(Gruppenleiter, id)
    if not leiter:
        flash("Leiter nicht gefunden.", "warning")
        return redirect(url_for('admin.leiter_verwalten'))
    if leiter.id == current_user.id:
        flash("Du kannst deine eigene Rolle nicht ändern.", "warning")
        return redirect(url_for('admin.leiter_verwalten'))
    rolle = request.form.get('rolle')
    if rolle not in ('leiter', 'kueche', 'admin'):
        flash("Ungültige Rolle.", "warning")
        return redirect(url_for('admin.leiter_verwalten'))
    leiter.ist_admin  = (rolle == 'admin')
    leiter.ist_kueche = (rolle == 'kueche')
    db.session.commit()
    flash(f"Rolle von '{leiter.name}' wurde geändert.", "success")
    return redirect(url_for('admin.leiter_verwalten'))

@admin_bp.route('/leiter_loeschen/<int:id>', methods=['POST'])
@login_required
@require_role('admin')
def leiter_loeschen(id):
    leiter = db.session.get(Gruppenleiter, id)
    if not leiter:
        flash("Benutzer nicht gefunden.", "warning")
        return redirect(url_for('admin.leiter_verwalten'))
    if leiter.id == current_user.id:
        flash("Du kannst dich nicht selbst löschen.", "warning")
        return redirect(url_for('admin.leiter_verwalten'))
    db.session.delete(leiter)
    db.session.commit()
    flash(f"Leiter '{leiter.name}' wurde gelöscht.", "success")
    return redirect(url_for('admin.leiter_verwalten'))


@admin_bp.route('/schichten_generieren', methods=['POST'])
@login_required
@require_role('admin')
def schichten_generieren():
    event = request.form.get('event_name')
    start_str = request.form.get('start_zeit')
    ende_str = request.form.get('ende_zeit')
    try:
        datum = date.fromisoformat(request.form.get('datum'))
        stunden_eingabe = float(request.form.get('stunden'))
        personen_pro_schicht = int(request.form.get('personen', 1))
    except (ValueError, TypeError):
        flash("Ungültige Eingabe für Stunden, Personen oder Datum.", "danger")
        return redirect(url_for('admin.schichtplan_admin'))
    intervall_minuten = int(stunden_eingabe * 60)
    if intervall_minuten <= 0:
        flash("Schichtdauer muss größer als 0 sein.", "warning")
        return redirect(url_for('admin.schichtplan_admin'))

    zeit_format = "%H:%M"
    aktuelle_zeit = datetime.strptime(start_str, zeit_format)
    ende_zeit = datetime.strptime(ende_str, zeit_format)

    while aktuelle_zeit < ende_zeit:
        naechste_zeit = aktuelle_zeit + timedelta(minutes=intervall_minuten)
        if naechste_zeit > ende_zeit: naechste_zeit = ende_zeit
        zeit_label = f"{aktuelle_zeit.strftime(zeit_format)} - {naechste_zeit.strftime(zeit_format)}"
        for _ in range(personen_pro_schicht):
            neue_schicht = Schicht(event_name=event, datum=datum, uhrzeit=zeit_label)
            db.session.add(neue_schicht)
        aktuelle_zeit = naechste_zeit

    db.session.commit()
    send_push_to_all("Neuer Schichtplan", "Ein neuer Schichtplan wurde erstellt.", "/schichtplan")
    return redirect(url_for('admin.admin_konsole'))


@admin_bp.route('/schicht_loeschen/<int:schicht_id>', methods=['POST'])
@login_required
@require_role('admin')
def schicht_loeschen(schicht_id):
    schicht = db.session.get(Schicht, schicht_id)
    if schicht:
        db.session.delete(schicht)
        db.session.commit()
    return redirect(url_for('admin.schichtplan_admin'))

@admin_bp.route('/schichtplan_leeren', methods=['POST'])
@login_required
@require_role('admin')
def schichtplan_leeren():
    Schicht.query.delete()
    db.session.commit()
    return redirect(url_for('admin.admin_konsole'))

@admin_bp.route('/schichtplan_admin')
@login_required
@require_role('admin')
def schichtplan_admin():
    alle_schichten = Schicht.query.order_by(Schicht.datum, Schicht.uhrzeit).all()
    return render_template('schichtplan_admin.html', schichten=alle_schichten)

@admin_bp.route('/admin_konsole')
@login_required
@require_role('admin')
def admin_konsole():
    return render_template('admin_konsole.html')

@admin_bp.route('/passwort_reset/<int:id>', methods=['POST'])
@login_required
@require_role('admin')
def passwort_reset(id):
    leiter = db.session.get(Gruppenleiter, id)
    standard_pw = os.getenv('STANDARD_PASSWORT')
    if not standard_pw:
        flash("STANDARD_PASSWORT nicht konfiguriert.", "danger")
        return redirect(url_for('admin.leiter_verwalten'))
    if not leiter:
        flash("Leiter nicht gefunden.", "warning")
        return redirect(url_for('admin.leiter_verwalten'))
    leiter.set_password(standard_pw)
    leiter.muss_passwort_aendern = True
    db.session.commit()
    flash(f"Passwort für {leiter.name} wurde erfolgreich zurückgesetzt.", "success")
    return redirect(url_for('admin.leiter_verwalten'))


@admin_bp.route('/leiter_entsperren/<int:id>', methods=['POST'])
@login_required
@require_role('admin')
def leiter_entsperren(id):
    leiter = db.session.get(Gruppenleiter, id)
    if not leiter:
        flash("Leiter nicht gefunden.", "warning")
        return redirect(url_for('admin.leiter_verwalten'))
    leiter.fehlversuche = 0
    leiter.gesperrt_bis = None
    db.session.commit()
    flash(f"{leiter.name} wurde entsperrt.", "success")
    return redirect(url_for('admin.leiter_verwalten'))


@admin_bp.route('/erster_admin_setup')
def erster_admin_setup():
    if os.getenv('SETUP_ERLAUBT') != 'ja':
        return "Setup deaktiviert.", 403
    if Gruppenleiter.query.filter_by(ist_admin=True).first():
        return "Es existiert bereits ein Admin. Route gesperrt!"
    admin_name = os.getenv('ADMIN_NAME', 'Admin')
    admin_passwort = os.getenv('ADMIN_PASSWORT')
    if not admin_passwort:
        return "ADMIN_PASSWORT nicht konfiguriert.", 500
    neuer_admin = Gruppenleiter(name=admin_name, ist_admin=True)
    neuer_admin.set_password(admin_passwort)
    db.session.add(neuer_admin)
    db.session.commit()
    return f"Admin '{admin_name}' angelegt. Login möglich."

