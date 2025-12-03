# PK Tools

**PK Tools** unifica tres herramientas en un único complemento de QGIS:

![](PICTURES/ICONS.png)

---

## 🔧 ¿Qué hace PK Tools?

PK Tools está pensado para capas de carreteras **lineales con geometría M** (calibración). Trabaja siempre sobre **una capa de trabajo configurable**, y a partir de ella ofrece tres herramientas:

---

## 🧭 Identificar PK

Permite identificar la vía y el punto kilométrico haciendo clic sobre una capa de carreteras (líneas calibradas con valores M).

- Muestra:
  - El nombre de la vía.
  - El PK interpolado (en km y en formato `km+000`).
  - Un enlace a Street View.
  - Botones para copiar vía, PK y coordenadas al portapapeles.
- Mantiene un **historial interno** de puntos identificados que se puede exportar a una capa temporal de puntos.
- El punto identificado queda marcado hasta que se selecciona otro o se apaga la herramienta.

![](PICTURES/Identificar.png)

---

## 📍 Localizar PK

Abre una ventana donde el usuario puede introducir:

- La carretera (mediante un campo identificador configurable).
- Un PK (km + m).

Y el complemento:

- Ubica el punto exacto en el mapa sobre la capa calibrada.
- Dibuja un marcador en el mapa.
- Muestra un enlace a Street View y un botón para centrar el mapa.
- Mantiene un **historial** accesible desde el menú desplegable del botón.
- Permite exportar puntos seleccionados del historial a una capa temporal.

El marcador permanece hasta que se localiza otro punto o se borra manualmente desde el menú.

![](PICTURES/Localizar.png)

---

## 📏 Distancia PK

Permite medir la **distancia entre dos PKs sobre la misma vía**, mostrando:

- La diferencia de PK (basada en los valores M de la capa).
- La distancia lineal real calculada sobre la geometría (en km).

Esto es útil porque puede haber discrepancias entre la calibración (M) y la geometría real.

Los puntos medidos quedan señalados con marcadores hasta que se realiza una nueva medición o se apaga la herramienta.

![](PICTURES/Distancia.png)

---

Estas herramientas son ideales para proyectos de carreteras o análisis de movilidad, agilizando en gran medida el flujo de trabajo.

---

## 📥 Instalación

1. Descarga el repositorio de GitHub: `Code → Download ZIP`.
2. Abre QGIS y ve a  
   `Complementos → Administrar e instalar complementos → Instalar desde ZIP`.
3. Selecciona el ZIP descargado y haz clic en **Instalar**.

**O bien (instalación manual):**

1. Descomprime y copia la carpeta `pk_tools` en la carpeta de complementos de tu perfil de QGIS. Por ejemplo:  
   - **Windows**:  
     `C:\Users\USUARIO\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\pk_tools`  
   - **Linux/Mac**:  
     `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/pk_tools`
2. Reinicia QGIS.
3. Activa el complemento en  
   `Complementos → Administrar e instalar complementos → Instalados`  
   marcando **PK Tools** si no lo está.

Una vez instalado y activado, verás una **barra de herramientas propia** llamada `PK Tools`, con tres botones principales (Identificar, Localizar, Distancia) y un pequeño botón de opciones (desplegable).

---

## 📋 Requisitos

- QGIS **3.22+** (probado en QGIS 3.34 LTR).
- Una capa de carreteras:
  - De tipo **línea**.
  - Con **geometría M** (calibración) válida.
- Un campo en la tabla de atributos que identifique la vía (por ejemplo, `ID_ROAD`, `CARRETERA`, etc.).
- Los valores M pueden estar:
  - En **metros** (comportamiento por defecto).
  - O directamente en **kilómetros** (configurable).

> ⚠️ Actualmente, las tres herramientas (**Identificar PK**, **Localizar PK** y **Distancia PK**) requieren que la capa tenga geometría M.  
> Si la capa no tiene M, el plugin mostrará un mensaje indicando que la capa no es válida.

---

## ⚙️ Configuración inicial

La primera vez que actives PK Tools, se abrirá automáticamente una ventana de **configuración**. También puedes abrirla en cualquier momento desde el pequeño botón de **opciones** (flecha / tres puntos) al final de la barra de herramientas `PK Tools`.

