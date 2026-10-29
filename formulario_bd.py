"""Formulario con opciones de banda visibles bajo cada tecnología."""
import tkinter as tk
from tkinter import ttk
from entradas_bandas import banda_base_5g
from opciones_ensayo import slots_incluidos
from configuracion import OPCIONES_2G, OPCIONES_3G, VARIANTES_5G


class SelectorBandas(ttk.Frame):
    """Casillas visibles y repartidas en filas según el espacio disponible."""
    def __init__(self, master, nombre, disponibles):
        super().__init__(master, padding=(0, 4))
        self.nombre = nombre
        self.al_cambiar = None
        self.variables, self.casillas = {}, {}
        self.no_disponibles = []
        ttk.Label(self, text='Bandas:').pack(anchor='w')
        self.opciones = ttk.Frame(self)
        self.opciones.pack(fill='x', pady=(3, 0))
        self.opciones.bind('<Configure>', self._distribuir)
        self.estado = ttk.Label(self, foreground='#B00020', wraplength=570)
        self.actualizar(disponibles)

    def _distribuir(self, _evento=None):
        width = self.opciones.winfo_width()
        if width <= 1:
            width = 550
        cell_width = max((c.winfo_reqwidth() + 16 for c in self.casillas.values()), default=1)
        columns = max(1, width // cell_width)
        for index, check in enumerate(self.casillas.values()):
            check.grid(row=index // columns, column=index % columns,
                       sticky='w', padx=(0, 16), pady=2)

    def _aviso(self):
        if self.no_disponibles:
            self.estado.configure(text='Bandas no disponibles: ' + ', '.join(self.no_disponibles) +
                                  '. Elige de nuevo entre las opciones mostradas.')
            self.estado.pack(anchor='w', pady=(3, 0))
        elif not self.disponibles:
            self.estado.configure(text='La base no contiene bandas para esta opción.')
            self.estado.pack(anchor='w', pady=(3, 0))
        else:
            self.estado.pack_forget()

    def actualizar(self, disponibles):
        selected = self.seleccion() + self.no_disponibles
        self.disponibles = list(dict.fromkeys(disponibles))
        for child in self.opciones.winfo_children():
            child.destroy()
        self.variables, self.casillas = {}, {}
        for band in self.disponibles:
            variable = self.variables[band] = tk.BooleanVar(self, value=band in selected)
            self.casillas[band] = ttk.Checkbutton(self.opciones, text=band, variable=variable,
                                                 command=self._cambiar)
        self.no_disponibles = [b for b in selected if b not in self.variables]
        self._distribuir()
        self._aviso()

    def _cambiar(self):
        self.no_disponibles = []
        self._aviso()
        if self.al_cambiar:
            self.al_cambiar()

    def seleccion(self):
        return [b for b, v in self.variables.items() if v.get()]

    def validar(self):
        if self.no_disponibles:
            return [f'{self.nombre}: bandas no disponibles: ' + ', '.join(self.no_disponibles) + '.']
        return [] if self.seleccion() else [f'{self.nombre}: selecciona al menos una banda.']

    def cargar(self, bands):
        for band, variable in self.variables.items():
            variable.set(band in bands)
        self.no_disponibles = [b for b in bands if b not in self.variables]
        self._aviso()
        if self.al_cambiar:
            self.al_cambiar()


class PanelCatalogo(ttk.Frame):
    def __init__(self, master, nombre, catalogo, tech=None):
        super().__init__(master, padding=(24, 4))
        self.nombre, self.tech = nombre, tech or nombre
        self.entrada = SelectorBandas(self, nombre, catalogo.bandas(self.tech))
        self.entrada.pack(fill='x')
        self.modos_guardados = []
        self.lbl_modos = ttk.Label(self, foreground='#555555', wraplength=570)

    def seleccion(self):
        bands = self.entrada.seleccion()
        return dict(bandas=bands, modos=list(self.modos_guardados)) if self.modos_guardados else bands

    def validar(self):
        return self.entrada.validar()

    def cargar(self, data):
        bands = data.get('bandas', []) if isinstance(data, dict) else data
        self.entrada.cargar(bands)
        self.modos_guardados = list(data.get('modos', [])) if isinstance(data, dict) else []
        if self.modos_guardados:
            self.lbl_modos.configure(text='Modos de las respuestas cargadas: ' + ', '.join(self.modos_guardados))
            self.lbl_modos.pack(anchor='w')

    def lineas(self):
        return ['Bandas: ' + ', '.join(self.entrada.seleccion())] + (
            ['Modos: ' + ', '.join(self.modos_guardados)] if self.modos_guardados else [])


class Panel5GCatalogo(PanelCatalogo):
    def __init__(self, master, nombre, catalogo):
        super().__init__(master, nombre, catalogo)
        available = catalogo.bandas('5G')
        self.variantes = {}
        for band in available:
            self.variantes.setdefault(banda_base_5g(band), []).append(band)
        for number, order in VARIANTES_5G.items():
            base = f'n{number}'
            if base in self.variantes:
                options = self.variantes[base]
                self.variantes[base] = [b for b in order if b in options] + [b for b in options if b not in order]
        self.entrada.actualizar(self.variantes)
        self.variables = {b: tk.BooleanVar() for b in available}
        self.marco_variantes = ttk.Frame(self)
        self.marco_variantes.pack(fill='x')
        self.entrada.al_cambiar = self._pintar_variantes

    def _pintar_variantes(self):
        for child in self.marco_variantes.winfo_children():
            child.destroy()
        for band in self.entrada.seleccion():
            options = self.variantes[band]
            if len(options) > 1 or options != [band]:
                frame = ttk.LabelFrame(self.marco_variantes, text=f'Variantes de {band}', padding=6)
                frame.pack(fill='x', pady=4)
                for option in options:
                    ttk.Checkbutton(frame, text=option, variable=self.variables[option]).pack(anchor='w')

    def _bandas_seleccionadas(self):
        result = []
        for band in self.entrada.seleccion():
            options = self.variantes[band]
            result.extend([b for b in options if self.variables[b].get()] if options != [band] else [band])
        return result

    def seleccion(self):
        bands = self._bandas_seleccionadas()
        return dict(bandas=bands, modos=list(self.modos_guardados)) if self.modos_guardados else bands

    def validar(self):
        errors = self.entrada.validar()
        for band in self.entrada.seleccion():
            options = self.variantes.get(band, [])
            if options != [band] and not any(self.variables[b].get() for b in options):
                errors.append(f'5G: selecciona al menos una variante de {band}.')
        return errors

    def cargar(self, data):
        bands = data.get('bandas', []) if isinstance(data, dict) else data
        self.entrada.cargar(list(dict.fromkeys(banda_base_5g(b) for b in bands)))
        for band, variable in self.variables.items():
            variable.set(band in bands)
        self.modos_guardados = list(data.get('modos', [])) if isinstance(data, dict) else []
        if self.modos_guardados:
            self.lbl_modos.configure(text='Modos de las respuestas cargadas: ' + ', '.join(self.modos_guardados))
            self.lbl_modos.pack(anchor='w')

    def lineas(self):
        return ['Bandas: ' + ', '.join(self._bandas_seleccionadas())]


class Panel2GCatalogo(ttk.Frame):
    def __init__(self, master, nombre, catalogo):
        super().__init__(master, padding=(24, 4))
        self.catalogo = catalogo
        self.sel, self.slots, self.detalles, self.bandas_modo = {}, {}, {}, {}
        for mode in OPCIONES_2G:
            block = ttk.Frame(self)
            block.pack(fill='x', pady=(2, 4))
            self.sel[mode] = tk.BooleanVar()
            ttk.Checkbutton(block, text=mode, variable=self.sel[mode],
                            command=lambda m=mode: self._mostrar(m)).pack(anchor='w')
            detail = self.detalles[mode] = ttk.Frame(block, padding=(20, 3, 0, 0))
            if mode != 'GSM':
                self.slots[mode] = {f'TX{n}': tk.BooleanVar() for n in range(1, 5)}
                row = ttk.Frame(detail)
                row.pack(anchor='w')
                for slot, variable in self.slots[mode].items():
                    ttk.Checkbutton(row, text=slot, variable=variable,
                        command=lambda m=mode, s=slot: self._cambiar(m, s)).pack(side='left', padx=(0, 10))
            self.bandas_modo[mode] = SelectorBandas(detail, mode, self._disponibles(mode))
            self.bandas_modo[mode].pack(fill='x')

    def _disponibles(self, mode):
        if mode == 'GSM':
            return self.catalogo.bandas('GSM')
        slots = [s for s, v in self.slots[mode].items() if v.get()] or [f'TX{n}' for n in range(1, 5)]
        lists = [self.catalogo.bandas(f'{mode} {s[2:]}TX') for s in slots]
        return [b for b in lists[0] if all(b in other for other in lists[1:])]

    def _mostrar(self, mode):
        if self.sel[mode].get():
            self.detalles[mode].pack(fill='x')
        else:
            self.detalles[mode].pack_forget()

    def _cambiar(self, mode, slot):
        n, checked = int(slot[2:]), self.slots[mode][slot].get()
        for s, variable in self.slots[mode].items():
            if checked and int(s[2:]) <= n:
                variable.set(True)
            elif not checked and int(s[2:]) >= n:
                variable.set(False)
        self.sel[mode].set(any(v.get() for v in self.slots[mode].values()))
        if hasattr(self, 'bandas_modo'):
            self.bandas_modo[mode].actualizar(self._disponibles(mode))
            self._mostrar(mode)

    def seleccion(self):
        data = {'GSM': self.sel['GSM'].get(), 'bandas_por_modo': {}}
        for mode in OPCIONES_2G:
            if self.sel[mode].get():
                data['bandas_por_modo'][mode] = self.bandas_modo[mode].seleccion()
            if mode != 'GSM':
                data[mode] = [s for s, v in self.slots[mode].items() if v.get()] if self.sel[mode].get() else None
        return data

    def validar(self):
        errors = []
        if not any(v.get() for v in self.sel.values()):
            errors.append('2G: selecciona al menos una tecnología.')
        for mode in OPCIONES_2G:
            if not self.sel[mode].get():
                continue
            if mode != 'GSM' and not any(v.get() for v in self.slots[mode].values()):
                errors.append(f'{mode}: selecciona los slots TX.')
            errors.extend(self.bandas_modo[mode].validar())
        return errors

    def cargar(self, data):
        for mode, variable in self.sel.items():
            variable.set(bool(data.get(mode)))
        for mode, variables in self.slots.items():
            active = slots_incluidos(data.get(mode))
            for slot, variable in variables.items():
                variable.set(slot in active)
            self.bandas_modo[mode].actualizar(self._disponibles(mode))
        for mode in OPCIONES_2G:
            if self.sel[mode].get():
                bands = data.get('bandas_por_modo', {}).get(mode, data.get('bandas'))
                self.bandas_modo[mode].cargar(bands if bands is not None else self._disponibles(mode))
            self._mostrar(mode)

    def lineas(self):
        lines = []
        for mode in OPCIONES_2G:
            if self.sel[mode].get():
                slots = ', '.join(s for s, v in self.slots.get(mode, {}).items() if v.get())
                lines.append(mode + (': ' + slots if slots else ''))
                lines.append('  Bandas: ' + ', '.join(self.bandas_modo[mode].seleccion()))
        return lines


class Panel3GCatalogo(ttk.Frame):
    def __init__(self, master, nombre, catalogo):
        super().__init__(master, padding=(24, 4))
        self.options = {}
        for tech in OPCIONES_3G:
            block = ttk.Frame(self)
            block.pack(fill='x', pady=2)
            variable = tk.BooleanVar()
            panel = PanelCatalogo(block, tech, catalogo)
            ttk.Checkbutton(block, text=tech, variable=variable,
                command=lambda v=variable, p=panel: p.pack(fill='x') if v.get() else p.pack_forget()).pack(anchor='w')
            self.options[tech] = variable, panel

    def seleccion(self):
        return {tech: p.seleccion() for tech, (v, p) in self.options.items() if v.get()}

    def validar(self):
        return ([e for v, p in self.options.values() if v.get() for e in p.validar()]
                if self.seleccion() else ['3G: selecciona una tecnología y sus bandas.'])

    def cargar(self, data):
        for tech, (variable, panel) in self.options.items():
            variable.set(tech in data)
            if tech in data:
                panel.cargar(data[tech] if isinstance(data, dict) else panel.entrada.disponibles)
                panel.pack(fill='x')
            else:
                panel.pack_forget()

    def lineas(self):
        return [tech + ' — ' + '; '.join(panel.lineas()) for tech, (v, panel) in self.options.items() if v.get()]


def fabricas(catalogo, wlan=None):
    if wlan is None:
        from cuestionario_ensayo import PanelWLAN
        wlan = PanelWLAN
    out = [('2G', lambda m, n: Panel2GCatalogo(m, n, catalogo)),
           ('3G', lambda m, n: Panel3GCatalogo(m, n, catalogo))]
    for tech in ('LTE', 'LTE CAT M1', 'LTE NB-IoT'):
        out.append((tech, lambda m, n: PanelCatalogo(m, n, catalogo)))
    out += [('5G', lambda m, n: Panel5GCatalogo(m, n, catalogo)), ('WLAN', wlan)]
    for tech in ['BT'] + [f'Custom{n}' for n in range(1, 9)]:
        if tech in catalogo.by_tech:
            out.append((tech, lambda m, n: PanelCatalogo(m, n, catalogo)))
    return out
