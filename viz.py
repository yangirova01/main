import streamlit as st
import folium
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon, box
from streamlit_folium import st_folium
from itertools import combinations

# Настройки страницы
st.set_page_config(layout="wide")
st.title("Оптимальное размещение модульного дома на участке")

# Инициализация состояния
if 'results' not in st.session_state:
    st.session_state.results = None
if 'site_polygon' not in st.session_state:
    st.session_state.site_polygon = None

# ===== Константы и вспомогательные функции =====
SECTION_TYPES = {
    "26x16": {"width": 26, "height": 16, "color": "#1f77b4", "name": "Стандарт 26x16"},
    "28x16": {"width": 28, "height": 16, "color": "#ff7f0e", "name": "Увеличенный 28x16"},
    "26x18": {"width": 26, "height": 18, "color": "#2ca02c", "name": "С улучшенной планировкой 26x18"},
    "18x18": {"width": 18, "height": 18, "color": "#9467bd", "name": "Компактный 18x18"}
}

def m_to_deg(meters, lat):
    """Конвертация метров в градусы с учетом широты"""
    return meters / (111320 * np.cos(np.radians(lat)))

def validate_coordinates(coords):
    """Проверка валидности координат участка"""
    if len(coords) < 3:
        raise ValueError("Участок должен содержать минимум 3 точки")
    if any(len(point) != 2 for point in coords):
        raise ValueError("Каждая точка должна содержать 2 координаты")
    return True

# ===== Ввод данных =====
with st.sidebar:
    st.header("Параметры участка")
    coord_input = st.text_area(
        "Координаты участка ([[lat, lon], ...]):",
        """[[55.796391, 37.535800],
        [55.796288, 37.535120],
        [55.795950, 37.535350],
        [55.796050, 37.536000]]""",
        height=150
    )

    st.header("Конфигурация дома")
    section_count = st.slider("Количество секций:", 2, 5, 2)
    selected_sections = []
    for i in range(section_count):
        selected_sections.append(st.selectbox(
            f"Секция {i+1}:",
            list(SECTION_TYPES.keys()),
            format_func=lambda x: SECTION_TYPES[x]["name"],
            key=f"section_{i}"
        ))

    st.header("Параметры размещения")
    margin = st.slider("Отступ от границ (м):", 0, 20, 5)
    min_distance = st.slider("Расстояние между секциями (м):", 0, 10, 2)
    floors = st.slider("Этажность:", 1, 25, 5)
    orientation = st.radio("Ориентация", ["Любая", "Север-Юг", "Восток-Запад"], index=0)

# Парсинг координат участка
try:
    coords = eval(coord_input)
    validate_coordinates(coords)
    site_polygon = Polygon(coords)
    centroid = list(site_polygon.centroid.coords)[0][::-1]
    st.session_state.site_polygon = site_polygon
except Exception as e:
    st.error(f"Ошибка ввода данных: {str(e)}")
    st.stop()

# ===== Алгоритм размещения =====
@st.cache_data(show_spinner="Подбираем оптимальные конфигурации...")
def generate_placements(_site_polygon, sections, margin, min_distance, floors, orientation):
    """Генерация возможных комбинаций секций"""
    placements = []
    min_lon, min_lat, max_lon, max_lat = _site_polygon.bounds
    
    # Определение допустимых углов поворота
    angles = [0, 90] if orientation == "Любая" else (
        [0] if orientation == "Север-Юг" else [90]
    )
    
    for angle in angles:
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
                "w": m_to_deg(w, centroid[1]),
                "h": m_to_deg(h, centroid[1]),
                "color": SECTION_TYPES[section]["color"],
                "name": SECTION_TYPES[section]["name"]
            })
            total_width += m_to_deg(w, centroid[1]) + m_to_deg(min_distance, centroid[1])
            total_height = max(total_height, m_to_deg(h, centroid[1]))
        
        margin_deg = m_to_deg(margin, centroid[1])
        
        # Оптимизированный шаг для больших участков
        lon_steps = 20 if (max_lon - min_lon) > 0.001 else 10
        lat_steps = 20 if (max_lat - min_lat) > 0.001 else 10
        
        # Поиск позиций
        for lon in np.linspace(min_lon + margin_deg, max_lon - total_width - margin_deg, lon_steps):
            for lat in np.linspace(min_lat + margin_deg, max_lat - total_height - margin_deg, lat_steps):
                current_x = lon
                valid = True
                house_polys = []
                
                for section in section_polys:
                    sec_poly = box(
                        current_x, lat,
                        current_x + section["w"], lat + section["h"]
                    )
                    
                    # Проверка на вхождение в участок и отступы
                    if not _site_polygon.contains(sec_poly.buffer(-margin_deg/2)):
                        valid = False
                        break
                    
                    house_polys.append({
                        "poly": sec_poly,
                        "color": section["color"],
                        "name": section["name"]
                    })
                    current_x += section["w"] + m_to_deg(min_distance, centroid[1])
                
                if valid and house_polys:
                    # Расчет общей площади с учетом КИ (коэффициента использования)
                    total_area = sum(
                        (p["poly"].bounds[2]-p["poly"].bounds[0]) * 
                        (p["poly"].bounds[3]-p["poly"].bounds[1]) * 
                        (111320**2) * floors * 0.7  # 0.7 - типовой КИ
                        for p in house_polys
                    )
                    
                    placements.append({
                        "position": [lon, lat],
                        "angle": angle,
                        "sections": house_polys,
                        "total_area": total_area,
                        "efficiency": total_area / _site_polygon.area * (111320**2)
                    })
    
    # Сортировка по эффективности использования площади
    return sorted(placements, key=lambda x: -x["efficiency"])[:15]

