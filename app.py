import streamlit as st
import pandas as pd
import cianparser

from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import time

###############################################################################
# 1. Вспомогательные функции
###############################################################################

def reverse_geocode_city(lat, lon):
    """
    Обратное геокодирование (reverse geocoding) с помощью Nominatim (OpenStreetMap).
    Возвращаем название города (city / town / municipality / region), если удалось найти.
    Иначе None.
    """
    geolocator = Nominatim(user_agent="cian_app")
    loc = geolocator.reverse((lat, lon), addressdetails=True)
    if not loc or not loc.raw:
        return None

    address_dict = loc.raw.get("address", {})
    city = address_dict.get("city")
    if not city:
        city = address_dict.get("town")
    if not city:
        city = address_dict.get("municipality")
    if not city:
        city = address_dict.get("state") or address_dict.get("region")

    return city

def parse_cian_for_city(city_name):
    """
    Парсим cianparser:
      - deal_type='sale'
      - rooms='all'
      - location=city_name
      - start_page=1, end_page=2
    Возвращаем список словарей объявлений (list of dict).
    """
    parser = cianparser.CianParser(location=city_name)
    data = parser.get_flats(
        deal_type="sale",
        rooms="all",
        with_saving_csv=False,
        additional_settings={
            "start_page": 1,
            "end_page": 2,
            "sort_by": "price_from_min_to_max",
        }
    )
    return data

def geocode_listing_address(row):
    """
    Из полей объявления (street, house_number, district, location) собираем адрес
    и геокодируем. Возвращаем (lat, lon) или None, если не удалось.
    """
    parts = []
    if row.get("street"):
        parts.append(str(row["street"]))
    if row.get("house_number"):
        parts.append(str(row["house_number"]))
    if row.get("district"):
        parts.append(str(row["district"]))
    if row.get("location"):
        parts.append(str(row["location"]))

    addr_str = ", ".join(parts).strip()
    if not addr_str:
        return None

    geolocator = Nominatim(user_agent="cian_app")
    loc = geolocator.geocode(addr_str)
    if loc:
        return (loc.latitude, loc.longitude)
    return None

###############################################################################
# 2. Streamlit-приложение
###############################################################################

def main():
    st.title("Парсинг Циан: вводим координаты → ищем в радиусе (до 10 объявлений)")

    # Вводим широту и долготу пользователя
    lat_user = st.number_input("Широта (latitude)", value=55.75, step=0.01, format="%.6f")
    lon_user = st.number_input("Долгота (longitude)", value=37.61, step=0.01, format="%.6f")

    # Слайдер радиуса
    radius_km = st.slider("Радиус поиска (км)", min_value=0.5, max_value=10.0, step=0.5, value=1.0)

    if st.button("Найти объявления"):
        st.write(f"Координаты пользователя: lat={lat_user}, lon={lon_user}")
        st.write(f"Ищем объявления в радиусе <= {radius_km} км")

        # 1) Определяем город (reverse geocoding -> city)
        city_name = reverse_geocode_city(lat_user, lon_user)
        if not city_name:
            st.error("Не удалось определить город по этим координатам. Попробуйте другие!")
            return
        st.info(f"Определённый город: {city_name}")

        # 2) Парсим Циан (для этого города)
        st.write("Парсим Циан (2 страницы, sale, all rooms)...")
        with st.spinner("Сбор данных cianparser..."):
            data = parse_cian_for_city(city_name)

        total_ads = len(data)
        st.write(f"Всего объявлений получено: {total_ads}")
        if not data:
            return

        # 3) Превращаем в DataFrame
        df = pd.DataFrame(data)

        # 4) Геокодируем каждое объявление, считаем расстояние
        st.write("Геокодируем каждое объявление и вычисляем расстояние...")
        df["listing_lat"] = None
        df["listing_lon"] = None
        df["distance_km"] = None

        for i in range(len(df)):
            row = df.iloc[i].to_dict()
            coords_ad = geocode_listing_address(row)
            if coords_ad:
                df.at[i, "listing_lat"] = coords_ad[0]
                df.at[i, "listing_lon"] = coords_ad[1]
                dist_km = geodesic((lat_user, lon_user), coords_ad).km
                df.at[i, "distance_km"] = dist_km
            else:
                df.at[i, "distance_km"] = 999999  # Ставим очень большое расстояние
            time.sleep(0.3)  # чтобы не спамить Nominatim

        # 5) Фильтруем по radius_km
        df_filtered = df[df["distance_km"] <= radius_km].copy()
        df_filtered.sort_values(by="distance_km", ascending=True, inplace=True)

        count_filtered = len(df_filtered)
        st.success(f"Объявлений в радиусе {radius_km} км: {count_filtered}")

        if count_filtered == 0:
            st.warning("Нет объявлений в заданном радиусе!")
            return

        # 6) Берём максимум 10
        top_10 = df_filtered.head(10)

        # 7) Считаем среднюю цену (price) и цену за м² (если total_meters > 0)
        if "price" not in top_10.columns:
            st.warning("В данных нет поля 'price'.")
            st.dataframe(top_10)
            return

        avg_price = top_10["price"].mean()

        if "total_meters" in top_10.columns:
            top_10["price_per_m2"] = None
            valid_subset = top_10[top_10["total_meters"] > 0].copy()
            if not valid_subset.empty:
                valid_subset["price_per_m2"] = valid_subset["price"] / valid_subset["total_meters"]
                avg_price_m2 = valid_subset["price_per_m2"].mean()
                st.write(f"**Средняя цена (<= {radius_km} км)**: {int(avg_price):,} руб.\n"
                         f"**Средняя цена за м²**: {int(avg_price_m2):,} руб/м²")
            else:
                st.write(f"**Средняя цена (<= {radius_km} км)**: {int(avg_price):,} руб.")
                st.write("Не удалось вычислить цену за м², т.к. нет валидных total_meters.")
        else:
            st.write(f"**Средняя цена (<= {radius_km} км)**: {int(avg_price):,} руб.")
            st.write("Не удалось вычислить цену за м² (нет поля total_meters).")

        st.markdown("### До 10 ближайших объявлений")
        cols = ["distance_km", "price", "total_meters", "district", "street",
                "house_number", "location", "url"]
        cols = [c for c in cols if c in top_10.columns]
        st.dataframe(top_10[cols].reset_index(drop=True))


if __name__ == "__main__":
    main()