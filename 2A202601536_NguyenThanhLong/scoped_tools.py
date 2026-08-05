import json
from typing import Dict, Any, List
from src.repository import DataStore

class ScopedTools:
    def __init__(self, data_store: DataStore):
        self.data_store = data_store

    def get_order_details(self, order_id: str) -> str:
        """Lấy thông tin chung của đơn hàng"""
        order = self.data_store.get_order(order_id)
        if order is None:
            return json.dumps({"error": "Order not found"})
        # Remove empty fields for brevity
        return json.dumps({k: v for k, v in order.items() if v is not None})

    def get_order_items(self, order_id: str) -> str:
        """Lấy danh sách các mặt hàng trong đơn hàng"""
        items = self.data_store.get_order_items(order_id)
        if items.empty:
            return "[]"
        # Convert to records and remove NaNs
        records = items.to_dict(orient="records")
        for r in records:
            for k in list(r.keys()):
                if r[k] != r[k] or r[k] is None: # check for NaN
                    del r[k]
        return json.dumps(records, default=str)

    def get_order_payments(self, order_id: str) -> str:
        """Lấy danh sách các thanh toán của đơn hàng"""
        payments = self.data_store.get_order_payments(order_id)
        if payments.empty:
            return "[]"
        return json.dumps(payments.to_dict(orient="records"), default=str)

    def get_customer_info(self, customer_id: str) -> str:
        """Lấy thông tin khách hàng bằng customer_id"""
        cust = self.data_store.customers[self.data_store.customers["customer_id"] == customer_id]
        if cust.empty:
            return json.dumps({"error": "Customer not found"})
        return json.dumps(cust.iloc[0].to_dict(), default=str)

    def get_related_orders_for_customer(self, customer_unique_id: str, exclude_order_id: str) -> str:
        """Lấy các order_id khác của cùng customer_unique_id"""
        custs = self.data_store.customers[self.data_store.customers["customer_unique_id"] == customer_unique_id]
        if custs.empty:
            return "[]"
        all_orders = self.data_store.orders[self.data_store.orders["customer_id"].isin(custs["customer_id"])]
        all_order_ids = all_orders["order_id"].tolist()
        related = [oid for oid in all_order_ids if oid != exclude_order_id]
        return json.dumps(related[:5])
