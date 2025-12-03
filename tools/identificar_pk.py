# -*- coding: utf-8 -*-
"""
Plugin QGIS: Identificar PK

Herramienta para identificar un PK (punto kilométrico) en capas lineales
con geometría M. Muestra un mensaje con información, enlaces a Street View
y botones de copia rápida. Además permite exportar puntos identificados
a una capa temporal de puntos.
"""

# IMPORTS
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import (
    QAction, QPushButton, QApplication,
    QMenu, QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QDialogButtonBox, QLabel
)
from qgis.PyQt.QtCore import Qt, QMimeData, QPoint, QVariant
from qgis.gui import QgsMapTool, QgsVertexMarker
from qgis.core import (
    QgsPointXY, QgsGeometry, QgsCoordinateTransform, QgsProject,
    QgsCoordinateReferenceSystem, QgsWkbTypes, QgsVectorLayer,
    QgsSpatialIndex, QgsField, QgsFeature, Qgis
)
from ..settings import read_current_settings


# Campo por defecto histórico (por si falta en settings)
EXPECTED_FIELD = "ID_ROAD"


def formato_pk(pk_total):
    """Convierte un valor decimal de PK en formato km+000."""
    km = int(pk_total)
    m = int(round((pk_total - km) * 1000))
    return f"{km}+{m:03d}"


