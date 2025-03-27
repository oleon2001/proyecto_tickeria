import sys
import re
import webbrowser
import mysql.connector
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLineEdit, QRadioButton, QVBoxLayout,
    QWidget, QPushButton, QMessageBox, QListWidget, QListWidgetItem, QDialog,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QLabel, QHBoxLayout, QFrame,
    QProgressBar
)
from PyQt5.QtGui import QFont, QIcon, QColor, QPalette
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QSize, QTimer


# Configuración de la base de datos (considerar usar variables de entorno en producción)
DB_CONFIG = {
    'user': 'glpi_rpt',
    'password': 'En304$2424-2',
    'host': '10.48.63.60',
    'database': 'glpidb',
    'port': '3306',
}


class DatabaseConnector:
    """Manejador de conexión y consultas a la base de datos"""
    
    def __init__(self):
        self.connection = None

    def connect(self):
        """Establece conexión con la base de datos"""
        try:
            self.connection = mysql.connector.connect(**DB_CONFIG)
            if self.connection.is_connected():
                print("Conexión exitosa a la base de datos")
                return self.connection
        except mysql.connector.Error as err:
            QMessageBox.critical(
                None, 
                "Error de Conexión", 
                f"No se pudo conectar a la base de datos:\n{err}"
            )
            sys.exit(1)

    def get_technicians(self):
        """Obtiene lista de técnicos desde la base de datos"""
        query = """
            SELECT DISTINCT CONCAT(realname, ' ', firstname) 
            FROM glpi_users 
            ORDER BY realname, firstname
        """
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            return [row[0] for row in cursor.fetchall()]


class LoadingOverlay(QWidget):
    """Overlay de carga con animación"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: rgba(45, 45, 45, 220);
                border-radius: 10px;
                padding: 20px;
            }
        """)
        
        content = QVBoxLayout(container)
        content.setAlignment(Qt.AlignCenter)
        
        self.spinner = QProgressBar()
        self.spinner.setRange(0, 0)
        self.spinner.setFixedSize(60, 60)
        self.spinner.setStyleSheet("""
            QProgressBar {
                border: 2px solid #4CAF50;
                border-radius: 30px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                width: 10px;
            }
        """)
        
        self.label = QLabel("Procesando solicitud...")
        self.label.setStyleSheet("color: #FFFFFF; font-size: 14px;")
        
        content.addWidget(self.spinner)
        content.addWidget(self.label)
        layout.addWidget(container)
        
        self.adjustSize()
        
    def showEvent(self, event):
        """Centra el overlay al mostrarse"""
        if self.parent():
            self.move(
                self.parent().width()//2 - self.width()//2,
                self.parent().height()//2 - self.height()//2
            )
        super().showEvent(event)


