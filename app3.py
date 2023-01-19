import os
import sys
from datetime import datetime, timedelta

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QHBoxLayout,
    QWidget,
    QTableView,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QMessageBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QCheckBox,
    QDateEdit,
    QInputDialog,
    QStyledItemDelegate,
    QHeaderView,
    QStyle,
    QStyleOptionViewItem
)
from PySide6.QtCore import Qt, Slot, QDate, QSize, QRect, QEvent
from PySide6.QtSql import QSqlDatabase, QSqlTableModel, QSqlQuery
from PySide6.QtGui import QIcon


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tasques per mòdul")
        layout = QHBoxLayout()
        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

        self.data = Data()

        self.module_model = QSqlTableModel(self)
        self.module_model.setTable("module")
        self.module_model.setEditStrategy(QSqlTableModel.OnFieldChange)
        self.module_model.setHeaderData(1, Qt.Horizontal, "Name")
        self.module_model.select()

        self.module_component = ViewComponent("Mòduls")
        self.module_component.view.setModel(self.module_model)
        self.module_component.view.hideColumn(0)
        self.module_component.view.setSelectionBehavior(
            QTableView.SelectionBehavior.SelectRows)
        index = self.module_model.index(0, 1)
        self.module_component.view.setCurrentIndex(index)
        self.module_component.setMaximumWidth(250)
        selection_model = self.module_component.view.selectionModel()
        selection_model.selectionChanged.connect(self.on_selection_changed)
        self.module_component.add_button.clicked.connect(self.add_module)
        self.module_component.del_button.clicked.connect(self.del_module)
        layout.addWidget(self.module_component)

        self.task_model = SQLTableModel(self)
        self.task_model.setTable("task")
        self.task_model.setEditStrategy(QSqlTableModel.OnFieldChange)
        self.task_model.setHeaderData(2, Qt.Horizontal, "Descripció")
        self.task_model.setHeaderData(3, Qt.Horizontal, "Data Finalització")
        self.task_model.setHeaderData(4, Qt.Horizontal, "Fet")
        id_module_selected = self.module_model.index(0, 0).data()
        self.task_model.setFilter(f"module_id = {id_module_selected}")
        self.task_model.select()

        self.tasks_component = ViewComponent("Tasques")
        self.tasks_component.view.setModel(self.task_model)
        self.tasks_component.view.hideColumn(0)
        self.tasks_component.view.hideColumn(1)
        self.tasks_component.add_button.clicked.connect(self.add_task)
        self.tasks_component.del_button.clicked.connect(self.del_task)
        layout.addWidget(self.tasks_component)

    def add_task(self):
        self.task_model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        task_dialog = TaskDialog()
        if task_dialog.exec():
            self.data.connection.transaction()
            description = task_dialog.description.text()
            deadline = task_dialog.date_time.dateTime().toString('dd/MM/yyyy')
            # finished = task_dialog.finished.isChecked()
            record = self.task_model.record()
            # record.remove(record.indexOf("id"))
            index = self.module_component.view.currentIndex()
            id_module_selected = self.module_model.record(
                index.row()).value("id")
            record.setValue("module_id", id_module_selected)
            record.setValue("description", description)
            record.setValue("deadline", deadline)
            record.setValue("finished", 0)

            if self.task_model.insertRecord(-1, record):
                if self.task_model.submitAll():
                    self.task_model.database().commit()
            else:
                self.data.connection.rollback()
                QMessageBox.critical(
                    self,
                    "Error insertant insertant nou mòdul",
                    self.task_model.database().lastError().databaseText(),
                    buttons=QMessageBox.Ok,
                    defaultButton=QMessageBox.Ok
                )
        self.task_model.setEditStrategy(QSqlTableModel.OnFieldChange)

    def del_task(self):
        self.task_model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        index = self.tasks_component.view.currentIndex()
        if self.task_model.removeRow(index.row()):
            self.task_model.submitAll()
        self.task_model.setEditStrategy(QSqlTableModel.OnFieldChange)

    def add_module(self):
        self.module_model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        name, ok = QInputDialog.getText(self, "Nou mòdul", "Nom del mòdul")
        if (ok):
            self.data.connection.transaction()
            record = self.module_model.record()
            record.setValue("name", name)
            if self.module_model.insertRecord(-1, record):
                if self.module_model.submitAll():
                    self.module_model.database().commit()
                    index = self.module_model.index(
                        self.module_model.rowCount() - 1, 1)
                    self.module_component.view.setCurrentIndex(index)
            else:
                self.data.connection.rollback()
                QMessageBox.critical(
                    self,
                    "Error insertant insertant nou mòdul",
                    "Error insertant insertant nou mòdul" +
                    self.module_model.database().lastError().databaseText(),
                    buttons=QMessageBox.Ok,
                    defaultButton=QMessageBox.Ok
                )
        self.module_model.setEditStrategy(QSqlTableModel.OnFieldChange)

    def del_module(self):
        ok = QMessageBox.warning(
            self,
            "Borrar mòdul",
            "Estàs segur de borrar el mòdul? Es borraran les seues tasques",
            buttons=QMessageBox.Ok | QMessageBox.Cancel,
            defaultButton=QMessageBox.Cancel
        )
        if ok:
            self.module_model.setEditStrategy(QSqlTableModel.OnManualSubmit)
            index = self.module_component.view.currentIndex()
            if self.module_model.removeRow(index.row()):
                self.module_model.submitAll()
                self.module_model.database().commit()
            self.module_model.setEditStrategy(QSqlTableModel.OnFieldChange)
            index = self.module_model.index(0, 1)
            self.module_component.view.setCurrentIndex(index)

    @Slot()
    def on_selection_changed(self, selected):
        indexes = selected.indexes()
        id_module_selected = indexes[0].data()
        self.task_model.setFilter(f"module_id = {id_module_selected}")


