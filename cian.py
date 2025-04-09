import streamlit as st
import pandas as pd
from cianparser import CianParser
from geopy.geocoders import Nominatim
import plotly.express as px
from geopy.extra.rate_limiter import RateLimiter
from functools import lru_cache
import time

# Настройки по умолчанию для быстрого поиска
DEFAULT_RADIUS = 0.5  # км
MAX_RADIUS = 3.0      # км
INITIAL_ROOMS = ["1", "2"]  # Самые популярные варианты

# Инициализация состояния
if 'valid_address' not in st.session_state:
    st.session_state.valid_address = ""
if 'fast_search' not in st.session_state:
    st.session_state.fast_search = True

# Кэшированный геокодер с ускоренными запросами
@st.cache_resource
def get_geocoder():
    geolocator = Nominatim(user_agent="fast_estate_app", timeout=5)
    return RateLimiter(geolocator.geocode, min_delay_seconds=0.5)

# Кэшируем подсказки адресов
@lru_cache(maxsize=50)
def get_address_suggestions(query: str):
    """Ускоренное получение подсказок с кэшированием"""
    try:
        if len(query) < 3:
            return []
        
        geocode = get_geocoder()
        locations = geocode(query, exactly_one=False, limit=3)  # Всего 3 подсказки
        return [loc.address.split(',')[0] for loc in locations][:3] if locations else []
    except Exception:
        return []

def quick_parse(address, radius, offer_type, rooms):
    """Быстрый парсинг с ограниченными параметрами"""
    try:
        parser = CianParser(location=address)
        
        params = {
            "rooms": rooms,
            "with_saving_csv": False,
            "additional_settings": {
                "radius": radius,
                "page": 1  # Только первая страница
            }
        }
        
        start_time = time.time()
        data = parser.get_newbuildings(**params) if offer_type == "Новостройка" \
              else parser.get_flats(deal_type="sale", **params)
        
        parse_time = time.time() - start_time
        st.session_state.last_parse_time = parse_time
        
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Ошибка быстрого поиска: {str(e)}")
        return pd.DataFrame()

# Интерфейс
st.set_page_config(page_title="Быстрый поиск недвижимости", layout="wide")
st.title("⚡ Быстрый поиск недвижимости")

# Блок быстрого поиска
with st.expander("🔍 Быстрый поиск", expanded=True):
    address = st.text_input(
        "Улица и дом:", 
        placeholder="Начните вводить...",
        key="fast_address"
    )
    
    # Подсказки адресов
    if address and len(address) >= 3:
        with st.spinner("Ищем варианты..."):
            suggestions = get_address_suggestions(address)
            if suggestions:
                selected = st.selectbox("Выберите адрес:", [""] + suggestions)
                if selected:
                    address = selected

    cols = st.columns(3)
    with cols[0]:
        radius = st.slider("Радиус (км)", 0.5, MAX_RADIUS, DEFAULT_RADIUS, 0.1)
    with cols[1]:
        offer_type = st.radio("Тип:", ["Вторичка", "Новостройка"], horizontal=True)
    with cols[2]:
        rooms = st.multiselect("Комнаты", ["Студия", "1", "2", "3", "4+"], default=INITIAL_ROOMS)

# Кнопка быстрого поиска
if st.button("Найти быстро", type="primary"):
    if not address:
        st.warning("Введите адрес")
        st.stop()
    
    with st.spinner(f"Быстрый поиск {offer_type.lower()}..."):
        # Используем только первые 2 выбранных типа комнат для ускорения
        quick_rooms = rooms[:2]
        df = quick_parse(address, radius, offer_type, tuple(quick_rooms))
        
        if df.empty:
            st.warning("Ничего не найдено. Попробуйте изменить параметры.")
            st.stop()
            
        # Быстрый показ первых результатов
        st.success(f"Найдено {len(df)} предложений (поиск занял {st.session_state.last_parse_time:.1f} сек)")
        
        # Оптимизированное отображение
        tab1, tab2 = st.tabs(["📋 Список", "📊 Графики"])
        
        with tab1:
            st.dataframe(
                df[['address', 'price', 'area', 'rooms']].head(10),
                height=300,
                use_container_width=True
            )
            
        with tab2:
            try:
                df['price_num'] = pd.to_numeric(df['price'].str.replace(r'\D', '', regex=True))
                df['area_num'] = pd.to_numeric(df['area'].astype(str).str.extract(r'(\d+\.?\d*)')[0])
                df = df.dropna(subset=['price_num', 'area_num'])
                df['price_per_m2'] = df['price_num'] / df['area_num']
                
                fig = px.scatter(
                    df.head(30),  # Ограничиваем для скорости
                    x='area_num',
                    y='price_num',
                    hover_name='address',
                    title='Цена vs Площадь'
                )
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Ошибка построения графика: {str(e)}")

# Расширенный поиск (по требованию)
if st.checkbox("Расширенный поиск"):
    with st.expander("🔎 Детальные параметры"):
        full_radius = st.slider("Полный радиус (км)", 0.5, 5.0, 2.0)
        all_rooms = st.multiselect("Все комнаты", ["Студия", "1", "2", "3", "4+"], default=["1", "2", "3"])
        
        if st.button("Полный поиск"):
            with st.spinner("Полноценный поиск..."):
                full_df = quick_parse(address, full_radius, offer_type, tuple(all_rooms))
                
                if not full_df.empty:
                    st.success(f"Всего найдено: {len(full_df)}")
                    st.dataframe(full_df, height=500)
