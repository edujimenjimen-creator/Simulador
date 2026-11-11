
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import date, timedelta

# --------------------------------
# CONFIGURACIÓN Y BASE DE DATOS
# --------------------------------

DB = "almacen.db"

conexion = sqlite3.connect(DB)
cursor = conexion.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS servicios (
    fecha TEXT PRIMARY KEY,
    picks INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS horas (
    fecha TEXT,
    hora INTEGER,
    tiendas INTEGER DEFAULT 0,
    picks INTEGER DEFAULT 0,
    PRIMARY KEY (fecha, hora)
)
""")

conexion.commit()

# Semana de servicio
lunes = date(2026, 11, 16)
dias = [
    (lunes + timedelta(days=i)) for i in range(6)
]

# --------------------------------
# APLICACIÓN
# --------------------------------

class AlmacenApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Gestión de Almacén")
        self.root.geometry("1150x800")
        self.root.minsize(900, 650)

        self.fecha_actual = dias[0].isoformat()
        self.pantalla = "servicio"

        self.store_vars = []
        self.pick_vars = []
        self.daily_var = tk.StringVar()

        self.crear_interfaz()
        self.mostrar_servicio()

    # --------------------------------
    # INTERFAZ PRINCIPAL
    # --------------------------------

    def crear_interfaz(self):

        self.root.configure(bg="#f1f4f8")

        self.sidebar = tk.Frame(
            self.root,
            bg="#17243a",
            width=250
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        tk.Label(
            self.sidebar,
            text="ALMACÉN",
            font=("Arial", 22, "bold"),
            bg="#17243a",
            fg="white"
        ).pack(pady=(30, 25))

        tk.Label(
            self.sidebar,
            text="DÍAS DE SERVICIO",
            font=("Arial", 10, "bold"),
            bg="#17243a",
            fg="#9eacc1"
        ).pack(anchor="w", padx=20, pady=10)

        for d in dias:
            texto = d.strftime("%A %d/%m")
            nombres = {
                "Monday": "Lunes",
                "Tuesday": "Martes",
                "Wednesday": "Miércoles",
                "Thursday": "Jueves",
                "Friday": "Viernes",
                "Saturday": "Sábado"
            }
            texto = texto.replace(
                d.strftime("%A"),
                nombres[d.strftime("%A")]
            )

            tk.Button(
                self.sidebar,
                text=texto,
                font=("Arial", 11),
                bg="#253750",
                fg="white",
                activebackground="#3d587b",
                activeforeground="white",
                relief="flat",
                anchor="w",
                padx=18,
                pady=12,
                command=lambda fecha=d: self.seleccionar_dia(fecha)
            ).pack(fill="x", padx=12, pady=3)

        tk.Label(
            self.sidebar,
            text="GESTIÓN HORARIA",
            font=("Arial", 10, "bold"),
            bg="#17243a",
            fg="#9eacc1"
        ).pack(anchor="w", padx=20, pady=(35, 10))

        self.boton(
            "Tiendas por hora",
            self.mostrar_tiendas
        )

        self.boton(
            "Picks por hora",
            self.mostrar_picks
        )

        self.contenido = tk.Frame(
            self.root,
            bg="#f1f4f8"
        )
        self.contenido.pack(
            side="right",
            fill="both",
            expand=True
        )

    def boton(self, texto, funcion):
        tk.Button(
            self.sidebar,
            text=texto,
            font=("Arial", 11),
            bg="#253750",
            fg="white",
            activebackground="#3d587b",
            activeforeground="white",
            relief="flat",
            anchor="w",
            padx=18,
            pady=12,
            command=funcion
        ).pack(fill="x", padx=12, pady=3)

    def limpiar(self):
        for widget in self.contenido.winfo_children():
            widget.destroy()

    def titulo(self, texto):
        tk.Label(
            self.contenido,
            text=texto,
            font=("Arial", 23, "bold"),
            bg="#f1f4f8",
            fg="#17243a"
        ).pack(anchor="w", padx=35, pady=(30, 20))

    def fecha_texto(self):
        return date.fromisoformat(
            self.fecha_actual
        ).strftime("%d/%m/%Y")

    # --------------------------------
    # CAMBIO DE DÍA
    # --------------------------------

    def seleccionar_dia(self, fecha):
        self.guardar()
        self.fecha_actual = fecha.isoformat()
        self.mostrar_servicio()

    # --------------------------------
    # SERVICIO DIARIO
    # --------------------------------

    def mostrar_servicio(self):

        self.pantalla = "servicio"
        self.limpiar()

        self.titulo(
            "Servicio del " + self.fecha_texto()
        )

        tarjeta = tk.Frame(
            self.contenido,
            bg="white",
            padx=30,
            pady=30
        )
        tarjeta.pack(
            anchor="nw",
            padx=35,
            fill="x"
        )

        tk.Label(
            tarjeta,
            text="PICKS DEL SERVICIO",
            font=("Arial", 13, "bold"),
            bg="white",
            fg="#17243a"
        ).pack(anchor="w", pady=(0, 15))

        cursor.execute(
            "SELECT picks FROM servicios WHERE fecha=?",
            (self.fecha_actual,)
        )
        resultado = cursor.fetchone()

        valor = resultado[0] if resultado else 0

        self.daily_var = tk.StringVar(value=str(valor))

        tk.Entry(
            tarjeta,
            textvariable=self.daily_var,
            font=("Arial", 20),
            width=15,
            relief="solid",
            bd=1
        ).pack(anchor="w")

        tk.Label(
            tarjeta,
            text="Introduce el número de picks del servicio.",
            font=("Arial", 10),
            bg="white",
            fg="gray"
        ).pack(anchor="w", pady=10)

        self.boton_guardar(tarjeta)

    # --------------------------------
    # TIENDAS POR HORA
    # --------------------------------

    def mostrar_tiendas(self):

        self.pantalla = "tiendas"
        self.limpiar()

        self.titulo(
            "Número de tiendas por hora - " + self.fecha_texto()
        )

        self.crear_tabla("tiendas")

    # --------------------------------
    # PICKS POR HORA
    # --------------------------------

    def mostrar_picks(self):

        self.pantalla = "picks"
        self.limpiar()

        self.titulo(
            "Picks realizados por hora - " + self.fecha_texto()
        )

        self.crear_tabla("picks")

    # --------------------------------
    # TABLA HORARIA CON SCROLL
    # --------------------------------

    def crear_tabla(self, tipo):

        exterior = tk.Frame(
            self.contenido,
            bg="#f1f4f8"
        )
        exterior.pack(
            fill="both",
            expand=True,
            padx=35,
            pady=5
        )

        canvas = tk.Canvas(
            exterior,
            bg="#f1f4f8",
            highlightthickness=0
        )

        scrollbar = ttk.Scrollbar(
            exterior,
            orient="vertical",
            command=canvas.yview
        )

        tabla = tk.Frame(canvas, bg="#f1f4f8")

        tabla.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window(
            (0, 0),
            window=tabla,
            anchor="nw"
        )

        canvas.configure(
            yscrollcommand=scrollbar.set
        )

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.store_vars = []
        self.pick_vars = []

        cursor.execute("""
            SELECT hora, tiendas, picks
            FROM horas
            WHERE fecha=?
            ORDER BY hora
        """, (self.fecha_actual,))

        datos = {
            fila[0]: (fila[1], fila[2])
            for fila in cursor.fetchall()
        }

        cabecera = tk.Frame(
            tabla,
            bg="#253750",
            padx=15,
            pady=12
        )
        cabecera.pack(fill="x", pady=(0, 8))

        tk.Label(
            cabecera,
            text="HORA",
            width=12,
            bg="#253750",
            fg="white",
            font=("Arial", 10, "bold")
        ).pack(side="left")

        if tipo == "tiendas":
            tk.Label(
                cabecera,
                text="NÚMERO DE TIENDAS",
                bg="#253750",
                fg="white",
                font=("Arial", 10, "bold")
            ).pack(side="left", padx=30)
        else:
            tk.Label(
                cabecera,
                text="PICKS POR HORA",
                bg="#253750",
                fg="white",
                font=("Arial", 10, "bold")
            ).pack(side="left", padx=30)

        for hora in range(24):

            tiendas, picks = datos.get(hora, (0, 0))

            fila = tk.Frame(
                tabla,
                bg="white",
                padx=15,
                pady=7
            )
            fila.pack(fill="x", pady=2)

            tk.Label(
                fila,
                text=f"{hora:02d}:00",
                width=12,
                font=("Arial", 11, "bold"),
                bg="white",
                fg="#17243a"
            ).pack(side="left")

            if tipo == "tiendas":

                variable = tk.StringVar(value=str(tiendas))

                entrada = tk.Entry(
                    fila,
                    textvariable=variable,
                    width=12,
                    font=("Arial", 12),
                    justify="center"
                )
                entrada.pack(side="left", padx=30)

                self.store_vars.append(variable)

            else:

                variable = tk.IntVar(value=picks)

                valor = tk.Label(
                    fila,
                    text=str(picks),
                    width=5,
                    bg="white",
                    font=("Arial", 12, "bold"),
                    fg="#1675bd"
                )
                valor.pack(side="left")

                slider = tk.Scale(
                    fila,
                    from_=0,
                    to=200,
                    orient="horizontal",
                    resolution=1,
                    variable=variable,
                    length=350,
                    bg="white",
                    highlightthickness=0,
                    command=lambda v, etiqueta=valor:
                        etiqueta.config(text=str(int(float(v))))
                )
                slider.pack(side="left", padx=20)

                self.pick_vars.append(variable)

        boton = tk.Button(
            self.contenido,
            text="GUARDAR DATOS",
            font=("Arial", 12, "bold"),
            bg="#1675bd",
            fg="white",
            activebackground="#105b96",
            activeforeground="white",
            relief="flat",
            padx=30,
            pady=12,
            command=self.guardar
        )
        boton.pack(anchor="e", padx=40, pady=15)

    # --------------------------------
    # GUARDAR DATOS
    # --------------------------------

    def guardar(self):

        if self.pantalla == "servicio":

            try:
                valor = self.daily_var.get().strip()
                picks = int(valor) if valor else 0

                if picks < 0:
                    raise ValueError

                cursor.execute("""
                    INSERT INTO servicios (fecha, picks)
                    VALUES (?, ?)
                    ON CONFLICT(fecha)
                    DO UPDATE SET picks=excluded.picks
                """, (self.fecha_actual, picks))

            except ValueError:
                messagebox.showerror(
                    "Error",
                    "Introduce un número entero válido de picks."
                )
                return

        elif self.pantalla in ("tiendas", "picks"):

            cursor.execute("""
                SELECT hora, tiendas, picks
                FROM horas
                WHERE fecha=?
            """, (self.fecha_actual,))

            cursor.execute("BEGIN")

            for hora in range(24):

                cursor.execute("""
                    SELECT tiendas, picks
                    FROM horas
                    WHERE fecha=? AND hora=?
                """, (self.fecha_actual, hora))

                actual = cursor.fetchone()
                tiendas = actual[0] if actual else 0
                picks = actual[1] if actual else 0

                if self.pantalla == "tiendas":
                    try:
                        valor = self.store_vars[hora].get().strip()
                        tiendas = int(valor) if valor else 0
                        if tiendas < 0:
                            raise ValueError
                    except ValueError:
                        messagebox.showerror(
                            "Error",
                            f"Número de tiendas no válido a las {hora:02d}:00."
                        )
                        conexion.rollback()
                        return

                else:
                    picks = self.pick_vars[hora].get()

                cursor.execute("""
                    INSERT INTO horas (fecha, hora, tiendas, picks)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(fecha, hora)
                    DO UPDATE SET
                        tiendas=excluded.tiendas,
                        picks=excluded.picks
                """, (self.fecha_actual, hora, tiendas, picks))

        conexion.commit()

        messagebox.showinfo(
            "Guardado",
            "Los datos se han guardado correctamente."
        )

    def boton_guardar(self, tarjeta):

        tk.Button(
            tarjeta,
            text="GUARDAR DATOS",
            font=("Arial", 11, "bold"),
            bg="#1675bd",
            fg="white",
            relief="flat",
            padx=25,
            pady=10,
            command=self.guardar
        ).pack(anchor="w", pady=20)


# --------------------------------
# INICIAR PROGRAMA
# --------------------------------

if __name__ == "__main__":

    root = tk.Tk()
    app = AlmacenApp(root)
    root.mainloop()
