import streamlit as st
import pandas as pd
import math

from shapely.geometry import Polygon
import plotly.graph_objs as go

# ----------------------------------------------------------------
# Нормативы по умолчанию (упрощённый пример)
# ----------------------------------------------------------------
DEFAULT_NORMATIVES = {
    "commercial_coeff": 0.7,         # Коэффициент коммерческой площади (от 1-го этажа)
    "residential_coeff": 0.7,        # Коэффициент жилой площади (от остальных этажей)
    "parking_space_area": 25.0,      # Площадь под 1 машиноместо (плоскостная)
    "population_per_25m2": 1.0/25.0, # Сколько жителей приходится на 1 м² жилья
    "landscaping_per_person": 5.0,   # Площадь благоустройства на 1 жителя
    # Примерные параметры для детсадов и школ:
    "kindergarten_ratio": 0.03,      # Доля дошкольников от населения
    "school_ratio": 0.10,            # Доля школьников от населения
    "kindergarten_area_per_child": 6.0,  # Площадь на 1 ребёнка в детсаду
    "school_area_per_student": 7.0,      # Площадь на 1 ученика в школе
}


def calculate_house_tep(
    floor_number: int,
    building_footprint_area: float,
    land_area: float,
    normatives: dict,
    parking_type: str = "только плоскостной"
):
    """
    Расчёт для дома (упрощённый, демонстрационный).
    """
    # Площадь 1-го этажа => commercial_area
    commercial_area = building_footprint_area * normatives["commercial_coeff"]

    # Общая площадь всех этажей
    total_floor_area = building_footprint_area * floor_number

    # Жилая площадь (исключаем коммерцию с 1 этажа):
    residential_area = (total_floor_area - commercial_area) * normatives["residential_coeff"]

    # Суммарная продаваемая (жилая + коммерческая)
    total_sellable_area = commercial_area + residential_area

    # Плотность застройки
    building_density = 0
    if land_area > 0:
        building_density = building_footprint_area / land_area

    # Численность населения (упрощённо)
    population = residential_area * normatives["population_per_25m2"]

    # Примерная логика машино-мест (1 машиноместо на 60 м² жилья)
    parking_spaces_base = math.ceil(residential_area / 60.0)

    # Разбиваем по типам
    # (упрощённо: если выбраны несколько типов — складываем кол-во)
    parking_spaces_ploskost = 0
    parking_spaces_underground = 0
    parking_spaces_multilevel = 0

    parking_type_lower = parking_type.lower()
    if "плоскостной" in parking_type_lower:
        parking_spaces_ploskost = parking_spaces_base
    if "подземный" in parking_type_lower:
        parking_spaces_underground = math.ceil(parking_spaces_base * 0.5)
    if "многоуровневый" in parking_type_lower:
        parking_spaces_multilevel = math.ceil(parking_spaces_base * 0.3)

    total_parking_spaces = parking_spaces_ploskost + parking_spaces_underground + parking_spaces_multilevel

    # Площадь под плоскостную парковку
    parking_area_ploskost = parking_spaces_ploskost * normatives["parking_space_area"]

    # Площадь благоустройства
    landscaping_area = population * normatives["landscaping_per_person"]

    return {
        "commercial_area": commercial_area,
        "residential_area": residential_area,
        "total_sellable_area": total_sellable_area,
        "building_density": building_density,
        "population": population,
        "parking_spaces_ploskostnoy": parking_spaces_ploskost,
        "parking_spaces_underground": parking_spaces_underground,
        "parking_spaces_multilevel": parking_spaces_multilevel,
        "total_parking_spaces": total_parking_spaces,
        "parking_area_ploskost": parking_area_ploskost,
        "landscaping_area": landscaping_area
    }


def calculate_social_infrastructure(
    population: float,
    normatives: dict,
    separate_kindergarten: bool,
    separate_school: bool
):
    """
    Расчёты для детских садов и школ.
    """
    kids_for_kindergarten = population * normatives["kindergarten_ratio"]
    kids_for_school = population * normatives["school_ratio"]

    # Площадь детсада
    kindergarten_area = kids_for_kindergarten * normatives["kindergarten_area_per_child"]
    if separate_kindergarten:
        kindergarten_area *= 1.2  # условная надбавка

    # Площадь школы
    school_area = kids_for_school * normatives["school_area_per_student"]
    if separate_school:
        school_area *= 1.2  # условная надбавка

    return {
        "kids_for_kindergarten": kids_for_kindergarten,
        "kids_for_school": kids_for_school,
        "kindergarten_area": kindergarten_area,
        "school_area": school_area
    }


