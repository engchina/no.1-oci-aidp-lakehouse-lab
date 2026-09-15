"""Lab 環境セットアップユーティリティモジュール.

Terraform では完全に自動化できない部分を、Gradio コンソールから
ワンクリックで実行するための機能を提供します。

- Lab DB 初期化
  - ATP へ source_01 ユーザー作成（権限付与 / REST 有効化）
  - AI Lakehouse へ gold_01 ユーザー作成（同左）
  - サンプル航空会社データ（AIRLINE_SAMPLE 25件）の読込
- AIDP 設定ガイド
  - AIDP ポリシー付与 / external catalog / medallion schema /
    LLM 設定 など、Workbench 上での手動作業のチェックリスト。
    必要な値（DSN・ユーザー名・Delta パス等）をコピー用に表示する。
- OAC 接続
  - OAC REST API によるデータ接続の作成（実験的）
  - AI Lakehouse ウォレットのダウンロード
- ヘルスチェック
  - 各リソースの疎通確認
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import gradio as gr
import oracledb
import requests
from dotenv import find_dotenv, get_key, load_dotenv, set_key

from utils.vpd_util import parse_oracle_connection_string

# モジュール読み込み時に .env を反映する（main.py からも読み込まれるが保険）
load_dotenv(find_dotenv())

logger = logging.getLogger(__name__)

# 参照資料（tmp/qiita/ にダウンロード済みの Qiita ハンズオン記事のタスク番号）
_ARTICLE_REF = (
    "参考: Qiita「【ハンズオン】AI × データ基盤：OCI AI Data Platform で実現する"
    "統合分析パイプラインの構築」（前編 Step1〜Step2 / 後編 Step3）"
)

_SAMPLE_TABLE = "AIRLINE_SAMPLE"

# ハンズオン記事 Step2 Task 1-2 より転載したサンプル航空会社データ（25件）
_SAMPLE_ROWS = [
    (1001, "Skynet Airways", "JFK", "LAX", 10, 5, 2475),
    (1002, "Sunwind Lines", "ORD", "SFO", -3, -5, 1846),
    (1003, "BlueJet", "ATL", "SEA", 0, 15, 2182),
    (1004, "Quantum Flyers", "DFW", "MIA", 5, 20, 1121),
    (1005, "Nebula Express", "BOS", "DEN", 12, 8, 1754),
    (1006, "Skynet Airways", "SEA", "ORD", -5, -2, 1721),
    (1007, "Sunwind Lines", "MIA", "ATL", 7, 4, 595),
    (1008, "BlueJet", "SFO", "BOS", 22, 18, 2704),
    (1009, "Quantum Flyers", "LAX", "JFK", -1, 0, 2475),
    (1010, "Nebula Express", "DEN", "DFW", 14, 20, 641),
    (1011, "Skynet Airways", "PHX", "SEA", 3, -2, 1107),
    (1012, "BlueJet", "ORD", "ATL", -7, -10, 606),
    (1013, "Quantum Flyers", "BOS", "JFK", 9, 11, 187),
    (1014, "Sunwind Lines", "LAX", "DFW", 13, 15, 1235),
    (1015, "Nebula Express", "SFO", "SEA", 0, 3, 679),
    (1016, "Skynet Airways", "ATL", "DEN", 6, 5, 1199),
    (1017, "BlueJet", "DFW", "PHX", -2, 1, 868),
    (1018, "Quantum Flyers", "ORD", "BOS", 8, -1, 867),
    (1019, "Sunwind Lines", "JFK", "MIA", 10, 16, 1090),
    (1020, "Nebula Express", "DEN", "ORD", -4, 0, 888),
    (1021, "Skynet Airways", "SEA", "ATL", 16, 12, 2182),
    (1022, "BlueJet", "MIA", "LAX", 5, 7, 2342),
    (1023, "Quantum Flyers", "DEN", "BOS", 2, -2, 1754),
    (1024, "Sunwind Lines", "SFO", "JFK", -6, -8, 2586),
    (1025, "Nebula Express", "ORD", "MIA", 11, 13, 1090),
]


# ---------------------------------------------------------------------------
# 接続ヘルパー
# ---------------------------------------------------------------------------

def _env(name: str, default: str = "") -> str:
    return str(os.environ.get(name, default) or default)


def _connect_admin(conn_env: str, wallet_env: str):
    """ADMIN ユーザーで ADB に接続する（thin mode + wallet_location）."""
    raw = _env(conn_env)
    if not raw or raw == "TODO":
        raise RuntimeError(f"{conn_env} が未設定です（.env / props を確認してください）")
    parts = parse_oracle_connection_string(raw)
    kwargs = {}
    wallet_dir = _env(wallet_env)
    if wallet_dir and Path(wallet_dir).is_dir():
        kwargs["wallet_location"] = wallet_dir
    return oracledb.connect(
        user=parts.username,
        password=parts.password,
        dsn=parts.dsn,
        **kwargs,
    )


def _schema_exists(conn, username: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM ALL_USERS WHERE USERNAME = :u", {"u": username.upper()})
        return bool(cur.fetchone()[0])


def _ensure_schema(conn, username: str, password: str) -> str:
    """ユーザー作成・権限付与・REST 有効化を実行する（幂等）.

    ハンズオン記事 前編 Task 3〜4 / Task 7〜8 の SQL を実行する。
    """
    user = username.upper()
    if not password:
        raise RuntimeError("パスワードが未入力です")
    executed: list[str] = []
    with conn.cursor() as cur:
        if _schema_exists(conn, user):
            executed.append(f"ユーザー {user} は既に存在するため作成をスキップ")
        else:
            cur.execute(f"CREATE USER {user} IDENTIFIED BY {password}")
            executed.append(f"CREATE USER {user}")
        grants = [
            "GRANT CONNECT, RESOURCE TO %u",
            "GRANT CREATE SESSION TO %u",
            "GRANT CREATE TABLE TO %u",
            "GRANT CREATE VIEW TO %u",
            "GRANT CREATE SEQUENCE TO %u",
            "GRANT CREATE PROCEDURE TO %u",
            "GRANT UNLIMITED TABLESPACE TO %u",
            "GRANT EXECUTE ON DBMS_CLOUD TO %u",
            "GRANT READ, WRITE ON DIRECTORY DATA_PUMP_DIR TO %u",
        ]
        for g in grants:
            cur.execute(g % user)
        executed.append("権限付与（CONNECT / RESOURCE / CREATE * / DBMS_CLOUD / DATA_PUMP_DIR）")
        # REST 有効化（既に有効な場合は ORDS-05094 等を無視）
        cur.execute(
            f"""
