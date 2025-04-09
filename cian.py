import streamlit as st
import pandas as pd
from cianparser import CianParser
from geopy.geocoders import Nominatim
import plotly.express as px
import re
import time
from functools import lru_cache

# Настройки
MAX_RETRIES = 3  # Количество попыток при ошибках
TIMEOUT = 10     # Таймаут запросов в секундах

# Инициализация состояния
if 'search_data' not in st.session_state:
    st.session_state.search_data = None
if 'last_query' not in st.session_state:
    st.session_state.last_query = {}

# Кэшированный геокодер
@st.cache_resource
def get_geocoder():
    return Nominatim(user_agent="reliable_estate_search", timeout=TIMEOUT)

# Улучшенный парсер с повторными попытками
def safe_cian_parse(address, radius, offer_type, rooms, retry_count=MAX_RETRIES):
    for attempt in range(retry_count):
        try:
            parser = CianParser(location=address)
            
            params = {
                "rooms": rooms,
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
            
            if data:
                df = pd.DataFrame(data)
                
                # Проверяем наличие обязательных полей
                required_cols = {'price', 'area', 'address', 'rooms'}
                if not required_cols.issubset(df.columns):
                    raise ValueError("Отсутствуют обязательные столбцы в данных")
                
                # Очистка данных
                df['price_clean'] = df['price'].apply(
                    lambda x: re.sub(r'[^\d]', '', str(x)) if pd.notnull(x) else ''
                )
                df['area_clean'] = df['area'].apply(
                    lambda x: re.sub(r'[^\d.]', '', str(x)) if pd.notnull(x) else ''
                )
                
                df['price_num'] = pd.to_numeric(df['price_clean'], errors='coerce')
                df['area_num'] = pd.to_numeric(df['area_clean'], errors='coerce')
                
                df = df.dropna(subset=['price_num', 'area_num'])
                
                if df.empty:
                    continue  # Пробуем еще раз если нет данных
                
                df['price_per_m2'] = df['price_num'] / df['area_num']
                
                return {
                    'data': df[['address', 'price_num', 'area_num', 'rooms', 'price_per_m2']]
                            .rename(columns={'price_num': 'price', 'area_num': 'area'}),
                    'time': time.time() - start_time
                }
            
        except Exception as e:
            if attempt == retry_count - 1:
                st.error(f"Ошибка после {retry_count} попыток: {str(e)}")
            time.sleep(1)  # Задержка между попытками
    
    return None

# Интерфейс
st.set_page_config(page_title="Устойчивый поиск недвижимости", layout="wide")
st.title("🔍 Устойчивый поиск недвижимости")

# Поисковая форма
with st.form("main_form"):
    address = st.text_input(
        "Введите точный адрес (например, 'Ленинский проспект 52'):",
        help="Начните вводить адрес, появятся подсказки"
    )
    
    # Подсказки адресов
    if address and len(address) > 2:
        try:
            locations = get_geocoder().geocode(address, exactly_one=False, limit=3)
            if locations:
                selected = st.selectbox(
                    "Выберите адрес из подсказок:",
                    [loc.address.split(',')[0] for loc in locations],
                    index=None
                )
                if selected:
                    address = selected
        except Exception:
            pass
    
    cols = st.columns([1,1,2])
    with cols[0]:
        radius = st.slider("Радиус (км)", 0.3, 2.0, 0.8, 0.1)
    with cols[1]:
        offer_type = st.radio("Тип", ["Вторичка", "Новостройка"])
    with cols[2]:
        rooms = st.multiselect(
            "Комнаты",
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
        
        # Проверяем, не повторяется ли запрос
        if current_query == st.session_state.last_query:
            st.info("Используются предыдущие результаты поиска")
        else:
            with st.spinner(f"Ищем {offer_type.lower()}..."):
                result = safe_cian_parse(
                    address=address,
                    radius=radius,
                    offer_type=offer_type,
                    rooms=tuple(rooms)
                )
                
                if result:
                    st.session_state.search_data = result['data']
                    st.session_state.last_query = current_query
                    st.success(f"Найдено {len(result['data'])} предложений за {result['time']:.1f} сек")
                else:
                    st.error("""
                    Не удалось получить данные. Возможные причины:
                    1. Нет предложений по заданным параметрам
                    2. Проблемы с соединением
                    3. Ограничения ЦИАН
                    Попробуйте изменить параметры поиска.
                    """)

# Отображение результатов
if st.session_state.search_data is not None:
    df = st.session_state.search_data
    
    st.subheader(f"Результаты поиска")
    
    # Основные метрики
    m1, m2, m3 = st.columns(3)
    m1.metric("Найдено предложений", len(df))
    m2.metric("Средняя цена", f"{df['price_per_m2'].mean():,.0f} ₽/м²")
    m3.metric("Диапазон цен", 
             f"{df['price_per_m2'].min():,.0f}-{df['price_per_m2'].max():,.0f} ₽/м²")
    
    # Таблица и графики
    tab1, tab2 = st.tabs(["Таблица данных", "Визуализация"])
    
    with tab1:
        st.dataframe(
            df.sort_values('price_per_m2'),
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
                df,
                x='price_per_m2',
                title='Распределение цен',
                labels={'price_per_m2': 'Цена за м² (₽)'}
            )
            st.plotly_chart(fig1, use_container_width=True)
        
        with c2:
            fig2 = px.scatter(
                df,
                x='area',
                y='price',
                color='rooms',
                hover_name='address',
                title='Цена vs Площадь',
                labels={'area': 'Площадь (м²)', 'price': 'Цена (₽)'}
            )
            st.plotly_chart(fig2, use_container_width=True)

# Советы по поиску
st.sidebar.markdown("""
### Советы для лучших результатов:
1. Вводите полный адрес (улица + дом)
2. Начинайте с небольшого радиуса (0.5-1 км)
3. Выбирайте 1-2 типа комнат
4. Для новостроек уточняйте название ЖК
""")
