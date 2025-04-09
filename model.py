import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Polygon, Point
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
import matplotlib.pyplot as plt

# Параметры из документа (примерные значения)
SECTION_SIZES = {
    'A': (15, 12),
    'B': (20, 10),
    'C': (25, 15)
}
GREEN_NORM = 0.3  # 30% озеленение
PARKING_NORM = 0.1  # 10% от площади застройки

def generate_dataset(num_samples=1000):
    data = []
    for _ in range(num_samples):
        # Генерация случайных входных параметров
        total_area = np.random.uniform(1000, 10000)
        building_area = np.random.uniform(100, min(3000, total_area*0.7))
        floors = np.random.randint(1, 10)
        
        # Генерация возможных вариантов планировки
        sections = generate_sections(building_area, floors)
        layout = optimize_layout(total_area, building_area, sections)
        
        if layout:
            efficiency = calculate_efficiency(layout)
            data.append({
                'total_area': total_area,
                'building_area': building_area,
                'floors': floors,
                'sections': len(sections),
                'section_types': '_'.join([s[0] for s in sections]),
                'efficiency': efficiency,
                'geometry': layout['geometry']
            })
    
    return pd.DataFrame(data)

def generate_sections(building_area, floors):
    sections = []
    remaining_area = building_area / floors  # Площадь на этаж
    
    while remaining_area > 0:
        section_type, (w, h) = np.random.choice(list(SECTION_SIZES.items()))
        section_area = w * h
        if section_area <= remaining_area:
            sections.append((section_type, w, h))
            remaining_area -= section_area
    
    return sections

def optimize_layout(total_area, building_area, sections):
    # Упрощенная логика оптимизации (реальная будет сложнее)
    try:
        # Создаем полигон участка (квадрат для примера)
        plot = Polygon([(0, 0), (np.sqrt(total_area), 0), 
                       (np.sqrt(total_area), np.sqrt(total_area)), 
                       (0, np.sqrt(total_area))])
        
        # Размещаем секции
        buildings = []
        x, y = 0, 0
        for section in sections:
            typ, w, h = section
            buildings.append({
                'type': typ,
                'geometry': Polygon([(x, y), (x+w, y), (x+w, y+h), (x, y+h)])
            })
            x += w + 5  # Отступ между секциями
        
        # Расчет озеленения и парковки
        green_area = total_area * GREEN_NORM
        parking_area = building_area * PARKING_NORM * (1 + 0.1*floors)
        
        return {
            'plot': plot,
            'buildings': buildings,
            'green_area': green_area,
            'parking_area': parking_area,
            'geometry': plot  # Для датасета
        }
    except:
        return None

def calculate_efficiency(layout):
    # Расчет эффективности использования пространства
    used_area = sum([b['geometry'].area for b in layout['buildings']])
    return used_area / layout['plot'].area

# Генерация и сохранение датасета
dataset = generate_dataset(100)
dataset.to_csv('urban_planning_dataset.csv', index=False)

# Обучение модели
X = dataset[['total_area', 'building_area', 'floors']]
y = dataset['efficiency']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
model = RandomForestRegressor()
model.fit(X_train, y_train)
