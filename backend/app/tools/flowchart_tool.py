from app.tools.get_schema import get_schema


def generate_er_diagram():
    schema = get_schema()

    mermaid = "erDiagram\n"

    relationships = {
        "orders": [
            ("customer_id", "customers"),
            ("product_id", "products")
        ],
        "inventory": [
            ("product_id", "products")
        ]
    }

    for table, columns in schema.items():
        mermaid += f"    {table.upper()} {{\n"

        for column, datatype in columns.items():
            mermaid += f"        {datatype} {column}\n"

        mermaid += "    }\n\n"

    for table, refs in relationships.items():
        for _, ref_table in refs:
            mermaid += f"    {ref_table.upper()} ||--o{{ {table.upper()} : contains\n"

    return mermaid
