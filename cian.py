import streamlit as st
import pandas as pd
from cianparser import CianParser
from geopy.geocoders import Nominatim
import plotly.express as px

def get_coordinates(address):
    """Получение координат по адресу с использованием геокодера"""
    try:
        geolocator = Nominatim(user_agent="real_estate_app")
        location = geolocator.geocode(address)
        if location:
            return (location.latitude, location.longitude)
        return None
    except Exception as e:
        st.error(f"Ошибка геокодинга: {str(e)}")
        return None

def parse_real_estate(address, radius, deal_type="sale", rooms=(1, 2, 3)):
    """Парсинг данных о недвижимости с использованием html5lib"""
    try:
        parser = CianParser(location=address)
        data = parser.get_flats(
            deal_type=deal_type,
            rooms=rooms,
            with_saving_csv=False,
            additional_settings={"radius": radius}
        )
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Ошибка парсинга: {str(e)}")
        return pd.DataFrame()

def clean_price_data(df):
    """Очистка и обработка данных о ценах"""
    if df.empty:
        return df
    
    # Преобразование цен и площадей
    df['price'] = df['price'].str.replace(r'[^\d]', '', regex=True).astype(float)
    df['area'] = df['area'].str.replace(r'[^\d.]', '', regex=True).astype(float)
    
    # Расчет цены за кв.м
    df['price_per_m2'] = df['price'] / df['area']
    
    # Фильтрация выбросов
    return df[(df['price_per_m2'] > 10000) & (df['price_per_m2'] < 1000000)]

def main():
    st.set_page_config(page_title="Анализ цен на недвижимость", layout="wide")
    st.title("📊 Анализ цен на недвижимость")
    
    # Ввод параметров
    with st.expander("🔍 Параметры поиска", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            address = st.text_input("Адрес участка", "Казань, Касаткина 3")
            radius = st.slider("Радиус поиска (км)", 0.5, 5.0, 1.0, 0.1)
        with col2:
            deal_type = st.radio("Тип недвижимости", ["Вторичка", "Новостройка"], index=0)
            rooms = st.multiselect(
                "Количество комнат", 
                ["Студия", "1", "2", "3", "4+"], 
                default=["1", "2", "3"]
            )
    
    if st.button("Собрать данные", type="primary"):
        with st.spinner("Поиск предложений..."):
            # Преобразование параметров
            cian_deal_type = "secondary" if deal_type == "Вторичка" else "newbuilding"
            cian_rooms = []
            for r in rooms:
                if r == "Студия": cian_rooms.append(0)
                elif r == "4+": cian_rooms.append(4)
                else: cian_rooms.append(int(r))
            
            # Получение координат
            coords = get_coordinates(address)
            if coords:
                st.success(f"Координаты участка: {coords[0]:.4f}, {coords[1]:.4f}")
            
            # Парсинг данных
            df = parse_real_estate(
                address=address,
                radius=radius,
                deal_type=cian_deal_type,
                rooms=tuple(cian_rooms)
            )
            
            if not df.empty:
                # Очистка данных
                df = clean_price_data(df)
                avg_price = df['price_per_m2'].mean()
                
                # Отображение результатов
                st.success(f"Найдено {len(df)} предложений")
                st.metric("Средняя цена за кв.м", f"{avg_price:,.0f} ₽".replace(",", " "))
                
                # Визуализация
                tab1, tab2 = st.tabs(["Данные", "Графики"])
                
                with tab1:
                    st.dataframe(
                        df[['price', 'area', 'rooms', 'price_per_m2', 'address', 'url']]
                        .sort_values('price_per_m2')
                        .head(50),
                        height=500,
                        column_config={
                            "price": st.column_config.NumberColumn("Цена", format="%.0f ₽"),
                            "area": st.column_config.NumberColumn("Площадь", format="%.1f м²"),
                            "price_per_m2": st.column_config.NumberColumn("Цена за м²", format="%.0f ₽"),
                            "url": st.column_config.LinkColumn("Ссылка")
                        }
                    )
                
                with tab2:
                    fig = px.histogram(
                        df,
                        x='price_per_m2',
                        nbins=30,
                        title='Распределение цен за кв.м',
                        labels={'price_per_m2': 'Цена за кв.м (₽)'}
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    fig2 = px.scatter(
                        df,
                        x='area',
                        y='price',
                        color='rooms',
                        title='Соотношение площади и цены',
                        labels={'area': 'Площадь (м²)', 'price': 'Цена (₽)'}
                    )
                    st.plotly_chart(fig2, use_container_width=True)
            else:
                st.warning("Не найдено предложений по заданным критериям")

if __name__ == "__main__":
    main()
