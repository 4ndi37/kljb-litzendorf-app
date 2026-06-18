from flask import Blueprint, render_template, redirect, request, url_for, flash
from flask_login import login_required
from models import db, Rezept, Zutat
from decorators import require_role

kueche_bp = Blueprint('kueche', __name__)


@kueche_bp.route('/kueche')
@login_required
@require_role('admin', 'kueche')
def kueche():

    alle_rezepte = Rezept.query.order_by(Rezept.name).all()
    return render_template('kueche.html', rezepte=alle_rezepte)


@kueche_bp.route('/rezept_speichern', methods=['POST'])
@login_required
@require_role('admin', 'kueche')
def rezept_speichern():
    try:
        standard_personen = int(request.form.get('standard_personen', 0))
    except ValueError:
        flash("Bitte eine gültige Zahl eingeben.")
        return redirect(url_for('kueche.kueche'))

    rezept = Rezept(
        name=request.form.get('name'),
        beschreibung=request.form.get('beschreibung'),
        standard_personen = standard_personen

    )
    db.session.add(rezept)
    db.session.commit()

    namen = request.form.getlist('zutat_name')
    mengen = request.form.getlist('zutat_menge')
    einheiten = request.form.getlist('zutat_einheit')

    for name, menge, einheit in zip(namen, mengen, einheiten):
        if name.strip():
            try:
                z = Zutat(name=name, menge=float(menge), einheit=einheit, rezept_id=rezept.id)
                db.session.add(z)
            except (ValueError, TypeError):
                flash(f"Zutat '{name}' wurde übersprungen (ungültige Menge).", "warning")
                continue

    db.session.commit()
    return redirect(url_for('kueche.kueche'))


@kueche_bp.route('/einkaufsliste', methods=['GET', 'POST'])
@login_required
@require_role('admin', 'kueche')
def einkaufsliste():
    alle_rezepte = Rezept.query.order_by(Rezept.name).all()
    einkaufsliste = []
    personen = 0

    if request.method == 'POST':
        try:
            kinder = int(request.form.get('kinder', 0))
            leiter = int(request.form.get('leiter', 0))
        except ValueError:
            flash("Bitte gültige Zahl eingeben.")
            return redirect(url_for('kueche.einkaufsliste'))
        personen = kinder + leiter
        ausgewaehlte_ids = request.form.getlist('rezept_ids')

        if personen == 0:
            flash("Bitte eine gültige Personenzahl eingeben.")
            return redirect(url_for('kueche.einkaufsliste'))
        for rid in ausgewaehlte_ids:
            rezept = db.session.get(Rezept, int(rid))
            if rezept and rezept.standard_personen > 0:
                faktor = personen / rezept.standard_personen
                for z in rezept.zutaten:
                    einkaufsliste.append({
                        'rezept': rezept.name,
                        'zutat': z.name,
                        'menge': round(z.menge * faktor, 1),
                        'einheit': z.einheit
                    })

    return render_template('einkaufsliste.html',
        rezepte=alle_rezepte,
        einkaufsliste=einkaufsliste,
        personen=personen
    )

@kueche_bp.route('/einkaufsliste_speichern', methods=['POST'])
@login_required
@require_role('admin', 'kueche')
def einkaufsliste_speichern():

    from models import EinkaufslisteGespeichert, EinkaufslisteEintrag
    name = request.form.get('liste_name')
    try:
        personen = int(request.form.get('personen'))
        eintraege_anzahl = int(request.form.get('eintraege_anzahl', 0))
    except ValueError:
        flash("Ungültige Eingabe.")
        return redirect(url_for('kueche.einkaufsliste'))

    neue_liste = EinkaufslisteGespeichert(name=name, personen=personen)
    db.session.add(neue_liste)
    db.session.commit()

    for i in range(eintraege_anzahl):
        try:
            menge = float(request.form.get(f'menge_{i}', 0))
        except ValueError:
            menge = 0.0
        eintrag = EinkaufslisteEintrag(
            rezept=request.form.get(f'rezept_{i}'),
            zutat=request.form.get(f'zutat_{i}'),
            menge=menge,
            einheit=request.form.get(f'einheit_{i}'),
            liste_id=neue_liste.id
        )
        db.session.add(eintrag)
    db.session.commit()
    return redirect(url_for('kueche.alle_einkaufslisten'))

@kueche_bp.route('/einkaufslisten')
@login_required
@require_role('admin', 'kueche')
def alle_einkaufslisten():
    from models import EinkaufslisteGespeichert
    listen = EinkaufslisteGespeichert.query.order_by(EinkaufslisteGespeichert.erstellt_am.desc()).all()
    return render_template('einkaufslisten_archiv.html', listen=listen)

@kueche_bp.route('/einkaufsliste_loeschen/<int:id>', methods=['POST'])
@login_required
@require_role('admin', 'kueche')
def einkaufsliste_loeschen(id):
    from models import EinkaufslisteGespeichert
    liste = db.session.get(EinkaufslisteGespeichert, id)
    if liste:
        db.session.delete(liste)
        db.session.commit()
    return redirect(url_for('kueche.alle_einkaufslisten'))
