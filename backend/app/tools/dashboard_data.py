def get_dashboard_data():
    return {
        "cards": {
            "customers": 50,
            "orders": 120,
            "products": 35,
            "revenue": 78500
        },

        "bar": {
            "labels": ["Jan", "Feb", "Mar", "Apr"],
            "values": [20, 45, 31, 60]
        },

        "line": {
            "labels": ["Jan", "Feb", "Mar", "Apr"],
            "values": [20, 40, 70, 110]
        },

        "pie": {
            "labels": ["Electronics", "Food", "Books"],
            "values": [40, 30, 30]
        }
    }
