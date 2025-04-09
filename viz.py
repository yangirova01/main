import streamlit as st
import folium
import numpy as np
import pandas as pd
from shapely.geometry import Polygon, box, LineString, Point
from shapely.ops import unary_union
from itertools import permutations, combinations
from streamlit_folium import st_folium
from math import cos, radians

# Конфигурация страницы
st.set_page_config(layout="wide", page_title="Проектировщик модульной застройки")
st.title("Оптимизатор размещения модульного комплекса")

# ===== КОНСТАНТЫ =====
SECTION_TYPES = {
    "Жилой L": {"size": (28, 16), "color": "#1f77b4", "type": "living", "floors": True},
    "Жилой M": {"size": (26, 16), "color": "#4b78ca", "type": "living", "floors": True},
    "Жилой S": {"size": (18, 18), "color": "#8ab4f7", "type": "living", "floors": True},
    "Паркинг": {"size": (20, 15), "color": "#7f7f7f", "type": "parking", "floors": False},
    "Школа": {"size": (30, 25), "color": "#2ca02c", "type": "social", "floors": False},
    "Сквер": {"size": (25, 25), "color": "#9467bd", "type": "green", "floors": False}
}

# ===== ФУНКЦИИ =====
def meters_to_degrees(meters, lat):
    return meters / (111320 * cos(radians(lat)))

def generate_all_combinations(sections):
    """Генерация всех уникальных комбинаций секций"""
    unique_combs = set()
    for perm in permutations(sections):
        if perm not in unique_combs:
            unique_combs.add(perm)
    return [list(comb) for comb in unique_combs]

def calculate_optimal_placements(site_poly, sections, params):
    """Полный перебор всех возможных вариантов размещения"""
    placements = []
    centroid_lat = site_poly.centroid.y
    min_lon, min_lat, max_lon, max_lat = site_poly.bounds
    
    # Конвертация параметров
    margin_deg = meters_to_degrees(params['margin'], centroid_lat)
    spacing_deg = meters_to_degrees(params['spacing'], centroid_lat)
    green_buffer_deg = meters_to_degrees(params['green_buffer'], centroid_lat)
    
    # Генерация всех комбинаций секций
    all_combinations = generate_all_combinations(sections)
    
    # Адаптивный шаг для перебора позиций
    lon_step = (max_lon - min_lon) / 20
    lat_step = (max_lat - min_lat) / 20
    
    for angle in params['angles']:
        for combination in all_combinations:
            # Рассчитываем общие габариты комбинации
            total_width = sum(meters_to_degrees(s['size'][0], centroid_lat) 
                          if angle == 0 else meters_to_degrees(s['size'][1], centroid_lat) 
                          for s in combination)
            total_width += (len(combination) - 1) * spacing_deg
            
            max_height = max(meters_to_degrees(s['size'][1], centroid_lat) 
                           if angle == 0 else meters_to_degrees(s['size'][0], centroid_lat) 
                           for s in combination)
            
            # Перебор возможных позиций
            for lon in np.arange(min_lon + margin_deg, 
                               max_lon - total_width - margin_deg, 
                               lon_step):
                for lat in np.arange(min_lat + margin_deg,
                                   max_lat - max_height - margin_deg,
                                   lat_step):
                    placement = try_place_combination(
                        site_poly=site_poly,
                        combination=combination,
                        angle=angle,
                        start_lon=lon,
                        start_lat=lat,
                        spacing_deg=spacing_deg,
                        margin_deg=margin_deg,
                        green_buffer_deg=green_buffer_deg,
                        params=params
                    )
                    
                    if placement:
                        placements.append(placement)
                        if len(placements) >= params['max_results']:
                            return placements
    
    return sorted(placements, key=lambda x: -x['score'])[:params['max_results']]

