from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLineEdit, QRadioButton, QVBoxLayout,
    QWidget, QPushButton, QMessageBox, QListWidget, QListWidgetItem, QDialog,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QLabel
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import QThread, pyqtSignal, Qt
import re
import sys
import webbrowser
import mysql.connector
import pandas as pd

class DatabaseConnector:
    def __init__(self):
        self.conexion = None

    def conectar_base_datos(self):
        try:
            self.conexion = mysql.connector.connect(
                user='glpi_rpt',
                password='En304$2424-2',
                host='10.48.63.60',
                database='glpidb',
                port='3306'
            )
            
            if self.conexion.is_connected():
                print("Conexión exitosa")
        except mysql.connector.Error as err:
            QMessageBox.critical(None, "Error de conexión", f"Error de conexión a la base de datos: {err}")
            sys.exit(1)

        return self.conexion

    def obtener_tecnicos(self):
        query = "SELECT DISTINCT CONCAT(realname, ' ', firstname) FROM glpi_users ORDER BY realname, firstname"
        cursor = self.conexion.cursor()
        cursor.execute(query)
        resultados = cursor.fetchall()
        cursor.close()
        return [r[0] for r in resultados]

class LoadingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle("Cargando...")
        self.setFixedSize(200, 100)
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Por favor espere, cargando..."))
        self.setLayout(layout)

class WorkerThread(QThread):
    done = pyqtSignal(object)

    def __init__(self, conexion, query, params):
        super().__init__()
        self.conexion = conexion
        self.query = query
        self.params = params

    def run(self):
        cursor = self.conexion.cursor()
        try:
            cursor.execute(self.query, self.params)
            resultados = cursor.fetchall()
            print("Resultados obtenidos:")  # Debug: imprime resultados obtenidos
        except mysql.connector.Error as err:
            print("Error ejecutando el query:", err)
            resultados = []
        finally:
            cursor.close()
        self.done.emit(resultados)

