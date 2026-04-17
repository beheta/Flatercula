
import sys
import requests
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QMenuBar, QMenu, QAction, QFileDialog,
    QDialog, QVBoxLayout, QLineEdit, QPushButton, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QProgressBar, QMessageBox
)
from PyQt5.QtGui import QTextCursor
from PyQt5.QtCore import Qt, QThread, pyqtSignal


# ----------------------------------------------------------------------
# Worker threads (run in background so the UI stays responsive)
# ----------------------------------------------------------------------
class ModelListThread(QThread):
    """Fetch the list of models from the Ollama API."""
    finished = pyqtSignal(list)          # emits a list of model dicts
    error = pyqtSignal(str)              # emits an error message string

    def run(self):
        try:
            response = requests.get("http://localhost:11434/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                self.finished.emit(models)
            else:
                self.error.emit("Failed to fetch the model list")
        except Exception as e:
            self.error.emit(str(e))


class ModelDeleteThread(QThread):
    """Delete a model via the Ollama API."""
    success = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, model_name):
        super().__init__()
        self.model_name = model_name

    def run(self):
        try:
            response = requests.delete(
                "http://localhost:11434/api/delete",
                json={"name": self.model_name}
            )
            if response.status_code == 200:
                self.success.emit(f"Deleted {self.model_name}")
            else:
                self.error.emit(f"Failed to delete {self.model_name}")
        except Exception as e:
            self.error.emit(str(e))


class ModelPullThread(QThread):
    """Pull (download) a model and report progress."""
    progress = pyqtSignal(int, str)   # percent, status text
    finished = pyqtSignal(str)        # final message
    error = pyqtSignal(str)

    def __init__(self, model_name):
        super().__init__()
        self.model_name = model_name

    def run(self):
        try:
            response = requests.post(
                "http://localhost:11434/api/pull",
                json={"name": self.model_name, "stream": True},
                stream=True
            )
            if response.status_code != 200:
                self.error.emit("Pull request failed")
                return

            total = None
            completed = 0
            status = ""

            # The API streams a series of JSON lines  we parse them onebyone.
            for line in response.iter_lines():
                if not line:
                    continue
                data = line.decode("utf-8")
                try:
                    json_data = eval(data)   # simple JSON parsing (same as original)
                except Exception:
                    continue

                status = json_data.get("status", "")
                if "total" in json_data:
                    total = json_data["total"]
                if "completed" in json_data:
                    completed = json_data["completed"]
                    if total:
                        percent = int((completed / total) * 100)
                        self.progress.emit(percent, status)

                if "error" in json_data:
                    self.error.emit(json_data["error"])
                    return

            self.finished.emit(f"Pull of {self.model_name} finished")
        except Exception as e:
            self.error.emit(str(e))


class ModelCreateThread(QThread):
    """Create a custom model from a base model + system prompt."""
    success = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, model_name, base_model, system_prompt):
        super().__init__()
        self.model_name = model_name
        self.base_model = base_model
        self.system_prompt = system_prompt

    def run(self):
        try:
            # Build a minimal Modelfile (the same format used by Ollama)
            modelfile = f"FROM {self.base_model}\nSYSTEM {self.system_prompt}"
            response = requests.post(
                "http://localhost:11434/api/create",
                json={"name": self.model_name, "modelfile": modelfile},
                stream=True
            )
            if response.status_code != 200:
                self.error.emit("Failed to create the model")
                return

            # The create endpoint also streams JSON  we just look for an error.
            for line in response.iter_lines():
                if not line:
                    continue
                data = line.decode("utf-8")
                try:
                    json_data = eval(data)
                except Exception:
                    continue
                if "error" in json_data:
                    self.error.emit(json_data["error"])
                    return

            self.success.emit(f"Created {self.model_name}")
        except Exception as e:
            self.error.emit(str(e))


