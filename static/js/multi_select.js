class MultiSelect {
    constructor(containerId, options, fieldName, placeholder) {
        this.options = options;
        this.fieldName = fieldName;
        this.selected = [];
        this.container = document.getElementById(containerId);
        if (!this.container) return;
        this._buildDOM(placeholder || 'Name tippen...');
        this._bindEvents();
    }

    _buildDOM(placeholder) {
        this.box = document.createElement('div');
        this.box.className = 'ms-box';

        this.chipsEl = document.createElement('div');
        this.chipsEl.className = 'ms-chips';

        this.searchEl = document.createElement('input');
        this.searchEl.type = 'text';
        this.searchEl.className = 'ms-search';
        this.searchEl.placeholder = placeholder;
        this.searchEl.setAttribute('autocomplete', 'off');
        this.searchEl.setAttribute('autocorrect', 'off');
        this.searchEl.setAttribute('autocapitalize', 'off');
        this.searchEl.setAttribute('spellcheck', 'false');

        this.box.appendChild(this.chipsEl);
        this.box.appendChild(this.searchEl);

        this.dropdownEl = document.createElement('ul');
        this.dropdownEl.className = 'ms-dropdown hidden';

        this.container.appendChild(this.box);
        this.container.appendChild(this.dropdownEl);
    }

    _bindEvents() {
        this.box.addEventListener('click', () => this.searchEl.focus());

        this.searchEl.addEventListener('input', () => {
            this._renderDropdown(this.searchEl.value);
        });

        this.searchEl.addEventListener('focus', () => {
            this._renderDropdown(this.searchEl.value);
        });

        this.searchEl.addEventListener('keydown', (e) => {
            if (e.key === 'Backspace' && this.searchEl.value === '' && this.selected.length > 0) {
                this._removeItem(this.selected[this.selected.length - 1].id);
            }
        });

        if (!MultiSelect._docListenerAdded) {
            MultiSelect._docListenerAdded = true;
            document.addEventListener('click', (e) => {
                document.querySelectorAll('.ms-container').forEach(c => {
                    if (!c.contains(e.target)) {
                        const dd = c.querySelector('.ms-dropdown');
                        if (dd) dd.classList.add('hidden');
                    }
                });
            });
        }
    }

    _renderDropdown(filter) {
        const lower = filter.toLowerCase();
        const filtered = this.options.filter(o =>
            o.name.toLowerCase().includes(lower) &&
            !this.selected.some(s => s.id === o.id)
        );

        this.dropdownEl.innerHTML = '';

        if (filtered.length === 0) {
            const li = document.createElement('li');
            li.className = 'ms-empty';
            if (filter) {
                li.textContent = 'Keine Ergebnisse';
            } else {
                li.textContent = this.selected.length > 0 ? 'Alle ausgewählt' : 'Keine Einträge';
            }
            this.dropdownEl.appendChild(li);
        } else {
            filtered.forEach(opt => {
                const li = document.createElement('li');
                li.className = 'ms-option';
                li.textContent = opt.name;
                li.addEventListener('mousedown', (e) => {
                    e.preventDefault();
                    this._addItem(opt);
                });
                this.dropdownEl.appendChild(li);
            });
        }

        this.dropdownEl.classList.remove('hidden');
    }

    _addItem(opt) {
        this.selected.push(opt);
        this.searchEl.value = '';
        this._renderChips();
        this._syncInputs();
        this._renderDropdown('');
        this.searchEl.focus();
    }

    _removeItem(id) {
        this.selected = this.selected.filter(s => s.id !== id);
        this._renderChips();
        this._syncInputs();
        this._renderDropdown(this.searchEl.value);
    }

    _renderChips() {
        this.chipsEl.innerHTML = '';
        this.selected.forEach(opt => {
            const chip = document.createElement('div');
            chip.className = 'ms-chip';

            const nameSpan = document.createElement('span');
            nameSpan.textContent = opt.name;

            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'ms-chip-remove';
            btn.textContent = '×';
            btn.setAttribute('aria-label', 'Entfernen');
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this._removeItem(opt.id);
            });

            chip.appendChild(nameSpan);
            chip.appendChild(btn);
            this.chipsEl.appendChild(chip);
        });
    }

    _syncInputs() {
        if (!this.fieldName) return;
        this.container.querySelectorAll('input[type="hidden"]').forEach(el => el.remove());
        this.selected.forEach(opt => {
            const inp = document.createElement('input');
            inp.type = 'hidden';
            inp.name = this.fieldName;
            inp.value = opt.id;
            this.container.appendChild(inp);
        });
    }

    preselectById(ids) {
        ids.forEach(id => {
            const opt = this.options.find(o => o.id === id);
            if (opt && !this.selected.some(s => s.id === id)) {
                this._addItem(opt);
            }
        });
    }

    clearSelection() {
        this.selected = [];
        this._renderChips();
        this._syncInputs();
    }

    getSelectedIds()   { return this.selected.map(s => s.id); }
    getSelectedNames() { return this.selected.map(s => s.name); }
}
