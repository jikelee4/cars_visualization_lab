
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from data_utils import (
    read_source,
    prepare_data,
    make_treemap,
)


st.set_page_config(
    page_title="汽车数据可视化实验",
    page_icon="🚗",
    layout="wide",
)

st.title("汽车数据可视化实验")
st.caption("数据集：04cars data.xls | 平行坐标图 + Treemap")


# --------------------------------------------------
# 1. 加载数据
# --------------------------------------------------
@st.cache_data
def load_data():
    raw = read_source()
    processed = prepare_data(raw)
    return (raw,) + processed


try:
    raw, df, numeric, name_col, cat_col, axes = load_data()
except Exception as exc:
    st.error(f"数据读取失败：{exc}")
    st.info(
        "请确认 04cars data.xls 与 app.py 位于同一文件夹，"
        "并安装 requirements.txt 中的依赖。"
    )
    st.stop()


axis_names = [
    display_name
    for display_name, original_name in axes
    if numeric[display_name].notna().any()
]


if len(raw) < 50:
    st.warning(f"原始数据只有 {len(raw)} 条，不满足至少 50 条记录的要求。")

if len(axis_names) < 10:
    st.error(
        f"当前仅识别到 {len(axis_names)} 个可用数值维度，"
        "请检查数据列名及数据内容，不能直接宣称满足 10 维要求。"
    )


# --------------------------------------------------
# 2. 侧边栏：类别筛选
# --------------------------------------------------
st.sidebar.header("数据筛选")

categories = sorted(df[cat_col].unique().tolist())

selected_categories = st.sidebar.multiselect(
    "选择车辆类别",
    options=categories,
    default=categories,
)

category_mask = df[cat_col].isin(selected_categories)

view_df = df.loc[category_mask].copy()
view_numeric = numeric.loc[category_mask].copy()


# --------------------------------------------------
# 3. 侧边栏：平行坐标图设置
# --------------------------------------------------
st.sidebar.header("平行坐标图设置")

default_axes = axis_names[:min(11, len(axis_names))]

selected_axes = st.sidebar.multiselect(
    "选择数值指标（至少选择 10 个）",
    options=axis_names,
    default=default_axes,
)

# 使用交换控件完成坐标轴位置交换
if len(selected_axes) >= 2:
    with st.sidebar.expander("交换两个坐标轴", expanded=False):
        swap_a = st.selectbox(
            "选择第一个指标",
            options=selected_axes,
            key="swap_axis_a",
        )

        swap_b = st.selectbox(
            "选择第二个指标",
            options=selected_axes,
            index=1,
            key="swap_axis_b",
        )

        if swap_a != swap_b:
            if st.button("交换坐标轴位置"):
                pos_a = selected_axes.index(swap_a)
                pos_b = selected_axes.index(swap_b)

                selected_axes[pos_a], selected_axes[pos_b] = (
                    selected_axes[pos_b],
                    selected_axes[pos_a],
                )

                st.session_state["axis_order"] = selected_axes
                st.rerun()

# 保留已交换的顺序
if (
    "axis_order" in st.session_state
    and set(st.session_state["axis_order"]) == set(selected_axes)
):
    selected_axes = st.session_state["axis_order"]

color_options = ["车辆类别"] + axis_names

color_by = st.sidebar.selectbox(
    "折线颜色依据",
    options=color_options,
    index=0,
)

max_records = max(50, min(428, len(view_df)))
default_records = min(250, len(view_df)) if len(view_df) >= 50 else 50

record_limit = st.sidebar.slider(
    "最多绘制的汽车记录数",
    min_value=50,
    max_value=max_records,
    value=default_records,
    step=25,
)

opacity = st.sidebar.slider(
    "折线透明度",
    min_value=0.05,
    max_value=0.80,
    value=0.25,
    step=0.05,
)


# --------------------------------------------------
# 4. 指标范围筛选
# --------------------------------------------------
with st.sidebar.expander("指标范围筛选", expanded=False):
    ranges = {}

    for axis in selected_axes:
        values = view_numeric[axis].dropna()

        if len(values) > 0 and values.min() < values.max():
            ranges[axis] = st.slider(
                f"{axis} 范围",
                min_value=float(values.min()),
                max_value=float(values.max()),
                value=(float(values.min()), float(values.max())),
                key=f"range_{axis}",
            )

for axis, (lower, upper) in ranges.items():
    keep = (
        view_numeric[axis].between(lower, upper)
        | view_numeric[axis].isna()
    )

    view_df = view_df.loc[keep].copy()
    view_numeric = view_numeric.loc[keep].copy()


# --------------------------------------------------
# 5. 数据概况
# --------------------------------------------------
st.subheader("数据集概况")

col1, col2, col3, col4 = st.columns(4)

col1.metric("原始记录数", len(raw))
col2.metric("原始字段数", raw.shape[1])
col3.metric("筛选后记录数", len(view_df))
col4.metric("可用数值维度", len(axis_names))