# ----------------------------------------------------------------------
# Dialog windows
# ----------------------------------------------------------------------
class ModelListDialog(QDialog):
    """Dialog that shows the list of models retrieved from the server."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Model List")
        self.layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        self.layout.addWidget(self.list_widget)

        self.load_button = QPushButton("Refresh List")
        self.load_button.clicked.connect(self.load_models)
        self.layout.addWidget(self.load_button)

        # Thread that actually fetches the list
        self.model_list_thread = ModelListThread()
        self.model_list_thread.finished.connect(self.show_models)
        self.model_list_thread.error.connect(self.show_error)

    def load_models(self):
        self.model_list_thread.start()

    def show_models(self, models):
        self.list_widget.clear()
        for model in models:
            item = QListWidgetItem(model["name"])
            self.list_widget.addItem(item)

    def show_error(self, message):
        QMessageBox.critical(self, "Error", message)


class ModelDeleteDialog(QDialog):
    """Dialog that lets the user pick a model to delete."""
    def __init__(self, models, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Delete Model")
        self.layout = QVBoxLayout(self)

        self.label = QLabel("Select a model to delete:")
        self.layout.addWidget(self.label)

        self.list_widget = QListWidget()
        for model in models:
            item = QListWidgetItem(model["name"])
            self.list_widget.addItem(item)
        self.layout.addWidget(self.list_widget)

        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_model)
        self.layout.addWidget(self.delete_button)

        self.delete_thread = None

    def delete_model(self):
        current_item = self.list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Warning", "No model selected")
            return

        model_name = current_item.text()
        self.delete_thread = ModelDeleteThread(model_name)
        self.delete_thread.success.connect(self.show_success)
        self.delete_thread.error.connect(self.show_error)
        self.delete_thread.start()

    def show_success(self, msg):
        QMessageBox.information(self, "Success", msg)
        self.accept()

    def show_error(self, msg):
        QMessageBox.critical(self, "Error", msg)


class ModelPullDialog(QDialog):
    """Dialog for pulling (downloading) a model."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pull Model")
        self.layout = QVBoxLayout(self)

        self.label = QLabel("Model name to pull:")
        self.layout.addWidget(self.label)

        self.input_line = QLineEdit()
        self.layout.addWidget(self.input_line)

        self.pull_button = QPushButton("Start Pull")
        self.pull_button.clicked.connect(self.start_pull)
        self.layout.addWidget(self.pull_button)

        self.progress_bar = QProgressBar()
        self.layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.layout.addWidget(self.status_label)

        self.pull_thread = None

    def start_pull(self):
        model_name = self.input_line.text().strip()
        if not model_name:
            QMessageBox.warning(self, "Warning", "Please enter a model name")
            return

        self.pull_thread = ModelPullThread(model_name)
        self.pull_thread.progress.connect(self.update_progress)
        self.pull_thread.finished.connect(self.show_finished)
        self.pull_thread.error.connect(self.show_error)
        self.pull_thread.start()

    def update_progress(self, percent, status):
        self.progress_bar.setValue(percent)
        self.status_label.setText(status)

    def show_finished(self, msg):
        QMessageBox.information(self, "Done", msg)
        self.accept()

    def show_error(self, msg):
        QMessageBox.critical(self, "Error", msg)