def try_place_combination(site_poly, combination, angle, start_lon, start_lat,
                         spacing_deg, margin_deg, green_buffer_deg, params):
    """Попытка размещения конкретной комбинации секций"""
    current_x = start_lon
    placed_sections = []
    green_zones = []
    living_area = 0
    
    for section in combination:
        # Определяем размеры с учетом ориентации
        width, height = section['size'] if angle == 0 else section['size'][::-1]
        w_deg = meters_to_degrees(width, site_poly.centroid.y)
        h_deg = meters_to_degrees(height, site_poly.centroid.y)
        
        # Создаем полигон секции
        section_poly = box(
            current_x, start_lat,
            current_x + w_deg, start_lat + h_deg
        )
        
        # Проверка валидности размещения
        if not is_valid_placement(section_poly, site_poly, placed_sections, margin_deg, params['red_lines']):
            return None
        
        # Добавляем секцию
        section_data = {
            'poly': section_poly,
            'type': section['type'],
            'color': section['color'],
            'size': (width, height),
            'floors': params['floors'] if section['floors'] else 1
        }
        placed_sections.append(section_data)
        
        # Расчет жилой площади
        if section['type'] == 'living':
            living_area += section_poly.area * (111320**2) * section_data['floors']
        
        # Добавляем зеленую зону
        if params['green_zones'] and section['type'] in ['living', 'social']:
            green_zone = section_poly.buffer(green_buffer_deg)
            green_zones.append(green_zone)
        
        current_x += w_deg + spacing_deg
    
    # Проверка зеленых зон
    if params['green_zones'] and not validate_green_zones(green_zones, placed_sections, site_poly):
        return None
    
    # Расчет показателей
    total_area = sum(s['poly'].area * (111320**2) * s['floors'] for s in placed_sections)
    efficiency = living_area / (site_poly.area * (111320**2))
    green_area = sum(g.area * (111320**2) for g in green_zones) if green_zones else 0
    
    return {
        'position': [start_lon, start_lat],
        'angle': angle,
        'sections': placed_sections,
        'green_zones': green_zones,
        'living_area': living_area,
        'total_area': total_area,
        'green_area': green_area,
        'efficiency': efficiency,
        'score': calculate_score(living_area, green_area, efficiency, params)
    }

def is_valid_placement(poly, site_poly, existing_sections, margin, red_lines):
    """Проверка валидности размещения одного элемента"""
    # Проверка границ участка с отступом
    if not site_poly.contains(poly.buffer(-margin/2)):
        return False
    
    # Проверка красных линий
    for line in red_lines:
        if poly.intersects(line):
            return False
    
    # Проверка пересечений с другими секциями
    for section in existing_sections:
        if poly.intersects(section['poly']):
            return False
    
    return True

def validate_green_zones(green_zones, sections, site_poly):
    """Проверка зеленых зон"""
    combined_green = unary_union(green_zones)
    
    # Проверка, что зеленые зоны не пересекают здания
    for section in sections:
        if combined_green.intersects(section['poly']):
            return False
    
    # Проверка, что зеленые зоны внутри участка
    if not site_poly.contains(combined_green):
        return False
    
    return True

def calculate_score(living_area, green_area, efficiency, params):
    """Комплексная оценка варианта"""
    living_score = living_area * params['living_weight']
    green_score = green_area * params['green_weight']
    efficiency_score = efficiency * params['efficiency_weight']
    return living_score + green_score + green_score

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
    
    st.header("Красные линии")
    red_line_input = st.text_area(
        "Координаты красных линий ([[[lat,lon],...], ...]):",
        """[[[55.796300, 37.535500], [55.796300, 37.535900]]]""",
        height=80
    )
    
    st.header("Состав комплекса")
    section_count = st.slider("Количество элементов:", 1, 10, 3)
    selected_sections = [st.selectbox(
        f"Элемент {i+1}:", list(SECTION_TYPES.keys()), key=f"section_{i}"
    ) for i in range(section_count)]
    
    st.header("Параметры размещения")
    margin = st.slider("Отступ от границ (м):", 0, 50, 10)
    spacing = st.slider("Расстояние между элементами (м):", 0, 50, 5)
    floors = st.slider("Этажность жилых зданий:", 1, 25, 5)
    green_buffer = st.slider("Зеленая зона вокруг объектов (м):", 0, 30, 5)
    orientation = st.radio("Ориентация зданий:", ["Любая", "Север-Юг", "Восток-Запад"])
    
    st.header("Критерии оценки")
    living_weight = st.slider("Важность жилой площади:", 0.1, 1.0, 0.5)
    green_weight = st.slider("Важность озеленения:", 0.1, 1.0, 0.3)
    efficiency_weight = st.slider("Важность эффективности:", 0.1, 1.0, 0.2)

