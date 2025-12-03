# -*- coding: utf-8 -*-
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import (
    QAction, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QCompleter, QPushButton, QMenu, QApplication,
    QListWidget, QListWidgetItem, QDialogButtonBox
)
from qgis.PyQt.QtCore import QMimeData, QVariant
from qgis.gui import QgsVertexMarker
from qgis.core import (
    QgsPointXY, QgsCoordinateTransform, QgsProject, QgsCoordinateReferenceSystem,
    QgsWkbTypes, QgsVectorLayer, QgsFields, QgsField, QgsFeature, QgsGeometry,
    Qgis
)
from ..settings import read_current_settings

# Campo por defecto histórico (fallback)
EXPECTED_FIELD = "ID_ROAD"


def formato_pk(pk_total):
    km = int(pk_total)
    m = int(round((pk_total - km) * 1000))
    return f"{km}+{m:03d}"


class LocalizarPK:
    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.action = None
        self.history_menu = None
        self.history = []   # [(via, pk_km, map_pt)]
        self.markers = []   # [QgsVertexMarker, QgsVertexMarker]
        self.layer = None
        self.id_field = EXPECTED_FIELD
        self.m_units = "m"   # "m" (por defecto) o "km"

    def create_action(self):
        icon = QIcon(":/plugins/pk_tools/icons/localizar.png")
        self.action = QAction(icon, "Localizar PK", self.iface.mainWindow())
        self.action.setToolTip("Localizar punto según PK en vía calibrada")
        self.history_menu = QMenu(self.iface.mainWindow())
        self.history_menu.setTitle("Historial")
        self.action.setMenu(self.history_menu)
        self.action.triggered.connect(self.run)
        self._update_history_menu()
        return self.action

    def initGui(self):
        # Solo se usaría si esta clase gestionara su propio botón,
        # pero pk_tools.py ya crea la acción con create_action().
        icon = QIcon(":/plugins/pk_tools/icons/localizar.png")
        self.action = QAction(icon, "Localizar PK", self.iface.mainWindow())
        self.action.setToolTip("Localizar punto según PK en vía calibrada")
        self.history_menu = QMenu(self.iface.mainWindow())
        self.history_menu.setTitle("Historial")
        self.action.setMenu(self.history_menu)
        self.action.triggered.connect(self.open_dialog)
        self.iface.addToolBarIcon(self.action)
        self._update_history_menu()

    def unload(self):
        if self.action:
            self.iface.removeToolBarIcon(self.action)

    # ---------------------------------------------------
    # Apertura del diálogo principal
    # ---------------------------------------------------
    def open_dialog(self):
        """
        Abre el diálogo de localización usando la capa/campo/unidades definidos en settings.
        """
        try:
            cfg = read_current_settings()
            layer_name = cfg.get("layer_name") or ""
            id_field = cfg.get("id_field") or EXPECTED_FIELD
            m_units = cfg.get("m_units") or "m"

            if not layer_name:
                self.iface.messageBar().pushMessage(
                    "Localizar PK",
                    "No hay capa de trabajo configurada. Abre 'Configuración PK Tools' para definirla.",
                    level=Qgis.Info
                )
                return

            # Buscar capa por nombre
            layer = None
            for lyr in QgsProject.instance().mapLayers().values():
                if isinstance(lyr, QgsVectorLayer) and lyr.name() == layer_name:
                    layer = lyr
                    break

            if not layer:
                self.iface.messageBar().pushMessage(
                    "Localizar PK",
                    f"No se ha encontrado la capa '{layer_name}'. Revisa la configuración de PK Tools.",
                    level=Qgis.Warning
                )
                return

            # Validar geometría lineal con M y campo identificador
            if layer.geometryType() != QgsWkbTypes.LineGeometry:
                self.iface.messageBar().pushMessage(
                    "Localizar PK",
                    f"La capa '{layer_name}' no es lineal.",
                    level=Qgis.Warning
                )
                return

            if not QgsWkbTypes.hasM(layer.wkbType()):
                self.iface.messageBar().pushMessage(
                    "Localizar PK",
                    f"La capa '{layer_name}' no tiene geometría M.",
                    level=Qgis.Warning
                )
                return

            if layer.fields().indexOf(id_field) == -1:
                self.iface.messageBar().pushMessage(
                    "Localizar PK",
                    f"La capa '{layer_name}' no tiene el campo '{id_field}'.",
                    level=Qgis.Warning
                )
                return

            # Guardar en la instancia
            self.layer = layer
            self.id_field = id_field
            self.m_units = m_units

        except Exception:
            self.iface.messageBar().pushMessage(
                "Localizar PK",
                "Error inesperado al preparar la capa.",
                level=Qgis.Warning
            )
            return

        # A partir de aquí, self.layer está validada
        field = self.id_field
        road_names = sorted({
            f[field]
            for f in self.layer.getFeatures()
            if f[field]
        })

        # ----- Construcción del diálogo -----
        dlg = QDialog(self.iface.mainWindow())
        dlg.setWindowTitle("Localizar PK")
        vbox = QVBoxLayout()

        # Carretera
        h1 = QHBoxLayout()
        h1.addWidget(QLabel("Carretera:"))
        self.le_road = QLineEdit()
        completer = QCompleter(road_names)
        self.le_road.setCompleter(completer)
        h1.addWidget(self.le_road)
        vbox.addLayout(h1)

        # PK (km + m)
        h2 = QHBoxLayout()
        h2.addWidget(QLabel("Kilómetros:"))
        self.le_km = QLineEdit("0")
        h2.addWidget(self.le_km)
        h2.addWidget(QLabel("Metros (+):"))
        self.le_m = QLineEdit("000")
        h2.addWidget(self.le_m)
        vbox.addLayout(h2)

        # Botones
        hbtn = QHBoxLayout()
        hbtn.addStretch()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancelar")
        btn_ok.clicked.connect(dlg.accept)
        btn_cancel.clicked.connect(dlg.reject)
        hbtn.addWidget(btn_ok)
        hbtn.addWidget(btn_cancel)
        vbox.addLayout(hbtn)

        dlg.setLayout(vbox)
        if dlg.exec_() != QDialog.Accepted:
            return

        via = self.le_road.text().strip()
        try:
            km = float(self.le_km.text())
            m = int(self.le_m.text())
        except ValueError:
            self.iface.messageBar().pushWarning("Localizar PK", "Valores de km o m inválidos.")
            return

        pk_total_km = km + m / 1000.0
        self.locate(via, pk_total_km)

    # ---------------------------------------------------
    # Lógica de localización
    # ---------------------------------------------------
    def locate(self, via, pk_km):
        field = self.id_field or EXPECTED_FIELD

        # 0) Preparar objetivo según unidades del M
        # Si m_units == "m": M en metros → target_m = pk_km * 1000
        # Si m_units == "km": M en kilómetros → target_m = pk_km
        if (self.m_units or "m") == "m":
            target_m = pk_km * 1000.0
        else:
            target_m = pk_km

        EPS = 1e-6

        # 1) Reunir TODAS las features de la vía
        if not self.layer:
            self.iface.messageBar().pushWarning("Localizar PK", "No hay capa seleccionada.")
            return

        feats = [f for f in self.layer.getFeatures() if f[field] == via]
        if not feats:
            self.iface.messageBar().pushInfo("Localizar PK", f"No se encontró vía '{via}'.")
            return

        # 2) Auxiliar: interpolar por M (multipartes + M invertida)
        def _interpolate_point_by_m(geom, target_val):
            verts = list(geom.vertices())
            if len(verts) < 2:
                return None
            for i in range(len(verts) - 1):
                p0, p1 = verts[i], verts[i + 1]
                m0, m1 = p0.m(), p1.m()
                if m0 is None or m1 is None:
                    continue
                # ¿target entre m0 y m1 sin asumir orden?
                if (m0 - EPS <= target_val <= m1 + EPS) or (m1 - EPS <= target_val <= m0 + EPS):
                    if abs(m1 - m0) < EPS:
                        return QgsPointXY(p0.x(), p0.y())
                    t = (target_val - m0) / (m1 - m0)
                    x = p0.x() + t * (p1.x() - p0.x())
                    y = p0.y() + t * (p1.y() - p0.y())
                    return QgsPointXY(x, y)
            return None

        # 3) Buscar el tramo que contiene el target
        global_min = None
        global_max = None
        map_pt = None

        for f in feats:
            geom = f.geometry()
            m_vals = [pt.m() for pt in geom.vertices() if pt.m() is not None]
            if not m_vals:
                continue
            fmin, fmax = min(m_vals), max(m_vals)
            global_min = fmin if global_min is None else min(global_min, fmin)
            global_max = fmax if global_max is None else max(global_max, fmax)

            if fmin - EPS <= target_m <= fmax + EPS:
                pt = _interpolate_point_by_m(geom, target_m)
                if pt is not None:
                    map_pt = pt
                    break  # encontrado

        if map_pt is None:
            if global_min is not None and global_max is not None:
                # Convertimos el rango a km para que sea consistente con pk_km
                if (self.m_units or "m") == "m":
                    min_km = global_min / 1000.0
                    max_km = global_max / 1000.0
                else:
                    min_km = global_min
                    max_km = global_max

                self.iface.messageBar().pushInfo(
                    "Localizar PK",
                    f"PK {formato_pk(pk_km)} fuera de rango de la vía "
                    f"(rango total ~ {min_km:.3f}–{max_km:.3f} km)."
                )
            else:
                self.iface.messageBar().pushInfo(
                    "Localizar PK",
                    f"No hay medidas M válidas en la vía '{via}'."
                )
            return

        # 4) Transformar al CRS del mapa
        map_crs = self.canvas.mapSettings().destinationCrs()
        layer_crs = self.layer.crs()
        if layer_crs != map_crs:
            xf = QgsCoordinateTransform(layer_crs, map_crs, QgsProject.instance())
            map_pt = xf.transform(map_pt)

        # 5) Dibujar marcador y UI
        self._limpiar_marcadores()
        self._add_marker(map_pt, QColor(0, 0, 255))

        crs_wgs84 = QgsCoordinateTransform(
            map_crs,
            QgsCoordinateReferenceSystem("EPSG:4326"),
            QgsProject.instance()
        )
        pt_wgs = crs_wgs84.transform(map_pt)
        lat, lon = pt_wgs.y(), pt_wgs.x()
        url_sv = (
            "https://www.google.com/maps/@?api=1&map_action=pano"
            f"&viewpoint={lat:.6f},{lon:.6f}&heading=0&pitch=10&fov=250"
        )

        message_text = (
            f"Vía: {via} – PK {formato_pk(pk_km)} ({pk_km:.3f} km) | "
            f"<a href='{url_sv}'>Ver en Street View ({lat:.6f},{lon:.6f})</a>"
        )
        msg = self.iface.messageBar().createMessage("Localizar PK", message_text)

        btn_zoom = QPushButton("Zoom")
        btn_zoom.clicked.connect(lambda: self._zoom_al_punto(map_pt))
        msg.layout().addWidget(btn_zoom)

        btn_coord = QPushButton("Copiar coordenadas")

        def _copy_coords_link():
            coord_txt = f"{lat:.6f},{lon:.6f}"
            html = f'<a href="{url_sv}">{coord_txt}</a>'
            mime = QMimeData()
            mime.setText(coord_txt)   # texto plano
            mime.setHtml(html)        # enlace HTML
            QApplication.clipboard().setMimeData(mime)

        btn_coord.clicked.connect(_copy_coords_link)
        msg.layout().addWidget(btn_coord)

        btn_clear = QPushButton("Limpiar")
        btn_clear.clicked.connect(self._limpiar_marcadores)
        msg.layout().addWidget(btn_clear)

        self.iface.messageBar().pushWidget(msg, level=Qgis.Info)

        # 6) Historial
        self.history.insert(0, (via, pk_km, map_pt))
        self._update_history_menu()

    # ---------------------------------------------------
    # Utilidades de zoom y marcadores
    # ---------------------------------------------------
    def _zoom_al_punto(self, punto):
        self.canvas.setCenter(punto)
        self.canvas.zoomScale(25000)
        self.canvas.refresh()

    def _limpiar_marcadores(self):
        for m in self.markers:
            try:
                self.canvas.scene().removeItem(m)
            except Exception:
                pass
        self.markers = []

    def _add_marker(self, map_pt, color):
        ring = QgsVertexMarker(self.canvas)
        ring.setCenter(QgsPointXY(map_pt))
        ring.setColor(color)
        ring.setFillColor(QColor(0, 0, 0, 0))
        ring.setIconType(QgsVertexMarker.ICON_CIRCLE)
        ring.setIconSize(20)
        ring.setPenWidth(4)

        dot = QgsVertexMarker(self.canvas)
        dot.setCenter(QgsPointXY(map_pt))
        dot.setColor(color)
        dot.setFillColor(color)
        dot.setIconType(QgsVertexMarker.ICON_CIRCLE)
        dot.setIconSize(6)
        dot.setPenWidth(0)

        self.markers = [ring, dot]

    # ---------------------------------------------------
    # Historial y exportación
    # ---------------------------------------------------
    def _update_history_menu(self):
        self.history_menu.clear()

        # 1) Limpiar marcador
        act_clear = QAction("Limpiar marcador", self.iface.mainWindow())
        act_clear.triggered.connect(self._limpiar_marcadores)
        self.history_menu.addAction(act_clear)

        # 2) Exportar puntos
        act_export = QAction("Exportar puntos", self.iface.mainWindow())
        act_export.triggered.connect(self._exportar_historial)
        self.history_menu.addAction(act_export)

        # 3) Separador
        self.history_menu.addSeparator()

        # 4) Historial (más recientes primero)
        for via, pk_km, map_pt in self.history:
            texto = f"{via} – {formato_pk(pk_km)}"
            act = QAction(texto, self.iface.mainWindow())
            act.triggered.connect(
                lambda checked, v=via, p=pk_km, mp=map_pt: self._from_history(v, p, mp)
            )
            self.history_menu.addAction(act)

    def _from_history(self, via, pk_km, map_pt):
        # Redibuja el marcador y muestra el mensaje
        self._limpiar_marcadores()
        self._add_marker(map_pt, QColor(0, 0, 255))

        crs_wgs84 = QgsCoordinateTransform(
            self.canvas.mapSettings().destinationCrs(),
            QgsCoordinateReferenceSystem("EPSG:4326"),
            QgsProject.instance()
        )
        pt_wgs = crs_wgs84.transform(map_pt)
        lat, lon = pt_wgs.y(), pt_wgs.x()
        url_sv = (
            "https://www.google.com/maps/@?api=1&map_action=pano"
            f"&viewpoint={lat:.6f},{lon:.6f}&heading=0&pitch=10&fov=250"
        )

        message_text = (
            f"Vía: {via} – PK {formato_pk(pk_km)} ({pk_km:.3f} km) | "
            f"<a href='{url_sv}'>Ver en Street View ({lat:.6f},{lon:.6f})</a>"
        )
        msg = self.iface.messageBar().createMessage("Localizar PK", message_text)

        btn_zoom = QPushButton("Zoom")
        btn_zoom.clicked.connect(lambda: self._zoom_al_punto(map_pt))
        msg.layout().addWidget(btn_zoom)

        btn_coord = QPushButton("Copiar coordenadas")

        def _copy_coords_link():
            coord_txt = f"{lat:.6f},{lon:.6f}"
            html = f'<a href="{url_sv}">{coord_txt}</a>'
            mime = QMimeData()
            mime.setText(coord_txt)
            mime.setHtml(html)
            QApplication.clipboard().setMimeData(mime)

        btn_coord.clicked.connect(_copy_coords_link)
        msg.layout().addWidget(btn_coord)

        btn_clear = QPushButton("Limpiar")
        btn_clear.clicked.connect(self._limpiar_marcadores)
        msg.layout().addWidget(btn_clear)

        self.iface.messageBar().pushWidget(msg, level=Qgis.Info)

    def _exportar_historial(self):
        if not self.history:
            self.iface.messageBar().pushWarning("Exportar", "No hay puntos en el historial.")
            return

        dlg = QDialog(self.iface.mainWindow())
        dlg.setWindowTitle("Exportar puntos del historial")
        vbox = QVBoxLayout()

        label = QLabel("Selecciona los puntos a exportar:")
        vbox.addWidget(label)

        list_widget = QListWidget()
        list_widget.setSelectionMode(QListWidget.MultiSelection)

        # Desmarcados por defecto, más recientes primero (self.history ya lo está)
        for i, (via, pk_km, _) in enumerate(self.history):
            texto = f"{via} – {formato_pk(pk_km)} ({pk_km:.3f} km)"
            item = QListWidgetItem(texto)
            item.setSelected(False)
            item.setData(1000, i)  # índice en self.history
            list_widget.addItem(item)

        vbox.addWidget(list_widget)

        # Botones: Marcar/Desmarcar todos
        hbtn = QHBoxLayout()
        btn_sel_all = QPushButton("Marcar todos")
        btn_unsel_all = QPushButton("Desmarcar todos")
        btn_sel_all.clicked.connect(
            lambda: [list_widget.item(i).setSelected(True) for i in range(list_widget.count())]
        )
        btn_unsel_all.clicked.connect(
            lambda: [list_widget.item(i).setSelected(False) for i in range(list_widget.count())]
        )
        hbtn.addWidget(btn_sel_all)
        hbtn.addWidget(btn_unsel_all)
        vbox.addLayout(hbtn)

        # Aceptar / Cancelar
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        vbox.addWidget(buttons)

        dlg.setLayout(vbox)
        if dlg.exec_() != QDialog.Accepted:
            return

        seleccionados = [item.data(1000) for item in list_widget.selectedItems()]
        if not seleccionados:
            return

        # Crear capa temporal (EPSG:4326)
        vl = QgsVectorLayer("Point?crs=EPSG:4326", "Localización de PKs", "memory")
        pr = vl.dataProvider()
        pr.addAttributes([
            QgsField("VIA", QVariant.String),
            QgsField("PK", QVariant.String)
        ])
        vl.updateFields()

        # Transformación a WGS84 desde CRS del mapa
        xf = QgsCoordinateTransform(
            self.canvas.mapSettings().destinationCrs(),
            QgsCoordinateReferenceSystem("EPSG:4326"),
            QgsProject.instance()
        )

        for idx in seleccionados:
            via, pk_km, map_pt = self.history[idx]
            pt = xf.transform(map_pt)
            feat = QgsFeature()
            feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(pt)))
            feat.setAttributes([via, formato_pk(pk_km)])
            pr.addFeature(feat)

        vl.updateExtents()
        QgsProject.instance().addMapLayer(vl)

    def run(self):
        """Método de entrada para integrarlo en el plugin unificado."""
        self.open_dialog()
