import streamlit as st
import folium
from shapely.geometry import Polygon
import geopandas as gpd
from streamlit_folium import st_folium
import numpy as np

# Настройки страницы
st.set_page_config(layout="wide")
st.title("Оптимальное размещение дома на участке")
st.markdown("""
Визуализация участка по координатам с размещением секций дома на OpenStreetMap.
""")

# ===== Ввод данных =====
st.sidebar.header("Параметры участка")

# Загрузка координат
coord_input = st.sidebar.text_area(
    "Координаты участка ([[lat,lon], [lat,lon], ...]):",
    """[[55.796391, 37.535800],
    [55.796288, 37.535120],
    [55.795950, 37.535350],
    [55.796050, 37.536000]]"""
)

# Парсинг координат
try:
    coords = eval(coord_input)
    site_polygon = Polygon(coords)
    centroid = [np.mean([p[0] for p in coords]), np.mean([p[1] for p in coords])]
except Exception as e:
    st.error(f"Ошибка загрузки координат: {e}")
    st.stop()

# ===== Параметры дома =====
st.sidebar.header("Параметры дома")

SECTION_TYPES = {
    "Секция 26x16": {"width": 26, "height": 16, "color": "blue"},
    "Секция 28x16": {"width": 28, "height": 16, "color": "red"},
    "Секция 18x18": {"width": 18, "height": 18, "color": "green"}
}

selected_section = st.sidebar.selectbox(
    "Тип секции:",
    list(SECTION_TYPES.keys())
)

section_count = st.sidebar.slider(
    "Количество секций:",
    1, 10, 2
)

# ===== Расчет позиций секций =====
def calculate_sections(polygon, section_type, count):
    """Рассчитывает позиции секций вдоль длинной стороны участка"""
    section = SECTION_TYPES[section_type]
    min_x, min_y, max_x, max_y = polygon.bounds
    
    # Определяем ориентацию (по длинной стороне)
    width = max_x - min_x
    height = max_y - min_y
    is_horizontal = width > height
    
    positions = []
    for i in range(count):
        if is_horizontal:
            x = min_x + (width/count) * i + 0.0001  # Небольшой отступ
            y = min_y + height/2 - section["height"]/2 * 0.00001
            w = section["width"] * 0.00001
            h = section["height"] * 0.00001
        else:
            x = min_x + width/2 - section["width"]/2 * 0.00001
            y = min_y + (height/count) * i + 0.0001
            w = section["width"] * 0.00001
            h = section["height"] * 0.00001
        
        positions.append({
            "coords": [
                [x, y],
                [x + w, y],
                [x + w, y + h],
                [x, y + h]
            ],
            "color": section["color"]
        })
    return positions

# ===== Визуализация на карте =====
def create_map(polygon, sections):
    """Создает интерактивную карту с участком и домом"""
    m = folium.Map(
        location=centroid,
        zoom_start=18,
        tiles="OpenStreetMap"
    )
    
    # Участок
    folium.GeoJson(
        gpd.GeoSeries(polygon).__geo_interface__,
        name="Участок",
        style_function=lambda x: {"fillColor": "yellow", "color": "orange"}
    ).add_to(m)
    
    # Секции дома
    for i, sec in enumerate(sections, 1):
        folium.Polygon(
            locations=sec["coords"],
            popup=f"Секция {i}",
            color=sec["color"],
            fill=True
        ).add_to(m)
    
    folium.LayerControl().add_to(m)
    return m

# ===== Основной поток =====
if st.button("Показать на карте"):
    sections = calculate_sections(site_polygon, selected_section, section_count)
    m = create_map(site_polygon, sections)
    st_folium(m, width=1200, height=600)
    
    # Вывод информации
    st.success(f"Участок содержит **{section_count} секций** типа *{selected_section}*")
    st.subheader("Координаты углов участка:")
    st.table([[f"{p[0]:.6f}, {p[1]:.6f}"] for p in coords])

# ===== Дополнительно =====
st.sidebar.header("О проекте")
st.sidebar.markdown("""
Используемые технологии:
- **OpenStreetMap** для картографии
- **Folium** для визуализации
- **Shapely** для геометрических расчетов
""")
