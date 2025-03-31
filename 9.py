from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLineEdit, QRadioButton, QVBoxLayout,
    QWidget, QPushButton, QMessageBox, QListWidget, QListWidgetItem, QDialog, QHBoxLayout, QProgressBar,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QLabel
)
from PyQt5.QtGui import QFont, QColor, QPalette, QFont, QIcon, QPainter, QBrush, QPen
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QSize, QRect
import re
import sys
import webbrowser
import mysql.connector
import pandas as pd


COLORS = {
    'background': '#F8F9FA',
    'primary': '#2A9D8F',
    'secondary': '#264653',
    'accent': '#E9C46A',
    'text': '#2B2D42',
    'success': '#4CAF50',
    'danger': '#E76F51',
    'light': '#FFFFFF',
    'dark': '#212529'
}

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
    cancel_requested = pyqtSignal()  # Señal para cancelar la operación

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle("")
        self.setFixedSize(300, 150)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)  # Eliminar barra de título
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)  # Márgenes internos
        layout.setSpacing(10)  # Espaciado entre elementos
        self.setLayout(layout)
        
        self.label = QLabel("Procesando solicitud...")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['light']};
                font-size: 16px;
                font-weight: bold;
                background: transparent; /* Fondo transparente */
            }}
        """)
        
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # Barra de progreso indeterminada
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                height: 12px;
            }}
            QProgressBar::chunk {{
                background-color: {COLORS['primary']};
                border-radius: 5px;
            }}
        """)
        
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['danger']};
                color: {COLORS['light']};
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {COLORS['dark']};
            }}
        """)
        self.cancel_button.clicked.connect(self.emit_cancel_signal)

        layout.addWidget(self.label)
        layout.addWidget(self.progress)
        layout.addWidget(self.cancel_button)
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['secondary']};
                border-radius: 12px;
                border: 2px solid {COLORS['primary']};
            }}
        """)

    def emit_cancel_signal(self):
        self.cancel_requested.emit()  # Emitir la señal de cancelación
        self.close()

class WorkerThread(QThread):
    done = pyqtSignal(object)

    def __init__(self, conexion, query, params):
        super().__init__()
        self.conexion = conexion
        self.query = query
        self.params = params
        self._is_cancelled = False  # Indicador de cancelación

    def run(self):
        cursor = self.conexion.cursor()
        try:
            cursor.execute(self.query, self.params)
            resultados = []
            while not self._is_cancelled:  # Verificar si se solicitó la cancelación
                row = cursor.fetchone()
                if row is None:
                    break
                resultados.append(row)
            if self._is_cancelled:
                print("Operación cancelada.")
                resultados = []  # Limpiar resultados si se cancela
        except mysql.connector.Error as err:
            print("Error ejecutando el query:", err)
            resultados = []
        finally:
            try:
                cursor.close()  # Cerrar el cursor correctamente
            except Exception as e:
                print(f"Error al cerrar el cursor: {e}")
        self.done.emit(resultados)

    def cancel(self):
        self._is_cancelled = True  # Establecer el indicador de cancelación

