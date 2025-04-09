import streamlit as st
import pandas as pd
from cianparser import CianParser
from geopy.geocoders import Nominatim
import plotly.express as px
from geopy.extra.rate_limiter import RateLimiter
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

# Кэшируем геокодер
@st.cache_resource
def init_geocoder():
    geolocator = Nominatim(user_agent="real_estate_analyzer_123")
    return RateLimiter(geolocator.geocode, min_delay_seconds=1)

def get_address_suggestions(query):
    """Получение подсказок адресов с обработкой ошибок"""
    try:
        if not query or len(query.strip()) < 3:
            return []
            
        geocode = init_geocoder()
        locations = geocode(query, exactly_one=False, limit=5)
        return [location.address for location in locations] if locations else []
    
    except (GeocoderTimedOut, GeocoderUnavailable):
        st.error("Сервис геокодирования временно недоступен")
        return []
    except Exception as e:
        st.error(f"Ошибка получения подсказок: {str(e)}")
        return []

def validate_address(address):
    """Проверка существования адреса"""
    try:
        if not address or len(address.strip()) < 3:
            return False, "Адрес слишком короткий"
            
        geocode = init_geocoder()
        location = geocode(address, exactly_one=True)
        return bool(location), "Адрес не найден" if not location else ""
        
    except Exception as e:
        return False, f"Ошибка проверки адреса: {str(e)}"

def main():
    st.set_page_config(page_title="Анализ цен на недвижимость", layout="wide")
    st.title("🏠 Анализ вторички и новостроек")
    
    # Инициализация состояния
    if 'address_suggestions' not in st.session_state:
        st.session_state.address_suggestions = []
    if 'selected_address' not in st.session_state:
        st.session_state.selected_address = ""
    if 'last_valid_address' not in st.session_state:
        st.session_state.last_valid_address = ""

    # Поле ввода с автодополнением
    address_input = st.text_input(
        "Введите адрес (например, 'Алексея Козина'):",
        value=st.session_state.selected_address,
        key="address_input",
        placeholder="Начните вводить адрес..."
    )

    # Обновление подсказок при изменении ввода
    if (address_input != st.session_state.get('last_query', '') and 
        len(address_input) >= 3):
        
        st.session_state.last_query = address_input
        with st.spinner("Ищем варианты адресов..."):
            suggestions = get_address_suggestions(address_input)
            st.session_state.address_suggestions = suggestions
            st.session_state.show_suggestions = bool(suggestions)

    # Отображение подсказок в выпадающем списке
    if (st.session_state.get('show_suggestions', False) and 
        st.session_state.address_suggestions):
        
        selected_suggestion = st.selectbox(
            "Выберите вариант адреса:",
            options=st.session_state.address_suggestions,
            index=None,
            key="address_suggestions",
            placeholder="Выберите из списка..."
        )
        
        if selected_suggestion:
            st.session_state.selected_address = selected_suggestion
            st.session_state.last_valid_address = selected_suggestion
            st.session_state.show_suggestions = False
            st.rerun()

    # Валидация адреса при отправке формы
    if st.button("Найти недвижимость", type="primary"):
        current_address = st.session_state.selected_address
        
        # Проверка на пустую строку
        if not current_address or not current_address.strip():
            st.error("Пожалуйста, введите адрес для поиска")
            return
            
        # Проверка существования адреса
        is_valid, validation_msg = validate_address(current_address)
        
        if not is_valid:
            st.error(validation_msg)
            return
            
        st.session_state.last_valid_address = current_address
        st.success(f"Адрес подтвержден: {current_address}")
        
        # Здесь будет основной код анализа недвижимости
        # ...

if __name__ == "__main__":
    main()
