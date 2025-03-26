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
            print("Resultados obtenidos:")
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
        self.query = ""
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Tickeria")
        self.setGeometry(100, 100, 400, 300)
        self.setFixedSize(400, 300)

        main_layout = QVBoxLayout()
        font = QFont("Arial", 10)

        self.fecha_ini = QLineEdit(self)
        self.fecha_ini.setPlaceholderText("Formato: yyyy-mm-dd")
        self.fecha_ini.setMaxLength(10)
        self.fecha_ini.setFont(font)

        self.fecha_fin = QLineEdit(self)
        self.fecha_fin.setPlaceholderText("Formato: yyyy-mm-dd")
        self.fecha_fin.setMaxLength(10)
        self.fecha_fin.setFont(font)

        self.radio_todos = QRadioButton("Todos los técnicos", self)
        self.radio_todos.setChecked(True)
        self.radio_todos.setFont(font)

        self.radio_seleccion = QRadioButton("Seleccionar técnicos", self)
        self.radio_seleccion.setFont(font)
        self.radio_seleccion.clicked.connect(self.seleccionar_tecnicos)

        self.borrar_seleccion_btn = QPushButton("Borrar Selección", self)
        self.borrar_seleccion_btn.setFont(font)
        self.borrar_seleccion_btn.clicked.connect(self.borrar_seleccion_tecnicos)

        self.ejecutar_btn = QPushButton("Ejecutar", self)
        self.ejecutar_btn.setFont(font)
        self.ejecutar_btn.clicked.connect(self.ejecutar_consulta)

        main_layout.addWidget(QLabel())
        main_layout.addWidget(self.fecha_ini)
        main_layout.addWidget(self.fecha_fin)
        main_layout.addWidget(self.radio_todos)
        main_layout.addWidget(self.radio_seleccion)
        main_layout.addWidget(self.borrar_seleccion_btn)
        main_layout.addWidget(self.ejecutar_btn)
        main_layout.addWidget(QLabel())

        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

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
        return re.match(r'^\d{4}-\d{2}-\d{2}$', fecha) is not None
    
    def handle_resultados(self, resultados):
        self.loading_dialog.hide()
        self.mostrar_resultados(resultados)

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

        self.query = f"""
            SELECT
                recibidos.tecnico_asignado,
                COALESCE(cerrados_sla.Cant_tickets_cerrados_dentro_SLA, 0) AS Cant_tickets_cerrados_dentro_SLA,
                COALESCE(cerrados_sla.Cant_tickets_cerrados_con_SLA, 0) AS Cant_tickets_cerrados_con_SLA,
                COALESCE(pendientes_sla.T_pendiente_sla_vencido, 0) AS tickets_pendientes_SLA,
                ROUND(
                    (COALESCE(cerrados_sla.Cant_tickets_cerrados_dentro_SLA, 0) / 
                    (COALESCE(cerrados_sla.Cant_tickets_cerrados_con_SLA, 0) + COALESCE(pendientes_sla.T_pendiente_sla_vencido, 0))) * 100, 
                    2
                ) AS `Cumplimiento SLA`,
                COALESCE(cerrados_count.total_tickets_cerrados, 0) AS Cant_tickets_cerrados,
                COALESCE(recibidos.total_tickets_del_mes, 0) AS Cant_tickets_recibidos,
                CASE
                    WHEN COALESCE(cerrados_count.total_tickets_cerrados, 0) = 0 THEN 0 
                    ELSE ROUND((COALESCE(cerrados_count.total_tickets_cerrados, 0) / COALESCE(recibidos.total_tickets_del_mes, 0)) * 100, 2) 
                END AS `CumplimientoTR/TC`,
                COALESCE(reabiertos.cuenta_de_tickets_reabiertos, 0) AS cuenta_de_tickets_reabiertos,
                CASE
                    WHEN COALESCE(reabiertos.cuenta_de_tickets_reabiertos, 0) = 0 THEN 'No hay tickets reabiertos'
                    ELSE ROUND(
                        (COALESCE(reabiertos.cuenta_de_tickets_reabiertos, 0) / COALESCE(cerrados_count.total_tickets_cerrados, 1)) * 100, 
                        2
                    )
                END AS `Proporción Reabiertos/Cerrados (%)`
            FROM (
                SELECT
                    CONCAT(gu.realname, ' ', gu.firstname) AS tecnico_asignado,
                    COUNT(DISTINCT gt.id) AS total_tickets_del_mes
                FROM
                    glpi_tickets gt
                JOIN glpi_entities ge ON gt.entities_id = ge.id
                JOIN glpi_tickets_users t_users_tec ON gt.id = t_users_tec.tickets_id AND t_users_tec.type = 2
                JOIN glpi_users gu ON t_users_tec.users_id = gu.id
                WHERE
                    gt.is_deleted = 0
                    AND ge.completename IS NOT NULL
                    AND LOCATE('@', ge.completename) = 0
                    AND LOCATE('CASOS DUPLICADOS', UPPER(ge.completename)) = 0
                    AND gt.date BETWEEN CONVERT_TZ(%s, 'America/Caracas', 'UTC')
                                    AND CONVERT_TZ(%s, 'America/Caracas', 'UTC')
                    {tecnicos_condicion}
                GROUP BY tecnico_asignado
            ) AS recibidos
            LEFT JOIN (
                SELECT
                    CONCAT(gu.realname, ' ', gu.firstname) AS tecnico_asignado,
                    COUNT(DISTINCT gt.id) AS total_tickets_cerrados
                FROM
                    glpi_tickets gt
                JOIN glpi_entities ge ON gt.entities_id = ge.id
                JOIN glpi_tickets_users t_users_tec ON gt.id = t_users_tec.tickets_id AND t_users_tec.type = 2
                JOIN glpi_users gu ON t_users_tec.users_id = gu.id
                WHERE
                    gt.is_deleted = 0
                    AND gt.status > 4
                    AND gt.solvedate BETWEEN CONVERT_TZ(%s, 'America/Caracas', 'UTC')
                                        AND CONVERT_TZ(%s, 'America/Caracas', 'UTC')
                    AND gt.date BETWEEN CONVERT_TZ(%s, 'America/Caracas', 'UTC') - INTERVAL 90 DAY
                                    AND CONVERT_TZ(%s, 'America/Caracas', 'UTC')
                    {tecnicos_condicion}
                GROUP BY tecnico_asignado
            ) AS cerrados_count ON recibidos.tecnico_asignado = cerrados_count.tecnico_asignado
            LEFT JOIN (
                SELECT
                    CONCAT(gu.realname, ' ', gu.firstname) AS tecnico_asignado,
                    SUM(CASE WHEN gt.solvedate <= gt.time_to_resolve THEN 1 ELSE 0 END) AS Cant_tickets_cerrados_dentro_SLA,
                    COUNT(DISTINCT gt.id) AS Cant_tickets_cerrados_con_SLA
                FROM
                    glpi_tickets gt
                JOIN glpi_entities ge ON gt.entities_id = ge.id
                JOIN glpi_tickets_users t_users_tec ON gt.id = t_users_tec.tickets_id AND t_users_tec.type = 2
                JOIN glpi_users gu ON t_users_tec.users_id = gu.id
                WHERE
                    gt.is_deleted = 0
                    AND gt.status > 4
                    AND gt.solvedate BETWEEN CONVERT_TZ(%s, 'America/Caracas', 'UTC')
                                        AND CONVERT_TZ(%s, 'America/Caracas', 'UTC')
                    AND gt.date BETWEEN CONVERT_TZ(%s, 'America/Caracas', 'UTC') - INTERVAL 90 DAY
                                AND CONVERT_TZ(%s, 'America/Caracas', 'UTC')
                    {tecnicos_condicion}
                GROUP BY tecnico_asignado
            ) AS cerrados_sla ON recibidos.tecnico_asignado = cerrados_sla.tecnico_asignado
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
                    {tecnicos_condicion}
                GROUP BY tecnico_asignado
            ) AS reabiertos ON recibidos.tecnico_asignado = reabiertos.tecnico_asignado
            LEFT JOIN (
                SELECT
                    CONCAT(gu.realname, ' ', gu.firstname) AS tecnico_asignado,
                    SUM(
                        (
                            (YEAR(CASE WHEN gt.solvedate IS NULL THEN DATE(%s) + INTERVAL 1 DAY ELSE gt.solvedate END) - YEAR(gt.`date`)) * 12
                        ) + 
                        (
                            MONTH(CASE WHEN gt.solvedate IS NULL THEN DATE(%s) + INTERVAL 1 DAY ELSE gt.solvedate END) - MONTH(gt.`date`)
                        )
                    ) AS T_pendiente_sla_vencido
                FROM
                    glpi_tickets gt
                JOIN glpi_entities ge ON gt.entities_id = ge.id
                JOIN glpi_tickets_users t_users_tec ON gt.id = t_users_tec.tickets_id AND t_users_tec.type = 2
                JOIN glpi_users gu ON t_users_tec.users_id = gu.id
                WHERE
                    gt.is_deleted = 0
                    AND gt.date BETWEEN CONVERT_TZ(%s, 'America/Caracas', 'UTC')
                                    AND CONVERT_TZ(%s, 'America/Caracas', 'UTC')
                    AND (
                        (gt.solvedate > gt.time_to_resolve
                        AND MONTH(gt.time_to_resolve) = MONTH(gt.date)
                        AND MONTH(gt.solvedate) != MONTH(gt.date))
                        OR gt.solvedate IS NULL
                    )
                    {tecnicos_condicion}
                GROUP BY tecnico_asignado
            ) AS pendientes_sla ON recibidos.tecnico_asignado = pendientes_sla.tecnico_asignado
            ORDER BY recibidos.tecnico_asignado;
        """

        params = (
            f'{fecha_ini} 00:00:00', f'{fecha_fin} 23:59:59',
            f'{fecha_ini} 00:00:00', f'{fecha_fin} 23:59:59',
            f'{fecha_ini} 00:00:00', f'{fecha_fin} 23:59:59',
            f'{fecha_ini} 00:00:00', f'{fecha_fin} 23:59:59',
            f'{fecha_ini} 00:00:00', f'{fecha_fin} 23:59:59',
            f'{fecha_ini} 00:00:00', f'{fecha_fin} 23:59:59',
            fecha_fin, fecha_fin,
            f'{fecha_ini} 00:00:00', f'{fecha_fin} 23:59:59'
        )

        self.loading_dialog.show()
        self.worker_thread = WorkerThread(self.conexion, self.query, params)
        self.worker_thread.done.connect(self.handle_resultados)
        self.worker_thread.start()

    def mostrar_resultados(self, resultados):
        df_tickets = pd.DataFrame(resultados, columns=[
            "Tecnico_Asignado", "Cerrados_dentro_SLA", "Cerrados_con_SLA",
            "tickets_pendientes_SLA", "Cumplimiento SLA", "Cant_tickets_cerrados",
            "Cant_tickets_recibidos", "CumplimientoTR/TC", "Reabiertos", "Proporción Reabiertos/Cerrados (%)"
        ])
        
        self.resultado_dlg = QDialog(self)
        self.resultado_dlg.setWindowTitle("Resultados")
        self.resultado_dlg.setGeometry(150, 150, 1000, 600)

        tree = QTreeWidget()
        tree.setHeaderLabels([
            "Técnico", "Cerrados dentro SLA", "Cerrados con SLA", "Pendientes SLA",
            "Cumplimiento SLA (%)", "Total Cerrados", "Tickets Recibidos",
            "Cumplimiento TR/TC (%)", "Tickets Reabiertos", "Proporción Reabiertos/Cerrados (%)", "Acción"
        ])
        tree.header().setSectionResizeMode(QHeaderView.ResizeToContents)

        for _, row in df_tickets.iterrows():
            item = QTreeWidgetItem([
                str(row["Tecnico_Asignado"]),
                str(row["Cerrados_dentro_SLA"]),
                str(row["Cerrados_con_SLA"]),
                str(row["tickets_pendientes_SLA"]),
                str(row["Cumplimiento SLA"]),
                str(row["Cant_tickets_cerrados"]),
                str(row["Cant_tickets_recibidos"]),
                str(row["CumplimientoTR/TC"]),
                str(row["Reabiertos"]),
                str(row["Proporción Reabiertos/Cerrados (%)"])
            ])
            
            btn = QPushButton("Mostrar")
            btn.clicked.connect(lambda _, t=row["Tecnico_Asignado"]: self.consulta_tickets_reabiertos(t))
            tree.addTopLevelItem(item)
            tree.setItemWidget(item, 10, btn)

        tree.itemClicked.connect(self.on_tecnico_clicked)
        self.tecnico_info_label = QLabel()

        layout = QVBoxLayout()
        layout.addWidget(tree)
        layout.addWidget(self.tecnico_info_label)
        self.resultado_dlg.setLayout(layout)
        self.resultado_dlg.exec_()

    def on_tecnico_clicked(self, item, column):
        if column == 0:
            self.tecnico_info_label.setText(f"Técnico seleccionado: {item.text(0)}")

    def consulta_tickets_reabiertos(self, tecnico):
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
        
        params = (
            f'{self.fecha_ini.text()} 00:00:00', 
            f'{self.fecha_fin.text()} 23:59:59', 
            tecnico
        )

        self.loading_dialog.show()
        self.worker_thread = WorkerThread(self.conexion, query2, params)
        self.worker_thread.done.connect(self.handle_resultados_tickets_reabiertos)
        self.worker_thread.start()

    def handle_resultados_tickets_reabiertos(self, resultados):
        self.loading_dialog.hide()
        resultados_filtrados = [row for row in resultados if row[3] is not None]
        
        if not resultados_filtrados:
            QMessageBox.information(self, "Tickets Reabiertos", "No se encontraron tickets reabiertos.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Tickets Reabiertos")
        dialog.setGeometry(150, 150, 600, 400)

        tree = QTreeWidget()
        tree.setHeaderLabels(["Ticket", "Reapertura", "Apertura", "Técnico"])
        tree.itemDoubleClicked.connect(self.abrir_enlace)

        for row in resultados_filtrados:
            item = QTreeWidgetItem([str(col) for col in row])
            font = item.font(0)
            font.setUnderline(True)
            item.setFont(0, font)
            item.setData(0, Qt.UserRole, "handCursor")
            tree.addTopLevelItem(item)

        tree.setStyleSheet("QTreeWidget::item:hover { cursor: pointer; }")

        layout = QVBoxLayout()
        layout.addWidget(tree)
        dialog.setLayout(layout)
        dialog.exec_()

    def abrir_enlace(self, item, column):
        if column == 0:
            webbrowser.open_new_tab(f"https://cs.intelix.biz/front/ticket.form.php?id={item.text(0)}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    db_connector = DatabaseConnector()
    window = MainWindow(db_connector)
    window.show()
    sys.exit(app.exec_())