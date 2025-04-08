import streamlit as st
import math
import plotly.graph_objects as go
import pandas as pd

def main():
    st.title("📊 Калькулятор ТЭП для жилого комплекса")
    st.markdown("""
    Введите параметры участка и здания, чтобы рассчитать:
    - Площади (коммерческая, жилая, парковка, озеленение)
    - Количество машиномест
    - Социальные объекты (СБП)
    """)

    with st.expander("⚙️ Основные параметры"):
        col1, col2 = st.columns(2)
        with col1:
            land_area = st.number_input("Площадь участка (кв.м)", min_value=0.0, value=3535.0)
            building_footprint = st.number_input("Площадь пятна застройки (кв.м)", min_value=0.0, value=1718.0)
            floors = st.number_input("Этажность", min_value=1, value=8)
        with col2:
            commercial_ground_floor = st.radio("1-й этаж под коммерцию?", ["Да", "Нет"], index=0)
            parking_norm_housing = st.number_input("Норма парковки: жильё (кв.м/место)", value=80.0)
            parking_norm_commercial = st.number_input("Норма парковки: коммерция (кв.м/место)", value=50.0)

    with st.expander("🚗 Парковка"):
        st.write("**Габариты машиноместа:**")
        col1, col2 = st.columns(2)
        with col1:
            parking_width = st.number_input("Ширина (м)", value=5.3)
            parking_length = st.number_input("Длина (м)", value=2.5)
        with col2:
            parking_disabled_width = st.number_input("Ширина для инвалидов (м)", value=3.6)
            parking_disabled_length = st.number_input("Длина для инвалидов (м)", value=7.5)

    with st.expander("🌳 Озеленение и СБП"):
        landscaping_norm = st.number_input("Норма озеленения (кв.м на 100 кв.м жилья)", value=20.0)
        landscaping_reduction = st.number_input("Коэффициент уменьшения озеленения", value=0.3, min_value=0.0, max_value=1.0)
        
        st.write("**Нормы СБП (кв.м на 100 кв.м жилья):**")
        sbp_playgrounds = st.number_input("Детские площадки", value=2.3)
        sbp_adult = st.number_input("Площадки для взрослых", value=0.4)
        sbp_sports = st.number_input("Спортивные площадки", value=6.6)
        sbp_other = st.number_input("Прочие элементы", value=0.0)

    # Расчёты
    if commercial_ground_floor == "Да":
        commercial_area = building_footprint * 0.7
        residential_area = building_footprint * (floors - 1) * 0.7
    else:
        commercial_area = 0
        residential_area = building_footprint * floors * 0.7

    total_sellable_area = commercial_area + residential_area

    parking_spaces = math.ceil(residential_area / parking_norm_housing) + math.ceil(commercial_area / parking_norm_commercial)
    parking_spaces_disabled = math.ceil(parking_spaces * 0.1)

    parking_area = parking_spaces * parking_width * parking_length
    parking_area_disabled = parking_spaces_disabled * parking_disabled_width * parking_disabled_length
    total_parking_area = (parking_area + parking_area_disabled) * 3  # С учётом проездов

    landscaping_area = (residential_area / 100) * landscaping_norm * (1 - landscaping_reduction)
    sbp_area = (residential_area / 100) * (sbp_playgrounds + sbp_adult + sbp_sports + sbp_other)

    free_area = land_area - building_footprint - total_parking_area - sbp_area - landscaping_area

    # Вывод результатов
    st.markdown("---")
    st.subheader("📈 Результаты расчётов")

    results = {
        "Коммерческая площадь (кв.м)": commercial_area,
        "Жилая площадь (кв.м)": residential_area,
        "Общая продаваемая площадь (кв.м)": total_sellable_area,
        "Требуемое число машиномест (шт)": parking_spaces,
        "Машиноместа для инвалидов (шт)": parking_spaces_disabled,
        "Площадь парковки (кв.м)": total_parking_area,
        "Площадь озеленения (кв.м)": landscaping_area,
        "Площадь СБП (кв.м)": sbp_area,
        "Свободная площадь участка (кв.м)": free_area
    }

    for param, value in results.items():
        st.metric(label=param, value=f"{value:.2f}" if isinstance(value, float) else value)

    # Визуализация с использованием Plotly (исправленная версия)
    st.markdown("---")
    st.subheader("📊 Распределение площади участка")
    
    labels = ["Здание", "Парковка", "Озеленение", "СБП", "Свободная площадь"]
    values = [
        building_footprint,
        total_parking_area,
        landscaping_area,
        sbp_area,
        free_area
    ]
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.3,
        textinfo='percent+label',
        marker=dict(colors=['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A'])
    )])  # Все скобки правильно сбалансированы
    
    fig.update_layout(
        title_text="Распределение площади участка",
        showlegend=True
    )
    
    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
