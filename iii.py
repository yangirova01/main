import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

# Конфигурация страницы
st.set_page_config(layout="wide")
st.title("Генератор домов из секций")

# Доступные типы секций
SECTION_TYPES = {
    "A (26x16 м)": (26, 16),
    "B (28x16 м)": (28, 16),
    "C (26x18 м)": (26, 18),
    "D (18x18 м)": (18, 18)
}

# Функция для создания дома из секций
def generate_house(sections):
    house = []
    current_x = 0
    
    for i, section in enumerate(sections):
        width, height = section
        house.append({
            "position": (current_x, 0),
            "size": (width, height),
            "label": f"Секция {i+1}"
        })
        current_x += width
    
    return house

# Функция для визуализации дома
def plot_house(house):
    fig, ax = plt.subplots(figsize=(12, 6))
    
    total_width = sum(section["size"][0] for section in house)
    max_height = max(section["size"][1] for section in house)
    
    # Отрисовка секций
    for section in house:
        x, y = section["position"]
        width, height = section["size"]
        
        rect = Rectangle((x, y), width, height, 
                        linewidth=2, edgecolor='black', 
                        facecolor=np.random.rand(3,), alpha=0.7)
        ax.add_patch(rect)
        
        # Подписи секций
        ax.text(x + width/2, y + height/2, 
               f"{section['label']}\n{width}x{height} м", 
               ha='center', va='center', fontsize=10)
    
    # Настройки графика
    ax.set_xlim(0, total_width + 5)
    ax.set_ylim(0, max_height + 5)
    ax.set_aspect('equal')
    ax.set_title(f"Дом из {len(house)} секций (Общая длина: {total_width} м)")
    ax.grid(True)
    
    return fig

# Интерфейс Streamlit
col1, col2 = st.columns(2)

with col1:
    st.header("Конфигуратор дома")
    
    # Выбор количества секций
    num_sections = st.slider("Количество секций", 2, 6, 2)
    
    # Выбор типа каждой секции
    sections = []
    for i in range(num_sections):
        section_type = st.selectbox(
            f"Тип секции {i+1}", 
            list(SECTION_TYPES.keys()),
            key=f"section_{i}"
        )
        sections.append(SECTION_TYPES[section_type])
    
    # Кнопка генерации
    if st.button("Сгенерировать дом"):
        house = generate_house(sections)
        
        with col2:
            st.header("Визуализация дома")
            fig = plot_house(house)
            st.pyplot(fig)
            
            # Расчет общей площади
            total_area = sum(w*h for w, h in sections)
            st.success(f"Общая площадь дома: {total_area} кв.м")
            
            # План дома в текстовом виде
            st.subheader("Состав дома:")
            for i, section in enumerate(house):
                st.write(f"{section['label']}: {section['size'][0]}x{section['size'][1]} м")

# Примеры готовых конфигураций
st.markdown("---")
st.subheader("Примеры типовых домов:")

example_cols = st.columns(3)

with example_cols[0]:
    if st.button("Дом 2A (26x16 + 26x16)"):
        house = generate_house([SECTION_TYPES["A (26x16 м)"]]*2)
        st.pyplot(plot_house(house))

with example_cols[1]:
    if st.button("Дом A+B (26x16 + 28x16)"):
        house = generate_house([SECTION_TYPES["A (26x16 м)"], SECTION_TYPES["B (28x16 м)"]])
        st.pyplot(plot_house(house))

with example_cols[2]:
    if st.button("Дом B+C+D (28x16 + 26x18 + 18x18)"):
        house = generate_house([
            SECTION_TYPES["B (28x16 м)"],
            SECTION_TYPES["C (26x18 м)"],
            SECTION_TYPES["D (18x18 м)"]
        ])
        st.pyplot(plot_house(house))
