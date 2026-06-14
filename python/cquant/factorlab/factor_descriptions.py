"""FactorDescriptionManager — 因子结构化描述管理器。

将 Alpha158 / Alpha360 等因子的结构化元数据（分类、公式、经济含义等）
持久化到 DuckDB，供前端因子浏览器、文档生成、AI Advisor 使用。
"""
from __future__ import annotations

import duckdb
import polars as pl


class FactorDescriptionManager:
    """因子结构化描述管理器。

    使用 DuckDB 存储因子描述元数据，支持按名称查询、全量导出、
    以及从内置数据加载默认 Alpha158/360 描述。

    Parameters
    ----------
    db_path : str
        DuckDB 数据库路径，":memory:" 表示纯内存模式。
    """

    _DDL = """\
        CREATE TABLE IF NOT EXISTS meta_factor_descriptions (
            factor_name       VARCHAR PRIMARY KEY,
            category          VARCHAR,
            display_name      VARCHAR,
            description       VARCHAR,
            formula           VARCHAR,
            economic_meaning  VARCHAR,
            use_case          VARCHAR
        )
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self.conn = duckdb.connect(db_path)
        self._init_table()

    # ── 初始化 ──────────────────────────────────────────────────────────────

    def _init_table(self) -> None:
        self.conn.execute(self._DDL)

    # ── 写入 ────────────────────────────────────────────────────────────────

    def write_descriptions(self, df: pl.DataFrame) -> None:
        """写入因子描述（UPSERT 语义：已存在则覆盖）。

        Parameters
        ----------
        df : pl.DataFrame
            必须包含与表结构匹配的 7 列：
            factor_name, category, display_name, description,
            formula, economic_meaning, use_case
        """
        # DuckDB INSERT OR REPLACE 需要列顺序匹配
        self.conn.execute(
            "INSERT OR REPLACE INTO meta_factor_descriptions "
            "SELECT factor_name, category, display_name, description, "
            "       formula, economic_meaning, use_case "
            "FROM df"
        )

    # ── 查询 ────────────────────────────────────────────────────────────────

    def read_descriptions(self, factor_names: list[str]) -> pl.DataFrame:
        """按因子名称列表查询描述。

        Parameters
        ----------
        factor_names : list[str]
            要查询的因子名称列表。

        Returns
        -------
        pl.DataFrame
            匹配的因子描述，未找到的名称不包含在结果中。
        """
        if not factor_names:
            return self._empty_df()
        placeholders = ", ".join(["?" for _ in factor_names])
        result = self.conn.execute(
            f"SELECT * FROM meta_factor_descriptions "
            f"WHERE factor_name IN ({placeholders})",
            factor_names,
        ).fetchdf()
        return pl.from_pandas(result)

    def read_by_category(self, category: str) -> pl.DataFrame:
        """按分类查询因子描述。

        Parameters
        ----------
        category : str
            分类标签，如 "kbar", "rolling_roc", "alpha360" 等。

        Returns
        -------
        pl.DataFrame
        """
        result = self.conn.execute(
            "SELECT * FROM meta_factor_descriptions WHERE category = ?",
            [category],
        ).fetchdf()
        return pl.from_pandas(result)

    def read_all(self) -> pl.DataFrame:
        """读取全部因子描述。

        Returns
        -------
        pl.DataFrame
        """
        result = self.conn.execute(
            "SELECT * FROM meta_factor_descriptions ORDER BY category, factor_name"
        ).fetchdf()
        return pl.from_pandas(result)

    def count(self) -> int:
        """返回因子描述总数。"""
        return self.conn.execute(
            "SELECT count(*) FROM meta_factor_descriptions"
        ).fetchone()[0]

    # ── 删除 ────────────────────────────────────────────────────────────────

    def delete_descriptions(self, factor_names: list[str]) -> None:
        """按因子名称删除描述。"""
        if not factor_names:
            return
        placeholders = ", ".join(["?" for _ in factor_names])
        self.conn.execute(
            f"DELETE FROM meta_factor_descriptions "
            f"WHERE factor_name IN ({placeholders})",
            factor_names,
        )

    # ── 内置数据加载 ────────────────────────────────────────────────────────

    def load_default_descriptions(self) -> int:
        """加载默认的 Alpha158 + Alpha360 因子描述。

        Returns
        -------
        int
            写入的描述条数。
        """
        from cquant.factorlab.factor_descriptions_data import (
            ALPHA158_DESCRIPTIONS,
            ALPHA360_DESCRIPTIONS,
        )

        all_desc = ALPHA158_DESCRIPTIONS + ALPHA360_DESCRIPTIONS
        df = pl.DataFrame(all_desc)
        self.write_descriptions(df)
        return len(all_desc)

    # ── 工具 ────────────────────────────────────────────────────────────────

    @staticmethod
    def _empty_df() -> pl.DataFrame:
        """返回带有正确列名的空 DataFrame。"""
        return pl.DataFrame({
            "factor_name": [],
            "category": [],
            "display_name": [],
            "description": [],
            "formula": [],
            "economic_meaning": [],
            "use_case": [],
        }).cast({
            "factor_name": pl.Utf8,
            "category": pl.Utf8,
            "display_name": pl.Utf8,
            "description": pl.Utf8,
            "formula": pl.Utf8,
            "economic_meaning": pl.Utf8,
            "use_case": pl.Utf8,
        })

    def close(self) -> None:
        """关闭数据库连接。"""
        self.conn.close()

    # ── 上下文管理器 ────────────────────────────────────────────────────────

    def __enter__(self) -> FactorDescriptionManager:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
