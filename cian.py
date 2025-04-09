import streamlit as st
import pandas as pd
from cianparser import CianParser
from geopy.geocoders import Nominatim
import plotly.express as px
from geopy.extra.rate_limiter import RateLimiter
from functools import lru_cache
import re

# Инициализация состояния
if 'valid_address' not in st.session_state:
    st.session_state.valid_address = ""
if 'search_results' not in st.session_state:
    st.session_state.search_results = None

# Кэшированный геокодер
@st.cache_resource
def get_geocoder():
    return Nominatim(user_agent="reliable_estate_app", timeout=7)

# Кэшированные подсказки адресов
@lru_cache(maxsize=50)
def get_cached_suggestions(query: str):
    try:
        if len(query) < 3:
            return []
        
        geocode = get_geocoder().geocode
        locations = geocode(query, exactly_one=False, limit=3)
        return [loc.address.split(',')[0] for loc in locations][:3] if locations else []
    except Exception:
        return []

def safe_parse_data(df):
    """Безопасная обработка данных с проверкой столбцов"""
    required_columns = {'price', 'area', 'address', 'rooms'}
    
    if not isinstance(df, pd.DataFrame) or not required_columns.issubset(df.columns):
        return None
    
    try:
        # Очистка и преобразование данных
        df = df.copy()
        df['price_clean'] = df['price'].apply(lambda x: re.sub(r'[^\d]', '', str(x)))
        df['area_clean'] = df['area'].apply(lambda x: re.sub(r'[^\d.]', '', str(x)))
        
        df['price_num'] = pd.to_numeric(df['price_clean'], errors='coerce')
        df['area_num'] = pd.to_numeric(df['area_clean'], errors='coerce')
        
        df = df.dropna(subset=['price_num', 'area_num'])
        df['price_per_m2'] = df['price_num'] / df['area_num']
        
        return df[['address', 'price_num', 'area_num', 'rooms', 'price_per_m2']]\
               .rename(columns={
                   'price_num': 'price',
                   'area_num': 'area'
               })
    except Exception:
        return None

def get_real_estate_data(address, radius, offer_type, rooms):
    """Безопасный парсинг данных с обработкой ошибок"""
    try:
        parser = CianParser(location=address)
        
        params = {
            "rooms": rooms,
            "with_saving_csv": False,
            "additional_settings": {"radius": radius, "page": 1}
        }
        
        if offer_type == "Новостройка":
            data = parser.get_newbuildings(**params)
        else:
            data = parser.get_flats(deal_type="sale", **params)
        
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

# Интерфейс
st.set_page_config(page_title="Надёжный поиск недвижимости", layout="wide")
st.title("🏡 Надёжный поиск недвижимости")

# Поисковая форма
with st.form("search_form"):
    address = st.text_input("Адрес (улица и дом):", help="Начните вводить адрес")
    
    # Подсказки адресов
    if address and len(address) >= 3:
        suggestions = get_cached_suggestions(address)
        if suggestions:
            selected_address = st.selectbox("Выберите адрес:", [""] + suggestions)
            if selected_address:
                address = selected_address
    
    cols = st.columns(3)
    with cols[0]:
        radius = st.slider("Радиус поиска (км)", 0.5, 3.0, 1.0, 0.1)
    with cols[1]:
        offer_type = st.radio("Тип недвижимости:", ["Вторичка", "Новостройка"])
    with cols[2]:
        rooms = st.multiselect("Комнаты:", ["Студия", "1", "2", "3", "4+"], default=["1", "2"])
    
    if st.form_submit_button("Найти", type="primary"):
        if not address:
            st.warning("Пожалуйста, введите адрес")
            st.stop()
        
        with st.spinner("Ищем предложения..."):
            raw_data = get_real_estate_data(address, radius, offer_type, tuple(rooms))
            clean_data = safe_parse_data(raw_data)
            
            if clean_data is None or clean_data.empty:
                st.error("Не удалось получить данные. Попробуйте другие параметры.")
                st.session_state.search_results = None
            else:
                st.session_state.search_results = clean_data
                st.session_state.valid_address = address
                st.success(f"Найдено {len(clean_data)} предложений")

# Отображение результатов
if st.session_state.search_results is not None:
    df = st.session_state.search_results
    
    st.subheader(f"Результаты для: {st.session_state.valid_address}")
    
    # Основные метрики
    cols = st.columns(3)
    avg_price = df['price_per_m2'].mean()
    cols[0].metric("Средняя цена", f"{avg_price:,.0f} ₽/м²")
    cols[1].metric("Минимальная цена", f"{df['price_per_m2'].min():,.0f} ₽/м²")
    cols[2].metric("Максимальная цена", f"{df['price_per_m2'].max():,.0f} ₽/м²")
    
    # Таблица данных
    with st.expander("📋 Все предложения", expanded=True):
        st.dataframe(
            df.sort_values('price_per_m2'),
            column_config={
                "price": st.column_config.NumberColumn("Цена", format="%.0f ₽"),
                "area": st.column_config.NumberColumn("Площадь", format="%.1f м²"),
                "price_per_m2": st.column_config.NumberColumn("Цена за м²", format="%.0f ₽")
            },
            height=400,
            use_container_width=True
        )
    
    # Графики
    tab1, tab2 = st.tabs(["📈 Распределение цен", "📊 Цена vs Площадь"])
    
    with tab1:
        fig1 = px.histogram(
            df,
            x='price_per_m2',
            nbins=20,
            title='Распределение цен за квадратный метр'
        )
        st.plotly_chart(fig1, use_container_width=True)
    
    with tab2:
        fig2 = px.scatter(
            df,
            x='area',
            y='price',
            color='rooms',
            hover_name='address',
            labels={'area': 'Площадь (м²)', 'price': 'Цена (₽)'}
        )
        st.plotly_chart(fig2, use_container_width=True)
