import streamlit as st
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, Point, MultiPolygon, LineString
import folium
from streamlit_folium import folium_static
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
import random
import math

# Константы из документа
PARKING_SPACE_AREA = 15  # м² на одно машиноместо
DISABLED_PARKING_SPACE_AREA = 20  # м² на одно машиноместо для инвалидов
GREEN_RATE = 0.3  # 30% участка должно быть озеленено
SOCIAL_AREA = 500  # м² под социально-бытовые площадки
BUILDING_SETBACK = 5  # минимальный отступ от границ участка (м)
PARKING_SETBACK = 3  # отступ парковки от границ (м)

def generate_layout(lot_area, building_area, floors, coordinates, 
                   total_parking_spaces, disabled_parking_spaces,
                   social_area=SOCIAL_AREA):
    """Генерация планировки участка с учетом всех требований"""
    # Создаем полигон участка
    lot_polygon = Polygon(coordinates)
    centroid = lot_polygon.centroid
    
    # Рассчитываем площади
    total_parking_area = (total_parking_spaces * PARKING_SPACE_AREA + 
                         disabled_parking_spaces * DISABLED_PARKING_SPACE_AREA)
    required_green_area = lot_area * GREEN_RATE
    
    # Создаем геометрические объекты
    features = {
        'lot': lot_polygon,
        'building': None,
        'parking': None,
        'disabled_parking': None,
        'green': None,
        'social': None,
        'setbacks': None,
        'no_construction': None
    }
    
    # 1. Определяем зону, где строительство невозможно
    # (вдоль границ участка с отступом)
    no_construction = lot_polygon.buffer(-BUILDING_SETBACK, join_style=2)
    features['no_construction'] = no_construction
    
    # 2. Размещаем здание в центре доступной зоны
    if no_construction.is_empty:
        buildable_area = lot_polygon
    else:
        buildable_area = no_construction
        
    buildable_centroid = buildable_area.centroid
    
    # Размеры здания (упрощенно - квадратное)
    building_side = math.sqrt(building_area)
    building_poly = Polygon([
        (buildable_centroid.x - building_side/2, buildable_centroid.y - building_side/2),
        (buildable_centroid.x + building_side/2, buildable_centroid.y - building_side/2),
        (buildable_centroid.x + building_side/2, buildable_centroid.y + building_side/2),
        (buildable_centroid.x - building_side/2, buildable_centroid.y + building_side/2)
    ])
    features['building'] = building_poly
    
    # 3. Размещаем парковку
    # Обычные места
    parking_rows = math.ceil(total_parking_spaces / 10)  # 10 мест в ряду
    parking_length = 10 * 5  # 5м на машиноместо
    parking_width = parking_rows * 3  # 3м ширина ряда
    
    parking_poly = Polygon([
        (buildable_centroid.x - 50, buildable_centroid.y - 30),
        (buildable_centroid.x - 50 + parking_length, buildable_centroid.y - 30),
        (buildable_centroid.x - 50 + parking_length, buildable_centroid.y - 30 + parking_width),
        (buildable_centroid.x - 50, buildable_centroid.y - 30 + parking_width)
    ])
    features['parking'] = parking_poly
    
    # Места для инвалидов (рядом со зданием)
    disabled_parking_poly = Polygon([
        (buildable_centroid.x - 10, buildable_centroid.y - 30),
        (buildable_centroid.x - 10 + disabled_parking_spaces * 5, buildable_centroid.y - 30),
        (buildable_centroid.x - 10 + disabled_parking_spaces * 5, buildable_centroid.y - 25),
        (buildable_centroid.x - 10, buildable_centroid.y - 25)
    ])
    features['disabled_parking'] = disabled_parking_poly
    
    # 4. Озеленение - оставшаяся площадь
    # Сначала собираем все занятые площади
    occupied = MultiPolygon([
        building_poly,
        parking_poly,
        disabled_parking_poly
    ])
    
    # Вычитаем из участка занятые площади + отступы
    green_area = lot_polygon.difference(occupied.buffer(PARKING_SETBACK))
    features['green'] = green_area
    
    # 5. Социально-бытовые площадки
    social_side = math.sqrt(social_area)
    social_poly = Polygon([
        (buildable_centroid.x + 40, buildable_centroid.y),
        (buildable_centroid.x + 40 + social_side, buildable_centroid.y),
        (buildable_centroid.x + 40 + social_side, buildable_centroid.y + social_side),
        (buildable_centroid.x + 40, buildable_centroid.y + social_side)
    ])
    features['social'] = social_poly
    
    # 6. Отступы (границы)
    setback_lines = []
    for i in range(len(coordinates)):
        start = coordinates[i]
        end = coordinates[(i+1)%len(coordinates)]
        line = LineString([start, end])
        setback_line = line.parallel_offset(BUILDING_SETBACK, 'left')
        setback_lines.append(setback_line)
    features['setbacks'] = MultiLineString(setback_lines)
    
    return features

