import sys
import re
import webbrowser
import mysql.connector
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLineEdit, QRadioButton, QVBoxLayout,
    QWidget, QPushButton, QMessageBox, QListWidget, QListWidgetItem, QDialog,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QLabel, QHBoxLayout, QFrame
)
from PyQt5.QtGui import QFont, QIcon, QColor
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QSize


class DatabaseConnector:
    """Clase para manejar la conexión y consultas a la base de datos"""
    
    def __init__(self):
        self.conexion = None

    def conectar_base_datos(self):
        """Establece conexión con la base de datos GLPI"""
        try:
            self.conexion = mysql.connector.connect(
                user='glpi_rpt',
                password='En304$2424-2',
                host='10.48.63.60',
                database='glpidb',
                port='3306',
            )
            
            if self.conexion.is_connected():
                print("Conexión exitosa")
        except mysql.connector.Error as err:
            QMessageBox.critical(None, "Error de conexión", 
                               f"Error de conexión a la base de datos: {err}")
            sys.exit(1)

        return self.conexion

    def obtener_tecnicos(self):
        """Obtiene la lista de técnicos desde la base de datos"""
        query = """
            SELECT DISTINCT CONCAT(realname, ' ', firstname) 
            FROM glpi_users 
            ORDER BY realname, firstname
        """
        cursor = self.conexion.cursor()
        cursor.execute(query)
        resultados = cursor.fetchall()
        cursor.close()
        return [r[0] for r in resultados]