# ============================================================
# CLASE PRINCIPAL DEL PLUGIN
# ============================================================
class IdentificarPK:
    """Controlador principal: gestiona la herramienta, mensajes y exportaciones."""

    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.tool = None          # instancia de IdentificarPKTool
        self.action = None        # solo se usaría si esta clase tuviera su propio botón
        self._current_msg = None  # referencia al mensaje visible en la barra

    # ---------- Inicialización opcional ----------
    # (pk_tools.py ya gestiona la toolbar, esto solo se usaría si quisieras
    # que IdentificarPK creara su propio botón de barra)
    def initGui(self):
        """Añade el botón a la barra de herramientas (no usado desde pk_tools.py)."""
        import os
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        icon = QIcon(icon_path)
        self.action = QAction(icon, "Identificar PK", self.iface.mainWindow())
        self.action.setToolTip("Identificar PK en línea calibrada")
        self.action.setCheckable(True)
        self.action.toggled.connect(self.toggle_tool)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        """Limpia todo al descargar el plugin."""
        self._pop_current_message()
        if self.tool:
            self.tool.clear_markers()
            if self.canvas.mapTool() == self.tool:
                self.canvas.unsetMapTool(self.tool)
            self.tool = None
        if self.action:
            self.iface.removeToolBarIcon(self.action)
            self.action = None

    # ---------- Gestión de la herramienta ----------
    def toggle_tool(self, checked):
        """Activa/desactiva la herramienta al pulsar el botón (si se usa initGui)."""
        if checked:
            ok = self.activate_tool()
            if not ok and self.action:
                self.action.setChecked(False)
        else:
            if self.tool:
                self.tool.clear_markers()
                if self.canvas.mapTool() == self.tool:
                    self.canvas.unsetMapTool(self.tool)
        self._pop_current_message()

    def activate_tool(self):
        """Selecciona la capa de configuración y activa la herramienta de identificación."""
        try:
            cfg = read_current_settings()
            layer_name = cfg.get("layer_name") or ""
            id_field = cfg.get("id_field") or EXPECTED_FIELD
            m_units = cfg.get("m_units") or "m"

            if not layer_name:
                self.iface.messageBar().pushMessage(
                    "Identificar PK",
                    "No hay capa de trabajo configurada. Abre 'Configuración PK Tools' para definirla.",
                    level=Qgis.Info
                )
                return False

            # Buscar la capa por nombre
            layer = None
            for lyr in QgsProject.instance().mapLayers().values():
                if isinstance(lyr, QgsVectorLayer) and lyr.name() == layer_name:
                    layer = lyr
                    break

            # Validar capa
            if (
                layer is None
                or layer.geometryType() != QgsWkbTypes.LineGeometry
                or not QgsWkbTypes.hasM(layer.wkbType())
                or layer.fields().indexOf(id_field) == -1
            ):
                self.iface.messageBar().pushMessage(
                    "Identificar PK",
                    (
                        f"La capa configurada '{layer_name}' no es válida. "
                        "Debe ser lineal, tener geometría M y contener el campo "
                        f"'{id_field}'."
                    ),
                    level=Qgis.Warning
                )
                return False

            # Inicializa la herramienta si no existe
            if not self.tool:
                self.tool = IdentificarPKTool(self.iface, self.canvas, self.show_pk_message)

            # Actualizar parámetros de la herramienta según la configuración
            self.tool.layer = layer
            self.tool.index = QgsSpatialIndex(layer.getFeatures())
            self.tool.id_field = id_field
            self.tool.m_units = m_units

            self.canvas.setMapTool(self.tool)
            return True

        except Exception:
            self.iface.messageBar().pushMessage(
                "Identificar PK",
                "Error inesperado al seleccionar la capa.",
                level=Qgis.Warning
            )
            return False

    # ---------- Mensajes ----------
    def _pop_current_message(self):
        """Elimina el mensaje actual de la barra si existe."""
        if self._current_msg is not None:
            try:
                self.iface.messageBar().popWidget(self._current_msg)
            except Exception:
                pass
            self._current_msg = None

    def show_pk_message(self, nombre_via, pk_value, url_sv, lat=None, lon=None):
        """Muestra en la barra el PK identificado, con enlace y botones de copia."""
        pk_str = formato_pk(pk_value)

        # Texto principal
        if lat is not None and lon is not None:
            texto = (
                f"Vía: {nombre_via} — PK {pk_str} ({pk_value:.3f} km) | "
                f"<a href='{url_sv}'>Street View: {lat:.6f},{lon:.6f}</a>"
            )
        else:
            texto = (
                f"Vía: {nombre_via} — PK {pk_str} ({pk_value:.3f} km) | "
                f"<a href='{url_sv}'>Street View</a>"
            )

        self._pop_current_message()
        msg = self.iface.messageBar().createMessage("Identificación de PK", texto)

        # Enlace adicional que NO cierra el mensaje
        lbl_sv = QLabel(f"<a href='{url_sv}'>[Street View]</a>")
        lbl_sv.setOpenExternalLinks(True)
        msg.layout().addWidget(lbl_sv)

        # Botones de copia
        btn_via = QPushButton("Copiar carretera")
        btn_via.clicked.connect(lambda: QApplication.clipboard().setText(f"{nombre_via}"))

        btn_pk = QPushButton("Copiar PK")
        btn_pk.clicked.connect(lambda: QApplication.clipboard().setText(pk_str))

        btn_coord = QPushButton("Copiar coordenadas")
        if url_sv and lat is not None and lon is not None:
            def _copy_coords_link():
                coord_txt = f"{lat:.6f},{lon:.6f}"
                html = f'<a href="{url_sv}">{coord_txt}</a>'
                mime = QMimeData()
                mime.setText(coord_txt)
                mime.setHtml(html)
                QApplication.clipboard().setMimeData(mime)
            btn_coord.clicked.connect(_copy_coords_link)
            btn_coord.setToolTip("Copia lat,lon como texto y como enlace HTML a Street View")
        else:
            btn_coord.setEnabled(False)

        msg.layout().addWidget(btn_via)
        msg.layout().addWidget(btn_pk)
        msg.layout().addWidget(btn_coord)

        self.iface.messageBar().pushWidget(msg, Qgis.Info)
        self._current_msg = msg

    def run(self):
        """Activa la herramienta (para el botón que usa pk_tools.py)."""
        return self.activate_tool()

    def deactivate(self):
        """Desactiva la herramienta y limpia el canvas."""
        if self.tool:
            self.tool.clear_markers()
            if self.canvas.mapTool() == self.tool:
                self.canvas.unsetMapTool(self.tool)
        self._pop_current_message()