### 1. Capa de trabajo

En el diálogo de configuración podrás elegir:

- La **capa de vías** sobre la que van a trabajar las tres herramientas.

Requisitos que se comprueban:

- Debe ser una **capa vectorial lineal**.
- Su geometría debe tener **M** (`LineStringM`, `MultiLineStringM`, etc.).

> Si la capa no aparece en la lista, asegúrate de que esté cargada en el proyecto y que su tipo de geometría incluya M.

### 2. Campo identificador de la vía

En el mismo diálogo:

- Elige el **campo que identifica la carretera / vía** (por ejemplo, `ID_ROAD`).

Notas:

- Si existe un campo `ID_ROAD`, el plugin lo propone automáticamente.
- Puedes seleccionar cualquier otro campo (cadena, código, etc.) que identifique de forma consistente la vía.

Este campo se utilizará en:

- **Identificar PK**: para mostrar el nombre de la vía.
- **Localizar PK**: para autocompletar la carretera al escribir.
- **Distancia PK**: para mostrar en el resultado sobre qué vía se está midiendo.

### 3. Unidades del campo M

También debes indicar en qué unidad están los valores M de la capa:

- **Metros** (opción por defecto).
- **Kilómetros**.

El plugin ajusta internamente las conversiones:

- Si eliges **Metros**:
  - M se interpreta como metros.
  - Los PK se muestran siempre en kilómetros (y en formato `km+000`).
- Si eliges **Kilómetros**:
  - M se interpreta directamente como kilómetros.
  - No se aplica el factor 1/1000.

### 4. Vista previa de valores M

La configuración muestra una **vista previa** de algunos valores M encontrados en la capa seleccionada:

- Verás líneas del tipo:  
  `Feature 123: M ~ 0.000, 13.250, 25.600, ...`
- Esta vista previa te puede ayudar a deducir si M está en **metros** (valores grandes, p.ej. 12500.0) o en **kilómetros** (valores tipo 12.500).

Cuando pulses **Aceptar**, la configuración se guarda mediante `QgsSettings` y se mantiene entre sesiones de QGIS (no hace falta volver a configurarlo cada vez que abras el proyecto).

---

## ✅ Uso básico

1. **Configura el plugin** una vez (capa, campo de vía y unidades M).
2. En la barra `PK Tools`:
   - Usa **Identificar PK** para obtener información al hacer clic sobre la vía.
   - Usa **Localizar PK** para ir a un PK concreto (con su historial y exportación).
   - Usa **Distancia PK** para medir la diferencia de PK y la distancia real entre dos puntos sobre la misma vía.
3. Reajusta la configuración desde el botón de opciones si cambias de capa o de convenciones (por ejemplo, otra capa calibrada en km).

---

## ⚠️ Limitaciones y advertencias

- **Tipo de capa**:
  - Solo se admiten capas lineales con geometría M.
  - Si la capa no es lineal o no tiene M, las herramientas no se activarán y el plugin mostrará un mensaje.
- **Consistencia de M**:
  - El plugin asume que los valores M son **monótonos** a lo largo de la línea (aunque maneja casos donde suben o bajan ligeramente).
  - Si la calibración es errática, los resultados pueden no ser fiables.
- **Rendimiento**:
  - En capas muy grandes (muchos trazados y vértices), la búsqueda de vecinos y la interpolación pueden tardar algo más.
- **Edición de capas**:
  - No se recomienda usar las herramientas mientras la capa de líneas está en edición para evitar resultados inconsistentes.
- **Street View**:
  - Requiere conexión a Internet.
  - El complemento genera enlaces a Google Street View; respeta siempre sus términos de uso.

💡 Consejo: revisa la **configuración** si cambias de proyecto o de capa, y comprueba que la unidad de M (metros o kilómetros) coincide con cómo está calibrada tu capa.

---

## 📄 Licencia

Este proyecto se distribuye bajo la **GNU General Public License v3.0 (GPL-3.0)**.  
Puedes usarlo, modificarlo y compartirlo libremente bajo los términos de esta licencia.

---

## 👤 Autor

- **Nombre**: Javi H. Piris  
- **GitHub**: [@Javisionario](https://github.com/Javisionario)
