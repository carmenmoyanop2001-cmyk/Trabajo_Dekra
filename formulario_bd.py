"""Opciones del formulario obtenidas del catálogo XLSX cargado."""
import re
import tkinter as tk
from tkinter import ttk
from opciones_ensayo import slots_incluidos


def checks(parent, variables, columns=6):
    frame = ttk.Frame(parent)
    frame.pack(anchor='w', fill='x')
    for i, (label, variable) in enumerate(variables.items()):
        ttk.Checkbutton(frame, text=label, variable=variable).grid(row=i // columns, column=i % columns,
                                                                 sticky='w', padx=(0, 10), pady=2)


class PanelCatalogo(ttk.Frame):
    def __init__(self, master, nombre, catalogo, tech=None):
        super().__init__(master, padding=(24, 4))
        self.nombre, self.tech = nombre, tech or nombre
        self.bandas = {b: tk.BooleanVar() for b in catalogo.bandas(self.tech)}
        ttk.Label(self, text='Bandas disponibles en la base cargada:').pack(anchor='w')
        checks(self, self.bandas)
        modes = list(dict.fromkeys(str(r.params['mode']) for r in catalogo.by_tech[self.tech] if r.params.get('mode')))
        self.modos = {m: tk.BooleanVar() for m in modes}
        self.modos_libres = tk.StringVar()
        if modes:
            ttk.Label(self, text='Modos (sin marcar: se incluyen todos los de las bandas elegidas):').pack(anchor='w', pady=(5, 0))
            checks(self, self.modos)
        else:
            ttk.Label(self, text='La base no informa Mode. Puedes dejarlo vacío o indicar modos para este ensayo, separados por comas:',
                      foreground='#555555', wraplength=620).pack(anchor='w', pady=(4, 0))
            ttk.Entry(self, textvariable=self.modos_libres, width=55).pack(anchor='w')

    def seleccion(self):
        bands = [b for b, v in self.bandas.items() if v.get()]
        modes = [m for m, v in self.modos.items() if v.get()]
        if not self.modos:
            modes = list(dict.fromkeys(m.strip() for m in self.modos_libres.get().split(',') if m.strip()))
        return dict(bandas=bands, modos=modes) if modes else bands

    def validar(self):
        return [] if any(v.get() for v in self.bandas.values()) else [f'{self.nombre}: selecciona al menos una banda de la base.']

    def cargar(self, data):
        bands = data.get('bandas', []) if isinstance(data, dict) else data
        # Compatibilidad con las respuestas WLAN anteriores.
        if isinstance(data, dict) and 'bandas' not in data:
            bands = (['2.4 GHz'] if data.get('2,4 GHz') else []) + data.get('5 GHz', {}).get('bandas', [])
        for b, v in self.bandas.items():
            v.set(b in bands)
        for m, v in self.modos.items():
            v.set(isinstance(data, dict) and m in data.get('modos', []))
        if isinstance(data, dict):
            modes = data.get('modos', [])
            if '2,4 GHz' in data or '5 GHz' in data:
                modes = list(dict.fromkeys(data.get('2,4 GHz', []) + data.get('5 GHz', {}).get('modos', [])))
            self.modos_libres.set(', '.join(modes))

    def lineas(self):
        data = self.seleccion()
        return [str(data)]