# ===== Визуализация =====
def create_map(_site_polygon, placements):
    """Создание интерактивной карты с вариантами"""
    m = folium.Map(location=centroid, zoom_start=17, tiles='cartodbpositron')
    
    # Участок
    folium.GeoJson(
        _site_polygon.__geo_interface__,
        style_function=lambda x: {
            "fillColor": "#ffff00",
            "color": "#ffa500",
            "weight": 2,
            "fillOpacity": 0.2
        },
        name="Граница участка",
        tooltip="Ваш участок"
    ).add_to(m)
    
    # Варианты размещения
    for i, place in enumerate(placements, 1):
        group = folium.FeatureGroup(name=f"Вариант {i}", show=False)
        
        for j, section in enumerate(place["sections"], 1):
            coords = [
                [section["poly"].bounds[1], section["poly"].bounds[0]],
                [section["poly"].bounds[1], section["poly"].bounds[2]],
                [section["poly"].bounds[3], section["poly"].bounds[2]],
                [section["poly"].bounds[3], section["poly"].bounds[0]]
            ]
            
            folium.Polygon(
                locations=coords,
                color=section["color"],
                fill=True,
                fillOpacity=0.7,
                weight=1,
                popup=f"""<b>Вариант {i}</b><br>
                          Секция {j}: {section['name']}<br>
                          Угол: {place['angle']}°<br>
                          Площадь: {place['total_area']/len(place['sections']):.1f} м²"""
            ).add_to(group)
        
        group.add_to(m)
    
    folium.LayerControl(collapsed=False).add_to(m)
    folium.LatLngPopup().add_to(m)
    return m

# ===== Основной блок =====
col1, col2 = st.columns([3, 1])

with col2:
    if st.button("🔄 Сгенерировать варианты", type="primary", use_container_width=True):
        with st.spinner("Оптимизируем размещение..."):
            placements = generate_placements(
                st.session_state.site_polygon,
                selected_sections,
                margin,
                min_distance,
                floors,
                orientation
            )
            st.session_state.results = placements
            
    if st.session_state.results:
        st.success(f"Найдено {len(st.session_state.results)} вариантов")
        best_option = max(st.session_state.results, key=lambda x: x['efficiency'])
        
        with st.expander("Лучший вариант", expanded=True):
            st.metric("Общая площадь", f"{best_option['total_area']:,.0f} м²")
            st.metric("Эффективность использования", f"{best_option['efficiency']:.1%}")
            st.metric("Этажность", floors)
            st.metric("Угол поворота", f"{best_option['angle']}°")
            
        if st.download_button(
            "📥 Экспорт в CSV",
            pd.DataFrame([{
                "Вариант": i+1,
                "Площадь (м²)": p["total_area"],
                "Эффективность": f"{p['efficiency']:.1%}",
                "Угол": f"{p['angle']}°",
                "Секций": len(p["sections"])
            } for i, p in enumerate(st.session_state.results)]).to_csv(index=False).encode('utf-8'),
            "варианты_размещения.csv",
            "text/csv",
            use_container_width=True
        ):
            st.toast("Файл экспортирован!", icon="✅")

with col1:
    if st.session_state.results:
        m = create_map(st.session_state.site_polygon, st.session_state.results)
        st_folium(m, width=800, height=600, returned_objects=[])
        
        st.subheader("Топ вариантов")
        df = pd.DataFrame([{
            "Вариант": i+1,
            "Площадь, м²": f"{p['total_area']:,.0f}",
            "Эффективность": f"{p['efficiency']:.1%}",
            "Угол": f"{p['angle']}°",
            "Секций": len(p["sections"])
        } for i, p in enumerate(st.session_state.results)])
        
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
    else:
        st.info("Задайте параметры и нажмите 'Сгенерировать варианты'")
        st.image("https://i.imgur.com/JiQkLZP.png", caption="Пример модульного дома")
