import streamlit as st
import pandas as pd
from cianparser import CianParser
from geopy.geocoders import Nominatim
import plotly.express as px
import re
import time
from functools import lru_cache

# Константы
MAX_RETRIES = 3
TIMEOUT = 10
CIAN_PARSER_CONFIG = {
    "room_mapping": {
        "Студия": "studio",
        "1": 1,
        "2": 2,
        "3": 3,
        "4+": 4
    }
}

# Инициализация состояния
def init_session_state():
    if 'search_data' not in st.session_state:
        st.session_state.search_data = None
    if 'last_query' not in st.session_state:
        st.session_state.last_query = {}
    if 'geo_cache' not in st.session_state:
        st.session_state.geo_cache = {}

# Кэшированный геокодер
@st.cache_resource
def get_geocoder():
    return Nominatim(user_agent="reliable_estate_search", timeout=TIMEOUT)

# Преобразование параметров комнат для ЦИАН
def prepare_rooms_param(selected_rooms):
    if not selected_rooms:
        return "all"
    
    cian_rooms = []
    for room in selected_rooms:
        mapped_room = CIAN_PARSER_CONFIG["room_mapping"].get(room)
        if mapped_room is not None:
            cian_rooms.append(mapped_room)
    
    return tuple(cian_rooms) if cian_rooms else "all"

# Очистка и преобразование данных
def clean_data(raw_data):
    if not raw_data:
        return None
    
    df = pd.DataFrame(raw_data)
    
    # Проверка обязательных полей
    required_cols = {'price', 'area', 'address', 'rooms'}
    if not required_cols.issubset(df.columns):
        raise ValueError("Отсутствуют обязательные столбцы в данных")
    
    # Очистка числовых полей
    numeric_cols = {
        'price': r'[^\d]',
        'area': r'[^\d.]'
    }
    
    for col, pattern in numeric_cols.items():
        clean_col = f"{col}_clean"
        df[clean_col] = df[col].apply(
            lambda x: re.sub(pattern, '', str(x)) if pd.notnull(x) else ''
        )
        df[col] = pd.to_numeric(df[clean_col], errors='coerce')
    
    df = df.dropna(subset=['price', 'area'])
    
    if df.empty:
        return None
    
    df['price_per_m2'] = df['price'] / df['area']
    return df[['address', 'price', 'area', 'rooms', 'price_per_m2']]

# Парсер с повторными попытками и обработкой ошибок
def safe_cian_parse(address, radius, offer_type, rooms, retry_count=MAX_RETRIES):
    cian_rooms = prepare_rooms_param(rooms)
    
    for attempt in range(retry_count):
        try:
            parser = CianParser(location=address)
            params = {
                "rooms": cian_rooms,
                "with_saving_csv": False,
                "additional_settings": {
                    "radius": radius,
                    "page": 1
                }
            }
            
            start_time = time.time()
            
            if offer_type == "Новостройка":
                data = parser.get_newbuildings(**params)
            else:
                data = parser.get_flats(deal_type="sale", **params)
            
            cleaned_data = clean_data(data)
            if cleaned_data is not None:
                return {
                    'data': cleaned_data,
                    'time': time.time() - start_time
                }
            
        except Exception as e:
            if attempt == retry_count - 1:
                st.error(f"Ошибка после {retry_count} попыток: {str(e)}")
                return None
            time.sleep(1)
    
    return None

# Получение подсказок по адресу с кэшированием
def get_address_suggestions(query):
    if not query or len(query) < 3:
        return []
    
    cache_key = hash(query)
    if cache_key in st.session_state.geo_cache:
        return st.session_state.geo_cache[cache_key]
    
    try:
        geolocator = get_geocoder()
        locations = geolocator.geocode(query, exactly_one=False, limit=3) or []
        suggestions = [loc.address.split(',')[0] for loc in locations]
        st.session_state.geo_cache[cache_key] = suggestions
        return suggestions
    except Exception:
        return []