# Обработка входных данных
try:
    # Парсинг участка
    coords = eval(coord_input)
    if len(coords) < 3:
        st.error("Участок должен содержать минимум 3 точки")
        st.stop()
    site_polygon = Polygon(coords)
    
    # Парсинг красных линий
    red_lines = [LineString(line) for line in eval(red_line_input)]
    
    # Параметры расчета
    params = {
        'margin': margin,
        'spacing': spacing,
        'floors': floors,
        'green_buffer': green_buffer,
        'green_zones': green_buffer > 0,
        'angles': [0, 90] if orientation == "Любая" else [0] if orientation == "Север-Юг" else [90],
        'red_lines': red_lines,
        'living_weight': living_weight,
        'green_weight': green_weight,
        'efficiency_weight': efficiency_weight,
        'max_results': 15
    }
    
    # Получаем выбранные секции с полными параметрами
    sections = [SECTION_TYPES[name] for name in selected_sections]
    
except Exception as e:
    st.error(f"Ошибка ввода данных: {str(e)}")
    st.stop()

# Основной блок
if st.button("Рассчитать оптимальные варианты", type="primary"):
    with st.spinner("Идет расчет оптимальных конфигураций..."):
        try:
            placements = calculate_optimal_placements(
                site_polygon,
                sections,
                params
            )
            
            if not placements:
                st.error("Не удалось найти ни одного валидного варианта. Попробуйте изменить параметры.")
                st.stop()
                
            st.session_state.placements = placements
            st.success(f"Найдено {len(placements)} оптимальных вариантов")
            
        except Exception as e:
            st.error(f"Ошибка при расчетах: {str(e)}")
            st.stop()

if 'placements' in st.session_state and st.session_state.placements:
    # Визуализация
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Создаем карту
        m = folium.Map(location=[site_polygon.centroid.y, site_polygon.centroid.x], zoom_start=17)
        
        # Участок
        folium.GeoJson(
            site_polygon.__geo_interface__,
            style_function=lambda x: {
                "fillColor": "#ffff00",
                "color": "#ffa500",
                "weight": 2,
                "fillOpacity": 0.1
            },
            name="Граница участка"
        ).add_to(m)
        
        # Красные линии
        for line in red_lines:
            folium.PolyLine(
                locations=[[y, x] for x, y in line.coords],
                color="red",
                weight=3,
                name="Красные линии"
            ).add_to(m)
        
        # Лучший вариант
        best = st.session_state.placements[0]
        for section in best['sections']:
            folium.Polygon(
                locations=[
                    [section['poly'].bounds[1], section['poly'].bounds[0]],
                    [section['poly'].bounds[1], section['poly'].bounds[2]],
                    [section['poly'].bounds[3], section['poly'].bounds[2]],
                    [section['poly'].bounds[3], section['poly'].bounds[0]]
                ],
                color=section['color'],
                fill=True,
                fillOpacity=0.7,
                popup=f"{section['type']} {section['size'][0]}x{section['size'][1]}м"
            ).add_to(m)
        
        # Зеленые зоны
        if best['green_zones']:
            for zone in best['green_zones']:
                folium.GeoJson(
                    zone.__geo_interface__,
                    style_function=lambda x: {
                        "fillColor": "#2ecc71",
                        "color": "#27ae60",
                        "fillOpacity": 0.3
                    },
                    name="Зеленые зоны"
                ).add_to(m)
        
        folium.LayerControl().add_to(m)
        st_folium(m, width=800, height=600)
    
    with col2:
        st.subheader("Топ вариантов")
        
        # Таблица результатов
        df = pd.DataFrame([{
            "Вариант": i+1,
            "Жилая площадь": f"{p['living_area']:,.0f} м²",
            "Озеленение": f"{p['green_area']:,.0f} м²" if p['green_area'] else "Нет",
            "Эффективность": f"{p['efficiency']:.1%}",
            "Оценка": f"{p['score']:,.1f}"
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
        
        # Детализация лучшего варианта
        st.subheader("Лучший вариант")
        st.markdown(f"""
        - **Жилая площадь**: {best['living_area']:,.0f} м²
        - **Общая площадь**: {best['total_area']:,.0f} м²
        - **Озеленение**: {best['green_area']:,.0f} м²
        - **Эффективность**: {best['efficiency']:.1%}
        - **Ориентация**: {'Север-Юг' if best['angle'] == 0 else 'Восток-Запад'}
        """)
        
        # Экспорт
        if st.button("Экспорт результатов в CSV"):
            csv = df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                "Скачать таблицу",
                csv,
                "оптимальные_варианты.csv",
                "text/csv"
            )

else:
    st.info("Задайте параметры участка и состава комплекса, затем нажмите кнопку 'Рассчитать оптимальные варианты'")
