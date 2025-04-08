import streamlit as st
import pandas as pd
from cianparser import CianParser
from geopy.geocoders import Nominatim
import plotly.express as px
from geopy.extra.rate_limiter import RateLimiter

# Кэшируем геокодер
@st.cache_resource
def init_geocoder():
    geolocator = Nominatim(user_agent="real_estate_autocomplete_123")
    return RateLimiter(geolocator.geocode, min_delay_seconds=1)

def get_address_suggestions(query):
    """Получение подсказок адресов"""
    try:
        geocode = init_geocoder()
        locations = geocode(query, exactly_one=False, limit=5)
        return [location.address for location in locations] if locations else []
    except Exception as e:
        st.error(f"Ошибка получения подсказок: {str(e)}")
        return []

def parse_cian_data(location, radius, deal_type, rooms):
    """Парсинг данных с ЦИАН с обработкой ошибок"""
    try:
        parser = CianParser(location=location)
        
        # Правильные значения deal_type согласно документации cianparser
        cian_deal_type = "sale" if deal_type == "Вторичка" else "rent_long"
        
        data = parser.get_flats(
            deal_type=cian_deal_type,
            rooms=rooms,
            with_saving_csv=False,
            additional_settings={"radius": radius}
        )
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Ошибка парсинга: {str(e)}")
        return pd.DataFrame()

def main():
    st.set_page_config(page_title="Анализ цен с ЦИАН", layout="wide")
    st.title("🏠 Анализ цен на недвижимость")
    
    # Инициализация состояния
    if 'address_suggestions' not in st.session_state:
        st.session_state.address_suggestions = []
    if 'selected_address' not in st.session_state:
        st.session_state.selected_address = "Казань, Касаткина 3"

    # Поле ввода с автодополнением
    def update_suggestions():
        query = st.session_state.address_input
        if len(query) > 3:
            with st.spinner("Поиск адресов..."):
                st.session_state.address_suggestions = get_address_suggestions(query)

    address_input = st.text_input(
        "Введите адрес:",
        st.session_state.selected_address,
        key="address_input",
        on_change=update_suggestions
    )

    # Выпадающий список подсказок
    if st.session_state.address_suggestions:
        selected_suggestion = st.selectbox(
            "Выберите адрес из подсказок:",
            st.session_state.address_suggestions,
            index=None,
            placeholder="Начните вводить адрес..."
        )
        
        if selected_suggestion:
            st.session_state.selected_address = selected_suggestion

    # Дополнительные параметры поиска
    with st.expander("Дополнительные параметры", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            radius = st.slider("Радиус поиска (км)", 0.5, 5.0, 1.0, 0.1)
            deal_type = st.radio("Тип недвижимости", ["Вторичка", "Аренда"], index=0)
        with col2:
            rooms = st.multiselect(
                "Количество комнат", 
                ["Студия", "1", "2", "3", "4+"], 
                default=["1", "2", "3"]
            )

    if st.button("Анализировать", type="primary"):
        if not st.session_state.selected_address:
            st.warning("Пожалуйста, введите адрес")
            return
            
        with st.spinner("Собираем данные..."):
            # Преобразуем комнаты в формат для парсера
            room_mapping = {"Студия": 0, "1": 1, "2": 2, "3": 3, "4+": 4}
            cian_rooms = [room_mapping[r] for r in rooms]
            
            # Получаем данные
            df = parse_cian_data(
                location=st.session_state.selected_address,
                radius=radius,
                deal_type=deal_type,
                rooms=tuple(cian_rooms)
            )
            
            if not df.empty:
                st.success(f"Найдено {len(df)} предложений")
                
                # Отображаем результаты
                st.dataframe(df[['address', 'price', 'area', 'rooms']].head(20))
                
                # Визуализация
                st.plotly_chart(
                    px.histogram(df, x='price', title='Распределение цен'),
                    use_container_width=True
                )
            else:
                st.warning("Не найдено предложений по заданным критериям")

if __name__ == "__main__":
    main()
