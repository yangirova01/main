import streamlit as st
import folium
import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon, box
from streamlit_folium import st_folium
from itertools import combinations

# Настройки страницы
st.set_page_config(layout="wide")
st.title("Оптимальное размещение дома из секций на участке")

# Инициализация состояния
if 'results' not in st.session_state:
    st.session_state.results = None

# ===== Ввод данных =====
st.sidebar.header("Параметры участка")
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
    centroid = list(site_polygon.centroid.coords)[0][::-1]
except Exception as e:
    st.error(f"Ошибка в координатах: {e}")
    st.stop()

# ===== Параметры секций =====
st.sidebar.header("Конфигурация дома")

SECTION_TYPES = {
    "26x16": {"width": 26, "height": 16, "color": "blue"},
    "28x16": {"width": 28, "height": 16, "color": "green"},
    "26x18": {"width": 26, "height": 18, "color": "red"},
    "18x18": {"width": 18, "height": 18, "color": "purple"}
}

section_count = st.sidebar.slider("Количество секций:", 2, 5, 2)
selected_sections = []
for i in range(section_count):
    selected_sections.append(st.sidebar.selectbox(
        f"Секция {i+1}:",
        list(SECTION_TYPES.keys()),
        key=f"section_{i}"
    ))

# Параметры размещения
margin = st.sidebar.slider("Отступ от границ (м):", 0, 20, 5)
floors = st.sidebar.slider("Этажность:", 1, 25, 5)

# ===== Алгоритм размещения =====
def generate_placements(site_polygon, sections, margin, floors):
    """Генерация возможных комбинаций секций"""
    placements = []
    min_lon, min_lat, max_lon, max_lat = site_polygon.bounds
    
    # Конвертация метров в градусы
    def m_to_deg(m):
        return m / (111320 * np.cos(np.radians(centroid[1])))
    
    # Генерация всех возможных комбинаций
    for angle in [0, 90]:  # Варианты поворота
        section_polys = []
        total_width = 0
        total_height = 0
        
        # Рассчитываем габариты всего дома
        for section in sections:
            w = SECTION_TYPES[section]["width"]
            h = SECTION_TYPES[section]["height"]
            if angle == 90:
                w, h = h, w
            section_polys.append({
                "w": m_to_deg(w),
                "h": m_to_deg(h),
                "color": SECTION_TYPES[section]["color"]
            })
            total_width += m_to_deg(w)
            total_height = max(total_height, m_to_deg(h))
        
        margin_deg = m_to_deg(margin)
        
        # Поиск позиций для всей комбинации
        for lon in np.linspace(min_lon + margin_deg, max_lon - total_width - margin_deg, 15):
            for lat in np.linspace(min_lat + margin_deg, max_lat - total_height - margin_deg, 15):
                current_x = lon
                valid = True
                house_polys = []
                
                # Проверяем каждую секцию
                for section in section_polys:
                    sec_poly = box(
                        current_x, lat,
                        current_x + section["w"], lat + section["h"]
                    )
                    if not site_polygon.contains(sec_poly):
                        valid = False
                        break
                    
                    house_polys.append({
                        "poly": sec_poly,
                        "color": section["color"]
                    })
                    current_x += section["w"]
                
                if valid:
                    placements.append({
                        "position": [lon, lat],
                        "angle": angle,
                        "sections": house_polys,
                        "total_area": sum(
                            (p["poly"].bounds[2]-p["poly"].bounds[0]) * 
                            (p["poly"].bounds[3]-p["poly"].bounds[1]) * 
                            (111320**2) * floors * 0.7 
                            for p in house_polys
                        )
                    })
    
    return sorted(placements, key=lambda x: -x["total_area"])[:10]  # Топ-10 вариантов

# ===== Визуализация =====
def create_map(site_polygon, placements):
    """Создание карты с вариантами размещения"""
    m = folium.Map(location=centroid, zoom_start=17)
    
    # Участок
    folium.GeoJson(
        site_polygon.__geo_interface__,
        style_function=lambda x: {
            "fillColor": "yellow",
            "color": "orange",
            "fillOpacity": 0.2
        },
        name="Граница участка"
    ).add_to(m)
    
    # Варианты размещения
    for i, place in enumerate(placements, 1):
        for section in place["sections"]:
            folium.Polygon(
                locations=[
                    [section["poly"].bounds[1], section["poly"].bounds[0]],
                    [section["poly"].bounds[1], section["poly"].bounds[2]],
                    [section["poly"].bounds[3], section["poly"].bounds[2]],
                    [section["poly"].bounds[3], section["poly"].bounds[0]]
                ],
                color=section["color"],
                fill=True,
                fillOpacity=0.7,
                popup=f"Вариант {i}\nУгол: {place['angle']}°"
            ).add_to(m)
    
    folium.LayerControl().add_to(m)
    return m

# ===== Основной блок =====
if st.button("Сгенерировать варианты размещения"):
    with st.spinner("Подбираем оптимальные конфигурации..."):
        placements = generate_placements(
            site_polygon,
            selected_sections,
            margin,
            floors
        )
        st.session_state.results = placements

if st.session_state.results:
    st.success(f"Найдено {len(st.session_state.results)} вариантов")
    
    # Отображение карты
    m = create_map(site_polygon, st.session_state.results)
    st_folium(m, width=1200, height=700)
    
    # Таблица результатов
    st.subheader("Лучшие варианты")
    results_data = []
    for i, place in enumerate(st.session_state.results, 1):
        results_data.append({
            "Вариант": i,
            "Угол поворота": f"{place['angle']}°",
            "Общая площадь": f"{place['total_area']:,.2f} м²",
            "Кол-во секций": len(place["sections"])
        })
    
    st.table(pd.DataFrame(results_data))
