# -*- coding: utf-8 -*-
"""
Módulo de configuración para PK Tools.

- Guarda y carga la configuración con QgsSettings.
- Proporciona un diálogo para seleccionar:
    * Capa de trabajo por defecto
    * Campo identificador de la vía
    * Unidades del campo M (m o km)
    * Vista previa de algunos valores M
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QDialogButtonBox, QTextEdit
)
from qgis.PyQt.QtCore import Qt
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsWkbTypes,
    QgsSettings, QgsGeometry, QgsPointXY
)


# Clave base en QgsSettings (queda en QGIS.ini bajo plugins/pk_tools/*)
SETTINGS_GROUP = "plugins/pk_tools"


class PKToolsSettings:
    """
    Pequeño wrapper para manejar la configuración del plugin.
    """
    KEY_LAYER_NAME = SETTINGS_GROUP + "/layer_name"
    KEY_ID_FIELD = SETTINGS_GROUP + "/id_field"
    KEY_M_UNITS  = SETTINGS_GROUP + "/m_units"   # "m" o "km"

    def __init__(self):
        self._qsettings = QgsSettings()

    def has_config(self) -> bool:
        """
        Indica si ya hay al menos una configuración guardada.
        """
        return self._qsettings.contains(self.KEY_LAYER_NAME)

    def load(self):
        """
        Devuelve un dict con la configuración actual (o valores por defecto).
        """
        layer_name = self._qsettings.value(self.KEY_LAYER_NAME, "", type=str)
        id_field   = self._qsettings.value(self.KEY_ID_FIELD, "ID_ROAD", type=str)
        m_units    = self._qsettings.value(self.KEY_M_UNITS, "m", type=str)
        if m_units not in ("m", "km"):
            m_units = "m"
        return {
            "layer_name": layer_name,
            "id_field": id_field,
            "m_units": m_units,
        }

    def save(self, layer_name: str, id_field: str, m_units: str):
        """
        Guarda los valores indicados.
        """
        self._qsettings.setValue(self.KEY_LAYER_NAME, layer_name)
        self._qsettings.setValue(self.KEY_ID_FIELD, id_field)
        self._qsettings.setValue(self.KEY_M_UNITS, m_units)


class PKToolsSettingsDialog(QDialog):
    """
    Diálogo de configuración.

    Permite al usuario elegir:
      - Capa por defecto (lineal con M)
      - Campo identificador de la vía
      - Unidades del campo M (m o km)
      - Vista previa de algunos valores M de la capa
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración de PK Tools")
        self.setMinimumWidth(420)

        self.settings_mgr = PKToolsSettings()
        self.current_cfg = self.settings_mgr.load()

        self._layers = self._find_candidate_layers()

        self._build_ui()
        self._populate_from_settings()

    # ---------------------------
    # Construcción de la UI
    # ---------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Capa
        row_layer = QHBoxLayout()
        row_layer.addWidget(QLabel("Capa de vías calibradas:"))
        self.cbo_layer = QComboBox()
        for lyr in self._layers:
            self.cbo_layer.addItem(lyr.name())
        self.cbo_layer.currentIndexChanged.connect(self._on_layer_changed)
        row_layer.addWidget(self.cbo_layer)
        layout.addLayout(row_layer)

        # Campo identificador
        row_field = QHBoxLayout()
        row_field.addWidget(QLabel("Campo identificador de la vía:"))
        self.cbo_field = QComboBox()
        row_field.addWidget(self.cbo_field)
        layout.addLayout(row_field)

        # Unidades del M
        row_units = QHBoxLayout()
        row_units.addWidget(QLabel("Unidades del campo M: (por defecto: metros)"))
        self.cbo_units = QComboBox()
        self.cbo_units.addItem("Metros", "m")
        self.cbo_units.addItem("Kilómetros", "km")
        row_units.addWidget(self.cbo_units)
        layout.addLayout(row_units)

        # Preview M
        layout.addWidget(QLabel("Vista previa de algunos valores M:"))
        self.txt_preview = QTextEdit()
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setMinimumHeight(120)
        layout.addWidget(self.txt_preview)

        # Botones OK / Cancelar
        self.btn_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            orientation=Qt.Horizontal,
            parent=self
        )
        self.btn_box.accepted.connect(self.accept)
        self.btn_box.rejected.connect(self.reject)
        layout.addWidget(self.btn_box)

    # ---------------------------
    # Rellenar datos iniciales
    # ---------------------------
    def _populate_from_settings(self):
        """
        Intenta seleccionar en la UI los valores guardados.
        """
        cfg = self.current_cfg

        # Seleccionar capa por nombre
        if self._layers and cfg["layer_name"]:
            for i, lyr in enumerate(self._layers):
                if lyr.name() == cfg["layer_name"]:
                    self.cbo_layer.setCurrentIndex(i)
                    break

        # Disparar actualización de campos + preview
        self._on_layer_changed(self.cbo_layer.currentIndex())

        # Seleccionar id_field
        if cfg["id_field"]:
            idx = self.cbo_field.findText(cfg["id_field"])
            if idx >= 0:
                self.cbo_field.setCurrentIndex(idx)

        # Seleccionar unidades
        units = cfg["m_units"]
        idx_units = self.cbo_units.findData(units)
        if idx_units >= 0:
            self.cbo_units.setCurrentIndex(idx_units)

    # ---------------------------
    # Búsqueda de capas y preview
    # ---------------------------
    def _find_candidate_layers(self):
        """
        Devuelve una lista de capas vectoriales lineales con M.
        """
        capas = []
        for layer in QgsProject.instance().mapLayers().values():
            if (isinstance(layer, QgsVectorLayer)
                and layer.geometryType() == QgsWkbTypes.LineGeometry
                and QgsWkbTypes.hasM(layer.wkbType())):
                capas.append(layer)
        return capas

    def _on_layer_changed(self, idx):
        """
        Cuando cambia la capa:
          - Rellena combo de campos
          - Actualiza preview de M
        """
        self.cbo_field.clear()
        if idx < 0 or idx >= len(self._layers):
            self.txt_preview.clear()
            return

        layer = self._layers[idx]

        # Campos: todos, pero si existe ID_ROAD lo dejamos seleccionado
        id_road_index = -1
        for i, fld in enumerate(layer.fields()):
            self.cbo_field.addItem(fld.name())
            if fld.name().upper() == "ID_ROAD":
                id_road_index = i
        if id_road_index >= 0:
            self.cbo_field.setCurrentIndex(id_road_index)

        # Preview de M
        self._update_preview(layer)

    def _update_preview(self, layer: QgsVectorLayer, max_features: int = 5):
        """
        Muestra algunos valores M de la capa para ayudar al usuario a
        deducir si están en metros o en kilómetros.
        """
        lines = []
        count = 0
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if not geom:
                continue
            m_vals = []
            for pt in geom.vertices():
                m = pt.m()
                if m is not None:
                    m_vals.append(m)
                if len(m_vals) >= 4:  # unos pocos valores por feature
                    break
            if m_vals:
                lines.append(f"Feature {feat.id()}: M ~ {', '.join(f'{v:.3f}' for v in m_vals)}")
                count += 1
            if count >= max_features:
                break

        if not lines:
            self.txt_preview.setPlainText("No se han encontrado valores M en las geometrías.")
        else:
            self.txt_preview.setPlainText("\n".join(lines))

    # ---------------------------
    # Acceso sencillo a valores
    # ---------------------------
    def selected_layer_name(self) -> str:
        idx = self.cbo_layer.currentIndex()
        if idx < 0 or idx >= len(self._layers):
            return ""
        return self._layers[idx].name()

    def selected_id_field(self) -> str:
        return self.cbo_field.currentText().strip()

    def selected_m_units(self) -> str:
        data = self.cbo_units.currentData()
        return data if data in ("m", "km") else "m"

    # ---------------------------
    # Aceptar diálogo
    # ---------------------------
    def accept(self):
        """
        Al aceptar, guardamos la configuración.
        """
        layer_name = self.selected_layer_name()
        id_field   = self.selected_id_field() or "ID_ROAD"
        m_units    = self.selected_m_units()

        self.settings_mgr.save(layer_name, id_field, m_units)
        super().accept()


def show_settings_dialog(iface):
    """
    Helper para abrir el diálogo de configuración desde el plugin.
    """
    parent = iface.mainWindow() if iface is not None else None
    dlg = PKToolsSettingsDialog(parent)
    dlg.exec_()


def read_current_settings():
    """
    Helper genérico para que otras herramientas lean la config actual.

    Ejemplo de uso:
        cfg = read_current_settings()
        id_field = cfg["id_field"]
        m_units  = cfg["m_units"]  # "m" / "km"
    """
    return PKToolsSettings().load()
