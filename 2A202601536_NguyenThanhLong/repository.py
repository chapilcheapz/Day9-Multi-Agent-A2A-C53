"""
Data Loader - Load 9 CSV files từ thư mục data/ vào pandas DataFrames.
Sử dụng mô hình Singleton DataStore để tối ưu bộ nhớ và tốc độ truy vấn cho các agent.
"""

import os
import pandas as pd
from typing import Optional


class DataStore:
    """Singleton lưu trữ toàn bộ dữ liệu CSV đã load."""

    _instance: Optional["DataStore"] = None

    def __new__(cls, data_dir: str = "data"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self, data_dir: str = "data"):
        if self._loaded:
            return
        self.data_dir = data_dir
        self._load_all()
        self._loaded = True

    def _load_all(self):
        """Load tất cả CSV files."""
        self.orders: pd.DataFrame = self._read("olist_orders_dataset.csv")
        self.order_items: pd.DataFrame = self._read("olist_order_items_dataset.csv")
        self.order_payments: pd.DataFrame = self._read("olist_order_payments_dataset.csv")
        self.order_reviews: pd.DataFrame = self._read("olist_order_reviews_dataset.csv")
        self.customers: pd.DataFrame = self._read("olist_customers_dataset.csv")
        self.products: pd.DataFrame = self._read("olist_products_dataset.csv")
        self.sellers: pd.DataFrame = self._read("olist_sellers_dataset.csv")
        self.geolocation: pd.DataFrame = self._read("olist_geolocation_dataset.csv")
        self.category_translation: pd.DataFrame = self._read(
            "product_category_name_translation.csv"
        )

        self._preprocess()

    def _read(self, filename: str) -> pd.DataFrame:
        """Đọc một CSV file từ thư mục data_dir."""
        path = os.path.join(self.data_dir, filename)
        return pd.read_csv(path)

    def _preprocess(self):
        """Tiền xử lý dữ liệu: ép kiểu datetime cho các cột thời gian."""
        datetime_cols = [
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ]
        for col in datetime_cols:
            if col in self.orders.columns:
                self.orders[col] = pd.to_datetime(self.orders[col], errors="coerce")

        if "shipping_limit_date" in self.order_items.columns:
            self.order_items["shipping_limit_date"] = pd.to_datetime(
                self.order_items["shipping_limit_date"], errors="coerce"
            )

    def get_order(self, order_id: str) -> Optional[pd.Series]:
        """Lấy thông tin đơn hàng theo order_id."""
        rows = self.orders[self.orders["order_id"] == order_id]
        if rows.empty:
            return None
        return rows.iloc[0]

    def get_order_items(self, order_id: str) -> pd.DataFrame:
        """Lấy danh sách các sản phẩm (items) trong đơn hàng."""
        return self.order_items[self.order_items["order_id"] == order_id]

    def get_order_payments(self, order_id: str) -> pd.DataFrame:
        """Lấy các dòng thanh toán (payments) của đơn hàng."""
        return self.order_payments[self.order_payments["order_id"] == order_id]

    def get_customer(self, customer_id: str) -> Optional[pd.Series]:
        """Lấy thông tin khách hàng theo customer_id."""
        rows = self.customers[self.customers["customer_id"] == customer_id]
        if rows.empty:
            return None
        return rows.iloc[0]

    def get_orders_by_customer_unique_id(self, customer_unique_id: str) -> pd.DataFrame:
        """Lấy tất cả các đơn hàng thuộc cùng một customer_unique_id."""
        customer_ids = self.customers[
            self.customers["customer_unique_id"] == customer_unique_id
        ]["customer_id"].tolist()
        return self.orders[self.orders["customer_id"].isin(customer_ids)]

    def get_product(self, product_id: str) -> Optional[pd.Series]:
        """Lấy thông tin sản phẩm theo product_id."""
        rows = self.products[self.products["product_id"] == product_id]
        if rows.empty:
            return None
        return rows.iloc[0]

    def get_seller(self, seller_id: str) -> Optional[pd.Series]:
        """Lấy thông tin người bán (seller) theo seller_id."""
        rows = self.sellers[self.sellers["seller_id"] == seller_id]
        if rows.empty:
            return None
        return rows.iloc[0]

    def get_category_translation(self, category_name: str) -> Optional[str]:
        """Dịch tên danh mục sản phẩm từ tiếng Bồ Đào Nha sang tiếng Anh."""
        rows = self.category_translation[
            self.category_translation["product_category_name"] == category_name
        ]
        if rows.empty:
            return category_name
        return rows.iloc[0]["product_category_name_english"]