BEGIN
  ORDS_ADMIN.ENABLE_SCHEMA(
    p_schema_name => '{user}',
    p_enabled => true,
    p_autheScheme => NULL,
    p_replace => true);
EXCEPTION
  WHEN OTHERS THEN
    IF SQLERRM LIKE 'ORDS-05094%' OR SQLERRM LIKE '%already%' THEN
      NULL;
    ELSE
      RAISE;
    END IF;
END;
"""
        )
        executed.append("ORDS_ADMIN.ENABLE_SCHEMA（REST 有効化）")
        # quota を unlimited に（記事 Task 4 末尾の手順）
        cur.execute(f"ALTER USER {user} QUOTA UNLIMITED ON DATA")
        executed.append("ALTER USER QUOTA UNLIMITED ON DATA")
    conn.commit()
    return "\n".join(f"- {item}" for item in executed)


def _login_check(conn_str: str, wallet_env: str, username: str, password: str) -> str:
    """指定ユーザーでのログイン可否を確認する."""
    parts = parse_oracle_connection_string(conn_str)
    kwargs = {}
    wallet_dir = _env(wallet_env)
    if wallet_dir and Path(wallet_dir).is_dir():
        kwargs["wallet_location"] = wallet_dir
    try:
        with oracledb.connect(
            user=username.upper(), password=password, dsn=parts.dsn, **kwargs
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM DUAL")
                cur.fetchone()
        return f"{username}: ログイン OK"
    except Exception as e:
        return f"{username}: ログイン失敗 ({e})"


def _persist_env(key: str, value: str) -> None:
    if value:
        try:
            set_key(".env", key, value)
        except Exception as e:
            logger.warning("set_key %s failed: %s", key, e)


def _env_or(key: str, default: str = "") -> str:
    """環境変数を優先し、未設定なら .env ファイルから読む."""
    value = _env(key)
    if value:
        return value
    try:
        return get_key(".env", key) or default
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Tab: Lab DB 初期化
# ---------------------------------------------------------------------------

def _init_source_schema(source_password: str) -> str:
    """ATP へ source_01 を作成する（前編 Task 3〜4）."""
    try:
        with _connect_admin("ORACLE_26AI_CONNECTION_STRING", "WALLET_ATP_DIR") as conn:
            report = _ensure_schema(conn, _env("SOURCE_SCHEMA_USER", "SOURCE_01"), source_password)
        _persist_env("SOURCE_SCHEMA_PASSWORD", source_password)
        return f"✅ ATP 初期化完了\n{report}\n\nパスワードを .env に保存しました（AIDP external catalog 設定时使用）"
    except Exception as e:
        logger.exception("init source schema failed")
        return f"❌ ATP 初期化に失敗しました: {e}"


def _init_gold_schema(gold_password: str) -> str:
    """AI Lakehouse へ gold_01 を作成する（前編 Task 7〜8）."""
    try:
        with _connect_admin("ORACLE_LAKEHOUSE_CONNECTION_STRING", "WALLET_LH_DIR") as conn:
            report = _ensure_schema(conn, _env("GOLD_SCHEMA_USER", "GOLD_01"), gold_password)
        _persist_env("GOLD_SCHEMA_PASSWORD", gold_password)
        return f"✅ AI Lakehouse 初期化完了\n{report}\n\nパスワードを .env に保存しました（OAC 接続で利用）"
    except Exception as e:
        logger.exception("init gold schema failed")
        return f"❌ AI Lakehouse 初期化に失敗しました: {e}"


def _load_sample_data() -> str:
    """ATP の source_01.AIRLINE_SAMPLE にサンプルデータを読込む（前編 Step2 Task 1）."""
    user = _env("SOURCE_SCHEMA_USER", "SOURCE_01").upper()
    password = _env_or("SOURCE_SCHEMA_PASSWORD")
    if not password:
        return "❌ SOURCE_SCHEMA_PASSWORD が未設定です。先に「source_01 スキーマ初期化」を実行してください。"
    conn_str = _env("ORACLE_26AI_CONNECTION_STRING")
    parts = parse_oracle_connection_string(conn_str)
    kwargs = {}
    wallet_dir = _env("WALLET_ATP_DIR")
    if wallet_dir and Path(wallet_dir).is_dir():
        kwargs["wallet_location"] = wallet_dir
    try:
        with oracledb.connect(user=user, password=password, dsn=parts.dsn, **kwargs) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM ALL_TABLES WHERE OWNER = :o AND TABLE_NAME = :t",
                    {"o": user, "t": _SAMPLE_TABLE},
                )
                exists = bool(cur.fetchone()[0])
                if not exists:
                    cur.execute(
                        f"""
