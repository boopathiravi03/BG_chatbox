def generate_flowchart():
    """
    Returns Mermaid ER Diagram for the sample database.
    """

    return """
erDiagram

    CUSTOMERS ||--o{ ORDERS : places
    PRODUCTS ||--o{ ORDERS : contains
    PRODUCTS ||--|| INVENTORY : has

    CUSTOMERS {
        int customer_id PK
        string name
        string email
        string city
    }

    PRODUCTS {
        int product_id PK
        string name
        string category
        float price
    }

    ORDERS {
        int order_id PK
        int customer_id FK
        int product_id FK
        int quantity
        date order_date
    }

    INVENTORY {
        int inventory_id PK
        int product_id FK
        int stock
    }
"""