class MainWindow(QMainWindow):
    def __init__(self, db_connector):
        super().__init__()
        self.conexion = db_connector.conectar_base_datos()
        self.tecnicos = db_connector.obtener_tecnicos()
        self.tecnicos_seleccionados = []
        self.loading_dialog = LoadingDialog(self)
        self.query = ""  # Initialize the query attribute
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Tickeria")
        self.setGeometry(100, 100, 400, 300)
        self.setFixedSize(400, 300)

        main_layout = QVBoxLayout()

        # Fuente
        font = QFont("Arial", 10)

        # Fecha inicio
        self.fecha_ini = QLineEdit(self)
        self.fecha_ini.setPlaceholderText("Formato: yyyy-mm-dd")
        self.fecha_ini.setMaxLength(10)
        self.fecha_ini.setFont(font)

        # Fecha fin
        self.fecha_fin = QLineEdit(self)
        self.fecha_fin.setPlaceholderText("Formato: yyyy-mm-dd")
        self.fecha_fin.setMaxLength(10)
        self.fecha_fin.setFont(font)

        # Radio buttons
        self.radio_todos = QRadioButton("Todos los técnicos", self)
        self.radio_todos.setChecked(True)
        self.radio_todos.setFont(font)

        self.radio_seleccion = QRadioButton("Seleccionar técnicos", self)
        self.radio_seleccion.setFont(font)
        self.radio_seleccion.clicked.connect(self.seleccionar_tecnicos)

        # Botones
        self.borrar_seleccion_btn = QPushButton("Borrar Selección", self)
        self.borrar_seleccion_btn.setFont(font)
        self.borrar_seleccion_btn.clicked.connect(self.borrar_seleccion_tecnicos)

        self.ejecutar_btn = QPushButton("Ejecutar", self)
        self.ejecutar_btn.setFont(font)
        self.ejecutar_btn.clicked.connect(self.ejecutar_consulta)

        # Espacio extra
        top_spacer = QLabel(self)
        bottom_spacer = QLabel(self)

        # Agregar widgets al layout
        main_layout.addWidget(top_spacer)
        main_layout.addWidget(self.fecha_ini)
        main_layout.addWidget(self.fecha_fin)
        main_layout.addWidget(self.radio_todos)
        main_layout.addWidget(self.radio_seleccion)
        main_layout.addWidget(self.borrar_seleccion_btn)
        main_layout.addWidget(self.ejecutar_btn)
        main_layout.addWidget(bottom_spacer)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Estilo
        self.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                color: #cccccc;
            }
            QLineEdit, QRadioButton, QPushButton {
                background-color: #444444;
                border: 1px solid #666666;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
        """)

    def seleccionar_tecnicos(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Seleccionar Técnicos")
        dialog.setGeometry(100, 100, 350, 450)

        search_input = QLineEdit(dialog)
        search_input.setPlaceholderText("Buscar técnico...")

        listbox = QListWidget(dialog)
        listbox.setSelectionMode(QListWidget.MultiSelection)
        self.populate_listbox(listbox)

        search_input.textChanged.connect(lambda: self.filtrar_tecnicos(listbox, search_input.text()))

        confirm_btn = QPushButton("Confirmar Selección", dialog)
        confirm_btn.clicked.connect(lambda: self.elegir_tecnicos(listbox, dialog))

        layout = QVBoxLayout()
        layout.addWidget(search_input)
        layout.addWidget(listbox)
        layout.addWidget(confirm_btn)
        dialog.setLayout(layout)
        dialog.setModal(True)
        dialog.exec_()

    def populate_listbox(self, listbox):
        listbox.clear()
        for tecnico in self.tecnicos:
            item = QListWidgetItem(tecnico)
            listbox.addItem(item)
            if tecnico in self.tecnicos_seleccionados:
                item.setSelected(True)

    def filtrar_tecnicos(self, listbox, search_text):
        search_text = search_text.lower()
        for i in range(listbox.count()):
            item = listbox.item(i)
            item.setHidden(search_text not in item.text().lower())

    def elegir_tecnicos(self, listbox, dialog):
        self.tecnicos_seleccionados = [
            listbox.item(idx).text() for idx in range(listbox.count())
            if listbox.item(idx).isSelected()
        ]
        dialog.close()

    def borrar_seleccion_tecnicos(self):
        self.tecnicos_seleccionados = []
        self.radio_todos.setChecked(True)

    def validar_fecha(self, fecha):
        patron = re.compile(r'^\d{4}-\d{2}-\d{2}$')
        return patron.match(fecha) is not None

    def ejecutar_consulta(self):
        fecha_ini = self.fecha_ini.text()
        fecha_fin = self.fecha_fin.text()

        if not self.validar_fecha(fecha_ini) or not self.validar_fecha(fecha_fin):
            QMessageBox.critical(self, "Error de validación", "Las fechas deben estar en formato yyyy-mm-dd.")
            return

        tecnicos_condicion = ""
        if self.radio_seleccion.isChecked() and self.tecnicos_seleccionados:
            tecnicos_str = "', '".join(self.tecnicos_seleccionados)
            tecnicos_condicion = f"AND CONCAT(gu.realname, ' ', gu.firstname) IN ('{tecnicos_str}')"

        # Update the query attribute
        self.query = f"""
            SELECT
                resultado.tecnico_asignado,
                COUNT(DISTINCT resultado.ticket_id) AS total_tickets_cerrados,
                SUM(resultado.tickets_fuera_del_plazo) AS tickets_fuera_del_plazo,
                SUM(resultado.tickets_en_plazo) AS tickets_en_plazo,
                ROUND(100 * SUM(resultado.tickets_fuera_del_plazo) / NULLIF(COUNT(DISTINCT resultado.ticket_id), 0), 2) AS porcentaje_fuera_del_plazo,
                ROUND(100 * SUM(resultado.tickets_en_plazo) / NULLIF(COUNT(DISTINCT resultado.ticket_id), 0), 2) AS porcentaje_en_plazo,
                COALESCE(reabiertos.cuenta_de_tickets_reabiertos, 0) AS cuenta_de_tickets_reabiertos
            FROM (
                SELECT
                    CONCAT(gu.realname, ' ', gu.firstname) AS tecnico_asignado,
                    gt.id AS ticket_id,
                    CASE
                        WHEN gt.time_to_resolve IS NOT NULL
                            AND (gis.date_creation > gt.time_to_resolve
                                OR gis.date_creation IS NULL AND gt.time_to_resolve < NOW()
                                OR gt.date_creation < CONVERT_TZ(%s, 'America/Caracas', 'UTC')
                                OR gt.date_creation > CONVERT_TZ(%s, 'America/Caracas', 'UTC'))
                           THEN 1
                        ELSE 0
                    END AS tickets_fuera_del_plazo,
                    CASE
                        WHEN gt.time_to_resolve IS NOT NULL
                            AND gis.date_creation <= gt.time_to_resolve
                            AND gt.date_creation BETWEEN CONVERT_TZ(%s, 'America/Caracas', 'UTC') AND CONVERT_TZ(%s, 'America/Caracas', 'UTC')
                           THEN 1
                        ELSE 0
                    END AS tickets_en_plazo
                FROM
                    glpi_tickets gt
                JOIN glpi_entities ge ON gt.entities_id = ge.id
                JOIN glpi_tickets_users t_users_tec ON gt.id = t_users_tec.tickets_id AND t_users_tec.type = 2
                JOIN glpi_users gu ON t_users_tec.users_id = gu.id
                LEFT JOIN glpi_itilsolutions gis ON gt.id = gis.items_id AND gis.itemtype = 'Ticket'
                WHERE
                    gt.is_deleted = 0
                    AND gt.status > 4
                    AND gt.solvedate BETWEEN CONVERT_TZ(%s, 'America/Caracas', 'UTC') AND CONVERT_TZ(%s, 'America/Caracas', 'UTC')
                    AND gt.date BETWEEN CONVERT_TZ(%s, 'America/Caracas', 'UTC') AND CONVERT_TZ(%s, 'America/Caracas', 'UTC')
                    AND ge.completename IS NOT NULL
                    AND LOCATE('@', ge.completename) = 0
                    AND LOCATE('CASOS DUPLICADOS', UPPER(ge.completename)) = 0
                    {tecnicos_condicion}
                GROUP BY
                    tecnico_asignado,
                    gt.id
            ) AS resultado
            LEFT JOIN (
                SELECT
                    CONCAT(gu.realname, ' ', gu.firstname) AS tecnico_asignado,
                    COUNT(DISTINCT gi.items_id) AS cuenta_de_tickets_reabiertos
                FROM
                    glpi_itilsolutions gi
                INNER JOIN glpi_tickets gt ON gi.items_id = gt.id
                INNER JOIN glpi_users gu ON gi.users_id = gu.id
                WHERE
                    gi.status = 4
                    AND gi.users_id_approval > 0
                    AND CONVERT_TZ(gi.date_approval, 'UTC', 'America/Caracas') BETWEEN %s AND %s
                GROUP BY
                    tecnico_asignado
            ) AS reabiertos ON resultado.tecnico_asignado = reabiertos.tecnico_asignado
            GROUP BY
                resultado.tecnico_asignado
            HAVING
                total_tickets_cerrados IS NOT NULL
            ORDER BY
                resultado.tecnico_asignado;
        """

        # Mostrar el diálogo de carga
        self.loading_dialog.show()

        # Crear el hilo y conectarlo al método para manejar resultados
        self.worker_thread = WorkerThread(self.conexion, self.query, (f'{fecha_ini} 00:00:00', f'{fecha_fin} 23:59:59', f'{fecha_ini} 00:00:00', f'{fecha_fin} 23:59:59', f'{fecha_ini} 00:00:00', f'{fecha_fin} 23:59:59'))
        self.worker_thread.done.connect(self.handle_resultados)
        self.worker_thread.start()


    def handle_resultados(self, resultados):
        print("Handling resultados:", resultados)  # Debug: visualiza los resultados
        # Ocultar el diálogo de carga
        self.loading_dialog.hide()
        
        if not resultados:
            QMessageBox.information(self, "Información", "No se encontraron resultados.")
            return

        # Mostrar resultados
        self.mostrar_resultados(resultados)

    def mostrar_resultados(self, resultados):
        df_tickets = pd.DataFrame(resultados, columns=[
            "Tecnico_Asignado", "Numero_De_Tickets", "Tickets_Fuera_De_Plazo", 
            "Tickets_En_Plazo", "Porcentaje_Fuera_De_Plazo", "Porcentaje_En_Plazo", 
            "Cuenta_De_Tickets_Reabiertos"
        ])
        
        if df_tickets.empty:
            print("DataFrame está vacío")  # Debug
            QMessageBox.information(self, "Sin resultados", "No hay datos para mostrar.")
            return

        self.resultado_dlg = QDialog(self)
        self.resultado_dlg.setWindowTitle("Resultados")
        self.resultado_dlg.setGeometry(150, 150, 800, 600)

        tree = QTreeWidget(self.resultado_dlg)
        tree.setHeaderLabels([
            "Técnico", "Número de Tickets", "Fuera de Plazo", "En Plazo", 
            "Porcentaje Fuera", "Porcentaje En", "Cuenta de Tickets Reabiertos", "Tickets_Reabiertos"])
        tree.header().setSectionResizeMode(QHeaderView.Stretch)

        for _, row in df_tickets.iterrows():
            item = QTreeWidgetItem([str(row[col]) for col in df_tickets.columns])
            
            # Crear un botón "Mostrar" y conectar el evento para cargar y mostrar los tickets reabiertos
            btn = QPushButton("Mostrar")
            btn.clicked.connect(lambda _, t=row["Tecnico_Asignado"]: self.consulta_tickets_reabiertos(t))
            
            tree.addTopLevelItem(item)
            tree.setItemWidget(item, 7, btn)  # Cambiado para reflejar la nueva columna

        # Conectar evento de clic
        tree.itemClicked.connect(self.on_tecnico_clicked)

        # Label para mostrar la información del técnico
        tecnico_info_label = QLabel(self.resultado_dlg)
        tecnico_info_label.setWordWrap(True)
        self.tecnico_info_label = tecnico_info_label

        layout = QVBoxLayout()
        layout.addWidget(tree)
        layout.addWidget(tecnico_info_label)  # Agregar label al layout
        self.resultado_dlg.setLayout(layout)
        self.resultado_dlg.exec_()

    def on_tecnico_clicked(self, item, column):
        if column == 0:  # Solo actuar si se hace clic en la columna del técnico
            tecnico_nombre = item.text(0)
            self.tecnico_info_label.setText(f"Técnico seleccionado: {tecnico_nombre}")

    def consulta_tickets_reabiertos(self, tecnico):
        print(f"Consultando tickets reabiertos para: {tecnico}")  # Debug

        # Mostrar el diálogo de carga antes de ejecutar la consulta
        self.loading_dialog.show()

        fecha_ini = self.fecha_ini.text()
        fecha_fin = self.fecha_fin.text()

        query2 = """
        SELECT gi.items_id AS Nro_Ticket,
            MAX(DATE_FORMAT(gi.date_approval,GET_FORMAT(DATE,'ISO'))) AS Fecha_Reapertura,
            MAX(DATE_FORMAT(gt.date_creation,GET_FORMAT(DATE,'ISO'))) AS Fecha_Apertura,
            CONCAT(gu.realname, " ", gu.firstname) AS Tecnico_Asignado
        FROM glpi_itilsolutions gi
        INNER JOIN glpi_tickets gt ON gt.id = gi.items_id
        INNER JOIN glpi_users gu ON gu.id = gi.users_id
        WHERE gi.status = 4 
            AND gi.users_id_approval > 0 
            AND CONVERT_TZ(gi.date_approval,'UTC', 'America/Caracas') BETWEEN %s AND %s
            AND CONCAT(gu.realname, ' ', gu.firstname) = %s
        GROUP BY Nro_Ticket;
"""

        self.worker_thread = WorkerThread(self.conexion, query2, (f'{fecha_ini} 00:00:00', f'{fecha_fin} 23:59:59', tecnico))
        self.worker_thread.done.connect(self.handle_resultados_tickets_reabiertos)
        self.worker_thread.start()

    def abrir_enlace(self, item, column):
        if column == 0:  # Verifica que la columna sea la correcta (número de ticket)
            nro_ticket = item.text(0)  # Obtiene el texto del primer elemento (Número de Ticket)
            url = f"https://cs.intelix.biz/front/ticket.form.php?id={nro_ticket}"
            webbrowser.open_new_tab(url)

    def handle_resultados_tickets_reabiertos(self, resultados):
        # Oculta el diálogo de carga
        self.loading_dialog.hide()

        # Filtra los resultados para eliminar las filas con "None"
        resultados_filtrados = [row for row in resultados if row[3] is not None]

        # Verifica si hay resultados válidos
        if not resultados_filtrados:
            QMessageBox.information(self, "Tickets Reabiertos", "No se encontraron tickets reabiertos para el técnico.")
            return

        # Creación del diálogo para mostrar los tickets reabiertos
        dialog = QDialog(self)
        dialog.setWindowTitle("Tickets Reabiertos por Técnico")
        dialog.setGeometry(150, 150, 600, 400)

        layout = QVBoxLayout()
        tree = QTreeWidget()
        tree.setHeaderLabels(["Número de Ticket", "Fecha de Reapertura", "Fecha de Apertura", "Técnico Asignado"])
        tree.header().setSectionResizeMode(QHeaderView.Stretch)

        # Conecta la señal itemDoubleClicked al método abrir_enlace solo en este contexto
        tree.itemDoubleClicked.connect(self.abrir_enlace)

        # Añade cada resultado filtrado al QTreeWidget
        for row in resultados_filtrados:
            item = QTreeWidgetItem([str(col) for col in row])
            
            # Personaliza el estilo del número de ticket
            font = item.font(0)
            font.setUnderline(True)  # Subraya el texto para que parezca un enlace
            item.setFont(0, font)

            # Añadir un cursor con estilo de mano al pasar sobre el número de ticket
            item.setData(0, Qt.UserRole, "handCursor")

            tree.addTopLevelItem(item)
        
        # Aplica un estilo CSS para que el cursor adopte la forma de mano
        tree.setStyleSheet("""
            QTreeWidget::item:hover {
                cursor: pointer;
            }
        """)

        layout.addWidget(tree)
        dialog.setLayout(layout)
        dialog.exec_()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    db_connector = DatabaseConnector()
    window = MainWindow(db_connector)
    window.show()
    sys.exit(app.exec_())