import streamlit as st
import pandas as pd
from cianparser import CianParser
from geopy.geocoders import Nominatim
import plotly.express as px
from geopy.extra.rate_limiter import RateLimiter

# Кэшируем геокодер для подсказок адресов
@st.cache_resource
def get_geocoder():
    geolocator = Nominatim(user_agent="real_estate_autocomplete")
    return RateLimiter(geolocator.geocode, min_delay_seconds=1)

def get_address_suggestions(query):
    """Получение подсказок адресов"""
    try:
        geolocator = get_geocoder()
        locations = geolocator.geocode(query, exactly_one=False, limit=5)
        return [location.address for location in locations] if locations else []
    except Exception as e:
        st.error(f"Ошибка получения подсказок: {str(e)}")
        return []

def main():
    st.set_page_config(page_title="Анализ цен с автодополнением", layout="wide")
    st.title("🏠 Поиск недвижимости с автодополнением адресов")
    
    # Поле ввода с автодополнением
    address_query = st.text_input("Начните вводить адрес...", "Казань, Касаткина 3")
    
    # Получаем подсказки при изменении текста
    if address_query and len(address_query) > 3:
        suggestions = get_address_suggestions(address_query)
        
        # Создаём кнопки для подсказок
        if suggestions:
            st.write("🔍 Возможно вы ищете:")
            cols = st.columns(3)
            
            for idx, suggestion in enumerate(suggestions[:3]):
                with cols[idx % 3]:
                    if st.button(suggestion, key=f"sugg_{idx}"):
                        address_query = suggestion  # Обновляем поле ввода
    
    # Остальной код анализа...
    if st.button("Анализировать", disabled=not address_query):
        # Здесь будет ваш код анализа из предыдущего примера
        st.success(f"Анализ для адреса: {address_query}")
        # Дальнейшая обработка...

if __name__ == "__main__":
    main()