class LoadingDialog(QDialog):
    """Diálogo para mostrar durante operaciones de carga"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        self.setModal(True)
        self.setWindowTitle("Cargando...")
        self.setFixedSize(300, 120)
        
        # Eliminar bordes de la ventana
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Frame principal con sombra
        main_frame = QFrame()
        main_frame.setStyleSheet("""
            QFrame {
                background-color: #3a3a3a;
                border-radius: 10px;
                border: 1px solid #4a4a4a;
            }
        """)
        
        frame_layout = QVBoxLayout(main_frame)
        frame_layout.setContentsMargins(15, 15, 15, 15)
        frame_layout.setSpacing(15)
        
        # Icono de carga
        icon_label = QLabel()
        icon_label.setPixmap(QIcon(":loading").pixmap(32, 32))
        icon_label.setAlignment(Qt.AlignCenter)
        
        # Texto
        text_label = QLabel("Procesando solicitud...")
        text_label.setAlignment(Qt.AlignCenter)
        text_label.setStyleSheet("color: #ffffff; font-size: 14px;")
        
        frame_layout.addWidget(icon_label)
        frame_layout.addWidget(text_label)
        layout.addWidget(main_frame)
        
        self.setLayout(layout)


class WorkerThread(QThread):
    """Hilo para ejecutar consultas en segundo plano"""
    
    done = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, conexion, query, params):
        super().__init__()
        self.conexion = conexion
        self.query = query
        self.params = params

    def run(self):
        """Ejecuta la consulta SQL en el hilo"""
        cursor = self.conexion.cursor()
        try:
            cursor.execute(self.query, self.params)
            resultados = cursor.fetchall()
        except mysql.connector.Error as err:
            self.error.emit(f"Error ejecutando el query: {err}")
            resultados = []
        finally:
            cursor.close()
        self.done.emit(resultados)


class TecnicosSelectionDialog(QDialog):
    """Diálogo para selección de técnicos"""
    
    def __init__(self, tecnicos, seleccionados=None, parent=None):
        super().__init__(parent)
        self.tecnicos = tecnicos
        self.seleccionados = seleccionados or []
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Seleccionar Técnicos")
        self.setMinimumSize(350, 450)
        
        # Estilo del diálogo
        self.setStyleSheet("""
            QDialog {
                background-color: #3a3a3a;
            }
            QListWidget {
                background-color: #444444;
                border: 1px solid #555555;
                border-radius: 5px;
                color: #eeeeee;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #5d5d5d;
                color: #ffffff;
            }
            QLineEdit {
                background-color: #444444;
                border: 1px solid #555555;
                border-radius: 5px;
                color: #eeeeee;
                padding: 5px;
                font-size: 12px;
            }
            QPushButton {
                background-color: #5d5d5d;
                border: 1px solid #666666;
                border-radius: 5px;
                color: #eeeeee;
                padding: 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #6d6d6d;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Barra de búsqueda
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar técnico...")
        self.search_input.setClearButtonEnabled(True)
        
        # Lista de técnicos
        self.listbox = QListWidget()
        self.listbox.setSelectionMode(QListWidget.MultiSelection)
        self.populate_listbox()
        
        # Botón de confirmación
        self.confirm_btn = QPushButton("Confirmar Selección")
        self.confirm_btn.clicked.connect(self.accept)
        
        # Conectar señales
        self.search_input.textChanged.connect(self.filtrar_tecnicos)
        
        layout.addWidget(QLabel("Seleccione los técnicos:"))
        layout.addWidget(self.search_input)
        layout.addWidget(self.listbox)
        layout.addWidget(self.confirm_btn)
        
        self.setLayout(layout)
        
    def populate_listbox(self):
        """Llena la lista con los técnicos disponibles"""
        self.listbox.clear()
        for tecnico in self.tecnicos:
            item = QListWidgetItem(tecnico)
            self.listbox.addItem(item)
            if tecnico in self.seleccionados:
                item.setSelected(True)
    
    def filtrar_tecnicos(self, search_text):
        """Filtra los técnicos según el texto de búsqueda"""
        search_text = search_text.lower()
        for i in range(self.listbox.count()):
            item = self.listbox.item(i)
            item.setHidden(search_text not in item.text().lower())
    
    def get_selected_tecnicos(self):
        """Devuelve los técnicos seleccionados"""
        return [
            self.listbox.item(idx).text() 
            for idx in range(self.listbox.count())
            if self.listbox.item(idx).isSelected()
        ]


class ResultsDialog(QDialog):
    """Diálogo para mostrar los resultados de las consultas"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Resultados")
        self.setMinimumSize(1000, 600)
        
        # Estilo del diálogo
        self.setStyleSheet("""
            QDialog {
                background-color: #2d2d2d;
                border: 2px solid #3d3d3d;
                border-radius: 10px;
            }
            QTreeWidget {
                background-color: #383838;
                alternate-background-color: #424242;
                border: 1px solid #4a4a4a;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #505050;
                color: #ffffff;
                padding: 6px;
                border: none;
                font-weight: bold;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 4px;
                padding: 5px 10px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # TreeWidget para mostrar resultados
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            "Técnico", "Cerrados dentro SLA", "Cerrados con SLA", "Pendientes SLA",
            "Cumplimiento SLA (%)", "Total Cerrados", "Tickets Recibidos",
            "Tickets Reabiertos", "Proporción Reabiertos/Cerrados (%)", "Acción"
        ])
        self.tree.header().setSectionResizeMode(QHeaderView.Interactive)
        self.tree.setAlternatingRowColors(True)
        
        # Etiqueta de información
        self.info_label = QLabel("Seleccione un técnico para ver detalles")
        self.info_label.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(self.tree)
        layout.addWidget(self.info_label)
        self.setLayout(layout)
    


    def load_data(self, data):
        self.tree.clear()
        for row in data.itertuples():
            proporcion_text = 'No hay tickets reabiertos' if row.Proporcion_Reabiertos_Cerrados == 0 else f"{row.Proporcion_Reabiertos_Cerrados}%"
            item = QTreeWidgetItem([
                str(row.Tecnico_Asignado),
                str(row.Cerrados_dentro_SLA),
                str(row.Cerrados_con_SLA),
                str(row.tickets_pendientes_SLA),
                f"{row.Cumplimiento_SLA}%",
                str(row.Cant_tickets_cerrados),
                str(row.Cant_tickets_recibidos),
                str(row.Reabiertos),
                proporcion_text
            ])
            
            # Resaltar valores importantes
            self.highlight_values(item)
            
            # Botón para mostrar tickets reabiertos
            btn = QPushButton("Detalles")
            btn.setProperty("tecnico", row.Tecnico_Asignado)
            btn.setCursor(Qt.PointingHandCursor)
        
            self.tree.addTopLevelItem(item)
            self.tree.setItemWidget(item, 9, btn)
    
    def highlight_values(self, item):
        """Resalta valores importantes en la tabla"""
        # Cumplimiento SLA
        cumplimiento_text = item.text(4).replace('%', '')
        try:
            cumplimiento = float(cumplimiento_text)
        except ValueError:
            cumplimiento = 0.0
        if cumplimiento < 80:
            item.setForeground(4, QColor('#ff6b6b'))  # Rojo para bajo cumplimiento
        elif cumplimiento > 95:
            item.setForeground(4, QColor('#6bff6b'))  # Verde para alto cumplimiento
        
        # Proporción Reabiertos/Cerrados
        proportion_text = item.text(8)
        if proportion_text == 'No hay tickets reabiertos':
            proportion = 0.0
        else:
            proportion = float(proportion_text.replace('%', ''))
        if proportion > 10:  # Más del 10% es preocupante
            item.setForeground(8, QColor('#ff6b6b'))


