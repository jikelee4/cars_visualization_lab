
from pathlib import Path
import re

import pandas as pd


# 默认从项目文件夹中读取汽车数据
DATA_FILE = Path(__file__).resolve().parent / "04cars data.xls"


def normalize_name(value):
    """去除列名中的空格、标点等，方便匹配字段。"""
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def read_source(path=DATA_FILE):
    """读取 .xls 文件，并规范化列名。"""
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"找不到数据文件：{path}\n"
            "请将 04cars data.xls 放到 app.py 同一目录。"
        )

    df = pd.read_excel(path, engine="xlrd")
    df.columns = [str(col).strip() for col in df.columns]

    if df.empty:
        raise ValueError("汽车数据集为空，请检查原始文件。")

    return df


def find_column(columns, candidates):
    """根据候选名称识别数据列。"""
    normalized = {normalize_name(col): col for col in columns}

    for candidate in candidates:
        key = normalize_name(candidate)
        if key in normalized:
            return normalized[key]

    # 对存在轻微命名差异的字段进行模糊匹配
    for col in columns:
        key = normalize_name(col)
        for candidate in candidates:
            candidate_key = normalize_name(candidate)
            if candidate_key and candidate_key in key:
                return col

    return None


def clean_numeric(series):
    """
    转换数值字段。
    无法转换的内容按缺失值处理，而不是填充为 0。
    """
    s = series.astype("string").str.strip()

    s = s.replace({
        "*": pd.NA,
        "": pd.NA,
        "nan": pd.NA,
        "None": pd.NA,
        "N/A": pd.NA,
        "NA": pd.NA,
        "-": pd.NA,
    })

    # 去除千位分隔符和货币符号
    s = s.str.replace(",", "", regex=False)
    s = s.str.replace("$", "", regex=False)
    s = s.str.replace("¥", "", regex=False)

    return pd.to_numeric(s, errors="coerce")


def prepare_data(raw):
    """
    返回：
    df       清洗后的原始表
    numeric  规范化后的数值指标表
    name_col 汽车名称列
    cat_col  分类列
    axes     [(显示名称, 原始列名), ...]
    """
    df = raw.copy()

    # 1. 识别汽车名称
    name_col = find_column(
        df.columns,
        ["Vehicle Name", "Car Name", "Vehicle", "Name", "Model"]
    )

    if name_col is None:
        manufacturer = find_column(
            df.columns, ["Manufacturer", "Make", "Brand"]
        )
        model = find_column(df.columns, ["Model"])

        if manufacturer and model and manufacturer != model:
            df["Vehicle Name"] = (
                df[manufacturer].fillna("").astype(str).str.strip()
                + " "
                + df[model].fillna("").astype(str).str.strip()
            ).str.strip()

            name_col = "Vehicle Name"
        else:
            # 无法识别时退回第一列
            name_col = df.columns[0]

    df[name_col] = (
        df[name_col]
        .fillna("Unknown vehicle")
        .astype(str)
        .str.strip()
    )

    df.loc[
        df[name_col].isin(["", "nan", "None"]),
        name_col
    ] = "Unknown vehicle"

    # 2. 识别车辆类别
    cat_col = find_column(
        df.columns,
        [
            "Vehicle Type", "Type", "Category",
            "Vehicle Class", "Class", "Body Style"
        ]
    )

    if cat_col == name_col:
        cat_col = None

    # 如果没有明确的类别列，寻找适合分组的文本列
    if cat_col is None:
        for col in df.columns:
            if col == name_col:
                continue

            values = df[col].dropna()
            unique_count = values.nunique()

            if (
                2 <= unique_count <= min(50, max(2, len(df) // 5))
                and not pd.api.types.is_numeric_dtype(df[col])
            ):
                cat_col = col
                break

    # 没有可用分类字段时，保留统一类别并明确提示
    if cat_col is None:
        cat_col = "Vehicle Category"
        df[cat_col] = "Unclassified"

    df[cat_col] = (
        df[cat_col]
        .fillna("Unclassified")
        .astype(str)
        .str.strip()
    )

    df.loc[
        df[cat_col].isin(["", "nan", "None"]),
        cat_col
    ] = "Unclassified"

    # 3. 优先识别汽车数据中常见的数值指标
    aliases = [
        ("Retail Price", ["Retail Price", "Price", "MSRP"]),
        ("Dealer Cost", ["Dealer Cost", "Invoice"]),
        ("Engine Size", ["Engine Size", "Engine Size (l)", "Displacement"]),
        ("Cylinders", ["Cylinders", "Cylinder", "Cyl"]),
        ("Horsepower", ["Horsepower", "HP"]),
        ("City MPG", ["City MPG", "MPG.city", "MPG City"]),
        ("Highway MPG", ["Highway MPG", "Hwy MPG", "MPG.highway"]),
        ("Weight", ["Weight", "Curb Weight"]),
        ("Wheel Base", ["Wheel Base", "Wheelbase"]),
        ("Length", ["Length", "Len"]),
        ("Width", ["Width"]),
        ("RPM", ["RPM"]),
        ("Fuel Tank Capacity", ["Fuel Tank Capacity", "Fuel.tank.capacity"]),
        ("Passengers", ["Passengers"]),
    ]

    axes = []
    used_columns = set()
    numeric_columns = {}

    # 避免把汽车名称、类别列当作指标
    excluded = {name_col, cat_col}

    for display_name, candidates in aliases:
        col = find_column(df.columns, candidates)

        if col is None or col in used_columns or col in excluded:
            continue

        values = clean_numeric(df[col])

        # 排除有效数值过少的字段
        min_valid = min(50, max(1, len(df) // 2))

        if values.notna().sum() >= min_valid:
            axes.append((display_name, col))
            numeric_columns[display_name] = values
            used_columns.add(col)

    # 4. 自动补充其他数值列
    for col in df.columns:
        if col in used_columns or col in excluded:
            continue

        values = clean_numeric(df[col])
        min_valid = min(50, max(1, len(df) // 2))

        if values.notna().sum() >= min_valid:
            display_name = str(col)

            # 避免显示名称冲突
            if display_name in numeric_columns:
                display_name = f"{display_name} ({col})"

            axes.append((display_name, col))
            numeric_columns[display_name] = values
            used_columns.add(col)

    numeric = pd.DataFrame(numeric_columns, index=df.index)

    return df, numeric, name_col, cat_col, axes


def make_treemap(df, name_col, cat_col):
    """
    构建三层 Treemap：
    根节点 -> 车辆类别 -> 单辆汽车。

    每辆汽车记录的权重为 1。
    使用独立 ID，避免同名车辆节点冲突。
    """
    rows = [
        {
            "ids": "root",
            "labels": "全部车辆",
            "parents": "",
            "values": len(df),
            "group": "全部车辆",
        }
    ]

    categories = df[cat_col].fillna("Unclassified").astype(str)
    names = df[name_col].fillna("Unknown vehicle").astype(str)

    for cat_index, cat in enumerate(
        sorted(categories.unique(), key=str.lower)
    ):
        mask = categories == cat

        category_id = f"category-{cat_index}"

        rows.append({
            "ids": category_id,
            "labels": cat,
            "parents": "root",
            "values": int(mask.sum()),
            "group": cat,
        })

        for idx in df.index[mask]:
            rows.append({
                "ids": f"vehicle-{idx}",
                "labels": str(names.loc[idx]),
                "parents": category_id,
                "values": 1,
                "group": cat,
            })

    return pd.DataFrame(rows)