from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user

def require_role(*rollen):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Zugriff verweigert.", "danger")
                return redirect(url_for('index'))
            if not any(getattr(current_user, f'ist_{rolle}', False) for rolle in rollen):
                flash("Zugriff verweigert.", "danger")
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator
