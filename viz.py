import streamlit as st
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, box, Point
import numpy as np
import pulp  # для оптимизации
from itertools import product

# Настройки страницы
st.set_page_config(layout="wide")
st.title("Оптимальная посадка зданий на участке")
st.markdown("""
**Цель:** Максимизировать ТЭП (жилая + коммерческая площадь) с учетом нормативов.
""")

# ===== Ввод данных =====
st.sidebar.header("Параметры участка")

# Загрузка координат
coord_input = st.sidebar.text_area(
    "Координаты участка ([[x1,y1], [x2,y2], ...]):",
    """[[5470588.79254556, 7517329.14918596],
    [5470558.74615099, 7517283.63207208],
    [5470568.90366933, 7517276.34205487],
    [5470578.192469, 7517269.62251705],
    [5470592.45919079, 7517290.97717859],
    [5470591.46521123, 7517302.12980881],
    [5470593.47552749, 7517305.23896183],
    [5470593.44056685, 7517305.57692839],
    [5470602.24724352, 7517319.45290543],
    [5470602.63759289, 7517319.39893184],
    [5470602.97562822, 7517319.93194058],
    [5470600.31627647, 7517321.64350201],
    [5470588.79254556, 7517329.14918596]]"""
)

# Парсинг координат
try:
    coords = eval(coord_input)
    site_polygon = Polygon(coords)
except:
    st.error("Ошибка загрузки координат!")
    st.stop()

# ===== Параметры секций =====
st.sidebar.header("Параметры зданий")

# Размеры секций (из ТЗ)
sections = [
    {"name": "26x16", "width": 26, "height": 16, "type": "Жилая"},
    {"name": "28x16", "width": 28, "height": 16, "type": "Жилая"},
    {"name": "26x18", "width": 26, "height": 18, "type": "Жилая"},
    {"name": "18x18", "width": 18, "height": 18, "type": "Жилая"},
    {"name": "Коммерция", "width": 30, "height": 20, "type": "Коммерческая"},
]

# Выбор секций
selected_sections = st.sidebar.multiselect(
    "Какие секции использовать?",
    [s["name"] for s in sections],
    default=["26x16", "18x18"]
)

# Этажность
floors = st.sidebar.slider("Этажность:", 1, 25, 5)

# Отступы
margin = st.sidebar.slider("Отступ от границ (м):", 0, 20, 5)

# ===== Ограничения =====
st.sidebar.header("Ограничения")

# Парковки
parking_type = st.sidebar.selectbox(
    "Тип парковки:",
    ["Плоскостная", "Подземная", "Многоуровневая"]
)

# Детский сад / школа
with st.sidebar.expander("Социальные объекты"):
    has_kindergarten = st.checkbox("Детский сад (встроенный)")
    has_school = st.checkbox("Школа (отдельно стоящая)")

# ===== Оптимизация =====
def optimize_placement(site, sections_list, floors, margin):
    """Оптимизирует размещение секций на участке."""
    # Генерация возможных позиций
    positions = []
    min_x, min_y, max_x, max_y = site.bounds

    for section in sections_list:
        for angle in [0, 90]:
            w = section["width"] if angle == 0 else section["height"]
            h = section["height"] if angle == 0 else section["width"]

            for x in np.arange(min_x + margin, max_x - w - margin, 5):
                for y in np.arange(min_y + margin, max_y - h - margin, 5):
                    rect = box(x, y, x + w, y + h)
                    if site.contains(rect):
                        positions.append({
                            "section": section,
                            "x": x, "y": y,
                            "width": w, "height": h,
                            "angle": angle
                        })

    # Создаем модель PuLP
    model = pulp.LpProblem("Maximize_TEP", pulp.LpMaximize)

    # Переменные: 1 если секция размещена, 0 иначе
    x = pulp.LpVariable.dicts(
        "pos", range(len(positions)), 
        cat="Binary"
    )

    # Целевая функция: максимизация площади
    model += pulp.lpSum(
        x[i] * (positions[i]["section"]["width"] * positions[i]["section"]["height"] * floors * 0.7)
        for i in range(len(positions))
    )

    # Ограничения:
    # 1) Секции не пересекаются
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            rect_i = box(
                positions[i]["x"], positions[i]["y"],
                positions[i]["x"] + positions[i]["width"],
                positions[i]["y"] + positions[i]["height"]
            )
            rect_j = box(
                positions[j]["x"], positions[j]["y"],
                positions[j]["x"] + positions[j]["width"],
                positions[j]["y"] + positions[j]["height"]
            )
            if rect_i.intersects(rect_j):
                model += x[i] + x[j] <= 1

    # Решаем задачу
    model.solve()

    # Возвращаем выбранные позиции
    return [positions[i] for i in range(len(positions)) if x[i].value() == 1]

# ===== Запуск оптимизации =====
if st.button("Рассчитать оптимальное размещение"):
    selected_sections_data = [s for s in sections if s["name"] in selected_sections]
    if not selected_sections_data:
        st.warning("Выберите секции!")
    else:
        with st.spinner("Оптимизация..."):
            best_positions = optimize_placement(site_polygon, selected_sections_data, floors, margin)

        # Визуализация
        fig, ax = plt.subplots(figsize=(12, 10))
        x, y = site_polygon.exterior.xy
        ax.plot(x, y, 'k-', linewidth=2, label="Граница участка")

        for i, pos in enumerate(best_positions):
            rect = plt.Rectangle(
                (pos["x"], pos["y"]), pos["width"], pos["height"],
                linewidth=1, edgecolor="r", facecolor="none",
                label=f"{pos['section']['name']} ({i+1})"
            )
            ax.add_patch(rect)
            ax.text(
                pos["x"] + pos["width"] / 2,
                pos["y"] + pos["height"] / 2,
                f"{i+1}\n{pos['section']['name']}",
                ha="center", va="center", color="b"
            )

        ax.set_aspect("equal")
        ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
        st.pyplot(fig)

        # Вывод ТЭП
        total_area = sum(
            pos["width"] * pos["height"] * floors * 0.7
            for pos in best_positions
        )
        st.success(f"**Максимальная полезная площадь (ТЭП):** {total_area:.2f} м²")

# ===== Что можно добавить? =====
st.sidebar.header("Доработки")
st.sidebar.markdown("""
- **Учет парковок** (по формуле из ТЗ)  
- **Расчет благоустройства** (озеленение, детские площадки)  
- **Оптимизация под детские сады/школы**  
- **Экспорт в KML/DWG**  
""")
