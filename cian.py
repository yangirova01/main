import streamlit as st
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# Кэшируем геокодер
@st.cache_resource
def init_geocoder():
    geolocator = Nominatim(user_agent="real_estate_app_autocomplete")
    # Правильное применение RateLimiter
    return RateLimiter(geolocator.geocode, min_delay_seconds=1)

def get_address_suggestions(query):
    """Получение подсказок адресов с обработкой ошибок"""
    try:
        geocode = init_geocoder()  # Получаем функцию с rate limiting
        locations = geocode(query, exactly_one=False, limit=5)
        return [location.address for location in locations] if locations else []
    except Exception as e:
        st.error(f"Ошибка получения подсказок: {str(e)}")
        return []

def main():
    st.set_page_config(page_title="Поиск с автодополнением", layout="wide")
    st.title("🔍 Поиск недвижимости с подсказками адресов")

    # Создаем состояние для хранения выбранного адреса
    if 'selected_address' not in st.session_state:
        st.session_state.selected_address = "Казань, Касаткина 3"

    # Поле ввода с обработкой изменений
    address_query = st.text_input(
        "Введите адрес:", 
        st.session_state.selected_address,
        key="address_input"
    )

    # Получаем подсказки только если изменился запрос
    if address_query != st.session_state.get('last_query', ''):
        st.session_state.last_query = address_query
        if len(address_query) > 3:  # Только для запросов от 4 символов
            with st.spinner("Ищем подходящие адреса..."):
                suggestions = get_address_suggestions(address_query)
                st.session_state.suggestions = suggestions

    # Отображаем подсказки если они есть
    if 'suggestions' in st.session_state and st.session_state.suggestions:
        st.write("Возможные варианты:")
        
        # Создаем колонки для кнопок
        cols = st.columns(3)
        
        for idx, suggestion in enumerate(st.session_state.suggestions[:6]):
            with cols[idx % 3]:
                if st.button(
                    suggestion, 
                    key=f"sugg_{idx}",
                    help="Нажмите чтобы выбрать этот адрес"
                ):
                    st.session_state.selected_address = suggestion
                    st.rerun()  # Обновляем интерфейс

    # Кнопка анализа с защитой от пустого ввода
    if st.button("Анализировать", disabled=not st.session_state.selected_address):
        st.success(f"Начинаем анализ для адреса: {st.session_state.selected_address}")
        # Здесь будет ваш основной код анализа

if __name__ == "__main__":
    main()
