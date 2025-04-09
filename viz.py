import streamlit as st
import folium
from shapely.geometry import Polygon, box, MultiPolygon
import geopandas as gpd
from streamlit_folium import st_folium
import numpy as np
from itertools import combinations
from pulp import LpProblem, LpMaximize, LpVariable, lpSum, value

# Настройки страницы
st.set_page_config(layout="wide")
st.title("Автоматический расчет оптимального количества секций")

# ===== Ввод данных =====
st.sidebar.header("Параметры участка")

# Загрузка координат
coord_input = st.sidebar.text_area(
    "Координаты участка ([[lat,lon],...]):",
    """[[55.796391, 37.535800],
    [55.796288, 37.535120],
    [55.795950, 37.535350],
    [55.796050, 37.536000]]""",
    height=150
)

# Парсинг координат
try:
    coords = eval(coord_input)
    site_polygon = Polygon(coords)
    centroid = list(site_polygon.centroid.coords)[0][::-1]  # (lon, lat)
except Exception as e:
    st.error(f"Ошибка в координатах: {e}")
    st.stop()

# ===== Параметры секций =====
st.sidebar.header("Параметры секций")

SECTION_TYPES = {
    "Жилая 26x16": {"width": 26, "height": 16, "value": 1.0, "color": "blue"},
    "Жилая 28x16": {"width": 28, "height": 16, "value": 1.2, "color": "green"},
    "Коммерческая 30x20": {"width": 30, "height": 20, "value": 1.5, "color": "orange"}
}

available_sections = st.sidebar.multiselect(
    "Доступные типы секций:",
    list(SECTION_TYPES.keys()),
    default=list(SECTION_TYPES.keys())
)

# Параметры размещения
margin = st.sidebar.slider("Отступ от границ (м):", 0, 20, 5)
min_distance = st.sidebar.slider("Минимальное расстояние между секциями (м):", 1, 20, 3)
floors = st.sidebar.slider("Этажность:", 1, 25, 5)

# Конвертация метров в градусы
def meters_to_degrees(meters, lat=centroid[1]):
    return meters / (111320 * np.cos(np.radians(lat)))

# ===== Генерация возможных позиций =====
def generate_possible_positions(polygon, sections, margin):
    positions = []
    min_lon, min_lat, max_lon, max_lat = polygon.bounds
    
    for section_name in sections:
        section = SECTION_TYPES[section_name]
        w = meters_to_degrees(section["width"])
        h = meters_to_degrees(section["height"])
        
        step = min(w, h)/2  # Уменьшенный шаг для плотной упаковки
        
        for lon in np.arange(min_lon + meters_to_degrees(margin), 
                           max_lon - w - meters_to_degrees(margin), 
                           step):
            for lat in np.arange(min_lat + meters_to_degrees(margin),
                               max_lat - h - meters_to_degrees(margin),
                               step):
                bbox = box(lon, lat, lon + w, lat + h)
                if polygon.contains(bbox):
                    positions.append({
                        "type": section_name,
                        "coords": [
                            [lat, lon],
                            [lat, lon + w],
                            [lat + h, lon + w],
                            [lat + h, lon]
                        ],
                        "value": section["value"] * w * h * floors,
                        "width": w,
                        "height": h,
                        "color": section["color"]
                    })
    return positions

# ===== Оптимизация размещения =====
def optimize_layout(positions, min_distance):
    # Создаем модель оптимизации
    model = LpProblem("Maximize_Value", LpMaximize)
    
    # Переменные решения (1 - разместить, 0 - нет)
    x = {i: LpVariable(f"x_{i}", cat="Binary") for i in range(len(positions))}
    
    # Целевая функция - максимизация полезной площади
    model += lpSum(x[i] * positions[i]["value"] for i in range(len(positions)))
    
    # Ограничения:
    # 1. Секции не должны пересекаться
    for i in range(len(positions)):
        for j in range(i+1, len(positions)):
            # Проверяем расстояние между секциями
            rect_i = box(
                positions[i]["coords"][0][1], positions[i]["coords"][0][0],
                positions[i]["coords"][2][1], positions[i]["coords"][2][0]
            )
            rect_j = box(
                positions[j]["coords"][0][1], positions[j]["coords"][0][0],
                positions[j]["coords"][2][1], positions[j]["coords"][2][0]
            )
            if rect_i.distance(rect_j) < meters_to_degrees(min_distance):
                model += x[i] + x[j] <= 1
    
    # Решаем задачу
    model.solve()
    
    # Возвращаем выбранные позиции
    return [positions[i] for i in range(len(positions)) if value(x[i]) == 1]

# ===== Визуализация =====
def create_map(polygon, sections):
    m = folium.Map(location=centroid, zoom_start=18)
    
    # Участок
    folium.GeoJson(
        gpd.GeoSeries(polygon).__geo_interface__,
        style_function=lambda x: {
            "fillColor": "yellow",
            "color": "orange",
            "fillOpacity": 0.2
        }
    ).add_to(m)
    
    # Секции
    for i, sec in enumerate(sections, 1):
        folium.Polygon(
            locations=sec["coords"],
            popup=f"{i}. {sec['type']}",
            color=sec["color"],
            fill=True,
            fillOpacity=0.7
        ).add_to(m)
    
    return m

# ===== Основной поток =====
if st.button("Рассчитать оптимальное размещение"):
    if not available_sections:
        st.warning("Выберите доступные типы секций!")
    else:
        with st.spinner("Генерация возможных позиций..."):
            positions = generate_possible_positions(site_polygon, available_sections, margin)
        
        with st.spinner("Оптимизация размещения..."):
            optimal_layout = optimize_layout(positions, min_distance)
        
        # Результаты
        total_value = sum(sec["value"] for sec in optimal_layout)
        st.success(f"Оптимальное количество секций: {len(optimal_layout)}")
        st.success(f"Общая полезная площадь (ТЭП): {total_value:.2f} усл.ед.")
        
        # Визуализация
        col1, col2 = st.columns([2, 1])
        
        with col1:
            m = create_map(site_polygon, optimal_layout)
            st_folium(m, width=800, height=600)
        
        with col2:
            st.subheader("Размещенные секции:")
            section_counts = {}
            for sec in optimal_layout:
                section_counts[sec["type"]] = section_counts.get(sec["type"], 0) + 1
            
            for sec_type, count in section_counts.items():
                st.markdown(f"**{sec_type}:** {count} шт.")
            
            st.subheader("Статистика:")
            st.markdown(f"**Общая площадь участка:** {site_polygon.area * 111320**2:.1f} м²")
            st.markdown(f"**Занятая площадь:** {sum(sec['width']*sec['height']*111320**2 for sec in optimal_layout):.1f} м²")
            st.markdown(f"**Коэффициент использования:** {sum(sec['value'] for sec in optimal_layout)/site_polygon.area:.2%}")

# ===== Дополнительная информация =====
st.sidebar.markdown("""
**Алгоритм работы:**
1. Генерирует все возможные позиции для секций
2. Оптимизирует размещение с учетом ограничений
3. Максимизирует полезную площадь (ТЭП)
""")