class MainWindow(QMainWindow):
    """Ventana principal de la aplicación"""
    
    def __init__(self, db_connector):
        super().__init__()
        self.db_connector = db_connector
        self.conexion = db_connector.conectar_base_datos()
        self.tecnicos = db_connector.obtener_tecnicos()
        self.tecnicos_seleccionados = []
        self.loading_dialog = LoadingDialog(self)
        self.setup_ui()
        
    def setup_ui(self):
        """Configura la interfaz de usuario principal"""
        self.setWindowTitle("Tickeria - Reportes GLPI")
        self.setWindowIcon(QIcon(":chart"))
        self.setMinimumSize(450, 400)
        
        # Fuente principal
        font = QFont("Segoe UI", 10)
        QApplication.setFont(font)
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Título
        title_label = QLabel("Reporte de Tickets por Técnico")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #ffffff;
                padding-bottom: 10px;
            }
        """)
        title_label.setAlignment(Qt.AlignCenter)
        
        # Frame para fechas
        date_frame = QFrame()
        date_frame.setStyleSheet("""
            QFrame {
                background-color: #444444;
                border-radius: 8px;
                padding: 10px;
            }
            QLabel {
                color: #eeeeee;
            }
        """)
        
        date_layout = QVBoxLayout(date_frame)
        date_layout.setContentsMargins(10, 10, 10, 10)
        date_layout.setSpacing(8)
        
        # Campos de fecha
        date_layout.addWidget(QLabel("Rango de Fechas:"))
        
        self.fecha_ini = QLineEdit()
        self.fecha_ini.setPlaceholderText("Fecha inicial (yyyy-mm-dd)")
        self.fecha_ini.setMaxLength(10)
        
        self.fecha_fin = QLineEdit()
        self.fecha_fin.setPlaceholderText("Fecha final (yyyy-mm-dd)")
        self.fecha_fin.setMaxLength(10)
        
        date_layout.addWidget(self.fecha_ini)
        date_layout.addWidget(self.fecha_fin)
        
        # Frame para opciones de técnicos
        tech_frame = QFrame()
        tech_frame.setStyleSheet("""
            QFrame {
                background-color: #444444;
                border-radius: 8px;
                padding: 10px;
            }
            QLabel {
                color: #eeeeee;
            }
        """)
        
        tech_layout = QVBoxLayout(tech_frame)
        tech_layout.setContentsMargins(10, 10, 10, 10)
        tech_layout.setSpacing(8)
        
        tech_layout.addWidget(QLabel("Selección de Técnicos:"))
        
        self.radio_todos = QRadioButton("Todos los técnicos")
        self.radio_todos.setChecked(True)
        
        self.radio_seleccion = QRadioButton("Seleccionar técnicos")
        self.radio_seleccion.toggled.connect(self.on_tech_selection_toggled)
        
        self.borrar_seleccion_btn = QPushButton("Borrar Selección")
        self.borrar_seleccion_btn.clicked.connect(self.borrar_seleccion_tecnicos)
        self.borrar_seleccion_btn.setEnabled(False)
        
        tech_layout.addWidget(self.radio_todos)
        tech_layout.addWidget(self.radio_seleccion)
        tech_layout.addWidget(self.borrar_seleccion_btn)
        
        # Botón de ejecución
        self.ejecutar_btn = QPushButton("Generar Reporte")
        self.ejecutar_btn.clicked.connect(self.ejecutar_consulta)
        self.ejecutar_btn.setStyleSheet("""
            QPushButton {
                background-color: #5d5d5d;
                border: 1px solid #666666;
                border-radius: 8px;
                color: #eeeeee;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #6d6d6d;
            }
            QPushButton:pressed {
                background-color: #4d4d4d;
            }
        """)
        
        # Agregar widgets al layout principal
        main_layout.addWidget(title_label)
        main_layout.addWidget(date_frame)
        main_layout.addWidget(tech_frame)
        main_layout.addStretch()
        main_layout.addWidget(self.ejecutar_btn)
        
        # Estilo general de la ventana
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2d2d2d;
            }
            QLineEdit {
                background-color: #383838;
                color: #ffffff;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                padding: 6px;
            }
            QRadioButton {
                color: #e0e0e0;
                spacing: 5px;
            }
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
    
    def on_tech_selection_toggled(self, checked):
        """Maneja el cambio en la selección de técnicos"""
        if checked:
            self.seleccionar_tecnicos()
        self.borrar_seleccion_btn.setEnabled(checked and bool(self.tecnicos_seleccionados))
    
    def seleccionar_tecnicos(self):
        """Muestra el diálogo para seleccionar técnicos"""
        dialog = TecnicosSelectionDialog(
            self.tecnicos, 
            self.tecnicos_seleccionados,
            self
        )
        
        if dialog.exec_() == QDialog.Accepted:
            self.tecnicos_seleccionados = dialog.get_selected_tecnicos()
            self.borrar_seleccion_btn.setEnabled(bool(self.tecnicos_seleccionados))
    
    def borrar_seleccion_tecnicos(self):
        """Borra la selección de técnicos"""
        self.tecnicos_seleccionados = []
        self.radio_todos.setChecked(True)
        self.borrar_seleccion_btn.setEnabled(False)
    
    def validar_fecha(self, fecha):
        """Valida el formato de fecha"""
        return re.match(r'^\d{4}-\d{2}-\d{2}$', fecha) is not None
    
    def ejecutar_consulta(self):
        """Ejecuta la consulta principal"""
        fecha_ini = self.fecha_ini.text()
        fecha_fin = self.fecha_fin.text()

        if not self.validar_fecha(fecha_ini) or not self.validar_fecha(fecha_fin):
            QMessageBox.critical(
                self, 
                "Error de validación", 
                "Las fechas deben estar en formato yyyy-mm-dd."
            )
            return

        tecnicos_condicion = ""
        if self.radio_seleccion.isChecked() and self.tecnicos_seleccionados:
            tecnicos_str = "', '".join(self.tecnicos_seleccionados)
            tecnicos_condicion = f"AND CONCAT(gu.realname, ' ', gu.firstname) IN ('{tecnicos_str}')"

        query = self.build_main_query(tecnicos_condicion)
        params = self.build_query_params(fecha_ini, fecha_fin)
        
        self.loading_dialog.show()
        self.worker_thread = WorkerThread(self.conexion, query, params)
        self.worker_thread.done.connect(self.handle_resultados)
        self.worker_thread.error.connect(self.handle_query_error)
        self.worker_thread.start()
    
    def build_main_query(self, tecnicos_condicion):
        """Construye la consulta SQL principal"""
        return f"""
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
                    WHEN COALESCE(reabiertos.cuenta_de_tickets_reabiertos, 0) = 0 THEN 0
                    ELSE ROUND(
                        (COALESCE(reabiertos.cuenta_de_tickets_reabiertos, 0) / COALESCE(cerrados_count.total_tickets_cerrados, 1)) * 100, 
                        2
                    )
                END AS Proporcion_Reabiertos_Cerrados
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
    
    def build_query_params(self, fecha_ini, fecha_fin):
        """Construye los parámetros para la consulta SQL"""
        return (
            f'{fecha_ini} 00:00:00', f'{fecha_fin} 23:59:59',
            f'{fecha_ini} 00:00:00', f'{fecha_fin} 23:59:59',
            f'{fecha_ini} 00:00:00', f'{fecha_fin} 23:59:59',
            f'{fecha_ini} 00:00:00', f'{fecha_fin} 23:59:59',
            f'{fecha_ini} 00:00:00', f'{fecha_fin} 23:59:59',
            f'{fecha_ini} 00:00:00', f'{fecha_fin} 23:59:59',
            fecha_fin, fecha_fin,
            f'{fecha_ini} 00:00:00', f'{fecha_fin} 23:59:59'
        )
    
    def handle_resultados(self, resultados):
        """Maneja los resultados de la consulta principal"""
        self.loading_dialog.hide()
        
        if not resultados:
            QMessageBox.information(self, "Resultados", "No se encontraron resultados para los criterios seleccionados.")
            return
        
        columnas = [
            "Tecnico_Asignado", "Cerrados_dentro_SLA", "Cerrados_con_SLA",
            "tickets_pendientes_SLA", "Cumplimiento_SLA", "Cant_tickets_cerrados",
            "Cant_tickets_recibidos", "Reabiertos", "Proporcion_Reabiertos_Cerrados"
        ]

        df_tickets = pd.DataFrame(resultados, columns=columnas)
        self.resultado_dlg = ResultsDialog(self)
        self.resultado_dlg.load_data(df_tickets)
        
        # Conectar señales para los botones de detalles
        for i in range(self.resultado_dlg.tree.topLevelItemCount()):
            item = self.resultado_dlg.tree.topLevelItem(i)
            btn = self.resultado_dlg.tree.itemWidget(item, 9)
            btn.clicked.connect(lambda _, t=item.text(0): self.consulta_tickets_reabiertos(t))
        
        self.resultado_dlg.exec_()
    
    def handle_query_error(self, error_msg):
        """Maneja errores en las consultas SQL"""
        self.loading_dialog.hide()
        QMessageBox.critical(self, "Error en la consulta", error_msg)
    
    def consulta_tickets_reabiertos(self, tecnico):
        """Consulta los tickets reabiertos para un técnico específico"""
        query = """
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
        self.worker_thread = WorkerThread(self.conexion, query, params)
        self.worker_thread.done.connect(self.handle_resultados_tickets_reabiertos)
        self.worker_thread.error.connect(self.handle_query_error)
        self.worker_thread.start()
    
    def handle_resultados_tickets_reabiertos(self, resultados):
        """Maneja los resultados de la consulta de tickets reabiertos"""
        self.loading_dialog.hide()
        resultados_filtrados = [row for row in resultados if row[3] is not None]
        
        if not resultados_filtrados:
            QMessageBox.information(self, "Tickets Reabiertos", "No se encontraron tickets reabiertos.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Tickets Reabiertos - {resultados_filtrados[0][3]}")
        dialog.setMinimumSize(600, 400)
        
        # Estilo del diálogo
        dialog.setStyleSheet("""
            QDialog {
                background-color: #3a3a3a;
            }
            QTreeWidget {
                background-color: #444444;
                border: 1px solid #555555;
                border-radius: 5px;
                color: #eeeeee;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 5px;
            }
            QTreeWidget::item:hover {
                background-color: #5d5d5d;
            }
            QHeaderView::section {
                background-color: #5d5d5d;
                padding: 5px;
                border: 1px solid #666666;
                font-size: 12px;
            }
        """)
        
        tree = QTreeWidget()
        tree.setHeaderLabels(["Ticket", "Reapertura", "Apertura", "Técnico"])
        tree.itemDoubleClicked.connect(self.abrir_enlace)
        tree.setAlternatingRowColors(True)

        for row in resultados_filtrados:
            item = QTreeWidgetItem([str(col) for col in row])
            # Estilo para el número de ticket (hacerlo parecer un enlace)
            font = item.font(0)
            font.setUnderline(True)
            item.setFont(0, font)
            item.setForeground(0, QColor('#4da6ff'))
            tree.addTopLevelItem(item)

        layout = QVBoxLayout()
        layout.addWidget(tree)
        dialog.setLayout(layout)
        dialog.exec_()
    
    def abrir_enlace(self, item, column):
        """Abre el ticket en el navegador web"""
        if column == 0:
            webbrowser.open_new_tab(f"https://cs.intelix.biz/front/ticket.form.php?id={item.text(0)}")


def main():
    """Función principal de la aplicación"""
    app = QApplication(sys.argv)
    
    # Establecer estilo general
    app.setStyle('Fusion')
    
    # Configurar paleta de colores oscuros
    palette = app.palette()
    palette.setColor(palette.Window, QColor(53, 53, 53))
    palette.setColor(palette.WindowText, Qt.white)
    palette.setColor(palette.Base, QColor(25, 25, 25))
    palette.setColor(palette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(palette.ToolTipBase, Qt.white)
    palette.setColor(palette.ToolTipText, Qt.white)
    palette.setColor(palette.Text, Qt.white)
    palette.setColor(palette.Button, QColor(53, 53, 53))
    palette.setColor(palette.ButtonText, Qt.white)
    palette.setColor(palette.BrightText, Qt.red)
    palette.setColor(palette.Link, QColor(42, 130, 218))
    palette.setColor(palette.Highlight, QColor(42, 130, 218))
    palette.setColor(palette.HighlightedText, Qt.black)
    app.setPalette(palette)
    
    # Crear e iniciar la ventana principal
    db_connector = DatabaseConnector()
    window = MainWindow(db_connector)
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()