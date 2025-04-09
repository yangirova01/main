import streamlit as st
import pandas as pd
from cianparser import CianParser
from geopy.geocoders import Nominatim
import plotly.express as px
from geopy.extra.rate_limiter import RateLimiter
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

# Инициализация состояния
if 'valid_address' not in st.session_state:
    st.session_state.valid_address = ""
if 'suggestions' not in st.session_state:
    st.session_state.suggestions = []
if 'show_suggestions' not in st.session_state:
    st.session_state.show_suggestions = False

# Кэшированный геокодер
@st.cache_resource
def get_geocoder():
    geolocator = Nominatim(user_agent="real_estate_app_2024_v3")
    return RateLimiter(geolocator.geocode, min_delay_seconds=1)

def get_address_suggestions(query):
    """Получение подсказок адресов"""
    try:
        if not query or len(str(query).strip()) < 3:
            return []
        
        geocode = get_geocoder()
        locations = geocode(str(query), exactly_one=False, limit=5)
        return [loc.address.split(',')[0] for loc in locations] if locations else []
    except Exception:
        return []

def validate_address(address):
    """Проверка существования адреса"""
    try:
        if not address or len(str(address).strip()) < 3:
            return False, "Введите адрес (минимум 3 символа)"
            
        geocode = get_geocoder()
        location = geocode(str(address), exactly_one=True)
        return bool(location), "Адрес не найден" if not location else ""
    except Exception as e:
        return False, f"Ошибка проверки адреса: {str(e)}"

def analyze_real_estate(address, radius, offer_type, rooms):
    """Анализ недвижимости"""
    try:
        parser = CianParser(location=address)
        
        if offer_type == "Новостройка":
            data = parser.get_newbuildings(
                rooms=rooms,
                with_saving_csv=False,
                additional_settings={"radius": radius}
            )
        else:
            data = parser.get_flats(
                deal_type="sale",
                rooms=rooms,
                with_saving_csv=False,
                additional_settings={"radius": radius}
            )
        
        df = pd.DataFrame(data)
        if not df.empty:
            df['offer_type'] = offer_type
            df['price'] = pd.to_numeric(df['price'].astype(str).str.replace(r'\D', '', regex=True), errors='coerce')
            df['area'] = pd.to_numeric(df['area'].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce')
            df = df.dropna(subset=['price', 'area'])
            df['price_per_m2'] = df['price'] / df['area']
            
        return df
    except Exception as e:
        st.error(f"Ошибка анализа: {str(e)}")
        return pd.DataFrame()

# Интерфейс приложения
st.set_page_config(page_title="Анализ недвижимости", layout="wide")
st.title("🏠 Анализ цен на недвижимость")

# Блок ввода адреса
address_input = st.text_input(
    "Введите улицу и дом (например, 'Алексея Козина 3'):",
    value=st.session_state.valid_address,
    key="addr_input",
    placeholder="Начните вводить адрес..."
)

# Обработка ввода адреса
if address_input and address_input != st.session_state.get('last_query', ''):
    st.session_state.last_query = address_input
    if len(str(address_input)) >= 3:
        with st.spinner("Поиск вариантов адресов..."):
            st.session_state.suggestions = get_address_suggestions(address_input)
            st.session_state.show_suggestions = bool(st.session_state.suggestions)

# Отображение подсказок
if st.session_state.show_suggestions and st.session_state.suggestions:
    selected = st.selectbox(
        "Выберите подходящий адрес:",
        options=st.session_state.suggestions,
        index=None,
        key="addr_suggestions",
        placeholder="Выберите из списка..."
    )
    
    if selected:
        st.session_state.valid_address = selected
        st.session_state.show_suggestions = False
        st.rerun()

# Параметры поиска
with st.expander("🔍 Параметры поиска", expanded=True):
    cols = st.columns(3)
    with cols[0]:
        radius = st.slider("Радиус поиска (км)", 0.5, 5.0, 1.0, 0.1)
    with cols[1]:
        offer_type = st.radio("Тип недвижимости", ["Вторичка", "Новостройка"])
    with cols[2]:
        rooms = st.multiselect(
            "Количество комнат",
            ["Студия", "1", "2", "3", "4+"],
            default=["1", "2"]
        )

# Блок анализа
if st.button("Найти предложения", type="primary"):
    current_address = str(address_input).strip() if address_input else ""
    
    # Валидация адреса
    is_valid, msg = validate_address(current_address)
    if not is_valid:
        st.error(msg)
        st.stop()
    
    st.session_state.valid_address = current_address
    
    with st.spinner(f"Ищем {offer_type.lower()}..."):
        # Преобразование комнат
        room_map = {"Студия": 0, "1": 1, "2": 2, "3": 3, "4+": 4}
        rooms_to_parse = [room_map[r] for r in rooms if r in room_map]
        
        if not rooms_to_parse:
            st.error("Выберите хотя бы один тип комнат")
            st.stop()
        
        # Анализ данных
        df = analyze_real_estate(
            address=current_address,
            radius=radius,
            offer_type=offer_type,
            rooms=tuple(rooms_to_parse)
        
        if df.empty:
            st.warning("По вашему запросу ничего не найдено")
            st.stop()
        
        # Отображение результатов
        st.success(f"Найдено {len(df)} предложений")
        
        # Основные метрики
        cols = st.columns(3)
        avg_price = df['price_per_m2'].mean()
        min_price = df['price_per_m2'].min()
        max_price = df['price_per_m2'].max()
        
        cols[0].metric("Средняя цена", f"{avg_price:,.0f} ₽/м²")
        cols[1].metric("Минимальная цена", f"{min_price:,.0f} ₽/м²")
        cols[2].metric("Максимальная цена", f"{max_price:,.0f} ₽/м²")
        
        # Вкладки с данными
        tab1, tab2 = st.tabs(["📊 Данные", "📈 Графики"])
        
        with tab1:
            st.dataframe(
                df[['address', 'price', 'area', 'rooms', 'price_per_m2']]
                .sort_values('price_per_m2')
                .rename(columns={
                    'address': 'Адрес',
                    'price': 'Цена',
                    'area': 'Площадь',
                    'rooms': 'Комнат',
                    'price_per_m2': 'Цена за м²'
                }),
                column_config={
                    "Цена": st.column_config.NumberColumn(format="%.0f ₽"),
                    "Площадь": st.column_config.NumberColumn(format="%.1f м²"),
                    "Цена за м²": st.column_config.NumberColumn(format="%.0f ₽")
                },
                height=500,
                use_container_width=True
            )
        
        with tab2:
            fig1 = px.histogram(
                df,
                x='price_per_m2',
                title='Распределение цен за квадратный метр',
                labels={'price_per_m2': 'Цена за м² (₽)'}
            )
            st.plotly_chart(fig1, use_container_width=True)
            
            fig2 = px.scatter(
                df,
                x='area',
                y='price',
                color='rooms',
                title='Зависимость цены от площади',
                labels={'area': 'Площадь (м²)', 'price': 'Цена (₽)'}
            )
            st.plotly_chart(fig2, use_container_width=True)
