from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Termin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    start = db.Column(db.Date)
    ende = db.Column(db.Date)
    ort = db.Column(db.String(100))
    startzeit = db.Column(db.String(5), nullable=True)
    typ = db.Column(db.String(50), default="sonstiges")
    leiter_id = db.Column(db.Integer, db.ForeignKey('gruppenleiter.id'), nullable=True)
    versteckt = db.Column(db.Boolean, default=False, nullable=False, server_default='0')

class Anwesenheit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    leiter_id = db.Column(db.Integer, db.ForeignKey('gruppenleiter.id'), nullable=False)
    termin_id = db.Column(db.Integer, db.ForeignKey('termin.id'), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    bemerkung = db.Column(db.String(200))
    leiter = db.relationship('Gruppenleiter')

konzept_leiter = db.Table('konzept_leiter',
                          db.Column('konzept_id', db.Integer, db.ForeignKey('konzept.id'), primary_key=True),
                          db.Column('leiter_id', db.Integer, db.ForeignKey('gruppenleiter.id'), primary_key=True)
                          )

class Konzept(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titel = db.Column(db.String(100), nullable=False)
    beschreibung = db.Column(db.Text)
    material = db.Column(db.Text)
    autoren = db.relationship('Gruppenleiter', secondary=konzept_leiter, backref='konzepte')
    auftritte = db.relationship('Programmpunkt', backref='konzept_info', lazy=True)

class Programmpunkt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tag = db.Column(db.String(50), nullable=False)
    uhrzeit = db.Column(db.String(10), nullable=False)
    ende = db.Column(db.String(10), nullable=False)
    termin_id = db.Column(db.Integer, db.ForeignKey('termin.id'), nullable=True)
    kategorie = db.Column(db.String(50), nullable=False, default="sonstiges")
    custom_titel = db.Column(db.String(100), nullable=True)
    konzept_id = db.Column(db.Integer, db.ForeignKey('konzept.id'), nullable=True)
    verantwortliche = db.Column(db.String(200), nullable=True)

class Protokoll(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    datum = db.Column(db.Date, nullable=False)
    schreiber = db.Column(db.String(100))
    anwesenheit = db.Column(db.Text)
    themen = db.relationship('ProtokollPunkt', backref='protokoll_parent', lazy=True)

class ProtokollPunkt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titel = db.Column(db.String(200), nullable=False)
    inhalt = db.Column(db.Text)
    protokoll_id = db.Column(db.Integer, db.ForeignKey('protokoll.id'), nullable=False)

class ProtokollEntwurfTop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titel = db.Column(db.String(200), nullable=False)
    inhalt = db.Column(db.Text)
    aufgaben_json = db.Column(db.Text, default='[]')

    @property
    def aufgaben(self):
        from json import loads
        try:
            return loads(self.aufgaben_json or '[]')
        except Exception:
            return []

class Info(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nachricht = db.Column(db.Text, nullable=False)
    zeitstempel = db.Column(db.DateTime, default=db.func.now())

class Gruppenleiter(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    passwort_hash = db.Column(db.String(128))
    ist_admin = db.Column(db.Boolean, default=False)
    todos = db.relationship('Todo', backref='besitzer', lazy=True)
    ist_kueche = db.Column(db.Boolean, default=False)
    muss_passwort_aendern = db.Column(db.Boolean, default=False)
    fehlversuche = db.Column(db.Integer, default=0)
    gesperrt_bis = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.passwort_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.passwort_hash, password)

    @property
    def ist_gesperrt(self):
        from datetime import datetime
        return self.gesperrt_bis is not None and self.gesperrt_bis > datetime.utcnow()

class Einstellung(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    wert = db.Column(db.String(50))

class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    aufgabe = db.Column(db.Text, nullable=False)
    erledigt = db.Column(db.Boolean, default=False)
    quelle = db.Column(db.String(200))
    leiter_id = db.Column(db.Integer, db.ForeignKey('gruppenleiter.id'), nullable=True)

class Abstimmungsantwort(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    leiter_id = db.Column(db.Integer, db.ForeignKey('gruppenleiter.id'), nullable=False)
    termin_id = db.Column(db.Integer, db.ForeignKey('termin.id'), nullable=False)
    antwort = db.Column(db.String(10), nullable=False)  # 'ja' oder 'nein'
    leiter = db.relationship('Gruppenleiter')

class Schicht(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_name = db.Column(db.String(100))
    datum = db.Column(db.Date)
    uhrzeit = db.Column(db.String(50))
    leiter_id = db.Column(db.Integer, db.ForeignKey('gruppenleiter.id'), nullable=True)
    besitzer = db.relationship('Gruppenleiter', backref='meine_schichten')

class Rezept(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    beschreibung = db.Column(db.Text)
    standard_personen = db.Column(db.Integer, nullable=False)
    zutaten = db.relationship('Zutat', backref='rezept', lazy=True, cascade='all, delete-orphan')

class Zutat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    menge = db.Column(db.Float, nullable=False)
    einheit = db.Column(db.String(20), nullable=False)
    rezept_id = db.Column(db.Integer, db.ForeignKey('rezept.id'), nullable=False)

class EinkaufslisteGespeichert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    personen = db.Column(db.Integer, nullable=False)
    erstellt_am = db.Column(db.DateTime, default=db.func.now())
    eintraege = db.relationship('EinkaufslisteEintrag', backref='liste', lazy=True, cascade='all, delete-orphan')

class EinkaufslisteEintrag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rezept = db.Column(db.String(100), nullable=False)
    zutat = db.Column(db.String(100), nullable=False)
    menge = db.Column(db.Float, nullable=False)
    einheit = db.Column(db.String(20), nullable=False)
    liste_id = db.Column(db.Integer, db.ForeignKey('einkaufsliste_gespeichert.id'), nullable=False)


block_leiter = db.Table('block_leiter',
    db.Column('block_id', db.Integer, db.ForeignKey('programmblock.id'), primary_key=True),
    db.Column('leiter_id', db.Integer, db.ForeignKey('gruppenleiter.id'), primary_key=True)
)

class Programmblock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titel = db.Column(db.String(100), nullable=False)
    beschreibung = db.Column(db.Text, nullable=True)
    termin_id = db.Column(db.Integer, db.ForeignKey('termin.id'), nullable=False)
    tag = db.Column(db.String(50), nullable=False)
    zeit_von = db.Column(db.String(10), nullable=True)
    zeit_bis = db.Column(db.String(10), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='entwurf')
    erstellt_am = db.Column(db.DateTime, default=db.func.now())
    zugewiesene_leiter = db.relationship('Gruppenleiter', secondary=block_leiter, backref='bloecke')
    punkte = db.relationship('Blockpunkt', backref='block', lazy=True,
                             cascade='all, delete-orphan', order_by='Blockpunkt.reihenfolge')

class Blockpunkt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    block_id = db.Column(db.Integer, db.ForeignKey('programmblock.id', ondelete='CASCADE'), nullable=False)
    uhrzeit = db.Column(db.String(10), nullable=False)
    ende = db.Column(db.String(10), nullable=False)
    custom_titel = db.Column(db.String(100), nullable=False)
    kategorie = db.Column(db.String(50), nullable=False, default='sonstiges')
    konzept_id = db.Column(db.Integer, db.ForeignKey('konzept.id'), nullable=True)
    notiz = db.Column(db.String(200), nullable=True)
    reihenfolge = db.Column(db.Integer, default=0)
    konzept_info = db.relationship('Konzept', backref='blockpunkt_einsaetze')


class PushSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    leiter_id = db.Column(db.Integer, db.ForeignKey('gruppenleiter.id'), nullable=False)
    endpoint = db.Column(db.Text, nullable=False, unique=True)
    p256dh = db.Column(db.Text, nullable=False)
    auth = db.Column(db.Text, nullable=False)
    erstellt_am = db.Column(db.DateTime, default=db.func.now())

