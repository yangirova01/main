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
import json

# ... (остальные константы и функции остаются такими же, как в предыдущем коде)

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
    st.write("Введите координаты участка в формате JSON (массив массивов [долгота, широта])")
    
    # Пример координат в JSON-формате
    default_coords = [
        [37.6175, 55.7558],
        [37.6185, 55.7558],
        [37.6185, 55.7548],
        [37.6175, 55.7548]
    ]
    
    # Поле для ввода JSON
    coords_json = st.text_area(
        "Координаты участка (JSON)", 
        value=json.dumps(default_coords),
        height=100
    )
    
    try:
        coordinates = json.loads(coords_json)
        # Преобразуем координаты в формат (lon, lat)
        coordinates = [(point[0], point[1]) for point in coordinates]
        
        # Валидация координат
        if len(coordinates) < 3:
            st.error("Необходимо указать минимум 3 точки для участка")
            return
        
        # Предварительный просмотр участка
        st.subheader("Предварительный просмотр участка")
        preview_map = folium.Map(location=[coordinates[0][1], coordinates[0][0]], zoom_start=15)
        folium.Polygon(
            locations=[[point[1], point[0]] for point in coordinates],
            color='blue',
            fill=True,
            fill_color='blue',
            fill_opacity=0.2
        ).add_to(preview_map)
        folium_static(preview_map, width=700, height=300)
        
    except json.JSONDecodeError:
        st.error("Ошибка в формате JSON. Пожалуйста, проверьте введенные данные")
        return
    except Exception as e:
        st.error(f"Ошибка при обработке координат: {str(e)}")
        return
    
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
