
import unittest
import pandas as pd

from data_utils import (
    read_source,
    prepare_data,
    make_treemap,
    clean_numeric,
)


class TestCarVisualization(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = read_source()

        (
            cls.df,
            cls.numeric,
            cls.name_col,
            cls.cat_col,
            cls.axes,
        ) = prepare_data(cls.raw)

    def test_record_count(self):
        """实验要求：至少 50 条汽车记录。"""
        self.assertGreaterEqual(len(self.raw), 50)

    def test_numeric_dimensions(self):
        """实验要求：至少 10 个数值维度。"""
        self.assertGreaterEqual(
            len(self.axes),
            10,
            msg=f"当前识别到的维度：{self.axes}",
        )

    def test_treemap_node_count(self):
        """实验要求：至少 50 个节点。"""
        tree = make_treemap(
            self.df,
            self.name_col,
            self.cat_col,
        )

        self.assertGreaterEqual(len(tree), 50)

    def test_treemap_hierarchy(self):
        """验证根节点、类别节点和汽车节点。"""
        tree = make_treemap(
            self.df,
            self.name_col,
            self.cat_col,
        )

        ids = set(tree["ids"])
        self.assertIn("root", ids)

        category_ids = set(
            tree.loc[
                tree["parents"] == "root",
                "ids",
            ]
        )

        self.assertGreater(len(category_ids), 0)

        vehicle_nodes = tree[
            tree["parents"].isin(category_ids)
        ]

        self.assertGreater(len(vehicle_nodes), 0)

    def test_missing_values_are_not_zero_filled(self):
        """验证缺失值不会被错误地替换成 0。"""
        source = pd.Series(["*", "12", "", "N/A"])
        result = clean_numeric(source)

        self.assertTrue(pd.isna(result.iloc[0]))
        self.assertEqual(result.iloc[1], 12)
        self.assertTrue(pd.isna(result.iloc[2]))
        self.assertTrue(pd.isna(result.iloc[3]))

    def test_treemap_weights(self):
        """每辆汽车计 1，根节点数量等于汽车记录数。"""
        tree = make_treemap(
            self.df,
            self.name_col,
            self.cat_col,
        )

        root = tree.loc[tree["ids"] == "root"].iloc[0]

        self.assertEqual(
            int(root["values"]),
            len(self.df),
        )

        leaves = tree[
            tree["ids"].astype(str).str.startswith("vehicle-")
        ]

        self.assertTrue((leaves["values"] == 1).all())


if __name__ == "__main__":
    unittest.main(verbosity=2)