class MainWindow(QMainWindow):
    def __init__(self, db_connector):
        super().__init__()
        self.conexion = db_connector.conectar_base_datos()
        self.tecnicos = db_connector.obtener_tecnicos()
        self.tecnicos_seleccionados = []
        self.loading_dialog = LoadingDialog(self)
        self.loading_dialog.cancel_requested.connect(self.cancelar_operacion)  # Conectar la señal de cancelación
        self.worker_thread = None
        self.query = ""
        self.setup_ui()

    def cancelar_operacion(self):
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.cancel()  # Solicitar la cancelación del hilo
            self.worker_thread.wait()  # Esperar a que el hilo termine
            self.worker_thread = None
            QMessageBox.information(self, "Operación cancelada", "La operación ha sido cancelada.")
        self.loading_dialog.hide()

    def setup_ui(self):
        self.setWindowTitle("Tickeria - Reportes GLPI")
        self.setGeometry(100, 100, 600, 500)
        self.setMinimumSize(600, 500)
        
        # Estilo general
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
            }}
            QLineEdit {{
                background: {COLORS['light']};
                border: 2px solid {COLORS['secondary']}20;
                border-radius: 8px;
                padding: 10px 15px;
                font-size: 14px;
                selection-background-color: {COLORS['primary']};
            }}
            QLineEdit:focus {{
                border-color: {COLORS['primary']};
            }}
            QRadioButton {{
                font-size: 14px;
                spacing: 8px;
                color: {COLORS['text']};
            }}
            QRadioButton::indicator {{
                width: 20px;
                height: 20px;
                border-radius: 10px;
                border: 2px solid {COLORS['secondary']};
            }}
            QRadioButton::indicator:checked {{
                background-color: {COLORS['primary']};
                border-color: {COLORS['primary']};
            }}
            QPushButton {{
                background-color: {COLORS['primary']};
                color: {COLORS['light']};
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: 600;
                min-width: 120px;
                transition: all 0.3s;
            }}
            QPushButton:hover {{
                background-color: {COLORS['secondary']};
                transform: translateY(-1px);
            }}
            QPushButton:pressed {{
                background-color: {COLORS['secondary']};
                transform: translateY(1px);
            }}
            QPushButton#secondary {{
                background-color: {COLORS['accent']};
                color: {COLORS['text']};
            }}
            QListWidget {{
                background: {COLORS['light']};
                border: 2px solid {COLORS['secondary']}20;
                border-radius: 8px;
            }}
            QListWidget::item {{
                padding: 12px;
                border-bottom: 1px solid {COLORS['secondary']}15;
            }}
            QListWidget::item:selected {{
                background-color: {COLORS['primary']}40;
                color: {COLORS['text']};
            }}
        """)
        
        # Encabezado con degradado
        header = QLabel("Reporte de Métricas de Técnicos")
        header.setStyleSheet(f"""
            QLabel {{
                font-size: 24px;
                font-weight: 700;
                color: {COLORS['secondary']};
                padding: 20px 0;
                qproperty-alignment: AlignCenter;
            }}
        """)
        
        # Campos de fecha mejorados
        date_layout = QHBoxLayout()
        self.fecha_ini = self.create_date_input("Fecha Inicio (YYYY-MM-DD)")
        self.fecha_fin = self.create_date_input("Fecha Fin (YYYY-MM-DD)")
        date_layout.addWidget(self.fecha_ini)
        date_layout.addWidget(self.fecha_fin)
        
        # Radio buttons con iconos
        self.radio_todos = QRadioButton("Todos los técnicos")
        self.radio_seleccion = QRadioButton("Seleccionar técnicos específicos")
        self.radio_todos.setChecked(True)
        
        # Botones con iconos
        button_layout = QHBoxLayout()
        self.borrar_seleccion_btn = QPushButton(" Limpiar", icon=QIcon(":/icons/clear.png"))
        self.borrar_seleccion_btn.setObjectName("secondary")
        self.ejecutar_btn = QPushButton(" Generar Reporte", icon=QIcon(":/icons/report.png"))
        
        button_layout.addWidget(self.borrar_seleccion_btn)
        button_layout.addWidget(self.ejecutar_btn)
        
        # Ensamblado final
        main_layout = QVBoxLayout()
        main_layout.addWidget(header)
        main_layout.addSpacing(10)
        main_layout.addLayout(date_layout)
        main_layout.addSpacing(10)
        main_layout.addWidget(self.radio_todos)
        main_layout.addWidget(self.radio_seleccion)
        main_layout.addSpacing(20)
        main_layout.addLayout(button_layout)
        main_layout.addStretch()
        
        widget = QWidget()
        widget.setLayout(main_layout)
        self.setCentralWidget(widget)
        
        # Conectar señales (mantener igual)

        
        # Conectar señales
        self.radio_seleccion.clicked.connect(self.seleccionar_tecnicos)
        self.borrar_seleccion_btn.clicked.connect(self.borrar_seleccion_tecnicos)
        self.ejecutar_btn.clicked.connect(self.ejecutar_consulta)

    def create_date_input(self, placeholder):
        input_field = QLineEdit()
        input_field.setPlaceholderText(placeholder)
        input_field.setFixedHeight(45)
        input_field.setClearButtonEnabled(True)
        input_field.setStyleSheet(f"""
            QLineEdit {{
                font-size: 14px;
                background: {COLORS['light']};
                border: 2px solid {COLORS['secondary']}30;
            }}
            QLineEdit:hover {{
                border-color: {COLORS['secondary']}60;
            }}
        """)
        return input_field

    def seleccionar_tecnicos(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Seleccionar Técnicos")
        dialog.setMinimumSize(450, 500)
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['background']};
                border-radius: 12px;
            }}
        """)

        dialog.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
            QListWidget {
                border: 1px solid #dfe6e9;
                border-radius: 6px;
                background: white;
                alternate-background-color: #f8f9fa;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #dfe6e9;
            }
            QListWidget::item:selected {
                background-color: #4CAF50;
                color: white;
            }
        """)

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
            "Cant_tickets_recibidos", "Reabiertos", "Proporción Reabiertos/Cerrados (%)"
        ])
        
        self.resultado_dlg = QDialog(self)
        self.resultado_dlg.setWindowTitle("Resultados")
        self.resultado_dlg.setGeometry(150, 150, 1200, 600)
        self.resultado_dlg.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['background']};
            }}
        """)
        
        tree = QTreeWidget()
        tree.setHeaderLabels([
            "Técnico", "Cerrados SLA ✔", "Total SLA", "Pendientes", 
            "Cumplimiento (%)", "Total Cerrados", "Recibidos",
            "Reabiertos", "Reab./Cerrados (%)", "Acción"
        ])
        
        tree.header().setDefaultAlignment(Qt.AlignCenter)
        tree.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        
        tree.setStyleSheet(f"""
            QTreeWidget {{
                background: {COLORS['light']};
                border: none;
                border-radius: 8px;
                alternate-background-color: {COLORS['background']};
            }}
            QHeaderView::section {{
                background-color: {COLORS['primary']};
                color: {COLORS['light']};
                padding: 8px;
                border: none;
                font-weight: 600;
            }}
            QTreeWidget::item {{
                border-bottom: 1px solid {COLORS['secondary']}15;
                padding: 8px 0;
                color: {COLORS['text']}; /* Mantener el color del texto */
            }}
            QTreeWidget::item:selected {{
                background-color: {COLORS['primary']}15;
                color: {COLORS['text']}; /* Evitar que el texto se vuelva blanco */
            }}
            QTreeWidget::item:hover {{
                background-color: {COLORS['primary']}15;
            }}
        """)
        
        for _, row in df_tickets.iterrows():
            item = QTreeWidgetItem([
                str(row["Tecnico_Asignado"]),
                str(row["Cerrados_dentro_SLA"]),
                str(row["Cerrados_con_SLA"]),
                str(row["tickets_pendientes_SLA"]),
                f"{row['Cumplimiento SLA']}%",
                str(row["Cant_tickets_cerrados"]),
                str(row["Cant_tickets_recibidos"]),
                str(row["Reabiertos"]),
                f"{row['Proporción Reabiertos/Cerrados (%)']}%"
            ])
            
            for i in range(1, 9):
                item.setTextAlignment(i, Qt.AlignCenter)
            
            btn = QPushButton()
            btn.setIcon(QIcon(":/icons/search.png"))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['accent']};
                    border-radius: 6px;
                    padding: 6px;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['secondary']};
                }}
            """)
            btn.clicked.connect(lambda _, t=row["Tecnico_Asignado"]: self.consulta_tickets_reabiertos(t))
            
            tree.addTopLevelItem(item)
            tree.setItemWidget(item, 9, btn)

        layout = QVBoxLayout()
        layout.addWidget(tree)
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
    app.setStyle('Fusion')  # Usar estilo Fusion para mejor apariencia
    
    # Establecer paleta de colores global
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(COLORS['background']))
    palette.setColor(QPalette.WindowText, QColor(COLORS['text']))
    palette.setColor(QPalette.Base, QColor(COLORS['light']))
    palette.setColor(QPalette.AlternateBase, QColor(COLORS['background']))
    palette.setColor(QPalette.Button, QColor(COLORS['primary']))
    palette.setColor(QPalette.ButtonText, QColor(COLORS['light']))
    palette.setColor(QPalette.Highlight, QColor(COLORS['primary']))
    palette.setColor(QPalette.HighlightedText, QColor(COLORS['light']))
    app.setPalette(palette)
    
    db_connector = DatabaseConnector()
    window = MainWindow(db_connector)
    window.show()
    sys.exit(app.exec_())