class Panel2GCatalogo(ttk.Frame):
    def __init__(self, master, nombre, catalogo):
        super().__init__(master, padding=(24, 4))
        self.sel, self.slots = {}, {}
        bands = []
        for tech in catalogo.by_tech:
            if tech == 'GSM' or re.fullmatch(r'E?GPRS [1-4]TX', tech):
                bands.extend(catalogo.bandas(tech))
        for mode in ('GSM', 'GPRS', 'EGPRS'):
            if mode == 'GSM' and 'GSM' not in catalogo.by_tech:
                continue
            if mode != 'GSM' and not any(t.startswith(mode + ' ') for t in catalogo.by_tech):
                continue
            self.sel[mode] = tk.BooleanVar()
            ttk.Checkbutton(self, text=mode, variable=self.sel[mode]).pack(anchor='w')
            if mode != 'GSM':
                self.slots[mode] = {f'TX{n}': tk.BooleanVar() for n in range(1, 5)}
                f = ttk.Frame(self)
                f.pack(anchor='w', padx=18)
                for slot, variable in self.slots[mode].items():
                    ttk.Checkbutton(f, text=slot, variable=variable,
                        command=lambda m=mode, s=slot: self._cambiar(m, s)).pack(side='left', padx=4)
        ttk.Label(self, text='Bandas:').pack(anchor='w', pady=(6, 0))
        self.bandas = {b: tk.BooleanVar() for b in dict.fromkeys(bands)}
        checks(self, self.bandas)

    def _cambiar(self, mode, slot):
        n = int(slot[2:])
        checked = self.slots[mode][slot].get()
        for s, v in self.slots[mode].items():
            if checked and int(s[2:]) <= n:
                v.set(True)
            elif not checked and int(s[2:]) >= n:
                v.set(False)
        self.sel[mode].set(any(v.get() for v in self.slots[mode].values()))

    def seleccion(self):
        data = {'GSM': bool(self.sel.get('GSM') and self.sel['GSM'].get()),
                'bandas': [b for b, v in self.bandas.items() if v.get()]}
        for m in ('GPRS', 'EGPRS'):
            data[m] = [s for s, v in self.slots.get(m, {}).items() if v.get()] if self.sel.get(m) and self.sel[m].get() else None
        return data

    def validar(self):
        data = self.seleccion()
        errors = []
        if not any(data.get(m) for m in ('GSM', 'GPRS', 'EGPRS')):
            errors.append('2G: elige un modo y, para GPRS/EGPRS, sus slots.')
        if not data['bandas']:
            errors.append('2G: elige al menos una banda.')
        return errors

    def cargar(self, data):
        for m, variable in self.sel.items():
            variable.set(bool(data.get(m)))
        for m, variables in self.slots.items():
            active = slots_incluidos(data.get(m))
            for s, v in variables.items():
                v.set(s in active)
        for b, v in self.bandas.items():
            v.set(b in data.get('bandas', list(self.bandas)))

    def lineas(self):
        return [str(self.seleccion())]


class Panel3GCatalogo(ttk.Frame):
    def __init__(self, master, nombre, catalogo):
        super().__init__(master, padding=(24, 4))
        self.options = {}
        for tech in ('WCDMA', 'HSDPA', 'HSPA', 'HSPA+', 'DC-HSDPA'):
            if tech not in catalogo.by_tech:
                continue
            variable = tk.BooleanVar()
            panel = PanelCatalogo(self, tech, catalogo)
            ttk.Checkbutton(self, text=tech, variable=variable,
                command=lambda v=variable, p=panel: p.pack(fill='x') if v.get() else p.pack_forget()).pack(anchor='w')
            self.options[tech] = variable, panel

    def seleccion(self):
        return {t: p.seleccion() for t, (v, p) in self.options.items() if v.get()}

    def validar(self):
        return ([e for v, p in self.options.values() if v.get() for e in p.validar()]
                if self.seleccion() else ['3G: selecciona una tecnología y sus bandas.'])

    def cargar(self, data):
        for t, (v, p) in self.options.items():
            v.set(t in data)
            if t in data:
                p.cargar(data[t] if isinstance(data, dict) else list(p.bandas))
                p.pack(fill='x')

    def lineas(self):
        return [str(self.seleccion())]


def fabricas(catalogo):
    out = []
    if any(t == 'GSM' or re.fullmatch(r'E?GPRS [1-4]TX', t) for t in catalogo.by_tech):
        out.append(('2G', lambda m, n: Panel2GCatalogo(m, n, catalogo)))
    if any(t in catalogo.by_tech for t in ('WCDMA', 'HSDPA', 'HSPA', 'HSPA+', 'DC-HSDPA')):
        out.append(('3G', lambda m, n: Panel3GCatalogo(m, n, catalogo)))
    for tech in ['LTE', 'LTE CAT M1', 'LTE NB-IoT', '5G', 'WLAN', 'BT'] + [f'Custom{n}' for n in range(1, 9)]:
        if tech in catalogo.by_tech:
            out.append((tech, lambda m, n: PanelCatalogo(m, n, catalogo)))
    return out
