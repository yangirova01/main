import streamlit as st
import math
import plotly.graph_objects as go

def calculate_kindergarten(residential_area, is_attached):
    """Расчет параметров детского сада по МНГП"""
    places_old = math.ceil(max(50, residential_area / 10000 * 36))
    groups_old = max(4, math.ceil(places_old / 20))
    
    places_new = math.ceil(max(50, residential_area / 10000 * 27))
    groups_new = max(4, math.ceil(places_new / 20))
    
    if is_attached:
        buildings_old = math.ceil(places_old / 150)
        buildings_new = math.ceil(places_new / 150)
    else:
        buildings_old = math.ceil(places_old / 350)
        buildings_new = math.ceil(places_new / 350)
    
    return {
        "old": {"places": places_old, "groups": groups_old, "buildings": buildings_old},
        "new": {"places": places_new, "groups": groups_new, "buildings": buildings_new}
    }

def calculate_school(residential_area):
    """Расчет параметров школы по МНГП"""
    places_old = math.ceil(residential_area / 10000 * 76)
    places_new = math.ceil(residential_area / 10000 * 57)
    return {
        "old": {"places": places_old, "building_area": places_old * 20},
        "new": {"places": places_new, "building_area": places_new * 20}
    }

def create_pie_chart(labels, values):
    """Создание круговой диаграммы с проверкой данных"""
    # Фильтрация нулевых значений
    non_zero = [(label, value) for label, value in zip(labels, values) if value > 0]
    if not non_zero:
        return None
    
    filtered_labels, filtered_values = zip(*non_zero)
    
    fig = go.Figure(data=[go.Pie(
        labels=filtered_labels,
        values=filtered_values,
        hole=0.3,
        textinfo='percent+label',
        textposition='inside',
        marker=dict(colors=['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A'])
    )])
    
    fig.update_layout(
        title_text="Распределение площади участка",
        showlegend=True,
        height=500,
        uniformtext_minsize=12,
        uniformtext_mode='hide'
    )
    return fig

def main():
    st.set_page_config(page_title="Калькулятор ТЭП", layout="wide")
    st.title("📊 Калькулятор ТЭП для жилого комплекса")
    
    # Ввод параметров
    with st.expander("⚙️ Основные параметры", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            land_area = st.number_input("Площадь участка (кв.м)", min_value=0.0, value=10000.0)
            building_footprint = st.number_input("Площадь пятна застройки (кв.м)", min_value=0.0, value=2000.0)
            floors = st.number_input("Этажность", min_value=1, value=10)
        with col2:
            commercial_ground_floor = st.radio("1-й этаж под коммерцию?", ["Да", "Нет"], index=0)
            is_attached_kindergarten = st.radio("Детский сад встроенно-пристроенный?", ["ДА", "НЕТ"], index=1)

    # Расчет площадей
    if commercial_ground_floor == "Да":
        commercial_area = building_footprint * 0.7
        residential_area = building_footprint * (floors - 1) * 0.7
    else:
        commercial_area = 0
        residential_area = building_footprint * floors * 0.7

    total_sellable_area = commercial_area + residential_area
    
    # Расчет социальных объектов
    kindergarten_data = calculate_kindergarten(residential_area, is_attached_kindergarten == "ДА")
    school_data = calculate_school(residential_area)

    # Визуализация
    st.markdown("---")
    st.subheader("📊 Распределение площади участка")
    
    # Расчет компонентов для диаграммы
    building_area = building_footprint
    parking_area = building_footprint * 0.5  # Примерный расчет
    landscaping_area = land_area * 0.2       # Примерный расчет
    sbp_area = land_area * 0.1               # Примерный расчет
    free_area = max(0, land_area - building_area - parking_area - landscaping_area - sbp_area)
    
    # Данные для диаграммы
    labels = ["Здание", "Парковка", "Озеленение", "СБП", "Свободная площадь"]
    values = [building_area, parking_area, landscaping_area, sbp_area, free_area]
    
    # Отображение сырых данных для отладки
    with st.expander("🔍 Данные для диаграммы"):
        st.write(dict(zip(labels, values)))
    
    # Создание и отображение диаграммы
    fig = create_pie_chart(labels, values)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Нет данных для отображения диаграммы. Проверьте входные параметры.")

    # Вывод результатов
    st.markdown("---")
    st.subheader("📈 Результаты расчётов")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Жилая площадь (кв.м)", f"{residential_area:,.2f}")
        st.metric("Коммерческая площадь (кв.м)", f"{commercial_area:,.2f}")
    with col2:
        st.metric("Общая площадь участка (кв.м)", f"{land_area:,.2f}")
        st.metric("Свободная площадь участка (кв.м)", f"{free_area:,.2f}")

if __name__ == "__main__":
    main()