st.caption(
    f"汽车名称字段：{name_col} | "
    f"类别字段：{cat_col}"
)


# --------------------------------------------------
# 6. 页面标签
# --------------------------------------------------
tab_parallel, tab_tree, tab_check = st.tabs([
    "平行坐标图",
    "Treemap 树图",
    "数据检查与测试",
])


# ==================================================
# 页面一：平行坐标图
# ==================================================
with tab_parallel:
    st.subheader("汽车多维指标对比")

    if len(selected_axes) < 10:
        st.warning(
            f"当前选择了 {len(selected_axes)} 个指标。"
            "实验要求至少 10 维，请增加指标数量。"
        )

    if len(selected_axes) < 2:
        st.info("至少选择两个数值指标才能绘制平行坐标图。")

    else:
        # 缺失值不填 0：绘图前排除所选指标存在缺失的记录
        valid_mask = view_numeric[selected_axes].notna().all(axis=1)

        plot_numeric = view_numeric.loc[
            valid_mask, selected_axes
        ].copy()

        plot_df = view_df.loc[valid_mask].copy()

        missing_count = len(view_df) - len(plot_df)

        st.caption(
            f"筛选后 {len(view_df)} 条记录；"
            f"由于所选指标缺失而未绘制 {missing_count} 条。"
        )

        # 绘图抽样，固定随机种子，保证重复实验可复现
        if len(plot_numeric) > record_limit:
            sampled_index = plot_numeric.sample(
                n=record_limit,
                random_state=42,
            ).index

            plot_numeric = plot_numeric.loc[sampled_index]
            plot_df = plot_df.loc[sampled_index]

        if len(plot_numeric) == 0:
            st.warning("当前筛选条件下没有可绘制的完整记录。")

        else:
            # 每个指标分别归一化至 [0, 1]，消除量纲差异
            scaled = pd.DataFrame(index=plot_numeric.index)

            for axis in selected_axes:
                lower = plot_numeric[axis].min()
                upper = plot_numeric[axis].max()

                if upper > lower:
                    scaled[axis] = (
                        plot_numeric[axis] - lower
                    ) / (upper - lower)
                else:
                    scaled[axis] = 0.5

            fig = go.Figure()

            # 按类别着色
            if color_by == "车辆类别":
                class_values = plot_df[cat_col].astype(str)

                palette = px.colors.qualitative.Safe

                color_map = {
                    category: palette[i % len(palette)]
                    for i, category in enumerate(
                        sorted(class_values.unique())
                    )
                }

                for idx in plot_numeric.index:
                    category = class_values.loc[idx]

                    details = (
                        f"<b>{plot_df.loc[idx, name_col]}</b><br>"
                        f"类别：{category}<br>"
                        + "<br>".join(
                            f"{axis}: "
                            f"{plot_numeric.loc[idx, axis]:g}"
                            for axis in selected_axes
                        )
                    )

                    fig.add_trace(
                        go.Scatter(
                            x=selected_axes,
                            y=scaled.loc[idx, selected_axes],
                            mode="lines",
                            line=dict(
                                color=color_map[category],
                                width=1.2,
                            ),
                            opacity=opacity,
                            text=[details] * len(selected_axes),
                            hovertemplate=(
                                "%{text}<extra></extra>"
                            ),
                            showlegend=False,
                        )
                    )

                # 添加类别图例
                for category, color in color_map.items():
                    fig.add_trace(
                        go.Scatter(
                            x=[None],
                            y=[None],
                            mode="lines",
                            name=category,
                            line=dict(color=color),
                        )
                    )

            # 按某个数值指标着色
            else:
                values = plot_numeric[color_by]
                lower = values.min()
                upper = values.max()

                for idx in plot_numeric.index:
                    value = float(values.loc[idx])

                    fraction = (
                        (value - lower) / (upper - lower)
                        if upper > lower
                        else 0.5
                    )

                    line_color = px.colors.sample_colorscale(
                        "Viridis",
                        [fraction],
                    )[0]

                    details = (
                        f"<b>{plot_df.loc[idx, name_col]}</b><br>"
                        + "<br>".join(
                            f"{axis}: "
                            f"{plot_numeric.loc[idx, axis]:g}"
                            for axis in selected_axes
                        )
                    )

                    fig.add_trace(
                        go.Scatter(
                            x=selected_axes,
                            y=scaled.loc[idx, selected_axes],
                            mode="lines",
                            line=dict(
                                color=line_color,
                                width=1.2,
                            ),
                            opacity=opacity,
                            text=[details] * len(selected_axes),
                            hovertemplate=(
                                "%{text}<extra></extra>"
                            ),
                            showlegend=False,
                        )
                    )

            fig.update_layout(
                title="汽车多维指标平行坐标视图",
                height=650,
                xaxis_title="汽车数值指标",
                yaxis_title="各指标独立归一化值",
                margin=dict(l=20, r=20, t=60, b=40),
                legend_title_text="车辆类别",
            )

            fig.update_yaxes(range=[-0.03, 1.03])

            st.plotly_chart(
                fig,
                use_container_width=True,
            )

            st.write(
                "**当前坐标轴顺序：**",
                " → ".join(selected_axes),
            )

            st.write("**当前绘制记录示例：**")

            display_data = pd.concat(
                [
                    plot_df[[name_col, cat_col]],
                    plot_numeric,
                ],
                axis=1,
            )

            st.dataframe(
                display_data.head(30),
                use_container_width=True,
            )