class ModelCreateDialog(QDialog):
    """Dialog for creating a custom model."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Custom Model")
        self.layout = QVBoxLayout(self)

        # Base model
        self.base_label = QLabel("Base model name:")
        self.layout.addWidget(self.base_label)
        self.base_edit = QLineEdit()
        self.layout.addWidget(self.base_edit)

        # Custom model name
        self.name_label = QLabel("New model name:")
        self.layout.addWidget(self.name_label)
        self.name_edit = QLineEdit()
        self.layout.addWidget(self.name_edit)

        # System prompt
        self.prompt_label = QLabel("System prompt:")
        self.layout.addWidget(self.prompt_label)
        self.prompt_edit = QLineEdit()
        self.layout.addWidget(self.prompt_edit)

        # Create button
        self.create_button = QPushButton("Create")
        self.create_button.clicked.connect(self.create_model)
        self.layout.addWidget(self.create_button)

        self.create_thread = None

    def create_model(self):
        model_name = self.name_edit.text().strip()
        base_model = self.base_edit.text().strip()
        system_prompt = self.prompt_edit.text().strip()

        if not (model_name and base_model and system_prompt):
            QMessageBox.warning(self, "Warning", "All fields must be filled")
            return

        self.create_thread = ModelCreateThread(model_name, base_model, system_prompt)
        self.create_thread.success.connect(self.show_success)
        self.create_thread.error.connect(self.show_error)
        self.create_thread.start()

    def show_success(self, message):
        QMessageBox.information(self, "Success", message)
        self.accept()

    def show_error(self, message):
        QMessageBox.critical(self, "Error", message)


class ModelPullDialog(QDialog):
    """Simple wrapper that only contains a ModelPullThread UI."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pull Model")
        self.layout = QVBoxLayout(self)

        self.label = QLabel("Model name to pull:")
        self.layout.addWidget(self.label)

        self.input_line = QLineEdit()
        self.layout.addWidget(self.input_line)

        self.pull_button = QPushButton("Pull")
        self.pull_button.clicked.connect(self.start_pull)
        self.layout.addWidget(self.pull_button)

        self.progress_bar = QProgressBar()
        self.layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.layout.addWidget(self.status_label)

        self.pull_thread = None

    def start_pull(self):
        model_name = self.input_line.text().strip()
        if not model_name:
            QMessageBox.warning(self, "Warning", "Please enter a model name")
            return

        self.pull_thread = ModelPullThread(model_name)
        self.pull_thread.progress.connect(self.update_progress)
        self.pull_thread.finished.connect(self.show_finished)
        self.pull_thread.error.connect(self.show_error)
        self.pull_thread.start()

    def update_progress(self, percent, status):
        self.progress_bar.setValue(percent)
        self.status_label.setText(status)

    def show_finished(self, msg):
        QMessageBox.information(self, "Done", msg)
        self.accept()

    def show_error(self, msg):
        QMessageBox.critical(self, "Error", msg)


# ----------------------------------------------------------------------
# Main window
# ----------------------------------------------------------------------
class MainWindow(QMainWindow):
    """Main application window  a simple text editor with a menu to manage models."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LLM Model Manager")
        self.setGeometry(100, 100, 800, 600)

        # Central widget  just a plain text editor (you can replace it with anything)
        self.text_edit = QTextEdit()
        self.setCentralWidget(self.text_edit)

        self.create_menu()

    def create_menu(self):
        menubar = self.menuBar()

        # ----- Model Operations menu -----
        model_menu = menubar.addMenu("Model Operations")

        # Show model list
        list_action = QAction("Show Model List", self)
        list_action.triggered.connect(self.show_model_list)
        model_menu.addAction(list_action)

        # Pull model
        pull_action = QAction("Pull Model", self)
        pull_action.triggered.connect(self.show_model_pull)
        model_menu.addAction(pull_action)

        # Delete model
        delete_action = QAction("Delete Model", self)
        delete_action.triggered.connect(self.show_model_delete)
        model_menu.addAction(delete_action)

        # Create custom model
        create_action = QAction("Create Custom Model", self)
        create_action.triggered.connect(self.show_model_create)
        model_menu.addAction(create_action)

    # ------------------------------------------------------------------
    # Slots that open the dialogs
    # ------------------------------------------------------------------
    def show_model_list(self):
        dialog = ModelListDialog(self)
        dialog.exec_()

    def show_model_pull(self):
        dialog = ModelPullDialog(self)
        dialog.exec_()

    def show_model_delete(self):
        """First fetch the model list, then open the delete dialog."""
        self.list_thread = ModelListThread()
        self.list_thread.finished.connect(
            lambda models: ModelDeleteDialog(models, self).exec_()
        )
        self.list_thread.start()

    def show_model_create(self):
        dialog = ModelCreateDialog(self)
        dialog.exec_()


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())