# ============================================================
# DIALOGO DE EXPORTACION
# ============================================================
class ExportDialog(QDialog):
    """Diálogo para seleccionar puntos recientes a exportar."""

    def __init__(self, parent, items_recent_first):
        super().__init__(parent)
        self.setWindowTitle("Exportar puntos del historial")
        self.items = items_recent_first

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Selecciona los puntos a exportar:"))

        # Lista con checkboxes
        self.listw = QListWidget()
        self.listw.setSelectionMode(QListWidget.NoSelection)
        for i, it in enumerate(self.items):
            txt = f"{i+1:02d} — PK {it['pk_str']} — {it['via']}"
            li = QListWidgetItem(txt)
            li.setFlags(li.flags() | Qt.ItemIsUserCheckable)
            li.setCheckState(Qt.Unchecked)
            self.listw.addItem(li)
        layout.addWidget(self.listw)

        # Botones de marcar/desmarcar todo
        btn_row = QHBoxLayout()
        btn_all = QPushButton("Marcar todo")
        btn_none = QPushButton("Desmarcar todo")
        btn_all.clicked.connect(lambda: self._set_all(Qt.Checked))
        btn_none.clicked.connect(lambda: self._set_all(Qt.Unchecked))
        btn_row.addWidget(btn_all)
        btn_row.addWidget(btn_none)
        layout.addLayout(btn_row)

        # Botones OK / Cancelar
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _set_all(self, state):
        """Marca o desmarca todos los ítems."""
        for i in range(self.listw.count()):
            self.listw.item(i).setCheckState(state)

    def selected_indices(self):
        """Devuelve los índices seleccionados por el usuario."""
        return [i for i in range(self.listw.count())
                if self.listw.item(i).checkState() == Qt.Checked]


