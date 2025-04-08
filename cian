import streamlit as st
import pandas as pd
from cianparser import CianParser
import math
import plotly.graph_objects as go
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

def get_coordinates(address):
    """Получение координат по адресу"""
    geolocator = Nominatim(user_agent="geoapiExercises")
    location = geolocator.geocode(address)
    if location:
        return (location.latitude, location.longitude)
    return None

def parse_cian_flats(location, radius_km, deal_type="sale", rooms=(1, 2, 3, 4)):
    """Парсинг данных с ЦИАН"""
    parser = CianParser(location=location)
    try:
        data = parser.get_flats(
            deal_type=deal_type,
            rooms=rooms,
            with_saving_csv=False,
            additional_settings={"radius": radius_km}
        )
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Ошибка при парсинге данных: {str(e)}")
        return None

def calculate_average_price(df):
    """Расчет средней цены за кв.м"""
    if df is None or df.empty:
        return None
    
    # Очистка данных
    df['price'] = df['price'].str.replace('[^\d]', '', regex=True).astype(float)
    df['area'] = df['area'].str.replace('[^\d.]', '', regex=True).astype(float)
    
    # Расчет цены за кв.м
    df['price_per_m2'] = df['price'] / df['area']
    
    # Удаление выбросов (цены < 10_000 или > 1_000_000 за кв.м)
    df = df[(df['price_per_m2'] > 10_000) & (df['price_per_m2'] < 1_000_000)]
    
    return df['price_per_m2'].mean()

def main():
    st.set_page_config(page_title="Анализ недвижимости", layout="wide")
    st.title("📊 Анализ стоимости недвижимости")
    
    # Ввод параметров
    with st.expander("🔍 Параметры поиска", expanded=True):
        address = st.text_input("Адрес участка", "Казань, Касаткина 3")
        radius = st.slider("Радиус поиска (км)", 0.5, 5.0, 1.0, 0.1)
        deal_type = st.radio("Тип недвижимости", ["Вторичка", "Новостройка"], index=0)
        rooms = st.multiselect(
            "Количество комнат", 
            ["Студия", "1", "2", "3", "4+"], 
            default=["1", "2", "3"]
        )
    
    if st.button("Собрать данные"):
        with st.spinner("Ищем предложения..."):
            # Преобразование параметров
            cian_deal_type = "secondary" if deal_type == "Вторичка" else "newbuilding"
            cian_rooms = []
            for r in rooms:
                if r == "Студия": cian_rooms.append(0)
                elif r == "4+": cian_rooms.append(4)
                else: cian_rooms.append(int(r))
            
            # Получаем координаты для проверки
            coords = get_coordinates(address)
            if coords:
                st.success(f"Координаты участка: {coords[0]:.4f}, {coords[1]:.4f}")
            
            # Парсинг данных
            df = parse_cian_flats(
                location=address,
                radius_km=radius,
                deal_type=cian_deal_type,
                rooms=tuple(cian_rooms)
            )
            
            if df is not None and not df.empty:
                st.success(f"Найдено {len(df)} предложений")
                
                # Расчет средней цены
                avg_price = calculate_average_price(df)
                if avg_price:
                    st.metric("Средняя цена за кв.м", f"{avg_price:,.0f} ₽".replace(",", " "))
                
                # Отображение данных
                st.dataframe(df[['price', 'area', 'rooms', 'address', 'url']].head(20))
                
                # Визуализация
                st.subheader("📈 Распределение цен")
                fig = go.Figure()
                fig.add_trace(go.Histogram(
                    x=df['price_per_m2'],
                    nbinsx=50,
                    marker_color='#636EFA'
                ))
                fig.update_layout(
                    title="Гистограмма цен за кв.м",
                    xaxis_title="Цена за кв.м (₽)",
                    yaxis_title="Количество предложений"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Не удалось найти данные. Попробуйте изменить параметры поиска.")

if __name__ == "__main__":
    main()
