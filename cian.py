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
    """Безопасный парсинг данных
