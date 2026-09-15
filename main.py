"""OCI AI Data Platform Lab Console - メインアプリケーションエントリポイント.

No.1-SQL-Assist の main.py をベースに、AIDP lab 向けに改造した Gradio アプリ。
保持する機能（No.1-SQL-Assist 由来）:
- 環境設定（OCI GenAI 認証 / Autonomous DB 管理 / Embedding テスト / OpenAI・LLM 設定・API key）
- データベース管理
- AI チャット（OCI GenAI）

追加する機能（lab 固有、utils/lab_setup_util.py）:
- Lab DB 初期化（source_01 / gold_01 ユーザー作成、権限付与、REST 有効化、サンプルデータ読込）
- AIDP 設定ガイド（Terraform では自動化できない手動手順のチェックリスト）
- OAC 接続（OAC API での接続作成 / ウォレットのダウンロード）
- ヘルスチェック
"""

import argparse
import logging
import os
import warnings
from typing import Optional

import gradio as gr
import oracledb
from dotenv import find_dotenv, load_dotenv
from gradio.themes import Default, GoogleFont

from utils.auth_util import do_auth
from utils.css_util import custom_css
from utils.llm_model_util import (
    bind_llm_model_settings_events,
    reset_model_dropdown_registry,
)
from utils.management_util import build_management_tab
from utils.chat_util import build_oci_chat_test_tab
from utils.settings_tab import build_settings_tab
from utils.lab_setup_util import (
    build_aidp_guide_tab,
    build_health_tab,
    build_lab_db_setup_tab,
    build_oac_setup_tab,
)
from utils.notebook_code_util import build_notebook_code_tab
from utils.vpd_util import OracleConnectionParts, parse_oracle_connection_string

# Suppress NumPy warnings related to longdouble
warnings.filterwarnings(
    "ignore", message=".*longdouble.*", category=RuntimeWarning
)
warnings.filterwarnings(
    "ignore", message=".*is deprecated.*", category=DeprecationWarning
)

# Load environment variables
load_dotenv(find_dotenv())
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger.info("Environment variables loaded")


# Lazy database connection pool
class LazyPool:
    """必要になるまで遅延初期化される oracledb 接続プール."""

    def __init__(self, config_name: str, **kwargs):
        self._pool = None
        self._kwargs = kwargs
        self._config_name = config_name
        self._lock = __import__("threading").RLock()

    def _ensure(self):
        with self._lock:
            if self._pool is None:
                dsn = self._kwargs.get("dsn")
                if not dsn or not str(dsn).strip():
                    logger.warning(f"{self._config_name} is not set")
                    raise RuntimeError(f"{self._config_name} is not set")
                logger.info("Creating DB connection pool")
                self._pool = oracledb.create_pool(**self._kwargs)

    def acquire(self):
        self._ensure()
        try:
            conn = self._pool.acquire()
            try:
                conn.ping()
            except Exception as e:
                logger.error(f"conn.ping failed, resetting pool: {e}")
                self.reset()
                conn = self._pool.acquire()
                conn.ping()
            return conn
        except Exception as e:
            logger.error(f"acquire failed, resetting pool: {e}")
            self.reset()
            conn = self._pool.acquire()
            conn.ping()
            return conn

    def close(self):
        with self._lock:
            if self._pool is not None:
                try:
                    self._pool.close()
                finally:
                    self._pool = None

    def reset(self):
        with self._lock:
            if self._pool is not None:
                try:
                    self._pool.close()
                except Exception as e:
                    logger.error(f"pool.close error: {e}")
            self._pool = None
            logger.info("Recreating DB connection pool")
            self._pool = oracledb.create_pool(**self._kwargs)

    def healthy(self) -> bool:
        try:
            with self.acquire() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1 FROM DUAL")
                    _ = cursor.fetchmany(size=1)
            return True
        except Exception as e:
            logger.error(f"healthy check failed: {e}")
            return False

    def __getattr__(self, name):
        self._ensure()
        return getattr(self._pool, name)