# ============================================================
# HERRAMIENTA DE MAPA
# ============================================================
class IdentificarPKTool(QgsMapTool):
    """Herramienta que captura clics en el mapa e identifica el PK más cercano."""
    MAX_HISTORY = 30  # número máximo de puntos guardados en el historial

    def __init__(self, iface, canvas, callback):
        super().__init__(canvas)
        self.iface = iface
        self.canvas = canvas
        self.callback = callback
        self.index = None
        self.layer = None
        self.markers = []
        self.history = []
        self.id_field = EXPECTED_FIELD   # se sobrescribe desde settings
        self.m_units = "m"               # "m" (por defecto) o "km"

    # ---------- Manejo de marcadores ----------
    def _add_marker(self, map_pt):
        """Dibuja un aro y un punto en el mapa."""
        ring = QgsVertexMarker(self.canvas)
        ring.setCenter(QgsPointXY(map_pt))
        ring.setColor(QColor(255, 0, 0))
        ring.setFillColor(QColor(0, 0, 0, 0))
        ring.setIconType(QgsVertexMarker.ICON_CIRCLE)
        ring.setIconSize(20)
        ring.setPenWidth(4)

        dot = QgsVertexMarker(self.canvas)
        dot.setCenter(QgsPointXY(map_pt))
        dot.setColor(QColor(255, 0, 0))
        dot.setFillColor(QColor(255, 0, 0))
        dot.setIconType(QgsVertexMarker.ICON_CIRCLE)
        dot.setIconSize(6)
        dot.setPenWidth(0)

        self.markers = [ring, dot]

    def clear_markers(self):
        """Elimina todos los marcadores del canvas."""
        for m in self.markers:
            try:
                self.canvas.scene().removeItem(m)
            except Exception:
                pass
        self.markers = []

    # ---------- Eventos de ratón / teclado ----------
    def canvasPressEvent(self, event):
        if event.button() == Qt.RightButton:
            self._show_context_menu(event)
            return
        super().canvasPressEvent(event)

    def canvasReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            punto = self.toMapCoordinates(event.pos())
            self.identify_point(punto)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.canvas.unsetMapTool(self)

    # ---------- Historial ----------
    def _push_history(self, via, pk_value, map_pt):
        """Guarda el resultado en el historial."""
        item = {
            'via': via,
            'pk_value': pk_value,
            'pk_str': formato_pk(pk_value),
            'map_pt': QgsPointXY(map_pt)
        }
        self.history.append(item)
        if len(self.history) > self.MAX_HISTORY:
            self.history = self.history[-self.MAX_HISTORY:]

    # ---------- Lógica de identificación ----------
    def identify_point(self, point):
        """Identifica el PK en el clic dado."""
        try:
            if not self.layer or not self.index:
                self.iface.messageBar().pushMessage(
                    "Identificar PK", "No hay capa válida asignada.",
                    level=Qgis.Warning
                )
                return

            map_crs = self.canvas.mapSettings().destinationCrs()
            layer = self.layer
            layer_crs = layer.crs()

            # Transformar punto al CRS de la capa
            point_layer_crs = point
            if layer_crs != map_crs:
                xf_to_layer = QgsCoordinateTransform(map_crs, layer_crs, QgsProject.instance())
                point_layer_crs = xf_to_layer.transform(point)

            # Buscar la línea más cercana
            nearest_ids = self.index.nearestNeighbor(point_layer_crs, 5)
            closest_feat, closest_dist, proj_pt = None, float('inf'), None
            for fid in nearest_ids:
                feat = layer.getFeature(fid)
                geom = feat.geometry()
                near = geom.nearestPoint(QgsGeometry.fromPointXY(QgsPointXY(point_layer_crs)))
                d = point_layer_crs.distance(near.asPoint())
                if d < closest_dist:
                    closest_dist = d
                    closest_feat = feat
                    proj_pt = near

            if not closest_feat or proj_pt is None:
                self.iface.messageBar().pushMessage(
                    "Identificar PK", "No se encontró línea cercana.",
                    level=Qgis.Info
                )
                return

            # Calcular PK interpolado según valores M
            geom_line = closest_feat.geometry()
            dist_click = geom_line.lineLocatePoint(proj_pt)
            verts = list(geom_line.vertices())
            if len(verts) < 2:
                self.iface.messageBar().pushMessage(
                    "Identificar PK", "Geometría no válida.",
                    level=Qgis.Warning
                )
                return

            cum = [0.0]
            for i in range(1, len(verts)):
                p0, p1 = verts[i-1], verts[i]
                cum.append(
                    cum[-1]
                    + QgsGeometry.fromPointXY(QgsPointXY(p0)).distance(
                        QgsGeometry.fromPointXY(QgsPointXY(p1))
                    )
                )

            idx = next(
                (i for i in range(len(cum) - 1) if cum[i] <= dist_click <= cum[i + 1]),
                len(cum) - 2
            )

            # Conversión de M a km según configuración:
            # - Si m_units == "m", el campo M está en metros → dividimos entre 1000
            # - Si m_units == "km", el campo M ya está en kilómetros → no convertimos
            factor = 1000.0 if (self.m_units or "m") == "m" else 1.0
            m1 = verts[idx].m() / factor
            m2 = verts[idx + 1].m() / factor

            start_seg = cum[idx]
            seg_len = cum[idx + 1] - start_seg
            t = (dist_click - start_seg) / seg_len if seg_len > 0 else 0.0
            pk_final = m1 + t * (m2 - m1)

            # Actualizar marcador
            self.clear_markers()
            proj_pt_map = proj_pt.asPoint()
            if layer_crs != map_crs:
                xf_to_map = QgsCoordinateTransform(layer_crs, map_crs, QgsProject.instance())
                proj_pt_map = xf_to_map.transform(proj_pt_map)
            self._add_marker(proj_pt_map)

            # Coordenadas WGS84 para Street View
            to_wgs84 = QgsCoordinateTransform(
                map_crs,
                QgsCoordinateReferenceSystem("EPSG:4326"),
                QgsProject.instance()
            )
            proj_pt_wgs = to_wgs84.transform(proj_pt_map)
            lat, lon = proj_pt_wgs.y(), proj_pt_wgs.x()
            url_sv = (
                f"https://www.google.com/maps/@?api=1&map_action=pano"
                f"&viewpoint={lat},{lon}&heading=0&pitch=10&fov=250"
            )

            field = self.id_field
            try:
                nombre_via = (
                    closest_feat[field]
                    if field and closest_feat[field] not in (None, "")
                    else "Vía desconocida"
                )
            except Exception:
                nombre_via = "Vía desconocida"

            # Guardar en historial y mostrar mensaje
            self._push_history(nombre_via, pk_final, proj_pt_map)
            self.callback(nombre_via, pk_final, url_sv, lat, lon)

        except Exception:
            self.iface.messageBar().pushMessage(
                "Identificar PK", "Error inesperado al calcular el PK.",
                level=Qgis.Warning
            )

    # ---------- Menú contextual ----------
    def _show_context_menu(self, mouse_event):
        menu = QMenu()
        act_export = menu.addAction("Exportar puntos")
        global_pos = self.canvas.mapToGlobal(mouse_event.pos())
        action = menu.exec_(global_pos if isinstance(global_pos, QPoint) else mouse_event.globalPos())
        if action == act_export:
            self._export_points_dialog()

    def _export_points_dialog(self):
        """Muestra el diálogo de exportación y guarda los puntos en una capa temporal."""
        if not self.history:
            self.iface.messageBar().pushMessage(
                "Identificar PK", "No hay puntos recientes para exportar.",
                level=Qgis.Info
            )
            return

        base = self.history[-self.MAX_HISTORY:]
        items_display = list(reversed(base))

        dlg = ExportDialog(self.iface.mainWindow(), items_display)
        if dlg.exec_() == QDialog.Accepted:
            idxs = dlg.selected_indices()
            if not idxs:
                self.iface.messageBar().pushMessage(
                    "Identificar PK", "No se seleccionaron puntos.",
                    level=Qgis.Info
                )
                return
            sel_items = [items_display[i] for i in idxs]
            lyr = self._ensure_output_layer()
            if not lyr:
                self.iface.messageBar().pushMessage(
                    "Identificar PK", "No se pudo crear la capa de salida.",
                    level=Qgis.Warning
                )
                return

            # Crear features y añadirlos
            prov = lyr.dataProvider()
            feats = []
            for it in sel_items:
                f = QgsFeature(lyr.fields())
                f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(it['map_pt'])))
                f['VIA'] = it['via']
                f['PK'] = it['pk_str']
                feats.append(f)

            prov.addFeatures(feats)
            lyr.updateExtents()
            lyr.triggerRepaint()
            lyr.dataProvider().forceReload()
            # Exportación silenciosa

    def _ensure_output_layer(self):
        """Crea o recupera la capa temporal de salida."""
        name = "Identificacion PKs"
        prj = QgsProject.instance()
        for lyr in prj.mapLayers().values():
            if (isinstance(lyr, QgsVectorLayer)
                and lyr.name() == name
                and lyr.geometryType() == QgsWkbTypes.PointGeometry):
                if {f.name() for f in lyr.fields()} >= {"VIA", "PK"}:
                    return lyr

        map_crs = self.canvas.mapSettings().destinationCrs()
        authid = map_crs.authid() or "EPSG:4326"
        vl = QgsVectorLayer(f"Point?crs={authid}", name, "memory")
        prov = vl.dataProvider()
        prov.addAttributes([
            QgsField("VIA", QVariant.String),
            QgsField("PK", QVariant.String)
        ])
        vl.updateFields()
        prj.addMapLayer(vl)
        return vl
