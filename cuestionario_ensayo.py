#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cuestionario de configuración de ensayo (SAR) con interfaz visual.

- Interfaz tkinter; la generación del Excel requiere lxml.
- Las respuestas se guardan en un archivo de texto (UTF-8).

Uso:  python cuestionario_ensayo.py

Al pulsar «Generar toma de datos» se crean un archivo de texto y el Excel (.xlsm) de la toma de datos.
"""

import os
import json
import queue
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from opciones_ensayo import slots_incluidos
from base_datos import Catalogo, BASE_PREDETERMINADA

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ERROR_GENERADOR = ''
try:                                   # generador del Excel (carpeta plantilla/ junto a este script)
    from generador_excel import generar as generar_excel
except Exception as _exc:              # p. ej. falta instalar lxml:  pip install lxml
    generar_excel, ERROR_GENERADOR = None, str(_exc)

# --------------------------------------------------------------------------
# Configuración
# --------------------------------------------------------------------------
from configuracion import (
    REGIONES, REGION_AYUDA, EXPOSICIONES, SI, NO, MIN_N, MAX_N, ARCHIVO_POR_DEFECTO, BANDAS_LTE, BANDAS_CATM1, BANDAS_NBIOT, BANDAS_5G, VARIANTES_5G, OPCIONES_2G, SLOTS_2G, OPCIONES_3G, WLAN_24, WLAN_5, WLAN_MODOS_24, WLAN_MODO_5, WLAN_MODOS_5, WLAN_UNII, CATEGORIAS
)

# --------------------------------------------------------------------------
# Zona con barra de desplazamiento
# --------------------------------------------------------------------------
class ScrollFrame(ttk.Frame):
    """Contenedor vertical desplazable. Los widgets se colocan en `self.inner`."""

    def __init__(self, master):
        super().__init__(master)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, yscrollincrement=20)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        self.inner = ttk.Frame(self.canvas, padding=(12, 10, 12, 4))
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>",
                        lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def desplazar(self, unidades):
        if self.canvas.yview() != (0.0, 1.0):          # solo si hay contenido fuera de vista
            self.canvas.yview_scroll(unidades, "units")

    def ver(self, widget=None):
        """Desplaza hasta mostrar `widget` (o el principio si es None)."""
        self.update_idletasks()
        if widget is None:
            self.canvas.yview_moveto(0.0)
            return
        total = max(self.inner.winfo_reqheight(), 1)
        offset = widget.winfo_rooty() - self.inner.winfo_rooty()
        self.canvas.yview_moveto(max(offset - 10, 0) / total)


# --------------------------------------------------------------------------
# "¿Cuántos?" + lista de nombres
# --------------------------------------------------------------------------
class ListaNombres(ttk.Frame):
    """Pide una cantidad (1-10), genera esa cantidad de campos y recoge los nombres."""

    def __init__(self, master, cat):
        super().__init__(master, padding=(4, 4))
        self.etiqueta_item = cat["item"]          # p. ej. "Batería"
        self.descripcion = cat["descripcion"]     # p. ej. "baterías adicionales"
        self.count_var = tk.StringVar()
        self.n_generado = 0
        self._name_vars = []                      # se conservan al cambiar la cantidad

        ttk.Label(self, text=cat["pregunta"], font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        ttk.Label(self, text=f"Introduce un número entero entre {MIN_N} y {MAX_N}.",
                  foreground="#555555").pack(anchor="w", pady=(2, 6))

        fila = ttk.Frame(self)
        fila.pack(fill="x")
        self.spin = ttk.Spinbox(fila, from_=MIN_N, to=MAX_N, width=6, textvariable=self.count_var,
                                justify="center")
        self.spin.pack(side="left")
        self.spin.bind("<Return>", lambda _e: self.generar())
        ttk.Button(fila, text="Generar lista", command=self.generar).pack(side="left", padx=8)

        self.aviso = ttk.Label(self, text="", foreground="#B00020")
        self.aviso.pack(anchor="w", pady=(4, 0))

        self.marco_lista = ttk.LabelFrame(self, text=f"Nombres de las {self.descripcion}", padding=8)
        self.marco_lista.pack(fill="x", pady=(6, 0))
        self._mensaje_vacio()

    # ----- utilidades internas -----
    def _limpiar_lista(self):
        for w in self.marco_lista.winfo_children():
            w.destroy()

    def _mensaje_vacio(self):
        self._limpiar_lista()
        ttk.Label(self.marco_lista, text="Indica la cantidad y pulsa «Generar lista».",
                  foreground="#777777").pack(anchor="w")

    def _leer_cantidad(self):
        """Devuelve el entero válido o None si el texto no es un entero entre MIN_N y MAX_N."""
        try:
            n = int(self.count_var.get().strip())
        except ValueError:
            return None
        return n if MIN_N <= n <= MAX_N else None

    # ----- acciones -----
    def generar(self):
        n = self._leer_cantidad()
        if n is None:
            # Valor no válido: se avisa, se borra y se vuelve a pedir.
            self.aviso.config(text=f"Valor no válido. Debe ser un entero entre {MIN_N} y {MAX_N}.")
            messagebox.showerror("Cantidad no válida",
                                 f"El número de {self.descripcion} debe ser un entero "
                                 f"entre {MIN_N} y {MAX_N}.\n\nVuelve a introducirlo.")
            self.count_var.set("")
            self.spin.focus_set()
            return False
        self.aviso.config(text="")

        # Se reutilizan los nombres ya escritos si se cambia la cantidad.
        while len(self._name_vars) < n:
            self._name_vars.append(tk.StringVar())

        self._limpiar_lista()
        por_columna = n if n <= 5 else 5          # 2 columnas si hay más de 5
        primero = None
        for i in range(n):
            fila, col = i % por_columna, (i // por_columna) * 2
            ttk.Label(self.marco_lista, text=f"{self.etiqueta_item} {i + 1}:").grid(
                row=fila, column=col, sticky="w", padx=(0, 6), pady=3)
            e = ttk.Entry(self.marco_lista, textvariable=self._name_vars[i], width=28)
            e.grid(row=fila, column=col + 1, sticky="we", padx=(0, 16), pady=3)
            primero = primero or e
        for c in (1, 3):
            self.marco_lista.columnconfigure(c, weight=1)
        self.n_generado = n
        if primero is not None:
            primero.focus_set()
        return True

    def validar(self):
        """Lista de errores (vacía si todo es correcto)."""
        n = self._leer_cantidad()
        if n is None:
            return [f"{self.descripcion.capitalize()}: indica un número entre {MIN_N} y {MAX_N}."]
        if n != self.n_generado:
            return [f"{self.descripcion.capitalize()}: pulsa «Generar lista» para {n} elemento(s)."]
        errores = []
        nombres = self.nombres()
        for i, nombre in enumerate(nombres, start=1):
            if not nombre:
                errores.append(f"{self.etiqueta_item} {i}: falta el nombre.")
        vistos = {}
        for i, nombre in enumerate(nombres, start=1):
            clave = nombre.casefold()
            if nombre and clave in vistos:
                errores.append(f"{self.etiqueta_item} {i}: el nombre «{nombre}» está repetido "
                               f"(también en {self.etiqueta_item} {vistos[clave]}).")
            vistos.setdefault(clave, i)
        return errores

    def nombres(self):
        return [" ".join(v.get().split()) for v in self._name_vars[:self.n_generado]]


# --------------------------------------------------------------------------
# Bloque fijo: pregunta Sí/No (botones de opción) + detalle que aparece debajo si es "Sí"
# --------------------------------------------------------------------------
class ElementoSeccion(ttk.LabelFrame):
    def __init__(self, master, cat):
        super().__init__(master, text=cat["pregunta_si"], padding=(10, 6))
        self.cat = cat
        self.var = tk.StringVar()

        fila = ttk.Frame(self)
        fila.pack(fill="x")
        for op in (SI, NO):
            ttk.Radiobutton(fila, text=op, value=op, variable=self.var,
                            command=self._al_cambiar).pack(side="left", padx=(0, 18))

        self.detalle = ListaNombres(self, cat)     # solo se muestra con "Sí"

    def _al_cambiar(self, _evento=None):
        if self.var.get() == SI:
            self.detalle.pack(fill="x", pady=(6, 0))
            self.detalle.spin.focus_set()
        else:
            self.detalle.pack_forget()

    def validar(self):
        resp = self.var.get()
        if not resp:
            return [f"{self.cat['pregunta_si']} Indica Sí o No."]
        return self.detalle.validar() if resp == SI else []


# --------------------------------------------------------------------------
# Paneles de cada tecnología (aparecen al marcar la tecnología)
# --------------------------------------------------------------------------
def _titulo(parent, texto):
    ttk.Label(parent, text=texto, font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(0, 4))


class Panel2G(ttk.Frame):
    """GPRS / EGPRS (con número de slots TX1-TX4) y GSM (sin slots)."""

    def __init__(self, master, nombre):
        super().__init__(master, padding=(26, 4, 4, 6))
        self.nombre = nombre
        self.sel, self.slot, self._marcos_slot = {}, {}, {}
        self.slot_checks = {}
        _titulo(self, "Selecciona las tecnologías 2G:")
        for op in OPCIONES_2G:
            self.sel[op] = tk.BooleanVar(value=False)
            bloque = ttk.Frame(self)
            bloque.pack(fill="x", anchor="w")
            ttk.Checkbutton(bloque, text=op, variable=self.sel[op],
                            command=lambda o=op: self._al_cambiar(o)).pack(anchor="w")
            if op != "GSM":
                self.slot[op] = tk.StringVar()
                self.slot_checks[op] = {s: tk.BooleanVar(value=False) for s in SLOTS_2G}
                marco = ttk.Frame(bloque, padding=(26, 0, 0, 4))
                ttk.Label(marco, text="Número de slots:").pack(side="left", padx=(0, 8))
                for s in SLOTS_2G:
                    ttk.Checkbutton(marco, text=f"{op} {s}", variable=self.slot_checks[op][s],
                                    command=lambda o=op, slot=s: self._cambiar_slot(o, slot)
                                    ).pack(side="left", padx=(0, 14))
                self._marcos_slot[op] = marco
        ttk.Label(self, text="Al marcar TXn se incluyen los inferiores; al desmarcarlo se quitan TXn y los superiores.",
                  wraplength=650, foreground="#555555").pack(anchor="w")

    def _cambiar_slot(self, op, slot):
        maximum = int(slot[2:]) - (0 if self.slot_checks[op][slot].get() else 1)
        self.slot[op].set(f'TX{maximum}' if maximum else '')
        for name, var in self.slot_checks[op].items():
            var.set(int(name[2:]) <= maximum)

    def _al_cambiar(self, op):
        marco = self._marcos_slot.get(op)
        if marco is None:
            return
        if self.sel[op].get():
            marco.pack(anchor="w")
        else:
            marco.pack_forget()

    def validar(self):
        if not any(self.sel[op].get() for op in OPCIONES_2G):
            return ["2G: selecciona al menos una opción (GPRS, EGPRS o GSM)."]
        return [f"2G – {op}: selecciona el número de slots."
                for op in ("GPRS", "EGPRS") if self.sel[op].get() and not self.slot[op].get()]

    def seleccion(self):
        return {'GPRS': slots_incluidos(self.slot['GPRS'].get()) if self.sel['GPRS'].get() else None,
                'EGPRS': slots_incluidos(self.slot['EGPRS'].get()) if self.sel['EGPRS'].get() else None,
                'GSM': bool(self.sel['GSM'].get())}

    def lineas(self):
        out = []
        for op in OPCIONES_2G:
            if self.sel[op].get():
                out.extend(["- GSM"] if op == "GSM" else
                           [f'- {op} {slot}' for slot in slots_incluidos(self.slot[op].get())])
        return out


class Panel3G(ttk.Frame):
    def __init__(self, master, nombre):
        super().__init__(master, padding=(26, 4, 4, 6))
        self.nombre = nombre
        self.sel = {}
        _titulo(self, "Selecciona las tecnologías 3G:")
        for op in OPCIONES_3G:
            self.sel[op] = tk.BooleanVar(value=False)
            ttk.Checkbutton(self, text=op, variable=self.sel[op]).pack(anchor="w")

    def validar(self):
        if not any(v.get() for v in self.sel.values()):
            return ["3G: selecciona al menos una opción."]
        return []

    def seleccion(self):
        return [op for op in OPCIONES_3G if self.sel[op].get()]

    def lineas(self):
        return [f"- {op}" for op in OPCIONES_3G if self.sel[op].get()]


class PanelBandas(ttk.Frame):
    """Pide los números de banda separados por comas y los valida contra el datasheet."""

    def __init__(self, master, nombre, mapa, variantes=None, etiquetas_en_lista=False,
                 prefijo=""):
        super().__init__(master, padding=(26, 4, 4, 6))
        self.nombre = nombre
        self.prefijo = prefijo                 # p. ej. "n" en 5G: vale "77" o "n77"
        self.mapa = mapa                       # número -> etiqueta (FDD1, TDD38, n77…)
        self.variantes = variantes or {}       # número -> [variantes]
        self.texto = tk.StringVar()
        self.aceptadas = []
        self._vars_variante = {e: tk.BooleanVar(value=False)
                               for lista in self.variantes.values() for e in lista}

        _titulo(self, "Introduzca el número de bandas separados por comas:")
        if etiquetas_en_lista:
            self.lista_validas = ", ".join(self.mapa[n] for n in self.mapa)   # n1, n2, n3…
        else:
            self.lista_validas = ", ".join(str(n) for n in self.mapa)
        ayuda = ""
        if self.prefijo:
            ej = next(iter(self.mapa))
            ayuda = f"\nPuedes escribir el número solo o con «{self.prefijo}» delante (p. ej. {ej} o {self.prefijo}{ej})."
        ttk.Label(self, text=f"Bandas disponibles: {self.lista_validas}{ayuda}", foreground="#555555",
                  wraplength=640, justify="left").pack(anchor="w", pady=(0, 6))
        fila = ttk.Frame(self)
        fila.pack(fill="x")
        self.entry = ttk.Entry(fila, textvariable=self.texto, width=44)
        self.entry.pack(side="left")
        self.entry.bind("<Return>", lambda _e: self.aceptar())
        ttk.Button(fila, text="Aceptar bandas", command=self.aceptar).pack(side="left", padx=8)
        self.aviso = ttk.Label(self, text="", foreground="#B00020", wraplength=640, justify="left")
        self.aviso.pack(anchor="w", pady=(4, 0))
        self.lbl_res = ttk.Label(self, text="", foreground="#1F5FA8", wraplength=640, justify="left")
        self.lbl_res.pack(anchor="w", pady=(2, 0))
        self.marco_var = ttk.Frame(self)
        self.marco_var.pack(fill="x")

    def _parsear(self):
        """Devuelve (números válidos ordenados y sin repetir, entradas no válidas, ¿vacío?)."""
        trozos = [t.strip() for t in self.texto.get().split(",") if t.strip()]
        if not trozos:
            return [], [], True
        validos, malos = [], []
        for t in trozos:
            t2 = t
            if self.prefijo and t2.lower().startswith(self.prefijo.lower()):
                t2 = t2[len(self.prefijo):].strip()
            if t2.isascii() and t2.isdigit() and int(t2) in self.mapa:
                validos.append(int(t2))
            else:
                malos.append(t)
        return sorted(set(validos)), malos, False

    def aceptar(self):
        nums, malos, vacio = self._parsear()
        if vacio or malos:
            detalle = ("No has introducido ninguna banda." if vacio else
                       f"Banda(s) no válida(s) para {self.nombre}: {', '.join(malos)}.")
            self.aviso.config(text=detalle)
            messagebox.showerror("Banda no válida",
                                 f"{detalle}\n\nBandas disponibles en el datasheet:\n"
                                 f"{self.lista_validas}\n\nVuelve a introducirlas.")
            self.texto.set("")
            self.aceptadas = []
            self.lbl_res.config(text="")
            self._pintar_variantes()
            self.entry.focus_set()
            return False
        self.aviso.config(text="")
        self.aceptadas = nums
        self.texto.set(", ".join(f"{self.prefijo}{n}" for n in nums))
        self.lbl_res.config(text=f"Bandas seleccionadas ({len(nums)}): "
                                 + ", ".join(self.mapa[n] for n in nums))
        self._pintar_variantes()
        return True

    def _pintar_variantes(self):
        for w in self.marco_var.winfo_children():
            w.destroy()
        for n in self.aceptadas:
            if n in self.variantes:
                marco = ttk.LabelFrame(self.marco_var, padding=(8, 4),
                                       text=f"Variantes de la banda n{n} (marca las que apliquen)")
                marco.pack(fill="x", pady=(6, 0))
                for etiqueta in self.variantes[n]:
                    ttk.Checkbutton(marco, text=etiqueta,
                                    variable=self._vars_variante[etiqueta]).pack(side="left", padx=(0, 14))

    def validar(self):
        nums, malos, vacio = self._parsear()
        if vacio:
            return [f"{self.nombre}: introduce al menos una banda."]
        if malos:
            return [f"{self.nombre}: bandas no válidas ({', '.join(malos)})."]
        if nums != self.aceptadas:
            return [f"{self.nombre}: pulsa «Aceptar bandas» para confirmar la selección."]
        return [f"{self.nombre}: marca al menos una variante de la banda n{n}."
                for n in nums if n in self.variantes
                and not any(self._vars_variante[e].get() for e in self.variantes[n])]

    def seleccion(self):
        return self._etiquetas()

    def _etiquetas(self):
        etiquetas = []
        for n in self.aceptadas:
            if n in self.variantes:
                etiquetas += [e for e in self.variantes[n] if self._vars_variante[e].get()]
            else:
                etiquetas.append(self.mapa[n])
        return etiquetas

    def lineas(self):
        etiquetas = []
        for n in self.aceptadas:
            if n in self.variantes:
                etiquetas += [e for e in self.variantes[n] if self._vars_variante[e].get()]
            else:
                etiquetas.append(self.mapa[n])
        return [f"Bandas ({len(etiquetas)}): " + ", ".join(etiquetas)]


def _rejilla(parent, variables, columnas=5):
    """Casillas en rejilla: variables = {texto: BooleanVar}."""
    marco = ttk.Frame(parent)
    marco.pack(anchor="w")
    for i, (texto, var) in enumerate(variables.items()):
        ttk.Checkbutton(marco, text=texto, variable=var).grid(
            row=i // columnas, column=i % columnas, sticky="w", padx=(0, 14), pady=1)
    return marco


class PanelWLAN(ttk.Frame):
    """WLAN: 2,4 GHz y/o 5 GHz (modo a por defecto + bandas U-NII) y sus modos."""

    def __init__(self, master, nombre):
        super().__init__(master, padding=(26, 4, 4, 6))
        self.nombre = nombre
        _titulo(self, "Selecciona las frecuencias WLAN:")
        self.sel = {WLAN_24: tk.BooleanVar(value=False), WLAN_5: tk.BooleanVar(value=False)}
        self._marcos = {}

        # --- 2,4 GHz ---
        b24 = ttk.Frame(self)
        b24.pack(fill="x", anchor="w")
        ttk.Checkbutton(b24, text=WLAN_24, variable=self.sel[WLAN_24],
                        command=lambda: self._al_cambiar(WLAN_24)).pack(anchor="w")
        m24 = ttk.Frame(b24, padding=(26, 2, 0, 6))
        ttk.Label(m24, text="Modos:", foreground="#555555").pack(anchor="w")
        self.modos_24 = {m: tk.BooleanVar(value=False) for m in WLAN_MODOS_24}
        _rejilla(m24, self.modos_24, columnas=8)
        self._marcos[WLAN_24] = m24

        # --- 5 GHz ---
        b5 = ttk.Frame(self)
        b5.pack(fill="x", anchor="w")
        ttk.Checkbutton(b5, text=WLAN_5, variable=self.sel[WLAN_5],
                        command=lambda: self._al_cambiar(WLAN_5)).pack(anchor="w")
        m5 = ttk.Frame(b5, padding=(26, 2, 0, 6))
        ttk.Label(m5, text="Bandas:", foreground="#555555").pack(anchor="w")
        self.unii = {u: tk.BooleanVar(value=False) for u in WLAN_UNII}
        _rejilla(m5, self.unii, columnas=5)
        ttk.Label(m5, text="Modos:", foreground="#555555").pack(anchor="w", pady=(6, 0))
        self.modo_a = tk.StringVar(value=WLAN_MODO_5)     # "a" queda seleccionado por defecto
        self.modos_5 = {m: tk.BooleanVar(value=False) for m in WLAN_MODOS_5}
        rej = ttk.Frame(m5)
        rej.pack(anchor="w")
        ttk.Radiobutton(rej, text=WLAN_MODO_5, value=WLAN_MODO_5, variable=self.modo_a).grid(
            row=0, column=0, sticky="w", padx=(0, 14))
        for i, (texto, var) in enumerate(self.modos_5.items(), start=1):
            ttk.Checkbutton(rej, text=texto, variable=var).grid(
                row=i // 6, column=i % 6, sticky="w", padx=(0, 14), pady=1)
        self._marcos[WLAN_5] = m5

    def _al_cambiar(self, frec):
        if self.sel[frec].get():
            self._marcos[frec].pack(fill="x")
        else:
            self._marcos[frec].pack_forget()

    def _sel(self, d):
        return [k for k, v in d.items() if v.get()]

    def validar(self):
        if not any(v.get() for v in self.sel.values()):
            return [f"WLAN: selecciona al menos una frecuencia ({WLAN_24} o {WLAN_5})."]
        errores = []
        if self.sel[WLAN_24].get() and not self._sel(self.modos_24):
            errores.append(f"WLAN {WLAN_24}: selecciona al menos un modo.")
        if self.sel[WLAN_5].get():
            unii = self._sel(self.unii)
            if not unii:
                errores.append("WLAN 5 GHz: selecciona al menos una banda U-NII.")
            else:
                for m in self._sel(self.modos_5):
                    if not any(m in WLAN_UNII[u] for u in unii):
                        donde = ", ".join(u for u in WLAN_UNII if m in WLAN_UNII[u])
                        errores.append(f"WLAN 5 GHz: el modo {m} no existe en el datasheet para "
                                       f"{', '.join(unii)} (solo en {donde}).")
        return errores

    def seleccion(self):
        out = {}
        if self.sel[WLAN_24].get():
            out[WLAN_24] = self._sel(self.modos_24)
        if self.sel[WLAN_5].get():
            out[WLAN_5] = {'bandas': self._sel(self.unii), 'modos': [WLAN_MODO_5] + self._sel(self.modos_5)}
        return out

    def lineas(self):
        out = []
        if self.sel[WLAN_24].get():
            modos = self._sel(self.modos_24)
            out += [f"- {WLAN_24}", f"    Modos ({len(modos)}): " + ", ".join(modos)]
        if self.sel[WLAN_5].get():
            modos = [WLAN_MODO_5] + self._sel(self.modos_5)
            out += [f"- {WLAN_5}",
                    "    Bandas U-NII: " + ", ".join(self._sel(self.unii)),
                    f"    Modos ({len(modos)}): " + ", ".join(modos)]
        return out

    def cargar(self, data):
        if isinstance(data, list) or (isinstance(data, dict) and 'bandas' in data):
            bands = data if isinstance(data, list) else data['bandas']
            modes = [] if isinstance(data, list) else data.get('modos', [])
            data = {}
            if '2.4 GHz' in bands:
                data[WLAN_24] = [m for m in modes if m in WLAN_MODOS_24]
            unii = [b for b in bands if b in WLAN_UNII]
            if unii:
                data[WLAN_5] = {'bandas': unii, 'modos': [m for m in modes if m in [WLAN_MODO_5] + WLAN_MODOS_5]}
        for freq, variable in self.sel.items():
            variable.set(freq in data)
            self._al_cambiar(freq)
        for mode, variable in self.modos_24.items():
            variable.set(mode in data.get(WLAN_24, []))
        five = data.get(WLAN_5, {})
        for band, variable in self.unii.items():
            variable.set(band in five.get('bandas', []))
        for mode, variable in self.modos_5.items():
            variable.set(mode in five.get('modos', []))


class TecnologiaBloque(ttk.Frame):
    """Casilla de una tecnología; al marcarla aparece su panel justo debajo."""

    def __init__(self, master, nombre, fabrica_panel):
        super().__init__(master)
        self.nombre = nombre
        self.var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self, text=nombre, variable=self.var,
                        command=self._al_cambiar).pack(anchor="w")
        self.panel = fabrica_panel(self, nombre)

    def _al_cambiar(self):
        if self.var.get():
            self.panel.pack(fill="x")
        else:
            self.panel.pack_forget()

    def activa(self):
        return self.var.get()

    def seleccion(self):
        return self.panel.seleccion() if self.activa() else None

    def validar(self):
        return self.panel.validar() if self.activa() else []

    def lineas(self):
        if not self.activa():
            return [f"{self.nombre}: {NO}"]
        return [f"{self.nombre}: {SI}"] + ["  " + l for l in self.panel.lineas()]


# Tecnologías disponibles (se irán ampliando)
TECNOLOGIAS = [
    ("2G", Panel2G),
    ("3G", Panel3G),
    ("LTE", lambda m, n: PanelBandas(m, n, BANDAS_LTE)),
    ("LTE CAT M1", lambda m, n: PanelBandas(m, n, BANDAS_CATM1)),
    ("LTE NB-IoT", lambda m, n: PanelBandas(m, n, BANDAS_NBIOT)),
    ("5G", lambda m, n: PanelBandas(m, n, BANDAS_5G, VARIANTES_5G,
                                    etiquetas_en_lista=True, prefijo="n")),
    ("WLAN", PanelWLAN),
]


# --------------------------------------------------------------------------
# Ventana de resumen: pregunta si se genera o no la toma de datos
# --------------------------------------------------------------------------
class ResumenDialog(tk.Toplevel):
    def __init__(self, master, texto):
        super().__init__(master)
        self.title("Resumen de la toma de datos")
        self.geometry("560x520")
        self.minsize(460, 400)
        self.transient(master)
        self.resultado = False

        marco = ttk.Frame(self, padding=12)
        marco.pack(fill="both", expand=True)
        ttk.Label(marco, text="Resumen de la toma de datos",
                  font=("TkDefaultFont", 11, "bold")).pack(anchor="w")

        cont = ttk.Frame(marco)
        cont.pack(fill="both", expand=True, pady=8)
        txt = tk.Text(cont, wrap="word", font=("Courier New", 10))
        sb = ttk.Scrollbar(cont, command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        txt.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        txt.insert("1.0", texto)
        txt.config(state="disabled")

        ttk.Label(marco, text="¿Quieres generar la toma de datos?",
                  font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(4, 6))
        botones = ttk.Frame(marco)
        botones.pack(fill="x")
        ttk.Button(botones, text="No, volver", command=self.destroy).pack(side="right")
        ttk.Button(botones, text="Sí, generar", command=self._si).pack(side="right", padx=8)

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.update_idletasks()
        self.grab_set()

    def _si(self):
        self.resultado = True
        self.destroy()

    def mostrar(self):
        self.wait_window(self)
        return self.resultado


# --------------------------------------------------------------------------
# Aplicación principal
# --------------------------------------------------------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Cuestionario de ensayo")
        self.geometry("800x760")
        self.minsize(720, 560)

        self.var_proyecto = tk.StringVar()
        self.var_region = {r: tk.BooleanVar(value=False) for r in REGIONES}
        self.var_expo = {e: tk.BooleanVar(value=False) for e in EXPOSICIONES}
        self.var_conducida = tk.StringVar()
        self.carpeta_guardado = Path(__file__).resolve().parent
        self.elementos = {}                       # clave -> ElementoSeccion
        self.tecnologias = {}                     # nombre -> TecnologiaBloque
        try:
            self.catalogo = Catalogo()
        except (OSError, ValueError):
            self.catalogo = None
        self.var_base = tk.StringVar(value=str(self.catalogo.path if self.catalogo else BASE_PREDETERMINADA))

        self._crear_widgets()
        self._configurar_rueda()

    # ------------------------------------------------------------------
    def _crear_widgets(self):
        barra = ttk.Frame(self)
        barra.pack(side="bottom", fill="x", padx=12, pady=10)
        ttk.Button(barra, text="Generar toma de datos", command=self.generar_toma_datos).pack(side="right")

        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True)
        cont = self.scroll.inner

        marco_base = ttk.LabelFrame(cont, text='Base de datos de tecnologías (.xlsx)', padding=(10, 6))
        marco_base.pack(fill='x', pady=4)
        ttk.Label(marco_base, textvariable=self.var_base, wraplength=650).pack(anchor='w')
        ttk.Button(marco_base, text='Elegir base de datos…', command=self._elegir_base).pack(side='left', pady=5)
        ttk.Button(marco_base, text='Recargar base', command=self._recargar_base).pack(side='left', padx=8)
        ttk.Button(marco_base, text='Cargar respuestas (.json)…', command=self._cargar_respuestas).pack(side='left', padx=8)

        self.marco_proyecto = ttk.LabelFrame(cont, text="Nombre del proyecto", padding=(10, 6))
        self.marco_proyecto.pack(fill="x", pady=4)
        self.entry_proyecto = ttk.Entry(self.marco_proyecto, textvariable=self.var_proyecto)
        self.entry_proyecto.pack(fill="x")

        self._pregunta_multiple(cont, "Regiones (puedes elegir varias)", self.var_region, REGION_AYUDA)
        self._pregunta_multiple(cont, "Exposure conditions (puedes elegir varias)", self.var_expo)
        self._pregunta(cont, "¿Aplica ensayos conducidos?", self.var_conducida, [SI, NO])
        ttk.Label(cont, text="Las tecnologías se incluyen siempre; salvo 2G/3G, sus pestañas llevan «Conducted» si eliges Sí.",
                  foreground="#555555", wraplength=650).pack(anchor="w", padx=10)

        # Baterías, accesorios y spotchecking: siempre visibles
        for cat in CATEGORIAS:
            sec = ElementoSeccion(cont, cat)
            sec.pack(fill="x", pady=4)
            self.elementos[cat["clave"]] = sec

        # Tecnologías: se marcan y aparecen sus opciones debajo
        marco_tec = self.marco_tec = ttk.LabelFrame(cont, text="Tecnologías", padding=(10, 6))
        marco_tec.pack(fill="x", pady=4)
        ttk.Label(marco_tec, text="Marca las tecnologías que aplican:",
                  foreground="#555555").pack(anchor="w", pady=(0, 4))
        self._actualizar_tecnologias()

    def _actualizar_tecnologias(self, anteriores=None):
        from formulario_bd import fabricas
        for bloque in self.tecnologias.values():
            bloque.destroy()
        if getattr(self, 'marco_otros', None):
            self.marco_otros.destroy()
        self.tecnologias = {}
        self.marco_otros = None
        for nombre, fabrica in fabricas(self.catalogo, wlan=PanelWLAN) if self.catalogo else []:
            parent = self.marco_tec
            if nombre == 'BT' or nombre.startswith('Custom'):
                if self.marco_otros is None:
                    self.marco_otros = ttk.Frame(self.marco_tec)
                    self.marco_otros.pack(fill='x', pady=(8, 0))
                    self.otros_contenido = ttk.Frame(self.marco_otros)
                    self.otros_boton = ttk.Button(self.marco_otros, text='Mostrar otras tecnologías', command=self._mostrar_otros)
                    self.otros_boton.pack(anchor='w')
                parent = self.otros_contenido
            bloque = TecnologiaBloque(parent, nombre, fabrica)
            bloque.pack(fill="x", pady=2)
            self.tecnologias[nombre] = bloque
            if anteriores and nombre in anteriores:
                bloque.panel.cargar(anteriores[nombre])
                bloque.var.set(True)
                bloque._al_cambiar()
                if parent is not self.marco_tec:
                    self.otros_contenido.pack(fill='x')
                    self.otros_boton.configure(text='Ocultar otras tecnologías')

    def _mostrar_otros(self):
        if self.otros_contenido.winfo_manager():
            self.otros_contenido.pack_forget()
            self.otros_boton.configure(text='Mostrar otras tecnologías')
        else:
            self.otros_contenido.pack(fill='x')
            self.otros_boton.configure(text='Ocultar otras tecnologías')

    def _elegir_base(self):
        path = filedialog.askopenfilename(title='Elegir base de datos de tecnologías', filetypes=[('Base de datos Excel', '*.xlsx')])
        if path:
            self._aplicar_base(path)

    def _recargar_base(self):
        self._aplicar_base(self.var_base.get())

    def _aplicar_base(self, path):
        try:
            catalogo = Catalogo(path)
        except (OSError, ValueError, KeyError) as exc:
            messagebox.showerror('Base no válida', str(exc))
            return
        anteriores = {n: b.seleccion() for n, b in self.tecnologias.items() if b.activa()}
        self.catalogo = catalogo
        self.var_base.set(str(catalogo.path))
        self._actualizar_tecnologias(anteriores)

    def _cargar_respuestas(self):
        if self.catalogo is None:
            messagebox.showerror('Falta la base de datos', 'Elige primero una base de datos XLSX válida.')
            return
        path = filedialog.askopenfilename(title='Cargar respuestas del ensayo', filetypes=[('Respuestas del cuestionario', '*.json')])
        if not path:
            return
        try:
            from validacion_datos import validar_datos
            data = json.loads(Path(path).read_text(encoding='utf-8'))
            validar_datos(data, catalogo=self.catalogo)
        except (OSError, ValueError, KeyError) as exc:
            messagebox.showerror('Respuestas no válidas para esta base', str(exc))
            return
        from opciones_ensayo import seleccion_multiple
        self.var_proyecto.set(data['proyecto'])
        for name, variable in self.var_region.items():
            variable.set(name in seleccion_multiple(data['region']))
        for name, variable in self.var_expo.items():
            variable.set(name in seleccion_multiple(data['exposure']))
        self.var_conducida.set(SI if data['conducida'] else NO)
        for key, section in self.elementos.items():
            names = data[key]
            section.var.set(SI if names else NO)
            section._al_cambiar()
            if names:
                section.detalle.count_var.set(str(len(names)))
                section.detalle.generar()
                for variable, text in zip(section.detalle._name_vars, names):
                    variable.set(text)
        self._actualizar_tecnologias(data['tecnologias'])

    def _pregunta(self, parent, texto, var, opciones, ayuda=None):
        marco = ttk.LabelFrame(parent, text=texto, padding=(10, 6))
        marco.pack(fill="x", pady=4)
        for op in opciones:
            etiqueta = op if not ayuda else f"{op}  ({ayuda[op]})"
            ttk.Radiobutton(marco, text=etiqueta, value=op, variable=var).pack(side="left", padx=(0, 18))
        return marco

    # ------------------------------------------------------------------
    # Rueda del ratón: desplaza la pantalla (y evita cambiar el número sin querer)
    # ------------------------------------------------------------------
    def _pregunta_multiple(self, parent, titulo, variables, ayuda=None):
        marco = ttk.LabelFrame(parent, text=titulo, padding=(10, 6))
        marco.pack(fill="x", pady=4)
        for op, var in variables.items():
            etiqueta = f'{op} ({ayuda[op]})' if ayuda and op in ayuda else op
            ttk.Checkbutton(marco, text=etiqueta, variable=var).pack(anchor="w")
        return marco

    @staticmethod
    def _marcadas(variables):
        return [name for name, var in variables.items() if var.get()]

    def _configurar_rueda(self):
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(seq, self._rueda)
            self.bind_class("TSpinbox", seq, self._rueda_y_cortar)

    def _rueda(self, evento):
        if getattr(evento, "num", None) == 4:
            paso = -1
        elif getattr(evento, "num", None) == 5:
            paso = 1
        else:
            paso = -1 if evento.delta > 0 else 1
        self.scroll.desplazar(paso * 2)

    def _rueda_y_cortar(self, evento):
        self._rueda(evento)
        return "break"

    # ------------------------------------------------------------------
    # Validación
    # ------------------------------------------------------------------
    def _nombre_proyecto(self):
        """Nombre del proyecto sin espacios sobrantes."""
        return " ".join(self.var_proyecto.get().split())

    def _nombre_archivo_sugerido(self):
        """Nombre de archivo basado en el proyecto (sin caracteres no válidos)."""
        base = "".join(c if c.isalnum() or c in " -_." else "_" for c in self._nombre_proyecto())
        base = base.strip(" ._")
        return f"{base}.txt" if base else ARCHIVO_POR_DEFECTO

    def _validar_general(self):
        errores = []
        if not self._nombre_proyecto():
            errores.append("Escribe el nombre del proyecto.")
        if not self._marcadas(self.var_region):
            errores.append('Elige al menos una región.')
        if not self._marcadas(self.var_expo):
            errores.append('Elige al menos una exposure condition.')
        if not self.var_conducida.get():
            errores.append('Indica si aplican ensayos conducidos.')
        return errores

    def _validar_todo(self):
        """Devuelve (errores, widget donde mostrar el primer error o None)."""
        errores = self._validar_general()
        try:
            self.catalogo = Catalogo(self.var_base.get())
        except (OSError, ValueError) as exc:
            errores.append('Elige una base de datos XLSX válida: ' + str(exc))
        destino = self.marco_proyecto if errores else None
        for cat in CATEGORIAS:
            sec = self.elementos[cat["clave"]]
            errs = sec.validar()
            if errs and destino is None:
                destino = sec
            errores.extend(errs)
        for nombre, bloque in self.tecnologias.items():
            errs = bloque.validar()
            if errs and destino is None:
                destino = bloque
            errores.extend(errs)
        if not errores:
            from validacion_datos import validar_datos
            try:
                validar_datos(self.datos_para_excel(), catalogo=self.catalogo)
            except ValueError as exc:
                errores.append(str(exc))
                destino = self.marco_proyecto
        return errores, destino

    # ------------------------------------------------------------------
    # Informe de texto
    # ------------------------------------------------------------------
    def _construir_informe(self):
        L = ["DATOS DEL ENSAYO",
             f"Fecha de creación: {datetime.now():%Y-%m-%d %H:%M:%S}",
             "",
             f"Nombre del proyecto: {self._nombre_proyecto()}",
             f"Regiones: {', '.join(self._marcadas(self.var_region))}",
             f"Exposure conditions: {', '.join(self._marcadas(self.var_expo))}",
             f"Aplica ensayos conducidos: {self.var_conducida.get()}",
             ""]
        for cat in CATEGORIAS:
            sec = self.elementos[cat["clave"]]
            if sec.var.get() != SI:
                L.append(f"{cat['titulo']}: {NO}")
                continue
            L.append(f"{cat['titulo']}: {SI}")
            L.append(f"  {cat['titulo_n']}: {sec.detalle.n_generado}")
            for i, nombre in enumerate(sec.detalle.nombres(), start=1):
                L.append(f"  {cat['item']} {i}: {nombre}")
        L += ["", "TECNOLOGÍAS"]
        for bloque in self.tecnologias.values():
            L.extend(bloque.lineas())
        if getattr(self, 'catalogo', None):
            L += ['', 'Base de datos: ' + self.catalogo.path.name, 'SHA-256: ' + self.catalogo.sha256]
        return "\n".join(L) + "\n"

    # ------------------------------------------------------------------
    # Guardado
    # ------------------------------------------------------------------
    def generar_toma_datos(self):
        errores, destino = self._validar_todo()
        if errores:
            messagebox.showwarning("No se puede generar la toma de datos",
                                   "Corrige lo siguiente:\n\n• " + "\n• ".join(errores))
            self.scroll.ver(destino)
            return

        texto = self._construir_informe()
        if not ResumenDialog(self, texto).mostrar():
            return                                   # eligió "No, volver"

        ruta = filedialog.asksaveasfilename(
            title="Generar toma de datos", defaultextension=".txt",
            initialdir=str(self.carpeta_guardado), initialfile=self._nombre_archivo_sugerido(),
            filetypes=[("Archivo de texto", "*.txt"), ("Todos los archivos", "*.*")])
        if not ruta:
            return
        try:
            Path(ruta).write_text(texto, encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Error al generar la toma de datos", f"No se pudo escribir el archivo:\n{exc}")
            return
        self.carpeta_guardado = Path(ruta).parent
        self._generar_excel(Path(ruta))

    # ------------------------------------------------------------------
    # Excel de la toma de datos
    # ------------------------------------------------------------------
    def datos_para_excel(self):
        """Respuestas del cuestionario en el formato que espera el generador del Excel."""
        def nombres(clave):
            sec = self.elementos[clave]
            return sec.detalle.nombres() if sec.var.get() == SI else []
        data = {
            'proyecto': self._nombre_proyecto(),
            'region': self._marcadas(self.var_region),
            'exposure': self._marcadas(self.var_expo),
            'conducida': self.var_conducida.get() == SI,
            'baterias': nombres('baterias'),
            'accesorios': nombres('accesorios'),
            'spotchecking': nombres('spotchecking'),
            'tecnologias': {n: b.seleccion() for n, b in self.tecnologias.items() if b.activa()},
        }
        if getattr(self, 'catalogo', None):
            data['base_datos'] = str(self.catalogo.path)
            data['base_datos_sha256'] = self.catalogo.sha256
        return data

    def _generar_excel(self, ruta_txt):
        if generar_excel is None:
            messagebox.showwarning("Toma de datos generada",
                                   f"Archivo de texto generado en:\n{ruta_txt}\n\n"
                                   f"No se pudo cargar el generador del Excel: {ERROR_GENERADOR}\n(Si falta lxml: pip install lxml)")
            return
        salida = ruta_txt.with_suffix('.xlsm')
        if salida.exists() and not messagebox.askyesno(
                "El Excel ya existe", f"Ya existe:\n{salida}\n\n¿Quieres sustituirlo?"):
            messagebox.showinfo("Toma de datos generada", f"Archivo de texto generado en:\n{ruta_txt}")
            return
        datos = self.datos_para_excel()
        catalogo = self.catalogo
        try:
            ruta_txt.with_suffix('.json').write_text(json.dumps(datos, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        except OSError as exc:
            messagebox.showerror('Error al guardar las respuestas', str(exc))
            return
        espera = ProgresoDialog(self, "Generando el Excel de la toma de datos…")
        cola = queue.Queue()

        def trabajo():
            try:
                cola.put(('ok', generar_excel(datos, str(salida), log=lambda *a: None, catalogo=catalogo)))
            except Exception as exc:                      # se muestra al usuario
                cola.put(('error', exc))

        threading.Thread(target=trabajo, daemon=True).start()

        def revisar():
            try:
                estado, res = cola.get_nowait()
            except queue.Empty:
                self.after(200, revisar)
                return
            espera.destroy()
            if estado == 'error':
                messagebox.showerror("Error al generar el Excel",
                                     f"El archivo de texto sí se generó:\n{ruta_txt}\n\nPero el Excel falló:\n{res}")
                return
            hojas = ", ".join(res['hojas'])
            avisos = res.get('avisos', [])
            detalle = '\n\nAvisos:\n' + '\n'.join(avisos) if avisos else ''
            messagebox.showinfo("Toma de datos generada",
                                f"Archivo de texto:\n{ruta_txt}\n\nExcel:\n{salida}\n\nHojas: {hojas}{detalle}")
        self.after(200, revisar)


class ProgresoDialog(tk.Toplevel):
    """Ventana sencilla de espera con barra indeterminada."""

    def __init__(self, master, texto):
        super().__init__(master)
        self.title("Un momento…")
        self.transient(master)
        self.resizable(False, False)
        marco = ttk.Frame(self, padding=20)
        marco.pack()
        ttk.Label(marco, text=texto).pack(pady=(0, 10))
        barra = ttk.Progressbar(marco, mode="indeterminate", length=280)
        barra.pack()
        barra.start(15)
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.update_idletasks()
        self.grab_set()


if __name__ == "__main__":
    App().mainloop()
