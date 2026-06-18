from flask import Blueprint, render_template, redirect, request, url_for, flash
from flask_login import login_required, current_user
from models import db, Termin, Konzept, Programmpunkt, Gruppenleiter
from decorators import require_role

konzepte_bp = Blueprint('konzepte', __name__)


@konzepte_bp.route('/konzept_loeschen/<int:id>', methods=['POST'])
@login_required
@require_role('admin')
def konzept_loeschen(id):
    konzept = db.session.get(Konzept, id)
    if not konzept:
        flash("Konzept nicht gefunden.", "warning")
        return redirect(url_for('konzepte.spiele_datenbank'))
    db.session.delete(konzept)
    db.session.commit()
    return redirect(url_for('konzepte.spiele_datenbank'))


@konzepte_bp.route('/spiele_datenbank')
@login_required
def spiele_datenbank():
    alle_konzepte = Konzept.query.order_by(Konzept.titel).all()

    einsaetze_pro_konzept = {}
    for k in alle_konzepte:
        termine_names = []
        seen_termin_ids = set()
        for pp in k.auftritte:
            if pp.termin_id and pp.termin_id not in seen_termin_ids:
                seen_termin_ids.add(pp.termin_id)
                termin = db.session.get(Termin, pp.termin_id)
                if termin:
                    termine_names.append(termin.name)
        einsaetze_pro_konzept[k.id] = termine_names

    return render_template('spiele_datenbank.html',
                           konzepte=alle_konzepte,
                           einsaetze_pro_konzept=einsaetze_pro_konzept)

@konzepte_bp.route('/konzept_speichern', methods=['POST'])
@login_required
def konzept_speichern():
    neues_konzept = Konzept(
        titel = request.form.get('titel'),
        beschreibung = request.form.get('beschreibung'),
        material = request.form.get('material'),
    )
    leiter_ids = request.form.getlist('leiter_ids')
    for lid in leiter_ids:
        try:
            leiter = db.session.get(Gruppenleiter, int(lid))
            if leiter:
                neues_konzept.autoren.append(leiter)
        except (ValueError, TypeError):
            continue
    db.session.add(neues_konzept)
    db.session.commit()
    return redirect(url_for('konzepte.spiele_datenbank'))

@konzepte_bp.route('/konzept_neu')
@login_required
def konzept_erstellen():
    alle_leiter = Gruppenleiter.query.order_by(Gruppenleiter.name).all()
    return render_template('konzept_erstellen.html', leiter_liste=alle_leiter)



@konzepte_bp.route('/packliste/<int:termin_id>/<tag>')
@login_required
def packliste(termin_id, tag):
    punkte = Programmpunkt.query.filter_by(termin_id=termin_id, tag=tag).all()
    termin = db.session.get(Termin, termin_id)
    material_sammlung = []
    for p in punkte:
        if p.konzept_info:
            bedarf = p.konzept_info.material if p.konzept_info.material else "Kein Material eingetragen"
            material_sammlung.append({"spiel": p.konzept_info.titel, "sachen": bedarf, "zeit": p.uhrzeit})
    return render_template('packliste.html', tag=tag, materialien=material_sammlung, event_name=termin.name)
