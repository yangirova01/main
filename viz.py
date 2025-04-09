import streamlit as st
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, box, MultiPolygon
import numpy as np
from itertools import combinations

# Настройки страницы
st.set_page_config(layout="wide")
st.title("Оптимальная посадка зданий на участке")
st.markdown("""
**Цель:** Максимизировать полезную площадь (ТЭП) с учетом нормативов и ограничений.
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
except Exception as e:
    st.error(f"Ошибка загрузки координат: {e}")
    st.stop()

# ===== Параметры зданий =====
st.sidebar.header("Параметры зданий")

# Размеры секций (из ТЗ)
SECTION_TYPES = {
    "Жилая 26x16": {"width": 26, "height": 16, "type": "Жилая", "color": "blue"},
    "Жилая 28x16": {"width": 28, "height": 16, "type": "Жилая", "color": "green"},
    "Жилая 26x18": {"width": 26, "height": 18, "type": "Жилая", "color": "red"},
    "Жилая 18x18": {"width": 18, "height": 18, "type": "Жилая", "color": "purple"},
    "Коммерция 30x20": {"width": 30, "height": 20, "type": "Коммерческая", "color": "orange"}
}

selected_sections = st.sidebar.multiselect(
    "Выберите типы секций:",
    list(SECTION_TYPES.keys()),
    default=["Жилая 26x16", "Жилая 18x18"]
)

# Параметры размещения
floors = st.sidebar.slider("Этажность:", 1, 25, 5)
margin = st.sidebar.slider("Отступ от границ (м):", 0, 20, 5)
step = st.sidebar.slider("Шаг сетки (м):", 1, 10, 3)

# ===== Алгоритм размещения =====
def generate_positions(site, sections, margin, step):
    """Генерирует возможные позиции для секций"""
    positions = []
    min_x, min_y, max_x, max_y = site.bounds
    
    for section_name in sections:
        section = SECTION_TYPES[section_name]
        for angle in [0, 90]:  # 0 и 90 градусов
            w = section["width"] if angle == 0 else section["height"]
            h = section["height"] if angle == 0 else section["width"]
            
            for x in np.arange(min_x + margin, max_x - w - margin, step):
                for y in np.arange(min_y + margin, max_y - h - margin, step):
                    rect = box(x, y, x + w, y + h)
                    if site.contains(rect):
                        positions.append({
                            "section": section_name,
                            "x": x, "y": y,
                            "width": w, "height": h,
                            "angle": angle,
                            "area": w * h * floors * 0.7  # Расчет ТЭП
                        })
    return positions

def optimize_placement(positions):
    """Оптимизирует размещение для максимальной площади"""
    positions.sort(key=lambda x: -x["area"])  # Сортируем по убыванию площади
    placed = []
    
    for pos in positions:
        conflict = False
        for placed_pos in placed:
            # Проверяем пересечение прямоугольников
            rect1 = box(pos["x"], pos["y"], 
                       pos["x"] + pos["width"], 
                       pos["y"] + pos["height"])
            rect2 = box(placed_pos["x"], placed_pos["y"], 
                        placed_pos["x"] + placed_pos["width"], 
                        placed_pos["y"] + placed_pos["height"])
            if rect1.intersects(rect2):
                conflict = True
                break
                
        if not conflict:
            placed.append(pos)
            
    return placed

# ===== Визуализация =====
def plot_site(site, buildings):
    """Визуализирует участок и здания"""
    fig, ax = plt.subplots(figsize=(12, 10))
    
    # Участок
    x, y = site.exterior.xy
    ax.plot(x, y, 'k-', linewidth=2, label="Граница участка")
    
    # Здания
    for i, building in enumerate(buildings, 1):
        color = SECTION_TYPES[building["section"]]["color"]
        rect = plt.Rectangle(
            (building["x"], building["y"]), 
            building["width"], building["height"],
            linewidth=1, edgecolor=color, facecolor=color + (0.3,),
            label=f"{building['section']} ({i})"
        )
        ax.add_patch(rect)
        ax.text(
            building["x"] + building["width"]/2,
            building["y"] + building["height"]/2,
            f"{i}\n{building['section']}",
            ha="center", va="center", color="black"
        )
    
    ax.set_aspect("equal")
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
    st.pyplot(fig)

# ===== Основной поток =====
if st.button("Рассчитать оптимальное размещение"):
    with st.spinner("Идет расчет..."):
        # Генерация и оптимизация позиций
        positions = generate_positions(site_polygon, selected_sections, margin, step)
        optimized = optimize_placement(positions)
        
        # Расчет общей площади
        total_area = sum(b["area"] for b in optimized)
        
        # Визуализация
        st.success(f"**Оптимальная полезная площадь (ТЭП):** {total_area:.2f} м²")
        st.info(f"**Размещено объектов:** {len(optimized)}")
        plot_site(site_polygon, optimized)
        
        # Вывод таблицы с результатами
        st.subheader("Детали размещения")
        result_table = []
        for i, b in enumerate(optimized, 1):
            result_table.append({
                "№": i,
                "Тип": b["section"],
                "Координаты (X,Y)": f"{b['x']:.1f}, {b['y']:.1f}",
                "Размеры (ШxГ)": f"{b['width']}x{b['height']}",
                "Площадь (ТЭП)": f"{b['area']:.1f} м²"
            })
        st.table(result_table)

# ===== Дополнительная информация =====
st.sidebar.header("О проекте")
st.sidebar.markdown("""
Этот инструмент помогает определить оптимальное расположение зданий на участке с учетом:
- Градостроительных нормативов
- Требований к отступам
- Максимизации полезной площади
""")