CREATE TABLE {_SAMPLE_TABLE} (
  FLIGHT_ID NUMBER,
  AIRLINE VARCHAR2(20),
  ORIGIN VARCHAR2(3),
  DEST VARCHAR2(3),
  DEP_DELAY NUMBER,
  ARR_DELAY NUMBER,
  DISTANCE NUMBER
)"""
                    )
                cur.execute(f"DELETE FROM {_SAMPLE_TABLE}")
                cur.executemany(
                    f"INSERT INTO {_SAMPLE_TABLE} "
                    f"(FLIGHT_ID, AIRLINE, ORIGIN, DEST, DEP_DELAY, ARR_DELAY, DISTANCE) "
                    f"VALUES (:1, :2, :3, :4, :5, :6, :7)",
                    _SAMPLE_ROWS,
                )
                cur.execute(f"SELECT COUNT(*) FROM {_SAMPLE_TABLE}")
                count = cur.fetchone()[0]
            conn.commit()
        return (
            f"✅ サンプルデータ読込完了: {user}.{_SAMPLE_TABLE} へ {count} 件\n"
            f"（ハンズオン記事 Step2 Task 1-1 / 1-2 と同じデータ）"
        )
    except Exception as e:
        logger.exception("load sample data failed")
        return f"❌ サンプルデータ読込に失敗しました: {e}"


def build_lab_db_setup_tab() -> None:
    gr.Markdown(
        f"**DB 内オブジェクトの自動作成**（Terraform ではユーザー作成まで自動化できないため）\n\n{_ARTICLE_REF}"
    )

    with gr.Accordion("1. ATP → source_01 スキーマ初期化", open=True):
        with gr.Row():
            source_password = gr.Textbox(
                label="source_01 パスワード",
                value=_env("SOURCE_SCHEMA_PASSWORD"),
                type="password",
                show_label=True,
            )
        source_btn = gr.Button("source_01 を作成・権限付与・REST 有効化")
        source_out = gr.Markdown("")

    with gr.Accordion("2. AI Lakehouse → gold_01 スキーマ初期化", open=True):
        with gr.Row():
            gold_password = gr.Textbox(
                label="gold_01 パスワード",
                value=_env("GOLD_SCHEMA_PASSWORD"),
                type="password",
                show_label=True,
            )
        gold_btn = gr.Button("gold_01 を作成・権限付与・REST 有効化")
        gold_out = gr.Markdown("")

    with gr.Accordion("3. サンプル航空会社データ読込（source_01.AIRLINE_SAMPLE）", open=True):
        load_btn = gr.Button("サンプルデータ 25 件を読込む（idempotent）")
        load_out = gr.Markdown("")

    source_btn.click(fn=_init_source_schema, inputs=[source_password], outputs=[source_out])
    gold_btn.click(fn=_init_gold_schema, inputs=[gold_password], outputs=[gold_out])
    load_btn.click(fn=_load_sample_data, inputs=None, outputs=[load_out])


# ---------------------------------------------------------------------------
# Tab: AIDP 設定ガイド
# ---------------------------------------------------------------------------

def _aidp_console_url() -> str:
    ocid = _env("AIDP_OCID")
    if ocid and ocid != "TODO":
        return f"https://aidp.oci.oraclecloud.com/?ocid={ocid}"
    return "（AIDP_OCID 未設定）"


def _atp_dsn() -> str:
    raw = _env("ORACLE_26AI_CONNECTION_STRING")
    if not raw or raw == "TODO":
        return ""
    return parse_oracle_connection_string(raw).dsn


def _check_aidp_status() -> str:
    """OCI SDK 経由で AIDP インスタンス状態を確認する（best effort）."""
    try:
        import oci

        config = oci.config.from_file()
        client = oci.ai_data_platform.AiDataPlatformClient(config)
        ocid = _env("AIDP_OCID")
        if not ocid or ocid == "TODO":
            return "❌ AIDP_OCID が未設定です"
        platform = client.get_ai_data_platform(ocid).data
        return (
            f"AIDP 状態: **{platform.state}**\n"
            f"AI 機能: {getattr(platform, 'ai_feature_status', '不明')}\n"
            f"表示名: {platform.display_name}"
        )
    except Exception as e:
        logger.exception("aidp status check failed")
        return (
            f"確認できませんでした: {e}\n\n"
            "（「環境設定」タブで OCI API キーを設定してから再試行してください）"
        )


def _oac_url_hint() -> str:
    name = _env("OAC_NAME")
    if not name or name == "TODO":
        return ""
    return f"https://{name}.analytics.oc<リージョンコード>.oraclecloud.com （リージョンコードは OCI コンソール参照）"


def build_aidp_guide_tab() -> None:
    gr.Markdown(
        "**AIDP Workbench での手動設定ガイド**\n\n"
        "Terraform は AIDP インスタンス本体までしか作成できないため、"
        "以下は AIDP コンソールで実施します。必要な値は下の一覧からコピーしてください。\n\n"
        f"{_ARTICLE_REF}"
    )

    with gr.Row():
        ns_input = gr.Textbox(label="Object Storage namespace", value=_env("OCI_NAMESPACE"), placeholder="例: abc123def456")
        ns_btn = gr.Button("namespace を保存")
        ns_out = gr.Markdown("")

    with gr.Accordion("必要値（コピー用）", open=True):
        gr.Markdown(
            f"""