# ------------------------------------------------------------------------------
# Streamlit-приложение
# ------------------------------------------------------------------------------
def main():
    st.title("Демо: Расчёт ТЭП + Визуализация на OpenStreetMap (Plotly)")

    # --------------------------
    # Блок 1: Редактирование нормативов
    # --------------------------
    with st.expander("1) Редактирование нормативов (по желанию)"):
        normatives = DEFAULT_NORMATIVES.copy()
        st.markdown("#### Основные нормативы для дома")
        normatives["commercial_coeff"] = st.number_input(
            "Коэффициент коммерческой площади (от 1 этажа)",
            value=normatives["commercial_coeff"],
            min_value=0.0, max_value=1.0, step=0.1
        )
        normatives["residential_coeff"] = st.number_input(
            "Коэффициент жилой площади (остальные этажи)",
            value=normatives["residential_coeff"],
            min_value=0.0, max_value=1.0, step=0.1
        )
        normatives["parking_space_area"] = st.number_input(
            "Площадь одного машиноместа (плоскостная), м²",
            value=normatives["parking_space_area"],
            min_value=0.0, step=5.0
        )
        normatives["population_per_25m2"] = st.number_input(
            "Численность (чел.) на 1 м² жилья (по умолчанию 1/25)",
            value=normatives["population_per_25m2"],
            min_value=0.0, step=0.001
        )
        normatives["landscaping_per_person"] = st.number_input(
            "Площадь благоустройства на 1 жителя, м²",
            value=normatives["landscaping_per_person"],
            min_value=0.0, step=1.0
        )

        st.markdown("#### Параметры для детсадов и школ")
        normatives["kindergarten_ratio"] = st.number_input(
            "Доля дошкольников от населения (0.03 = 3%)",
            value=normatives["kindergarten_ratio"],
            min_value=0.0, max_value=1.0, step=0.01
        )
        normatives["school_ratio"] = st.number_input(
            "Доля школьников от населения (0.1 = 10%)",
            value=normatives["school_ratio"],
            min_value=0.0, max_value=1.0, step=0.01
        )
        normatives["kindergarten_area_per_child"] = st.number_input(
            "Площадь на 1 ребёнка (детсад), м²",
            value=normatives["kindergarten_area_per_child"],
            min_value=0.0, step=1.0
        )
        normatives["school_area_per_student"] = st.number_input(
            "Площадь на 1 ученика (школа), м²",
            value=normatives["school_area_per_student"],
            min_value=0.0, step=1.0
        )

    # --------------------------
    # Блок 2: Ввод координат и визуализация
    # --------------------------
    st.markdown("## 2) Ввод координат участка и визуализация")

    st.write("Введите координаты в формате массива пар `[широта, долгота]`. Пример:")
    st.code("[[55.751244, 37.618423], [55.752, 37.62], [55.75, 37.62]]")

    coords_str = st.text_area("Координаты (list of [lat, lon])", value="")
    coords_list = []
    polygon_area = 0.0
    if coords_str.strip():
        import ast
        try:
            coords_list = ast.literal_eval(coords_str)
        except Exception as e:
            st.error(f"Ошибка парсинга: {e}")
            coords_list = []

    if coords_list and len(coords_list) >= 3:
        # Посмотрим, удастся ли построить полигон
        try:
            poly = Polygon(coords_list)
            polygon_area = poly.area  # Площадь в «квадратных градусах», если это lat/lon
            # Для корректной площади в метрах нужно делать геопроекцию.
            # Условно показываем "площадь" в градусах.
            st.write(f"**Площадь (в градусах²):** {polygon_area:.6f}")
        except Exception as e:
            st.error(f"Не удалось построить полигон: {e}")

        # Визуализация через plotly с OpenStreetMap:
        # Сконструируем trace, чтобы отрисовать линию по периметру.
        # Для корректности отображения многоугольника замкнём его (повторим первую точку в конце).
        coords_for_plot = coords_list[:]
        if coords_for_plot[0] != coords_for_plot[-1]:
            coords_for_plot.append(coords_for_plot[0])

        lats = [c[0] for c in coords_for_plot]
        lons = [c[1] for c in coords_for_plot]

        # Найдём "центр" для установки фокуса карты (возьмём среднее)
        mid_lat = sum(lats) / len(lats)
        mid_lon = sum(lons) / len(lons)

        fig_map = go.Figure()
        # Добавим слой - сам многоугольник (в виде линии)
        fig_map.add_trace(go.Scattermapbox(
            lat=lats,
            lon=lons,
            mode='lines',
            fill='toself',   # чтоб закрасить полигон
            fillcolor='royalblue',
            line=dict(width=2, color='blue'),
            name='Участок'
        ))

        fig_map.update_layout(
            mapbox=dict(
                style='open-street-map',
                center=dict(lat=mid_lat, lon=mid_lon),
                zoom=14
            ),
            margin={"r":0,"t":0,"l":0,"b":0}
        )

        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.info("Введите корректный список координат (не менее трёх точек).")

    # --------------------------
    # Блок 3: Расчёт для жилого дома
    # --------------------------
    st.markdown("## 3) Параметры дома и расчёт ТЭП")
    building_footprint_area = st.number_input("Площадь застройки (пятно дома), м²", min_value=0.0, step=100.0, value=2000.0)
    floor_number = st.number_input("Этажность", min_value=1, max_value=50, value=9)
    parking_type_options = [
        "только плоскостной",
        "только подземный",
        "только многоуровневый",
        "плоскостной + подземный",
        "плоскостной + многоуровневый",
        "плоскостной + многоуровневый + подземный"
    ]
    parking_type = st.selectbox("Тип паркинга", parking_type_options)

    # Условно считаем, что land_area мы не можем точно получить из lon/lat без проекции,
    # поэтому позволим вводить "физическую" площадь участка отдельно
    land_area = st.number_input("Площадь участка (м²) — фактическая, а не в градусах",
                                min_value=0.0, step=100.0, value=5000.0)

    if st.button("Рассчитать ТЭП (дом)"):
        house_tep = calculate_house_tep(
            floor_number=floor_number,
            building_footprint_area=building_footprint_area,
            land_area=land_area,
            normatives=normatives,
            parking_type=parking_type
        )

        df_house = pd.DataFrame({
            "Показатель": [
                "Коммерческая площадь (м²)",
                "Жилая площадь (м²)",
                "Суммарная продаваемая площадь (м²)",
                "Плотность застройки (доля)",
                "Примерная численность населения (чел.)",
                "Парковка (плоскостная), машино-мест",
                "Парковка (подземная), машино-мест",
                "Парковка (многоуровневая), машино-мест",
                "Всего машино-мест",
                "Площадь плоскостной парковки (м²)",
                "Площадь благоустройства (м²)"
            ],
            "Значение": [
                round(house_tep["commercial_area"], 2),
                round(house_tep["residential_area"], 2),
                round(house_tep["total_sellable_area"], 2),
                round(house_tep["building_density"], 3),
                round(house_tep["population"], 2),
                house_tep["parking_spaces_ploskostnoy"],
                house_tep["parking_spaces_underground"],
                house_tep["parking_spaces_multilevel"],
                house_tep["total_parking_spaces"],
                round(house_tep["parking_area_ploskost"], 2),
                round(house_tep["landscaping_area"], 2),
            ]
        })
        st.table(df_house)

        # Сохраним население
        st.session_state["population"] = house_tep["population"]

    st.markdown("---")

    # --------------------------
    # Блок 4: Расчёты для детсадов и школ
    # --------------------------
    st.markdown("## 4) Детские сады и школы")
    separate_kindergarten = st.checkbox("Отдельно стоящий детский сад?")
    separate_school = st.checkbox("Отдельно стоящая школа?")

    if "population" not in st.session_state:
        st.warning("Сначала выполните расчёт ТЭП для дома, чтобы определить население.")
    else:
        population_val = st.session_state["population"]
        st.info(f"Будет использоваться численность населения: ~ {population_val:.2f} чел.")
        if st.button("Рассчитать (сады и школы)"):
            social_tep = calculate_social_infrastructure(
                population=population_val,
                normatives=normatives,
                separate_kindergarten=separate_kindergarten,
                separate_school=separate_school
            )
            df_social = pd.DataFrame({
                "Показатель": [
                    "Требуемое число дошкольников (чел.)",
                    "Требуемое число школьников (чел.)",
                    "Площадь детсадов (м²)",
                    "Площадь школ (м²)",
                ],
                "Значение": [
                    round(social_tep["kids_for_kindergarten"], 2),
                    round(social_tep["kids_for_school"], 2),
                    round(social_tep["kindergarten_area"], 2),
                    round(social_tep["school_area"], 2),
                ]
            })
            st.table(df_social)

    st.markdown("---")
    st.markdown("© Пример демонстрационного приложения на Streamlit + Plotly")

if __name__ == "__main__":
    main()