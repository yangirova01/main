import streamlit as st
import math
import plotly.graph_objects as go

def calculate_kindergarten(residential_area, is_attached):
    """Расчет параметров детского сада по МНГП"""
    # Расчет по старому МНГП (36 мест на 10000 кв.м)
    places_old = math.ceil(max(50, residential_area / 10000 * 36))
    groups_old = max(4, math.ceil(places_old / 20))
    
    # Расчет по новому МНГП (27 мест на 10000 кв.м)
    places_new = math.ceil(max(50, residential_area / 10000 * 27))
    groups_new = max(4, math.ceil(places_new / 20))
    
    # Расчет количества зданий
    if is_attached:
        buildings_old = math.ceil(places_old / 150)
        buildings_new = math.ceil(places_new / 150)
    else:
        buildings_old = math.ceil(places_old / 350)
        buildings_new = math.ceil(places_new / 350)
    
    return {
        "old": {
            "places": places_old,
            "groups": groups_old,
            "buildings": buildings_old
        },
        "new": {
            "places": places_new,
            "groups": groups_new,
            "buildings": buildings_new
        }
    }

def calculate_school(residential_area):
    """Расчет параметров школы по МНГП"""
    # Расчет по старому МНГП (76 мест на 10000 кв.м)
    places_old = math.ceil(residential_area / 10000 * 76)
    
    # Расчет по новому МНГП (57 мест на 10000 кв.м)
    places_new = math.ceil(residential_area / 10000 * 57)
    
    # Расчет площади здания (20 кв.м на место)
    building_area_old = places_old * 20
    building_area_new = places_new * 20
    
    return {
        "old": {
            "places": places_old,
            "building_area": building_area_old
        },
        "new": {
            "places": places_new,
            "building_area": building_area_new
        }
    }

def main():
    st.set_page_config(page_title="Калькулятор ТЭП", layout="wide")
    st.title("📊 Калькулятор ТЭП для жилого комплекса")
    st.markdown("""
    Введите параметры участка и здания, чтобы рассчитать:
    - Площади (коммерческая, жилая, парковка, озеленение)
    - Количество машиномест
    - Социальные объекты (детские сады, школы)
    """)

    with st.expander("⚙️ Основные параметры", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            land_area = st.number_input("Площадь участка (кв.м)", min_value=0.0, value=10000.0)
            building_footprint = st.number_input("Площадь пятна застройки (кв.м)", min_value=0.0, value=2000.0)
            floors = st.number_input("Этажность", min_value=1, value=10)
        with col2:
            commercial_ground_floor = st.radio("1-й этаж под коммерцию?", ["Да", "Нет"], index=0)
            parking_norm_housing = st.number_input("Норма парковки: жильё (кв.м/место)", value=80.0)
            parking_norm_commercial = st.number_input("Норма парковки: коммерция (кв.м/место)", value=50.0)
            is_attached_kindergarten = st.radio("Детский сад встроенно-пристроенный?", ["ДА", "НЕТ"], index=1)

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
        landscaping_reduction = st.number_input("Коэффициент уменьшения озеленения", value=0.3, 
                                             min_value=0.0, max_value=1.0, step=0.1)
        
        st.write("**Нормы СБП (кв.м на 100 кв.м жилья):**")
        col1, col2 = st.columns(2)
        with col1:
            sbp_playgrounds = st.number_input("Детские площадки", value=2.3)
            sbp_adult = st.number_input("Площадки для взрослых", value=0.4)
        with col2:
            sbp_sports = st.number_input("Спортивные площадки", value=6.6)
            sbp_other = st.number_input("Прочие элементы", value=0.0)

    # Основные расчеты
    if commercial_ground_floor == "Да":
        commercial_area = building_footprint * 0.7
        residential_area = building_footprint * (floors - 1) * 0.7
    else:
        commercial_area = 0
        residential_area = building_footprint * floors * 0.7

    total_sellable_area = commercial_area + residential_area

    # Расчет парковки
    parking_spaces = math.ceil(residential_area / parking_norm_housing) + math.ceil(commercial_area / parking_norm_commercial)
    parking_spaces_disabled = math.ceil(parking_spaces * 0.1)
    parking_area = parking_spaces * parking_width * parking_length
    parking_area_disabled = parking_spaces_disabled * parking_disabled_width * parking_disabled_length
    total_parking_area = (parking_area + parking_area_disabled) * 3  # С учетом проездов

    # Расчет озеленения и СБП
    landscaping_area = (residential_area / 100) * landscaping_norm * (1 - landscaping_reduction)
    sbp_area = (residential_area / 100) * (sbp_playgrounds + sbp_adult + sbp_sports + sbp_other)
    free_area = land_area - building_footprint - total_parking_area - sbp_area - landscaping_area

    # Расчет социальных объектов
    kindergarten_data = calculate_kindergarten(residential_area, is_attached_kindergarten == "ДА")
    school_data = calculate_school(residential_area)

    # Вывод результатов
    st.markdown("---")
    st.subheader("📈 Результаты расчётов")

    # Основные параметры
    st.write("### Основные параметры")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Жилая площадь (кв.м)", f"{residential_area:,.2f}".replace(",", " "))
        st.metric("Коммерческая площадь (кв.м)", f"{commercial_area:,.2f}".replace(",", " "))
    with col2:
        st.metric("Общая продаваемая площадь (кв.м)", f"{total_sellable_area:,.2f}".replace(",", " "))
        st.metric("Свободная площадь участка (кв.м)", f"{free_area:,.2f}".replace(",", " "))
    with col3:
        st.metric("Требуемое число машиномест (шт)", f"{parking_spaces:,}".replace(",", " "))
        st.metric("Машиноместа для инвалидов (шт)", parking_spaces_disabled)

    # Социальные объекты
    st.write("### Социальные объекты")
    
    st.write("#### Детские сады")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**По старому МНГП (36 мест/10000 кв.м)**")
        st.metric("Количество мест", kindergarten_data["old"]["places"])
        st.metric("Количество групп", kindergarten_data["old"]["groups"])
        st.metric("Количество зданий", kindergarten_data["old"]["buildings"])
    with col2:
        st.write("**По новому МНГП (27 мест/10000 кв.м)**")
        st.metric("Количество мест", kindergarten_data["new"]["places"])
        st.metric("Количество групп", kindergarten_data["new"]["groups"])
        st.metric("Количество зданий", kindergarten_data["new"]["buildings"])

    st.write("#### Школы")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**По старому МНГП (76 мест/10000 кв.м)**")
        st.metric("Количество мест", school_data["old"]["places"])
        st.metric("Площадь здания (кв.м)", f"{school_data['old']['building_area']:,.2f}".replace(",", " "))
    with col2:
        st.write("**По новому МНГП (57 мест/10000 кв.м)**")
        st.metric("Количество мест", school_data["new"]["places"])
        st.metric("Площадь здания (кв.м)", f"{school_data['new']['building_area']:,.2f}".replace(",", " "))

    # Визуализация
    st.markdown("---")
    st.subheader("📊 Распределение площади участка")
    
    labels = ["Здание", "Парковка", "Озеленение", "СБП", "Свободная площадь"]
    values = [building_footprint, total_parking_area, landscaping_area, sbp_area, free_area]
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.3,
        textinfo='percent+label',
        marker=dict(colors=['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A'])
    )])
    
    fig.update_layout(
        title_text="Распределение площади участка",
        showlegend=True,
        height=500
    )
    
    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