def _build_pool_kwargs(conn_env: str, wallet_env: str) -> dict:
    """接続文字列 (user/password@dsn) とウォレット環境変数からプール引数を構築する."""
    raw = os.environ.get(conn_env, "")
    if not raw or raw == "TODO":
        logger.warning(f"{conn_env} is not set")
        return {}
    try:
        parts: OracleConnectionParts = parse_oracle_connection_string(raw)
    except Exception as e:
        logger.error(f"parse {conn_env} failed: {e}")
        return {}
    kwargs = dict(
        user=parts.username,
        password=parts.password,
        dsn=parts.dsn,
        min=0,
        max=8,
        increment=1,
        timeout=30,
        getmode=oracledb.POOL_GETMODE_WAIT,
    )
    wallet_dir = os.environ.get(wallet_env, "")
    if wallet_dir and os.path.isdir(wallet_dir):
        kwargs["wallet_location"] = wallet_dir
    else:
        logger.warning(f"{wallet_env} ({wallet_dir}) not found; wallet なしで接続します")
    return kwargs


atp_kwargs = _build_pool_kwargs("ORACLE_26AI_CONNECTION_STRING", "WALLET_ATP_DIR")
lh_kwargs = _build_pool_kwargs("ORACLE_LAKEHOUSE_CONNECTION_STRING", "WALLET_LH_DIR")

# アプリ自体の状態（OCI 認証情報・設定）を保持するプール。
# No.1-SQL-Assist と同様に ATP の ADMIN ユーザー接続を使用する。
pool = LazyPool("ORACLE_26AI_CONNECTION_STRING", **atp_kwargs)
lakehouse_pool = LazyPool("ORACLE_LAKEHOUSE_CONNECTION_STRING", **lh_kwargs)
logger.info(
    "Database pools configured (atp=%s, lakehouse=%s)",
    bool(atp_kwargs),
    bool(lh_kwargs),
)


# Configure Gradio theme
theme = Default(
    spacing_size="sm",
    font=[
        GoogleFont(name="Noto Sans JP"),
        GoogleFont(name="Roboto"),
        "Arial",
        "sans-serif",
    ],
).set()

# Create Gradio interface
reset_model_dropdown_registry()
with gr.Blocks(
    css=custom_css, theme=theme, title="OCI AI Data Platform Lab Console"
) as app:
    gr.Markdown(value="# OCI AI Data Platform Lab Console ", elem_classes="main_Header")
    gr.Markdown(
        value="### ATP + Autonomous AI Lakehouse + AIDP + OAC のワンクリック lab 環境。"
        "Terraform では自動化できない初期化をこのコンソールから実行できます。",
        elem_classes="sub_Header",
    )

    with gr.Tabs() as primary_tabs:
        with gr.TabItem(label="Lab DB 初期化") as lab_db_tab:
            build_lab_db_setup_tab()

        with gr.TabItem(label="AIDP 設定ガイド") as aidp_guide_tab:
            build_aidp_guide_tab()

        with gr.TabItem(label="AIDP Notebook コード") as notebook_code_tab:
            build_notebook_code_tab()

        with gr.TabItem(label="OAC 接続") as oac_tab:
            build_oac_setup_tab()

        with gr.TabItem(label="ヘルスチェック") as health_tab:
            build_health_tab()

        with gr.TabItem(label="環境設定") as settings_tab:
            llm_model_settings_controls = build_settings_tab(pool)

        with gr.TabItem(label="データベース管理") as management_tab:
            build_management_tab(pool, None)

        with gr.TabItem(label="AI チャット") as chat_tab:
            build_oci_chat_test_tab(pool)

    bind_llm_model_settings_events(app, llm_model_settings_controls)

    gr.Markdown(
        value="### 本ソフトウェアは検証評価用です。日常利用のための基本機能は備えていない点につきましてご理解をよろしくお願い申し上げます。",
        elem_classes="sub_Header",
    )
    gr.Markdown(value="### Developed by Oracle Japan", elem_classes="sub_Header")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Launch AIDP lab console web application")
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host address to bind the server (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port number to run the server (default: 8080)",
    )
    args = parser.parse_args()

    app.queue()
    app.launch(
        server_name=args.host,
        server_port=args.port,
        max_threads=200,
        show_api=False,
        auth=do_auth,
    )