| 項目 | 値 |
|---|---|
| AIDP コンソール | `{_aidp_console_url()}` |
| OAC URL | `{_oac_url_hint()}` |
| ATP DSN | `{_atp_dsn()}` |
| source_01 ユーザー名 | `{_env('SOURCE_SCHEMA_USER', 'SOURCE_01')}` |
| source_01 パスワード | `{_env_or('SOURCE_SCHEMA_PASSWORD', '(未設定 —「Lab DB 初期化」タブで実行)')}` |
| gold_01 ユーザー名 | `{_env('GOLD_SCHEMA_USER', 'GOLD_01')}` |
| gold_01 パスワード | `{_env_or('GOLD_SCHEMA_PASSWORD', '(未設定 —「Lab DB 初期化」タブで実行)')}` |
| Delta 保存先バケット | `{_env('BUCKET_NAME', '(未設定)')}` |
| Delta パス（例） | `oci://{_env('BUCKET_NAME', '<bucket>')}@<namespace>/delta/airline_sample` |
"""
        )

    with gr.Accordion("手順チェックリスト（前編 Step2 / 後編 Step3）", open=True):
        gr.Markdown(
            """
1. **AIDP ポリシー追加**（本 stack では Terraform が未対応のため手動）
   - AIDP コンソール → インスタンス → Add policies → `Standard` を選択して追加
   - Optional policies から `Enable object deletion` も追加（バケットへの Delta 書き込みに必要）
