from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Todo, Gruppenleiter
from decorators import require_role
from push_notifications import send_push_to_user

todos_bp = Blueprint('todos', __name__)

@todos_bp.route('/todos')
@login_required
def todos():
    meine_todos = Todo.query.filter_by(leiter_id=current_user.id, erledigt=False).all()
    meine_erledigten = Todo.query.filter_by(leiter_id=current_user.id, erledigt=True).all()

    alle_leiter = []
    if current_user.ist_admin:
        alle_leiter = Gruppenleiter.query.order_by(Gruppenleiter.name).all()

    return render_template('todos.html',
        todos=meine_todos,
        erledigte=meine_erledigten,
        alle_leiter=alle_leiter
    )


@todos_bp.route('/todo_erledigt/<int:todo_id>', methods=['POST'])
@login_required
def todo_erledigt(todo_id):
    todo = db.session.get(Todo, todo_id)
    if not todo:
        flash("Aufgabe nicht gefunden.", "warning")
        return redirect(url_for('todos.todos'))
    if todo.leiter_id != current_user.id and not current_user.ist_admin:
        flash("Das ist nicht deine Aufgabe!", "danger")
        return redirect(url_for('todos.todos'))
    todo.erledigt = True
    db.session.commit()
    flash("Aufgabe als erledigt markiert.", "success")

    return redirect(url_for('todos.todos'))


@todos_bp.route('/todo_erstellen', methods=['POST'])
@login_required
@require_role('admin')
def todo_erstellen():
    aufgabe = (request.form.get('aufgabe') or '').strip()
    leiter_ids = request.form.getlist('leiter_ids')
    if not aufgabe:
        flash("Aufgabentext darf nicht leer sein.", "warning")
        return redirect(url_for('todos.todos'))
    if not leiter_ids:
        flash("Bitte mindestens einen Gruppenleiter auswählen.", "warning")
        return redirect(url_for('todos.todos'))

    quelle = f"Aufgabe von {current_user.name}"
    empfaenger = set()
    for lid in leiter_ids:
        try:
            leiter = db.session.get(Gruppenleiter, int(lid))
        except (ValueError, TypeError):
            continue
        if leiter:
            db.session.add(Todo(aufgabe=aufgabe, leiter_id=leiter.id, quelle=quelle, erledigt=False))
            empfaenger.add(leiter.id)
    db.session.commit()
    for lid in empfaenger:
        send_push_to_user(lid, "Neue Aufgabe", f"'{aufgabe}' wurde dir zugewiesen.", "/todos")
    flash("Aufgabe(n) erstellt.", "success")
    return redirect(url_for('todos.todos'))


@todos_bp.route('/todo_loeschen/<int:todo_id>', methods=['POST'])
@login_required
@require_role('admin')
def todo_loeschen(todo_id):
    todo = db.session.get(Todo, todo_id)
    if not todo:
        flash("Aufgabe nicht gefunden.", "warning")
        return redirect(url_for('todos.todos'))
    db.session.delete(todo)
    db.session.commit()
    flash("Aufgabe gelöscht.", "success")
    return redirect(url_for('todos.todos'))
