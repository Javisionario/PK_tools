# -*- coding: utf-8 -*-
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import QAction, QPushButton, QApplication
from qgis.PyQt.QtCore import Qt
from qgis.gui import QgsMapTool, QgsVertexMarker
from qgis.core import (
    QgsPointXY,
    QgsGeometry,
    QgsCoordinateTransform,
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsWkbTypes,
    QgsVectorLayer,
    QgsSpatialIndex,
    Qgis
)

from ..settings import read_current_settings

# Campo por defecto histórico (fallback si no hay settings)
EXPECTED_FIELD = "ID_ROAD"


def formato_pk(pk_total):
    km = int(pk_total)
    m = int(round((pk_total - km) * 1000))
    if m == 1000:
        km += 1
        m = 0
    return f"{km:02d}+{m:03d}"


class DistanciaPK:
    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.action = None
        self.tool = None
        # Para controlar solo nuestro mensaje
        self.current_msg = None

    def initGui(self):
        import os
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        icon = QIcon(icon_path)
        self.action = QAction(icon, "Medir Distancia PK", self.iface.mainWindow())
        self.action.setToolTip("Mide distancia entre dos PKs sobre la misma vía")
        self.action.setCheckable(True)
        self.action.toggled.connect(self.toggle_tool)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.tool:
            try:
                self.tool.reset()
            except Exception:
                pass
        if self.tool and self.canvas.mapTool() == self.tool:
            self.canvas.unsetMapTool(self.tool)
        self._close_messagebar()
        if self.action:
            self.iface.removeToolBarIcon(self.action)
            self.action = None

    def toggle_tool(self, checked):
        if checked:
            ok = self.activate_tool()
            if not ok and self.action:
                self.action.setChecked(False)
        else:
            if self.tool and self.canvas.mapTool() == self.tool:
                self.canvas.unsetMapTool(self.tool)
            if self.tool:
                self.tool.reset()
            self._close_messagebar()

    def activate_tool(self):
        """
        Activa la herramienta usando la capa/campo/unidades definidos en settings.
        """
        try:
            cfg = read_current_settings()
            layer_name = cfg.get("layer_name") or ""
            id_field = cfg.get("id_field") or EXPECTED_FIELD
            m_units = cfg.get("m_units") or "m"

            if not layer_name:
                self.iface.messageBar().pushMessage(
                    "Distancia PK",
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

            if not layer:
                self.iface.messageBar().pushMessage(
                    "Distancia PK",
                    f"No se ha encontrado la capa '{layer_name}'. Revisa la configuración de PK Tools.",
                    level=Qgis.Warning
                )
                return False

            # Validar tipo de geometría
            if layer.geometryType() != QgsWkbTypes.LineGeometry:
                self.iface.messageBar().pushMessage(
                    "Distancia PK",
                    f"La capa '{layer_name}' no es lineal.",
                    level=Qgis.Warning
                )
                return False

            # Validar presencia de M
            if not QgsWkbTypes.hasM(layer.wkbType()):
                self.iface.messageBar().pushMessage(
                    "Distancia PK",
                    f"La capa '{layer_name}' no tiene geometría M.",
                    level=Qgis.Warning
                )
                return False

            # Comprobar que existe el campo identificador
            if layer.fields().indexOf(id_field) == -1:
                self.iface.messageBar().pushMessage(
                    "Distancia PK",
                    f"La capa '{layer_name}' no tiene el campo '{id_field}'.",
                    level=Qgis.Warning
                )
                return False

            # Crear herramienta si no existe
            if not self.tool:
                self.tool = DistanciaTool(self.iface, self.canvas, self.show_distance_message)

            self.tool.layer = layer
            self.tool.index = QgsSpatialIndex(layer.getFeatures())
            self.tool.id_field = id_field
            self.tool.m_units = m_units
            self.tool.reset()

            self.canvas.setMapTool(self.tool)
            return True

        except Exception:
            self.iface.messageBar().pushMessage(
                "Distancia PK",
                "Error inesperado al seleccionar capa.",
                level=Qgis.Warning
            )
            return False

    def show_distance_message(self, nombre_via, pk1, pk2, dist_pk_km, dist_lineal_km):
        # Cerrar mensaje anterior antes de crear uno nuevo
        self._close_messagebar()

        pk1_str = formato_pk(pk1)
        pk2_str = formato_pk(pk2)
        texto = (
            f"{nombre_via} | PK1: {pk1_str} · PK2: {pk2_str} | "
            f"Dist. PK: {dist_pk_km:.3f} km · Dist. Lineal: {dist_lineal_km:.3f} km"
        )

        msg = self.iface.messageBar().createMessage("Distancia PK", texto)

        btn_pk = QPushButton("Copiar distancia PK")
        btn_pk.clicked.connect(lambda: QApplication.clipboard().setText(f"{dist_pk_km:.3f} km"))

        btn_lin = QPushButton("Copiar distancia lineal")
        btn_lin.clicked.connect(lambda: QApplication.clipboard().setText(f"{dist_lineal_km:.3f} km"))

        msg.layout().addWidget(btn_pk)
        msg.layout().addWidget(btn_lin)

        # Guardamos el handler para poder cerrar solo este mensaje
        self.current_msg = self.iface.messageBar().pushWidget(msg, Qgis.Info)

    def _close_messagebar(self):
        """Cierra solo el mensaje de esta herramienta, si existe."""
        if self.current_msg:
            try:
                self.iface.messageBar().popWidget(self.current_msg)
            except Exception:
                try:
                    self.current_msg.close()
                except Exception:
                    pass
            finally:
                self.current_msg = None

    def run(self):
        return self.activate_tool()

    def deactivate(self):
        if self.tool:
            try:
                self.tool.reset()
            except Exception:
                pass
            if self.canvas.mapTool() == self.tool:
                self.canvas.unsetMapTool(self.tool)
        self._close_messagebar()


class DistanciaTool(QgsMapTool):
    def __init__(self, iface, canvas, callback):
        super().__init__(canvas)
        self.iface = iface
        self.canvas = canvas
        self.callback = callback
        self.layer = None
        self.index = None
        self.id_field = EXPECTED_FIELD   # se sobreescribe desde settings
        self.m_units = "m"               # "m" (por defecto) o "km"
        self.reset()

    def reset(self):
        if hasattr(self, 'markers'):
            for m in self.markers:
                try:
                    self.canvas.scene().removeItem(m)
                except Exception:
                    pass
        self.markers = []
        self.pk_values = []
        self.line_distances = []
        self.first_feat = None
        self.click_count = 0

    def canvasReleaseEvent(self, event):
        pt_map = self.toMapCoordinates(event.pos())
        if self.click_count >= 2:
            # Nueva medición: borra puntos (la barra se reemplaza en show_distance_message)
            self.reset()
        self._process_click(pt_map)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.canvas.unsetMapTool(self)

    def _process_click(self, click_pt_map):
        try:
            if not self.layer or not self.index:
                self.iface.messageBar().pushMessage(
                    "Distancia PK",
                    "No hay capa válida asignada.",
                    level=Qgis.Warning
                )
                return

            map_crs = self.canvas.mapSettings().destinationCrs()
            layer_crs = self.layer.crs()

            layer_pt = click_pt_map
            if map_crs != layer_crs:
                xf_to_layer = QgsCoordinateTransform(map_crs, layer_crs, QgsProject.instance())
                layer_pt = xf_to_layer.transform(click_pt_map)

            if self.click_count == 0:
                # Primer punto
                fids = self.index.nearestNeighbor(layer_pt, 5)
                closest_feat, proj_pt_layer = None, None
                min_d = float('inf')
                for fid in fids:
                    feat = self.layer.getFeature(fid)
                    near = feat.geometry().nearestPoint(QgsGeometry.fromPointXY(QgsPointXY(layer_pt)))
                    d = layer_pt.distance(near.asPoint())
                    if d < min_d:
                        min_d = d
                        closest_feat = feat
                        proj_pt_layer = near

                if not closest_feat:
                    self.iface.messageBar().pushMessage(
                        "Distancia PK",
                        "No se encontró línea cercana.",
                        level=Qgis.Info
                    )
                    return

                self.first_feat = closest_feat
                pk1, dist1 = self._compute_pk_and_dist(closest_feat.geometry(), proj_pt_layer)

                proj1_map = proj_pt_layer.asPoint()
                if map_crs != layer_crs:
                    xf_to_map = QgsCoordinateTransform(layer_crs, map_crs, QgsProject.instance())
                    proj1_map = xf_to_map.transform(proj1_map)
                self._add_marker(proj1_map)

                self.pk_values.append(pk1)
                self.line_distances.append(dist1)
                self.click_count = 1

            else:
                # Segundo punto sobre la MISMA geometría (first_feat)
                geom = self.first_feat.geometry()
                near_layer = geom.nearestPoint(QgsGeometry.fromPointXY(QgsPointXY(layer_pt)))
                pk2, dist2 = self._compute_pk_and_dist(geom, near_layer)

                proj2_map = near_layer.asPoint()
                if map_crs != layer_crs:
                    xf_to_map = QgsCoordinateTransform(layer_crs, map_crs, QgsProject.instance())
                    proj2_map = xf_to_map.transform(proj2_map)
                self._add_marker(proj2_map)

                self.pk_values.append(pk2)
                self.line_distances.append(dist2)
                self.click_count = 2

                dist_pk = abs(self.pk_values[1] - self.pk_values[0])               # km
                dist_lineal = abs(self.line_distances[1] - self.line_distances[0]) # unidades de capa
                # Se asume CRS en metros → pasa a km
                dist_lineal_km = dist_lineal / 1000.0

                # Nombre de la vía usando el campo configurado
                try:
                    val = self.first_feat[self.id_field]
                    nombre_via = val if val not in (None, "") else "Vía desconocida"
                except Exception:
                    nombre_via = "Vía desconocida"

                self.callback(
                    nombre_via,
                    self.pk_values[0],
                    self.pk_values[1],
                    dist_pk,
                    dist_lineal_km
                )

        except Exception as e:
            self.iface.messageBar().pushMessage(
                "Distancia PK",
                f"Error al calcular: {e}",
                level=Qgis.Warning
            )

    def _compute_pk_and_dist(self, geom_line, proj_pt_layer):
        """
        Devuelve:
          - pk_km: PK interpolado en km, según valores M y unidades configuradas.
          - dist_click: distancia acumulada a lo largo de la línea (unidades del CRS).
        """
        dist_click = geom_line.lineLocatePoint(proj_pt_layer)
        verts = list(geom_line.vertices())
        if len(verts) < 2:
            return 0.0, 0.0

        cum = [0.0]
        for i in range(1, len(verts)):
            seg = QgsGeometry.fromPolylineXY([QgsPointXY(verts[i-1]), QgsPointXY(verts[i])])
            cum.append(cum[-1] + seg.length())

        idx = next(
            (i for i in range(len(cum)-1) if cum[i] <= dist_click <= cum[i+1]),
            len(cum)-2
        )

        # Conversión de M según configuración:
        #   - "m": divide entre 1000 (M en metros)
        #   - "km": no divide (M en kilómetros)
        factor = 1000.0 if (self.m_units or "m") == "m" else 1.0
        m1 = verts[idx].m() / factor
        m2 = verts[idx+1].m() / factor

        start = cum[idx]
        seg_len = cum[idx+1] - start
        t = (dist_click - start) / seg_len if seg_len > 0 else 0.0
        pk_km = m1 + t * (m2 - m1)
        return pk_km, dist_click

    def _add_marker(self, map_pt):
        ring = QgsVertexMarker(self.canvas)
        ring.setCenter(QgsPointXY(map_pt))
        ring.setColor(QColor(0, 200, 0))
        ring.setFillColor(QColor(0, 0, 0, 0))
        ring.setIconType(QgsVertexMarker.ICON_CIRCLE)
        ring.setIconSize(20)
        ring.setPenWidth(4)

        dot = QgsVertexMarker(self.canvas)
        dot.setCenter(QgsPointXY(map_pt))
        dot.setColor(QColor(0, 200, 0))
        dot.setFillColor(QColor(0, 200, 0))
        dot.setIconType(QgsVertexMarker.ICON_CIRCLE)
        dot.setIconSize(6)
        dot.setPenWidth(0)

        self.markers.extend([ring, dot])

    def deactivate(self):
        super().deactivate()