2. **AIDP 外部カタログ作成**（前編 Step2 Task 2）
   - AIDP コンソール → Create → Catalog
   - Catalog type: `External catalog` / External source type: `Oracle Autonomous Transaction Processing`
   - ATP instance: 本 stack で作成した ATP / Service: `<atp名>_high` / Username: `source_01`
3. **AIDP 内部カタログ作成**（前編 Step2 Task 4-3）
   - 標準カタログ `airlines_data_catalog_01` を作成し、`bronze` / `silver` / `gold` スキーマを notebook で作成
4. **Bronze 取り込み**（前編 Step2 Task 4）
   - notebook で `COPY FROM` を実行し、`oci://<bucket>@<namespace>/delta/airline_sample` に Delta 保存
   - 距離が不正のレコードを削除（クレンジング）
5. **Silver 加工 + レビュー付与**（前編 Step2 Task 5）
   - 航空会社別平均を LEFT JOIN 付与し、`REVIEW` 列を UDF でランダム付与
6. **LLM 設定 + 感情分析**（前編 Step2 Task 5-4）
   - AIDP の LLM 設定で API key（例: xai.grok-4）を登録
   - レビュー文の Sentiment 列を生成
7. **AIDP と AI Lakehouse の接続**（前編 Step2 Task 6）
   - AIDP コンソールで Lakehouse への接続設定（サービス主体への DBMS_SHARE はコンソールが代行）
8. **Gold 書き出し**（前編 Step2 Task 7）
   - エンリッチ済みデータを `gold_01.AIRLINE_SAMPLE_GOLD` へ保存
9. **OAC 接続 + ダッシュボード**（後編 Step3）
   - 「OAC 接続」タブから接続を作成（または OAC UI で手動）
   - dataset 作成 → ビジュアル / ダッシュボード作成