class QueryWorker(QThread):
    """Hilo para ejecutar consultas en segundo plano"""
    
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    
    def __init__(self, connection, query, params):
        super().__init__()
        self.connection = connection
        self.query = query
        self.params = params
        
    def run(self):
        """Ejecuta la consulta SQL"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(self.query, self.params)
                results = cursor.fetchall()
                self.finished.emit(results)
        except Exception as e:
            self.error.emit(f"Error en la consulta: {str(e)}")


class TechnicianDialog(QDialog):
    """Diálogo de selección de técnicos con búsqueda"""
    
    def __init__(self, technicians, selected=None, parent=None):
        super().__init__(parent)
        self.technicians = technicians
        self.selected = selected or []
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Selección de Técnicos")
        self.setMinimumSize(400, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #2D2D2D;
            }
            QListWidget {
                background-color: #383838;
                color: #EAEAEA;
                border: 1px solid #454545;
                border-radius: 4px;
                font-size: 13px;
            }
            QLineEdit {
                background-color: #383838;
                color: #EAEAEA;
                border: 1px solid #454545;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 4px;
                padding: 8px 16px;
                min-width: 100px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #45A049;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        # Barra de búsqueda
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Buscar técnico...")
        self.search_field.addAction(QIcon(":search"), QLineEdit.LeadingPosition)
        
        # Lista de técnicos
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.MultiSelection)
        self.populate_list()
        
        # Botones
        self.confirm_btn = QPushButton("Confirmar")
        self.confirm_btn.clicked.connect(self.accept)
        
        # Conexiones
        self.search_field.textChanged.connect(self.filter_technicians)
        
        layout.addWidget(QLabel("Seleccione uno o más técnicos:"))
        layout.addWidget(self.search_field)
        layout.addWidget(self.list_widget)
        layout.addWidget(self.confirm_btn)
        
    def populate_list(self):
        """Llena la lista con los técnicos disponibles"""
        self.list_widget.clear()
        for tech in self.technicians:
            item = QListWidgetItem(tech)
            item.setSelected(tech in self.selected)
            self.list_widget.addItem(item)
            
    def filter_technicians(self, text):
        """Filtra técnicos basado en el texto de búsqueda"""
        text = text.lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(text not in item.text().lower())
            
    def get_selected(self):
        """Devuelve los técnicos seleccionados"""
        return [item.text() for item in self.list_widget.selectedItems()]


class ResultsViewer(QDialog):
    """Visualizador de resultados con tabla interactiva"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Resultados del Reporte")
        self.setMinimumSize(1200, 700)
        self.setStyleSheet("""
            QDialog {
                background-color: #2D2D2D;
            }
            QTreeWidget {
                background-color: #383838;
                color: #EAEAEA;
                alternate-background-color: #404040;
                font-size: 12px;
                border: none;
            }
            QHeaderView::section {
                background-color: #4CAF50;
                color: white;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 4px;
                padding: 6px 12px;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Configuración de la tabla
        self.table = QTreeWidget()
        self.table.setHeaderLabels([
            "Técnico", "SLA Cumplido", "SLA Total", "Pendientes",
            "% Cumplimiento", "Cerrados", "Recibidos", 
            "Reabiertos", "% Reaperturas", "Acciones"
        ])
        self.table.header().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.AscendingOrder)
        
        layout.addWidget(self.table)
        
    def load_data(self, data):
        """Carga datos en la tabla"""
        self.table.clear()
        
        for row in data.itertuples():
            item = QTreeWidgetItem([
                str(row.Tecnico_Asignado),
                str(row.Cerrados_dentro_SLA),
                str(row.Cerrados_con_SLA),
                str(row.tickets_pendientes_SLA),
                f"{row.Cumplimiento_SLA}%",
                str(row.Cant_tickets_cerrados),
                str(row.Cant_tickets_recibidos),
                str(row.Reabiertos),
                f"{row.Proporcion_Reabiertos_Cerrados}%"
            ])
            
            # Botón de detalles
            btn = QPushButton("Ver Detalles")
            btn.setProperty("technician", row.Tecnico_Asignado)
            btn.setCursor(Qt.PointingHandCursor)
            
            self.table.addTopLevelItem(item)
            self.table.setItemWidget(item, 9, btn)
            
            # Resaltado de valores
            self.highlight_item(item)
            
    def highlight_item(self, item):
        """Resalta valores importantes"""
        compliance = float(item.text(4).replace('%', ''))
        if compliance < 80:
            item.setForeground(4, QColor('#FF5252'))
        elif compliance > 95:
            item.setForeground(4, QColor('#4CAF50'))
            
        reopen_rate = float(item.text(8).replace('%', ''))
        if reopen_rate > 15:
            item.setForeground(8, QColor('#FF5252'))


class MainApp(QMainWindow):
    """Ventana principal de la aplicación"""
    
    def __init__(self):
        super().__init__()
        self.db = DatabaseConnector()
        self.db.connect()
        self.technicians = self.db.get_technicians()
        self.selected_tech = []
        self.loading = LoadingOverlay(self)
        self.setup_ui()
        
    def setup_ui(self):
        """Configura la interfaz gráfica"""
        self.setWindowTitle("Analizador de Tickets GLPI")
        self.setWindowIcon(QIcon(":chart"))
        self.setMinimumSize(600, 500)
        
        # Widget central
        central = QWidget()
        self.setCentralWidget(central)
        
        # Layout principal
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Sección de fechas
        date_frame = QFrame()
        date_frame.setStyleSheet("background-color: #383838; border-radius: 8px;")
        date_layout = QVBoxLayout(date_frame)
        date_layout.addWidget(QLabel("Rango de Fechas:", styleSheet="color: #EAEAEA;"))
        
        self.start_date = QLineEdit(placeholderText="Fecha inicial (AAAA-MM-DD)")
        self.end_date = QLineEdit(placeholderText="Fecha final (AAAA-MM-DD)")
        for field in [self.start_date, self.end_date]:
            field.setStyleSheet("""
                QLineEdit {
                    background-color: #454545;
                    color: #EAEAEA;
                    border-radius: 4px;
                    padding: 8px;
                }
            """)
            date_layout.addWidget(field)
        
        # Sección de técnicos
        tech_frame = QFrame()
        tech_frame.setStyleSheet("background-color: #383838; border-radius: 8px;")
        tech_layout = QVBoxLayout(tech_frame)
        tech_layout.addWidget(QLabel("Selección de Técnicos:", styleSheet="color: #EAEAEA;"))
        
        self.radio_all = QRadioButton("Todos los técnicos", checked=True)
        self.radio_select = QRadioButton("Seleccionar técnicos")
        self.clear_btn = QPushButton("Limpiar Selección", enabled=False)
        
        for widget in [self.radio_all, self.radio_select, self.clear_btn]:
            widget.setStyleSheet("color: #EAEAEA;")
            
        self.radio_select.toggled.connect(self.toggle_tech_selection)
        self.clear_btn.clicked.connect(self.clear_selection)
        
        tech_layout.addWidget(self.radio_all)
        tech_layout.addWidget(self.radio_select)
        tech_layout.addWidget(self.clear_btn)
        
        # Botón de ejecución
        self.run_btn = QPushButton("Generar Reporte", clicked=self.run_report)
        self.run_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 8px;
                padding: 12px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45A049;
            }
        """)
        
        # Ensamblar layout
        layout.addWidget(date_frame)
        layout.addWidget(tech_frame)
        layout.addStretch()
        layout.addWidget(self.run_btn)
        
    def toggle_tech_selection(self, checked):
        """Maneja la selección de técnicos"""
        if checked:
            self.select_technicians()
        self.clear_btn.setEnabled(checked and bool(self.selected_tech))
        
    def select_technicians(self):
        """Muestra el diálogo de selección"""
        dialog = TechnicianDialog(self.technicians, self.selected_tech, self)
        if dialog.exec_() == QDialog.Accepted:
            self.selected_tech = dialog.get_selected()
            
    def clear_selection(self):
        """Limpia la selección de técnicos"""
        self.selected_tech = []
        self.radio_all.setChecked(True)
        
    def validate_dates(self):
        """Valida el formato de las fechas"""
        pattern = r'^\d{4}-\d{2}-\d{2}$'
        return all(re.match(pattern, d) for d in [self.start_date.text(), self.end_date.text()])
        
    def run_report(self):
        """Ejecuta la consulta principal"""
        if not self.validate_dates():
            QMessageBox.warning(self, "Error", "Formato de fecha inválido. Use AAAA-MM-DD")
            return
            
        # Construir consulta y parámetros
        query = self.build_query()
        params = self.build_params()
        
        self.loading.show()
        self.worker = QueryWorker(self.db.connection, query, params)
        self.worker.finished.connect(self.handle_results)
        self.worker.error.connect(self.show_error)
        self.worker.start()
        
    def build_query(self):
        """Construye la consulta SQL"""
        tech_condition = ""
        if self.radio_select.isChecked() and self.selected_tech:
            tech_list = "', '".join(self.selected_tech)
            tech_condition = f"AND CONCAT(gu.realname, ' ', gu.firstname) IN ('{tech_list}')"
            
        return f"""
            -- Consulta SQL original aquí --
            {tech_condition}
            -- Resto de la consulta --
        """
        
    def build_params(self):
        """Construye los parámetros para la consulta"""
        return (
            self.start_date.text(), self.end_date.text(),
            # ... otros parámetros necesarios ...
        )
        
    def handle_results(self, data):
        """Maneja los resultados de la consulta"""
        self.loading.hide()
        if not data:
            QMessageBox.information(self, "Resultados", "No se encontraron datos")
            return
            
        # Procesar datos y mostrar en ResultsViewer
        columns = [
            "Tecnico_Asignado", "Cerrados_dentro_SLA", "Cerrados_con_SLA",
            "tickets_pendientes_SLA", "Cumplimiento_SLA", "Cant_tickets_cerrados",
            "Cant_tickets_recibidos", "Reabiertos", "Proporcion_Reabiertos_Cerrados"
        ]
        df = pd.DataFrame(data, columns=columns)
        
        viewer = ResultsViewer(self)
        viewer.load_data(df)
        viewer.exec_()
        
    def show_error(self, message):
        """Muestra errores al usuario"""
        self.loading.hide()
        QMessageBox.critical(self, "Error", message)


def setup_styles(app):
    """Configura el estilo visual de la aplicación"""
    app.setStyle("Fusion")
    
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(35, 35, 35))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Highlight, QColor(76, 175, 80))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    setup_styles(app)
    
    window = MainApp()
    window.show()
    
    sys.exit(app.exec_())