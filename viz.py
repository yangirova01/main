import streamlit as st
import folium
import numpy as np
import pandas as pd
from shapely.geometry import Polygon, box
from streamlit_folium import st_folium

# Конфигурация страницы
st.set_page_config(layout="wide", page_title="Оптимальное размещение модульного дома")
st.title("Оптимизация размещения модульного дома на участке")

# Инициализация состояния сессии
if 'placements' not in st.session_state:
    st.session_state.placements = None
if 'site_polygon' not in st.session_state:
    st.session_state.site_polygon = None

# ===== КОНСТАНТЫ =====
SECTION_TYPES = {
    "26x16": {"width": 26, "height": 16, "color": "#1f77b4"},
    "28x16": {"width": 28, "height": 16, "color": "#ff7f0e"}, 
    "26x18": {"width": 26, "height": 18, "color": "#2ca02c"},
    "18x18": {"width": 18, "height": 18, "color": "#9467bd"}
}

# ===== ФУНКЦИИ =====
def meters_to_degrees(meters, latitude):
    """Конвертирует метры в градусы с учетом широты"""
    return meters / (111320 * np.cos(np.radians(latitude)))

def validate_coordinates(coords):
    """Проверяет валидность координат участка"""
    if len(coords) < 3:
        raise ValueError("Участок должен содержать минимум 3 точки")
    if any(len(point) != 2 for point in coords):
        raise ValueError("Каждая точка должна содержать 2 координаты")
    return True

def calculate_placements(site_poly, sections, margin, spacing, floors, orientation):
    """Вычисляет возможные варианты размещения секций"""
    placements = []
    min_lon, min_lat, max_lon, max_lat = site_poly.bounds
    centroid_lat = site_poly.centroid.y
    
    angles = [0, 90] if orientation == "Любая" else [0] if orientation == "Север-Юг" else [90]
    
    for angle in angles:
        sections_meta = []
        total_width = 0
        
        for section in sections:
            w, h = (SECTION_TYPES[section]["height"], SECTION_TYPES[section]["width"]) if angle == 90 else (
                   (SECTION_TYPES[section]["width"], SECTION_TYPES[section]["height"]))
            
            sections_meta.append({
                "width": meters_to_degrees(w, centroid_lat),
                "height": meters_to_degrees(h, centroid_lat),
                "color": SECTION_TYPES[section]["color"]
            })
            total_width += meters_to_degrees(w + spacing, centroid_lat)
        
        max_height = max(s["height"] for s in sections_meta)
        margin_deg = meters_to_degrees(margin, centroid_lat)
        
        for lon in np.linspace(min_lon + margin_deg, max_lon - total_width - margin_deg, 15):
            for lat in np.linspace(min_lat + margin_deg, max_lat - max_height - margin_deg, 15):
                current_x = lon
                valid = True
                house_sections = []
                
                for section in sections_meta:
                    section_poly = box(
                        current_x, lat,
                        current_x + section["width"], lat + section["height"]
                    )
                    
                    if not site_poly.contains(section_poly.buffer(-margin_deg/2)):
                        valid = False
                        break
                    
                    house_sections.append({
                        "poly": section_poly,
                        "color": section["color"]
                    })
                    current_x += section["width"] + meters_to_degrees(spacing, centroid_lat)
                
                if valid and house_sections:
                    area = sum(
                        (p["poly"].bounds[2] - p["poly"].bounds[0]) *
                        (p["poly"].bounds[3] - p["poly"].bounds[1]) *
                        (111320**2) * floors * 0.7
                        for p in house_sections
                    )
                    
                    placements.append({
                        "position": [lon, lat],
                        "angle": angle,
                        "sections": house_sections,
                        "total_area": area,
                        "efficiency": area / (site_poly.area * (111320**2))
                    })
    
    return sorted(placements, key=lambda x: -x["efficiency"])[:10]

def create_placement_map(site_poly, placements):
    """Создает интерактивную карту с вариантами размещения"""
    m = folium.Map(location=[site_poly.centroid.y, site_poly.centroid.x], zoom_start=17)
    
    # Отображение участка
    folium.GeoJson(
        site_poly.__geo_interface__,
        style_function=lambda x: {
            "fillColor": "#ffff00",
            "color": "#ffa500",
            "weight": 2,
            "fillOpacity": 0.2
        },
        name="Граница участка"
    ).add_to(m)
    
    # Отображение вариантов размещения
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

# ===== ИНТЕРФЕЙС =====
with st.sidebar:
    st.header("Параметры участка")
    coord_input = st.text_area(
        "Координаты участка ([[lat, lon], ...]):",
        """[[55.796391, 37.535800],
        [55.796288, 37.535120],
        [55.795950, 37.535350],
        [55.796050, 37.536000]]""",
        height=120
    )
    
    st.header("Конфигурация дома")
    section_count = st.slider("Количество секций:", 2, 5, 2)
    selected_sections = [st.selectbox(
        f"Секция {i+1}:", list(SECTION_TYPES.keys()), key=f"section_{i}"
    ) for i in range(section_count)]
    
    st.header("Параметры размещения")
    margin = st.slider("Отступ от границ (м):", 0, 20, 5)
    spacing = st.slider("Расстояние между секциями (м):", 0, 10, 2)
    floors = st.slider("Этажность:", 1, 25, 5)
    orientation = st.radio("Ориентация дома:", ["Любая", "Север-Юг", "Восток-Запад"])

# Обработка ввода координат
try:
    coords = eval(coord_input)
    validate_coordinates(coords)
    site_polygon = Polygon(coords)
    st.session_state.site_polygon = site_polygon
except Exception as e:
    st.error(f"Ошибка ввода данных: {str(e)}")
    st.stop()

# Основной блок
if st.button("Рассчитать варианты размещения", type="primary"):
    with st.spinner("Оптимизация размещения..."):
        placements = calculate_placements(
            site_polygon,
            selected_sections,
            margin,
            spacing,
            floors,
            orientation
        )
        st.session_state.placements = placements

if st.session_state.placements:
    st.success(f"Найдено {len(st.session_state.placements)} вариантов")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st_folium(
            create_placement_map(site_polygon, st.session_state.placements),
            width=700,
            height=500
        )
    
    with col2:
        st.subheader("Лучшие варианты")
        df = pd.DataFrame([{
            "Вариант": i+1,
            "Площадь (м²)": f"{p['total_area']:,.0f}",
            "Эффективность": f"{p['efficiency']:.1%}",
            "Угол": f"{p['angle']}°"
        } for i, p in enumerate(st.session_state.placements)])
        
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Эффективность": st.column_config.ProgressColumn(
                    format="%.1f%%",
                    min_value=0,
                    max_value=1.0
                )
            }
        )
        
        if st.button("Экспорт в CSV"):
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Скачать",
                csv,
                "размещение_дома.csv",
                "text/csv"
            )
else:
    st.info("Задайте параметры и нажмите 'Рассчитать варианты размещения'")