def visualize_scheme(features, coordinates):
    """Визуализация схемы согласно требованиям"""
    centroid = features['lot'].centroid
    m = folium.Map(location=[centroid.y, centroid.x], zoom_start=18)
    
    # Границы участка
    folium.GeoJson(
        features['lot'],
        style_function=lambda x: {
            'fillColor': 'transparent',
            'color': 'black',
            'weight': 3,
            'dashArray': '5, 5'
        },
        name="Граница участка"
    ).add_to(m)
    
    # Зона, где строительство невозможно
    if features['no_construction']:
        folium.GeoJson(
            features['no_construction'],
            style_function=lambda x: {
                'fillColor': 'red',
                'color': 'red',
                'fillOpacity': 0.2
            },
            name="Строительство невозможно"
        ).add_to(m)
    
    # Отступы
    if features['setbacks']:
        folium.GeoJson(
            features['setbacks'],
            style_function=lambda x: {
                'color': 'orange',
                'weight': 2
            },
            name="Отступы"
        ).add_to(m)
    
    # Здание
    if features['building']:
        folium.GeoJson(
            features['building'],
            style_function=lambda x: {
                'fillColor': 'darkblue',
                'color': 'darkblue',
                'fillOpacity': 0.7
            },
            name="ОКС"
        ).add_to(m)
    
    # Парковка
    if features['parking']:
        folium.GeoJson(
            features['parking'],
            style_function=lambda x: {
                'fillColor': 'gray',
                'color': 'gray',
                'fillOpacity': 0.5
            },
            name="Парковка"
        ).add_to(m)
    
    # Парковка для инвалидов
    if features['disabled_parking']:
        folium.GeoJson(
            features['disabled_parking'],
            style_function=lambda x: {
                'fillColor': 'blue',
                'color': 'blue',
                'fillOpacity': 0.7
            },
            name="Парковка для инвалидов"
        ).add_to(m)
    
    # Озеленение
    if features['green']:
        folium.GeoJson(
            features['green'],
            style_function=lambda x: {
                'fillColor': 'green',
                'color': 'green',
                'fillOpacity': 0.3
            },
            name="Озеленение"
        ).add_to(m)
    
    # Социально-бытовые площадки
    if features['social']:
        folium.GeoJson(
            features['social'],
            style_function=lambda x: {
                'fillColor': 'purple',
                'color': 'purple',
                'fillOpacity': 0.5
            },
            name="Социально-бытовые площадки"
        ).add_to(m)
    
    # Добавляем контрольные точки
    folium.Marker(
        [centroid.y, centroid.x],
        icon=folium.DivIcon(html='<div style="font-weight: bold; color: black">Центр участка</div>')
    ).add_to(m)
    
    # Добавляем легенду
    legend_html = """
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: 180px; height: 250px; 
                border:2px solid grey; z-index:9999; font-size:14px;
                background-color:white;
                padding: 10px;">
        <b>Легенда</b><br>
        <i style="background: black; width: 15px; height: 15px; 
                  display: inline-block; opacity: 0.7"></i> Граница участка<br>
        <i style="background: red; width: 15px; height: 15px; 
                  display: inline-block; opacity: 0.2"></i> Строительство невозможно<br>
        <i style="background: orange; width: 15px; height: 15px; 
                  display: inline-block; opacity: 0.7"></i> Отступы<br>
        <i style="background: darkblue; width: 15px; height: 15px; 
                  display: inline-block; opacity: 0.7"></i> ОКС<br>
        <i style="background: gray; width: 15px; height: 15px; 
                  display: inline-block; opacity: 0.5"></i> Парковка<br>
        <i style="background: blue; width: 15px; height: 15px; 
                  display: inline-block; opacity: 0.7"></i> Парковка инвалидов<br>
        <i style="background: green; width: 15px; height: 15px; 
                  display: inline-block; opacity: 0.3"></i> Озеленение<br>
        <i style="background: purple; width: 15px; height: 15px; 
                  display: inline-block; opacity: 0.5"></i> Соц. площадки<br>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
    
    folium.LayerControl().add_to(m)
    
    return m

def main():
    st.title("Генератор схемы планировки участка")
    st.subheader("Согласно предоставленным требованиям")
    
    # Ввод параметров
    st.header("Основные параметры")
    col1, col2 = st.columns(2)
    
    with col1:
        lot_area = st.number_input("Площадь участка (кв.м)", min_value=100.0, value=8693.0)
        building_area = st.number_input("Площадь проектируемого пятна застройки (кв.м)", 
                                      min_value=100.0, value=1872.0)
        floors = st.number_input("Этажность здания", min_value=1, max_value=20, value=0)
    
    with col2:
        total_parking = st.number_input("Требуемое число машиномест (шт)", 
                                      min_value=0, value=148)
        disabled_parking = st.number_input("Требуемое число мест для инвалидов (шт)", 
                                         min_value=0, value=15)
        social_area = st.number_input("Площадь социально-бытовых площадок (кв.м)", 
                                    min_value=0.0, value=500.0)
    
    st.header("Координаты участка")
    st.write("Введите координаты углов участка в порядке обхода (минимум 3 точки)")
    
    # Пример координат (можно заменить на ввод пользователя)
    default_coords = [
        (37.6175, 55.7558),
        (37.6185, 55.7558),
        (37.6185, 55.7548),
        (37.6175, 55.7548)
    ]
    
    cols = st.columns(4)
    coordinates = []
    
    for i in range(4):
        with cols[i]:
            st.write(f"Точка {i+1}")
            lat = st.number_input(f"Широта {i+1}", value=default_coords[i][1], key=f"lat_{i}")
            lon = st.number_input(f"Долгота {i+1}", value=default_coords[i][0], key=f"lon_{i}")
            coordinates.append((lon, lat))
    
    if st.button("Сгенерировать схему"):
        with st.spinner("Генерация схемы..."):
            features = generate_layout(
                lot_area, building_area, floors, coordinates,
                total_parking, disabled_parking, social_area
            )
            
            st.success("Схема успешно сгенерирована!")
            
            # Отображение параметров
            st.subheader("Параметры планировки")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Площадь участка:** {lot_area:.2f} кв.м")
                st.write(f"**Площадь застройки:** {building_area:.2f} кв.м")
                st.write(f"**Этажность:** {floors}")
                st.write(f"**Машиноместа:** {total_parking} (обычные) + {disabled_parking} (для инвалидов)")
            
            with col2:
                required_green = lot_area * GREEN_RATE
                actual_green = features['green'].area if features['green'] else 0
                st.write(f"**Требуемое озеленение:** {required_green:.2f} кв.м")
                st.write(f"**Фактическое озеленение:** {actual_green:.2f} кв.м")
                st.write(f"**Социальные площадки:** {social_area:.2f} кв.м")
                st.write(f"**Зона без строительства:** {features['no_construction'].area:.2f} кв.м")
            
            # Визуализация
            st.subheader("Схема планировки участка")
            m = visualize_scheme(features, coordinates)
            folium_static(m, width=800, height=600)
            
            # Предупреждения о несоответствиях
            if actual_green < required_green:
                st.warning(f"Недостаточно озеленения! Требуется: {required_green:.2f} кв.м, фактически: {actual_green:.2f} кв.м")
            
            if features['building'].area < building_area:
                st.warning(f"Не удалось разместить все здание! Требуется: {building_area:.2f} кв.м, размещено: {features['building'].area:.2f} кв.м")

if __name__ == "__main__":
    main()