class ViewComponent(QWidget):
    def __init__(self, title):
        super().__init__()
        main_layout = QVBoxLayout()

        self.setLayout(main_layout)
        self.view = QTableView()
        self.view.setItemDelegate(StyledItemDelegate(self.view))
        self.view.verticalHeader().setVisible(False)
        self.view.horizontalHeader().setStretchLastSection(True)
        self.view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        main_layout.addWidget(QLabel(title))
        main_layout.addWidget(self.view)

        buttons = QHBoxLayout()
        icon_path = os.path.join(os.path.dirname(__file__), "images/add.svg")
        self.add_button = QPushButton(icon=QIcon(icon_path))
        icon_path = os.path.join(os.path.dirname(__file__), "images/del.svg")
        self.del_button = QPushButton(icon=QIcon(icon_path))
        # icon_path = os.path.join(os.path.dirname(__file__), "images/edit.svg")
        # self.edit_button = QPushButton(icon=QIcon(icon_path))
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.del_button)
        # buttons.addWidget(self.edit_button)
        main_layout.addLayout(buttons)


class TaskDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Tasca")
        buttons = QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        button_box = QDialogButtonBox(buttons)

        form_layout = QFormLayout()
        self.setLayout(form_layout)

        self.description = QLineEdit()
        self.date_time = QDateEdit(datetime.now().date() + timedelta(days=1))
        # self.finished = QCheckBox()

        form_layout.addRow(QLabel("Descripció: "), self.description)
        form_layout.addRow(QLabel("Plaç: "), self.date_time)
        # form_layout.addRow(QLabel("Feta?: "), self.finished)

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        form_layout.addWidget(button_box)


class Data():
    def __init__(self) -> None:
        self.connection = QSqlDatabase.addDatabase("QSQLITE")
        path = os.path.join(os.path.dirname(__file__),
                            "data.sqlite")
        self.connection.setDatabaseName(path)

        if not self.connection.open():
            QMessageBox.critical(
                None,
                "Error connectant a la base de dades!",
                f"Database Error: {self.connection.lastError().databaseText()}"
            )
            sys.exit(1)
        else:
            self.connection.exec("PRAGMA foreign_keys = 1")

        if os.path.getsize(path) == 0:
            createTablesQuery = QSqlQuery()
            module_table_created = createTablesQuery.exec(
                """
                CREATE TABLE IF NOT EXISTS module (
                id INTEGER PRIMARY KEY ASC,
                name TEXT NOT NULL UNIQUE);
                """
            )
            task_table_created = createTablesQuery.exec(
                """
                CREATE TABLE IF NOT EXISTS task (
                id INTEGER PRIMARY KEY ASC,
                module_id integer NOT NULL,
                description TEXT NOT NULL,
                deadline TEXT NOT NULL,
                finished INTEGER NOT NULL,
                CONSTRAINT fk_module
                    FOREIGN KEY (module_id)
                    REFERENCES module (id)
                    ON DELETE CASCADE);
                """
            )
            if not (module_table_created and task_table_created):
                QMessageBox.critical(
                    None,
                    "Error connectant a la base de dades!",
                    f"Database Error: {self.connection.lastError().databaseText()}"
                )
                sys.exit(1)

            insertModulesQuery = QSqlQuery()
            # Estil OBDC
            prepared = insertModulesQuery.prepare(
                """
                INSERT INTO module (
                    name
                )
                VALUES (?)
                """
            )

            if prepared:
                data = ["DI", "AD", "PMDM", "PSP", "SGE",
                        "EIE", "ANG-II", "PROJECTE", "FCT"]
                # Inserció amb addBindValue
                for name in data:
                    insertModulesQuery.addBindValue(name)
                    insertModulesQuery.exec()

            insertModulesQuery = QSqlQuery()
            # Estil OBDC
            prepared = insertModulesQuery.prepare(
                """
                INSERT INTO task (
                    module_id,
                    description,
                    deadline,
                    finished
                )
                VALUES (?, ?, ?, ?)
                """
            )

            if prepared:
                data = [
                    ("1", "Tasca de prova 1", "23/01/2023", 0),
                    ("1", "Tasca de prova 2", "23/01/2023", 1),
                    ("2", "Tasca de prova 3", "23/01/2023", 1)
                ]
                # Inserció amb addBindValue
                for module_id, description, deadline, finished in data:
                    insertModulesQuery.addBindValue(module_id)
                    insertModulesQuery.addBindValue(description)
                    insertModulesQuery.addBindValue(deadline)
                    insertModulesQuery.addBindValue(finished)
                    insertModulesQuery.exec()


class StyledItemDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        if index.column() == 3:
            day, month, year = index.data().split("/")
            date = QDate(int(year), int(month), int(day))
            editor = QDateEdit(date, parent)
            editor.setDisplayFormat("dd/MM/yyyy")
        elif index.column() == 4:
            editor = None
        else:
            editor = super(StyledItemDelegate, self).createEditor(
                parent, option, index)

        return editor

    def setModelData(self, editor, model, index):
        if index.column() == 3:
            date = editor.date()
            model.setData(index, date.toString("dd/MM/yyyy"), Qt.DisplayRole)
        else:
            QStyledItemDelegate.setModelData(self, editor, model, index)

    def paint(self, painter, option, index):
        if index.column() == 4:  # centrar el CheckBox
            viewItemOption = QStyleOptionViewItem(option)
            center = QStyle.alignedRect(option.direction, Qt.AlignCenter,
                                        QSize(option.decorationSize.width() +
                                              5, option.decorationSize.height()),
                                        QRect(option.rect.x(), option.rect.y(),
                                              option.rect.width(), option.rect.height()))
            viewItemOption.rect = center
            super().paint(painter, viewItemOption, index)
        else:
            super().paint(painter, option, index)

    def editorEvent(self, event, model, option, index):
        if index.column() == 4:
            flags = model.flags(index)
            if not (flags and Qt.ItemIsUserCheckable) or not (flags and Qt.ItemIsEnabled):
                return False

            value = index.data(Qt.CheckStateRole)
            # if not value.isValid():
            #     return False

            if event.type() == QEvent.MouseButtonRelease:
                check_rect = QStyle.alignedRect(option.direction, Qt.AlignCenter,
                                                QSize(option.decorationSize.width() +
                                                      5, option.decorationSize.height()),
                                                QRect(option.rect.x(), option.rect.y(),
                                                      option.rect.width(), option.rect.height()))
                if not check_rect.contains(event.pos()):
                    return False
            elif event.type() == QEvent.KeyPress:
                if event.key() != Qt.Key_Space and event.key() != Qt.Key_Select:
                    return False
            else:
                return False

            if value == Qt.Checked.value:
                state = Qt.Unchecked
            else:
                state = Qt.Checked
            return model.setData(index, state, Qt.CheckStateRole)

        return super().editorEvent(event, model, option, index)


class SQLTableModel(QSqlTableModel):
    def __init__(self, parent):
        super().__init__(parent)

    def flags(self, index):
        if index.column() == 4:
            return super().flags(index) | Qt.ItemIsUserCheckable
        else:
            return super().flags(index)

    def data(self, index, role):
        if index.column() == 4:
            if role == Qt.CheckStateRole:
                checked = QSqlTableModel.data(self, index, Qt.DisplayRole)
                if checked:
                    return Qt.Checked
                else:
                    return Qt.Unchecked
        else:
            return QSqlTableModel.data(self, index, role)

    def setData(self, index, value, role):
        if index.column() == 3 and role == Qt.DisplayRole:
            return super().setData(index, value)
        if index.column() == 4 and role == Qt.CheckStateRole:
            if value == Qt.Checked:
                return super().setData(index, 1)
            else:
                return super().setData(index, 0)
        else:
            return super().setData(index, value, role)


if __name__ == "__main__":
    app = QApplication([])

    ventana1 = MainWindow()
    ventana1.setMinimumSize(800, 400)
    ventana1.show()

    app.exec()