# Отображение результатов
def display_results(data):
    st.subheader(f"Результаты поиска ({len(data)} предложений)")
    
    # Основные метрики
    m1, m2, m3 = st.columns(3)
    m1.metric("Найдено предложений", len(data))
    m2.metric("Средняя цена", f"{data['price_per_m2'].mean():,.0f} ₽/м²")
    m3.metric("Диапазон цен", 
             f"{data['price_per_m2'].min():,.0f}-{data['price_per_m2'].max():,.0f} ₽/м²")
    
    # Таблица и графики
    tab1, tab2 = st.tabs(["Таблица данных", "Визуализация"])
    
    with tab1:
        st.dataframe(
            data.sort_values('price_per_m2'),
            column_config={
                "price": st.column_config.NumberColumn("Цена", format="%.0f ₽"),
                "area": st.column_config.NumberColumn("Площадь", format="%.1f м²"),
                "price_per_m2": st.column_config.NumberColumn("Цена/м²", format="%.0f ₽")
            },
            height=400,
            use_container_width=True
        )
    
    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            fig1 = px.histogram(
                data,
                x='price_per_m2',
                title='Распределение цен',
                labels={'price_per_m2': 'Цена за м² (₽)'}
            )
            st.plotly_chart(fig1, use_container_width=True)
        
        with c2:
            fig2 = px.scatter(
                data,
                x='area',
                y='price',
                color='rooms',
                hover_name='address',
                title='Цена vs Площадь',
                labels={'area': 'Площадь (м²)', 'price': 'Цена (₽)'}
            )
            st.plotly_chart(fig2, use_container_width=True)

# Основной интерфейс
def main():
    init_session_state()
    st.set_page_config(page_title="Устойчивый поиск недвижимости", layout="wide")
    st.title("🔍 Устойчивый поиск недвижимости")
    
    with st.form("main_form"):
        address = st.text_input(
            "Введите точный адрес (например, 'Москва, Ленинский проспект 52'):",
            help="Рекомендуется указывать город для более точного поиска"
        )
        
        # Подсказки адресов
        suggestions = get_address_suggestions(address)
        if suggestions:
            selected = st.selectbox(
                "Выберите адрес из подсказок:",
                suggestions,
                index=None
            )
            if selected:
                address = selected
        
        cols = st.columns([1,1,2])
        with cols[0]:
            radius = st.slider("Радиус поиска (км)", 0.3, 2.0, 0.8, 0.1)
        with cols[1]:
            offer_type = st.radio("Тип недвижимости", ["Вторичка", "Новостройка"])
        with cols[2]:
            rooms = st.multiselect(
                "Количество комнат",
                ["Студия", "1", "2", "3", "4+"],
                default=["1", "2"]
            )
        
        if st.form_submit_button("Найти", type="primary"):
            if not address or len(address.strip()) < 3:
                st.warning("Введите корректный адрес (минимум 3 символа)")
                st.stop()
            
            current_query = {
                'address': address,
                'radius': radius,
                'offer_type': offer_type,
                'rooms': tuple(rooms)
            }
            
            if current_query == st.session_state.last_query and st.session_state.search_data is not None:
                st.info("Используются предыдущие результаты поиска")
            else:
                with st.spinner(f"Ищем {offer_type.lower()} в районе {address}..."):
                    result = safe_cian_parse(
                        address=address,
                        radius=radius,
                        offer_type=offer_type,
                        rooms=rooms
                    )
                    
                    if result:
                        st.session_state.search_data = result['data']
                        st.session_state.last_query = current_query
                        st.success(f"Данные успешно получены за {result['time']:.1f} сек")
                    else:
                        st.error("""
                        Не удалось получить данные. Возможные причины:
                        1. Нет предложений по заданным параметрам
                        2. Проблемы с соединением
                        3. Ограничения ЦИАН
                        Попробуйте изменить параметры поиска.
                        """)
    
    if st.session_state.search_data is not None:
        display_results(st.session_state.search_data)
    
    # Боковая панель с советами
    st.sidebar.markdown("""
    ### Советы для лучших результатов:
    1. Всегда указывайте город в адресе
    2. Начинайте с небольшого радиуса (0.5-1 км)
    3. Для новостроек уточняйте название ЖК
    4. Выбирайте не более 2-3 вариантов комнат
    5. При ошибках попробуйте перезагрузить страницу
    """)

if __name__ == "__main__":
    main()