# ==================================================
# 页面二：Treemap
# ==================================================
with tab_tree:
    st.subheader("汽车数据层次结构")

    st.write(
        "层级结构：全部车辆 → 车辆类别 → 单辆汽车"
    )

    tree_data = make_treemap(
        df,
        name_col,
        cat_col,
    )

    tree_fig = px.treemap(
        tree_data,
        ids="ids",
        names="labels",
        parents="parents",
        values="values",
        color="group",
        color_discrete_sequence=px.colors.qualitative.Safe,
        custom_data=["group", "values"],
    )

    tree_fig.update_traces(
        root_color="#64748b",
        marker=dict(
            line=dict(
                width=1,
                color="white",
            )
        ),
        hovertemplate=(
            "<b>%{label}</b><br>"
            "父级：%{parent}<br>"
            "车辆数量：%{value}<br>"
            "占父级比例：%{percentParent:.1%}"
            "<extra></extra>"
        ),
        maxdepth=3,
    )

    tree_fig.update_layout(
        height=700,
        margin=dict(t=35, l=10, r=10, b=10),
    )

    st.plotly_chart(
        tree_fig,
        use_container_width=True,
    )

    st.caption(
        f"节点总数：{len(tree_data)}，"
        "包含根节点、类别节点和汽车叶节点。"
    )

    st.markdown("""
    **交互操作说明**

    1. 将鼠标悬停在矩形上，查看名称、父级、数量和占比。
    2. 点击类别矩形，进入该类别查看内部汽车。
    3. 使用图中的层级路径返回上一级。
    4. 不同类别使用不同颜色，白色边界用于区分相邻矩形。
    """)


# ==================================================
# 页面三：数据检查
# ==================================================
with tab_check:
    st.subheader("原始数据预览")

    st.dataframe(
        raw.head(20),
        use_container_width=True,
    )

    st.subheader("缺失值统计")

    missing_stats = pd.DataFrame({
        "字段名称": raw.columns,
        "缺失数量": [
            int(raw[col].isna().sum())
            for col in raw.columns
        ],
        "缺失比例(%)": [
            round(float(raw[col].isna().mean() * 100), 2)
            for col in raw.columns
        ],
    })

    st.dataframe(
        missing_stats,
        use_container_width=True,
    )

    st.subheader("识别出的数值指标")

    axis_stats = pd.DataFrame([
        {
            "图表指标": display_name,
            "原始字段": original_name,
            "有效数值数": int(numeric[display_name].notna().sum()),
            "缺失数": int(numeric[display_name].isna().sum()),
        }
        for display_name, original_name in axes
    ])

    st.dataframe(
        axis_stats,
        use_container_width=True,
    )

    tree_data = make_treemap(
        df,
        name_col,
        cat_col,
    )

    checks = [
        (
            "原始记录不少于 50 条",
            len(raw) >= 50,
            f"{len(raw)} 条",
        ),
        (
            "可用数值维度不少于 10 个",
            len(axis_names) >= 10,
            f"{len(axis_names)} 个",
        ),
        (
            "Treemap 节点不少于 50 个",
            len(tree_data) >= 50,
            f"{len(tree_data)} 个",
        ),
        (
            "Treemap 具有三层层次结构",
            (
                (tree_data["ids"] == "root").any()
                and (tree_data["parents"] == "root").any()
                and tree_data["parents"].astype(str).str.startswith(
                    "category-"
                ).any()
            ),
            "根节点、类别节点、车辆节点",
        ),
    ]

    st.subheader("实验要求自动检查")

    for title, passed, detail in checks:
        if passed:
            st.success(f"通过：{title}（{detail}）")
        else:
            st.error(f"未通过：{title}（{detail}）")

    st.subheader("人工交互测试建议")

    st.markdown("""
    - **维度测试：** 选择至少 10 个指标，检查横轴和指标顺序。
    - **筛选测试：** 只保留一个车辆类别，观察折线数量变化。
    - **范围测试：** 缩小价格或马力范围，观察筛选结果变化。
    - **坐标轴交换：** 交换两个指标，检查轴的位置是否互换。
    - **重叠测试：** 对比不同透明度和不同绘图记录数下的效果。
    - **Treemap 测试：** 悬停查看信息，点击类别进行下钻。
    - **缺失值测试：** 检查 `*` 等内容没有被错误地填充为 0。
    """)
