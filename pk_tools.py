# -*- coding: utf-8 -*-
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QToolButton, QMenu, QStyle
from qgis.PyQt.QtCore import Qt,QSize

from . import resources_rc
from .tools.identificar_pk import IdentificarPK
from .tools.localizar_pk import LocalizarPK
from .tools.distancia_pk import DistanciaPK
from .settings import PKToolsSettings, show_settings_dialog


class PKToolsPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.settings_mgr = PKToolsSettings()
        self.identificar = IdentificarPK(iface)
        self.localizar = LocalizarPK(iface)
        self.distancia = DistanciaPK(iface)

        self.toolbar = None
        self.actions = []  # por si quieres usarlo después

    def initGui(self):
        """Crear la barra de herramientas propia del plugin y sus botones."""

        # Crear toolbar propia
        self.toolbar = self.iface.addToolBar("PK Tools")
        self.toolbar.setObjectName("PKTools")

        # Identificar PK (checkable)
        act_id = QAction(
            QIcon(":/plugins/pk_tools/icons/identificar.png"),
            "Identificar PK",
            self.iface.mainWindow()
        )
        act_id.setCheckable(True)
        act_id.toggled.connect(
            lambda checked: self.identificar.run() if checked else self.identificar.deactivate()
        )
        self.toolbar.addAction(act_id)
        self.actions.append(act_id)

        # Localizar PK (con menú desplegable propio, ya lo crea localizar_pk)
        act_loc = self.localizar.create_action()
        self.toolbar.addAction(act_loc)
        self.actions.append(act_loc)

        # Distancia PK (checkable)
        act_dist = QAction(
            QIcon(":/plugins/pk_tools/icons/distancia.png"),
            "Distancia PK",
            self.iface.mainWindow()
        )
        act_dist.setCheckable(True)
        act_dist.toggled.connect(
            lambda checked: self.distancia.run() if checked else self.distancia.deactivate()
        )
        self.toolbar.addAction(act_dist)
        self.actions.append(act_dist)

        # Flecha desplegable de opciones
        menu_button = QToolButton(self.iface.mainWindow())
        menu_button.setPopupMode(QToolButton.InstantPopup)
        menu_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        menu_button.setAutoRaise(True)  # estilo plano, como los demás

        # Icono estándar de Qt para "toolbar overflow" / menú
        std_icon = self.iface.mainWindow().style().standardIcon(QStyle.SP_ToolBarVerticalExtensionButton)
        menu_button.setIcon(std_icon)
        menu_button.setIconSize(QSize(12, 12))  # icono más pequeño que los demás
        menu_button.setFixedWidth(18)           # ancho muy contenido
        menu_button.setToolTip("Opciones PK Tools")

        # Menú de opciones
        options_menu = QMenu(menu_button)
        act_cfg = QAction("Configuración PK Tools", self.iface.mainWindow())
        act_cfg.triggered.connect(lambda: show_settings_dialog(self.iface))
        options_menu.addAction(act_cfg)

        menu_button.setMenu(options_menu)
        
        '''
        menu_button = QToolButton(self.iface.mainWindow())
        menu_button.setPopupMode(QToolButton.InstantPopup)
        menu_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        menu_button.setToolTip("Opciones PK Tools")

        options_menu = QMenu(menu_button)
        act_cfg = QAction("Configuración PK Tools", self.iface.mainWindow())
        act_cfg.triggered.connect(lambda: show_settings_dialog(self.iface))
        options_menu.addAction(act_cfg)

        menu_button.setMenu(options_menu)
        '''
        # Añadimos el botón de flecha al final de la toolbar
        self.toolbar.addWidget(menu_button)

        # Guardamos referencias por si te hicieran falta
        self.actions.append(act_cfg)
        self.menu_button = menu_button
        self.options_menu = options_menu

        # Si no hay configuración previa, abrir el diálogo una vez
        if not self.settings_mgr.has_config():
            show_settings_dialog(self.iface)

    def unload(self):
        """Eliminar la barra de herramientas al desinstalar el plugin."""
        if self.toolbar is not None:
            # Quitamos la toolbar completa, con todas sus acciones y widgets
            self.iface.mainWindow().removeToolBar(self.toolbar)
            self.toolbar = None
        self.actions = []