"""
        )

    with gr.Accordion("AIDP 状態確認", open=False):
        status_btn = gr.Button("AIDP インスタンス状態を確認")
        status_out = gr.Markdown("")

    def _save_ns(value: str) -> str:
        _persist_env("OCI_NAMESPACE", value)
        return "✅ namespace を .env に保存しました"

    ns_btn.click(fn=_save_ns, inputs=[ns_input], outputs=[ns_out])
    status_btn.click(fn=_check_aidp_status, inputs=None, outputs=[status_out])


# ---------------------------------------------------------------------------
# Tab: OAC 接続
# ---------------------------------------------------------------------------

_WALLET_LH_PATH = "/u01/aipoc/props/wallet_lh.zip"


def _oac_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _oac_create_connection(base_url: str, token: str, conn_name: str, username: str, password: str) -> str:
    """OAC REST API でデータ接続を作成する（実験的）.

    OAC のバージョンにより request 形式が異なる可能性があるため、
    応答をそのまま表示して調整できるようにしている。
    """
    base = base_url.rstrip("/")
    if not base.startswith("https://"):
        return "❌ OAC base URL は https:// で始まる形式で指定してください"
    if not token:
        return "❌ OAC Personal Access Token が未入力です"
    dsn = ""
    raw = _env("ORACLE_LAKEHOUSE_CONNECTION_STRING")
    if raw and raw != "TODO":
        dsn = parse_oracle_connection_string(raw).dsn
    payload = {
        "name": conn_name,
        "type": "ORACLE_ADB",
        "parameters": {
            "host": dsn,
            "username": username.upper(),
            "password": password,
            "isSecure": True,
        },
    }
    try:
        resp = requests.post(
            f"{base}/api/public/connections",
            headers=_oac_headers(token),
            json=payload,
            timeout=60,
        )
        body = resp.text[:2000]
        if resp.ok:
            return (
                f"✅ 接続作成リクエスト成功 (HTTP {resp.status_code})\n\n"
                f"```json\n{body}\n```\n\n"
                "ウォレットが必要な場合は OAC UI で接続を編集し、"
                "下の「AI Lakehouse ウォレット」をアップロードしてください。"
            )
        return (
            f"⚠️ HTTP {resp.status_code}\n\n```json\n{body}\n```\n\n"
            "OAC のバージョンにより接続作成 API の形式が異なる場合があります。"
            "応答を参照の上、OAC UI で手動作成しても構いません。"
        )
    except Exception as e:
        logger.exception("oac create connection failed")
        return f"❌ リクエストに失敗しました: {e}"


def _oac_wallet_download():
    if Path(_WALLET_LH_PATH).is_file():
        return {"path": _WALLET_LH_PATH, "orig_name": "wallet_lh.zip"}
    return {"path": None, "orig_name": None}


def build_oac_setup_tab() -> None:
    gr.Markdown(
        "**OAC への接続作成**（後編 Step3 Task 1〜2）\n\n"
        "API 経由の自動作成は実験的です。失敗時は OAC UI で手動作成してください"
        "（接続タイプ: Oracle Autonomous Data Warehouse / wallet アップロード / "
        "ユーザー `gold_01` / service `<lakehouse名>_high`）。\n\n"
        f"{_ARTICLE_REF}"
    )

    with gr.Row():
        base_url = gr.Textbox(label="OAC base URL", value=_env_or("OAC_BASE_URL"), placeholder="https://<name>.analytics.oc<region>.oraclecloud.com")
        token = gr.Textbox(label="OAC Personal Access Token", value=_env_or("OAC_ACCESS_TOKEN"), type="password", show_label=True)

    with gr.Row():
        conn_name = gr.Textbox(label="接続名", value="adl-conn-01")
        username = gr.Textbox(label="接続ユーザー", value=_env("GOLD_SCHEMA_USER", "GOLD_01"))
        password = gr.Textbox(label="接続パスワード", value=_env_or("GOLD_SCHEMA_PASSWORD"), type="password", show_label=True)

    create_btn = gr.Button("OAC API で接続を作成（実験的）")
    create_out = gr.Markdown("")

    gr.Markdown("### AI Lakehouse ウォレット（手動接続の場合に OAC でアップロード）")
    with gr.Row():
        wallet_dl = gr.DownloadButton("wallet_lh.zip をダウンロード")
        wallet_btn = gr.Button("ウォレット状態を確認")
        wallet_out = gr.Markdown("")

    def _save_oac_settings(base, tok):
        _persist_env("OAC_BASE_URL", base)
        _persist_env("OAC_ACCESS_TOKEN", tok)
        return "✅ OAC 設定を .env に保存しました"

    save_btn = gr.Button("OAC 設定を保存")
    save_out = gr.Markdown("")

    create_btn.click(fn=_oac_create_connection, inputs=[base_url, token, conn_name, username, password], outputs=[create_out])
    save_btn.click(fn=_save_oac_settings, inputs=[base_url, token], outputs=[save_out])
    wallet_dl.click(fn=_oac_wallet_download, inputs=None, outputs=[wallet_dl])
    wallet_btn.click(
        fn=lambda: f"{'✅ ファイル存在: ' + _WALLET_LH_PATH if Path(_WALLET_LH_PATH).is_file() else '❌ ' + _WALLET_LH_PATH + ' が見つかりません'}",
        inputs=None,
        outputs=[wallet_out],
    )


# ---------------------------------------------------------------------------
# Tab: ヘルスチェック
# ---------------------------------------------------------------------------

def _health_all() -> str:
    lines = ["# ヘルスチェック結果", ""]

    def _check_db(label: str, conn_env: str, wallet_env: str) -> None:
        try:
            with _connect_admin(conn_env, wallet_env) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM DUAL")
                    cur.fetchone()
            lines.append(f"- ✅ {label}: 接続 OK")
        except Exception as e:
            lines.append(f"- ❌ {label}: 接続失敗 ({str(e)[:200]})")

    _check_db("ATP (ADMIN)", "ORACLE_26AI_CONNECTION_STRING", "WALLET_ATP_DIR")
    _check_db("AI Lakehouse (ADMIN)", "ORACLE_LAKEHOUSE_CONNECTION_STRING", "WALLET_LH_DIR")

    src_pw = _env_or("SOURCE_SCHEMA_PASSWORD")
    if src_pw:
        lines.append(f"- {_login_check(_env('ORACLE_26AI_CONNECTION_STRING'), 'WALLET_ATP_DIR', _env('SOURCE_SCHEMA_USER', 'SOURCE_01'), src_pw)}")
    else:
        lines.append("- ⚠️ source_01: パスワード未設定のためスキップ")

    gold_pw = _env_or("GOLD_SCHEMA_PASSWORD")
    if gold_pw:
        lines.append(f"- {_login_check(_env('ORACLE_LAKEHOUSE_CONNECTION_STRING'), 'WALLET_LH_DIR', _env('GOLD_SCHEMA_USER', 'GOLD_01'), gold_pw)}")
    else:
        lines.append("- ⚠️ gold_01: パスワード未設定のためスキップ")

    oac_base = _env_or("OAC_BASE_URL")
    if oac_base and oac_base.startswith("https://"):
        try:
            requests.get(oac_base, timeout=15)
            lines.append(f"- ✅ OAC ({oac_base}): 到達可能")
        except Exception as e:
            lines.append(f"- ⚠️ OAC ({oac_base}): {str(e)[:150]}")
    else:
        lines.append("- ⚠️ OAC: base URL 未設定のためスキップ（「OAC 接続」タブで設定）")

    lines.append("")
    lines.append(f"- {_check_aidp_status().splitlines()[0]}")
    return "\n".join(lines)


def build_health_tab() -> None:
    gr.Markdown("Terraform で作成したリソース群の疎通を一括確認します。")
    btn = gr.Button("全チェックを実行")
    out = gr.Markdown("")
    btn.click(fn=_health_all, inputs=None, outputs=[out])
