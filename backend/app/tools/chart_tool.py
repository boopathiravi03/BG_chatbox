def generate_chart(result: dict, chart_type="bar", title="Chart"):
    if not result["success"]:
        return None

    columns = result["columns"]
    rows = result["rows"]

    if len(columns) < 2:
        return None

    labels = []
    values = []

    for row in rows:
        labels.append(str(row[0]))

        try:
            values.append(float(row[1]))
        except:
            values.append(0)

    return {
        "chart_type": chart_type,
        "title": title,
        "labels": labels,
        "values": values
    }
