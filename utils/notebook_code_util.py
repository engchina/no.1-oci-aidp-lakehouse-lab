"""AIDP Notebook コード生成ユーティリティモジュール.

Qiita ハンドオンの前編 Step2（Bronze / Silver / Gold / OAC 連携）で
AIDP Notebook に貼り付けるコードブロックを、本 lab の環境値
（バケット名 / Object Storage namespace / LLM モデル名 / カタログ名）を
差し込んだ状態で表示し、タスクごとにコピーできるようにします。

Terraform / Gradio では AIDP Notebook 内のセル実行を自動化できないため、
記事の各 Task と 1:1 に対応するコードを「そのまま使える形」で提供します。
"""

from __future__ import annotations

import logging
from string import Template

import gradio as gr

from utils.lab_setup_util import _env, _env_or, _persist_env

logger = logging.getLogger(__name__)

# ハンズオン記事の既定値（記事では「任意」だが lab ではこれらを使用）
DEFAULT_ATP_CATALOG = "atp_external_catalog_01"
DEFAULT_DATA_CATALOG = "airlines_data_catalog_01"
DEFAULT_ADB_CATALOG = "airlines_external_adb_gold_01"
DEFAULT_LLM_MODEL = "xai.grok-4"

# ---------------------------------------------------------------------------
# コードテンプレート（string.Template: $PLACEHOLDER のみ置換）
# ---------------------------------------------------------------------------

# 前編 Step2 Task 4-1: 外部カタログ（ATP）の反映確認
_T4_1 = """airlines_sample_table = "${ATP_CATALOG}.source_01.AIRLINE_SAMPLE"

# Confirm AIRLINE_SAMPLE table is reflected in spark
spark.sql("SHOW TABLES IN ${ATP_CATALOG}.source_01").show(truncate=False)

df = spark.table(airlines_sample_table)
df.show()"""

# 前編 Step2 Task 4-2: Bronze Delta を Object Storage へ書き込み
_T4_2 = """# Object Storage 上の Bronze レイヤー保存先
# （ネームスペースはご自身の Object Storage namespace）
delta_path = "oci://${BUCKET}@${NAMESPACE}/delta/airline_sample"

df.write.format("delta").mode("overwrite").save(delta_path)"""

# 前編 Step2 Task 4-3: 内部カタログ + Bronze テーブル登録
_T4_3 = """bronze_table = "${DATA_CATALOG}.bronze.airline_sample_delta"

# Create New Internal Catalog & Schema to store data
spark.sql("CREATE CATALOG IF NOT EXISTS ${DATA_CATALOG}")
spark.sql("CREATE SCHEMA IF NOT EXISTS ${DATA_CATALOG}.bronze")

# Drop the table if it exists, to avoid conflicts
spark.sql(f"DROP TABLE IF EXISTS {bronze_table}")

# Create new bronze table
spark.sql(f\"\"\"
CREATE TABLE IF NOT EXISTS {bronze_table}
USING DELTA
LOCATION '{delta_path}'
\"\"\")"""

# 前編 Step2 Task 4-4: クレンジング（不正な距離レコードを削除）
_T4_4 = """spark.sql(f\"\"\"
DELETE FROM {bronze_table}
WHERE DISTANCE IS NULL OR DISTANCE < 0
\"\"\")"""

# 前編 Step2 Task 4-5: Delta バージョニング（タイムトラベル）確認
_T4_5 = """# クレンジング前のバージョン 0 を読み込み（Delta のタイムトラベル確認）
df_v0 = spark.read.format("delta").option("versionAsOf", 0).load(delta_path)
df_v0.show()"""

# 前編 Step2 Task 5-1: Silver レイヤーへの書き込み
_T5_1 = """df_clean = spark.table(bronze_table)
silver_path = "oci://${BUCKET}@${NAMESPACE}/delta/silver/airline_sample"
silver_table = "${DATA_CATALOG}.silver.airline_sample_delta"

# データを保存するための Silver スキーマを作成
spark.sql("CREATE SCHEMA IF NOT EXISTS ${DATA_CATALOG}.silver")

# クレンジング済みの DataFrame を Delta 形式で Object Storage に書き込む
df_clean.write.format("delta").mode("overwrite").save(silver_path)

# 既にテーブル定義が存在する場合は削除して競合を防ぐ
spark.sql(f"DROP TABLE IF EXISTS {silver_table}")
spark.sql(f\"\"\"
CREATE TABLE {silver_table}
USING DELTA
LOCATION '{silver_path}'
\"\"\")

# 正常にクレンジングされたことを確認
spark.sql(f"SELECT * FROM {silver_table}").show()"""

# 前編 Step2 Task 5-2: 航空会社別平均値を LEFT JOIN でエンリッチ
_T5_2 = """# Enrich data by adding aggregates/average delays and distance
from pyspark.sql import functions as F

df = spark.table("${DATA_CATALOG}.silver.airline_sample_delta")

# Calculate averages by airline
avg_df = df.groupBy("AIRLINE").agg(
    F.avg("DEP_DELAY").alias("AVG_DEP_DELAY"),
    F.avg("ARR_DELAY").alias("AVG_ARR_DELAY"),
    F.avg("DISTANCE").alias("AVG_DISTANCE"),
)

# Join with the detail table
enhanced_df = df.join(avg_df, on="AIRLINE", how="left")
enhanced_df.show()"""

# 前編 Step2 Task 5-3: レビュー文を UDF で付与
_T5_3 = """# Add New Review Column for Sentiment Analysis
import random

sample_reviews = [
    "The flight was on time and comfortable.",
    "Long delay and unfriendly staff.",
    "Quick boarding and smooth flight.",
    "Lost my luggage, not happy.",
    "Great service and tasty snacks.",
]

from pyspark.sql.functions import udf
from pyspark.sql.types import StringType

random_review_udf = udf(lambda: random.choice(sample_reviews), StringType())
df_with_review = enhanced_df.withColumn("REVIEW", random_review_udf())
df_with_review.show()"""

# 前編 Step2 Task 5-4（1/2）: LLM モデル疎通確認
_T5_4A = """# test model
spark.sql("select query_model('${MODEL}', 'OCIで提供されているExaDB-Dとは?') as questions").show(truncate=False)"""

# 前編 Step2 Task 5-4（2/2）: LLM による感情分析パイプライン
_T5_4B = """from pyspark.sql.functions import expr, from_json, col, regexp_replace

# --- 1. 出力構造の定義 ---
# LLMから返却されるJSONのキーと型を定義
json_schema = "label STRING, reason STRING"

# --- 2. プロンプトの構築 ---
# 感情(label)と理由(reason)をJSON形式で一括取得するための指示文
prompt_cmd = \"\"\"concat('Review: ', REVIEW, '. Analyze the sentiment and briefly explain the reason. ',
                      'Return your response ONLY as a JSON object with keys "label" (Positive/Negative/Neutral) and "reason".')\"\"\"

# --- 3. 分析パイプラインの実行 ---
enhanced_df = (
    df_with_review
    # A. LLMモデルへの問い合わせ実行
    .withColumn("raw_output", expr(f"query_model('${MODEL}', {prompt_cmd})"))
    # B. レスポンスのクレンジング
    # パースエラーを防ぐため、LLMが混入させることのあるマークダウン記号(```json)や改行を除去
    .withColumn("cleaned_json", regexp_replace(col("raw_output"), r"(^```json|```$|\\n)", ""))
    # C. JSONパース（文字列を構造化データ(Struct型)に変換）
    .withColumn("parsed", from_json(col("cleaned_json"), json_schema))
    # D. カラムの展開（構造体から「ラベル」と「理由」を個別のカラムとして抽出）
    .withColumn("SENTIMENT_LABEL", col("parsed.label"))
    .withColumn("SENTIMENT_REASON", col("parsed.reason"))
)

# --- 4. 結果の確認 ---
# 必要なカラムのみを選択して表示
enhanced_df.select("REVIEW", "SENTIMENT_LABEL", "SENTIMENT_REASON").show(10, False)"""

# 前編 Step2 Task 7-2: Gold スキーマ作成 + エンリッチ済みデータ書き込み
_T7_2 = """# Save Averaged Data to Gold Schema
gold_path = "oci://${BUCKET}@${NAMESPACE}/delta/gold/airline_sample_avg"
gold_table = "${DATA_CATALOG}.gold.airline_sample_avg"

# Create Gold Schema
spark.sql("CREATE SCHEMA IF NOT EXISTS ${DATA_CATALOG}.gold")

enhanced_df.write.format("delta").option("mergeSchema", "true").mode("overwrite").save(gold_path)
spark.sql(f"DROP TABLE IF EXISTS {gold_table}")
spark.sql(f\"\"\"
CREATE TABLE {gold_table}
USING DELTA
LOCATION '{gold_path}'
\"\"\")

df_gold = spark.table(gold_table)
df_gold.show()"""

# 前編 Step2 Task 7-3: 列名の大文字化（OAC の可視化要件）
_T7_3 = """# Before pushing dataframe, make sure all columns are upper case
# to prevent visualization issues in OAC
# (OAC needs all columns capitalized in order to analyze data)
for col_name in df_gold.columns:
    df_gold = df_gold.withColumnRenamed(col_name, col_name.upper())
df_gold.show()"""

# 前編 Step2 Task 7-4: 型キャスト + 列順整理 + 一時ビュー登録
_T7_4 = """from pyspark.sql.functions import col
from pyspark.sql.types import DecimalType, StringType

# Oracleテーブルの型定義に合わせたキャスト処理
df_gold_typed = (
    df_gold
    # 数値列のキャスト (OracleのNUMBER型に対応)
    .withColumn("FLIGHT_ID", col("FLIGHT_ID").cast(DecimalType(38, 10)))
    .withColumn("DEP_DELAY", col("DEP_DELAY").cast(DecimalType(38, 10)))
    .withColumn("ARR_DELAY", col("ARR_DELAY").cast(DecimalType(38, 10)))
    .withColumn("DISTANCE", col("DISTANCE").cast(DecimalType(38, 10)))
    .withColumn("AVG_DEP_DELAY", col("AVG_DEP_DELAY").cast(DecimalType(38, 10)))
    .withColumn("AVG_ARR_DELAY", col("AVG_ARR_DELAY").cast(DecimalType(38, 10)))
    .withColumn("AVG_DISTANCE", col("AVG_DISTANCE").cast(DecimalType(38, 10)))
    # テキスト列のキャスト (OracleのVARCHAR2型に対応)
    .withColumn("AIRLINE", col("AIRLINE").cast(StringType()))
    .withColumn("ORIGIN", col("ORIGIN").cast(StringType()))
    .withColumn("DEST", col("DEST").cast(StringType()))
    .withColumn("REVIEW", col("REVIEW").cast(StringType()))
    .withColumn("SENTIMENT_LABEL", col("SENTIMENT_LABEL").cast(StringType()))
    .withColumn("SENTIMENT_REASON", col("SENTIMENT_REASON").cast(StringType()))
)

# Oracleテーブルの定義順に合わせてカラムリストを更新
col_order = [
    "FLIGHT_ID", "AIRLINE", "ORIGIN", "DEST",
    "DEP_DELAY", "ARR_DELAY", "DISTANCE",
    "AVG_DEP_DELAY", "AVG_ARR_DELAY", "AVG_DISTANCE",
    "REVIEW", "SENTIMENT_LABEL", "SENTIMENT_REASON",
]
df_gold_typed = df_gold_typed.select(col_order)

# スキーマの最終確認
print(df_gold_typed.printSchema())

# Spark SQL用の一時ビューとして登録
df_gold_typed.createOrReplaceTempView("df_gold")"""

# 前編 Step2 Task 8-3: Gold テーブルへの INSERT（セル言語: SQL）
_T8_3 = """INSERT into ${ADB_CATALOG}.${GOLD_SCHEMA}.airline_sample_gold
select * from df_gold"""

# タスク順序: (accordion タイトル, 説明, テンプレート, 言語)
_NOTEBOOK_BLOCKS = [
    (
        "Task 4-1: 外部カタログ（ATP）の反映確認",
        "external catalog に ATP 側の `AIRLINE_SAMPLE` が反映されていることを確認します。\n"
        "「AIRLINE_SAMPLE が一覧に出れば OK」。ここでエラーになる場合は「AIDP 設定ガイド」の手順 2"
        "（external catalog 作成）を見直してください。",
        _T4_1,
        "python",
    ),
    (
        "Task 4-2: Bronze Delta を Object Storage へ書き込み",
        "ATP から読み込んだデータを Delta 形式で Object Storage の `delta/airline_sample` に保存します。\n"
        "実行後、バケット配下に `delta/airline_sample/_delta` と `delta/airline_sample/` 配下のデータファイルができます"
        "（「ヘルスチェック」タブでも delta パスの存在を確認できます）。",
        _T4_2,
        "python",
    ),
    (
        "Task 4-3: 内部カタログ + Bronze テーブル登録",
        "メダリオンアーキテクチャの **Bronze** として、Object Storage の Delta を Spark 側にテーブル登録します。\n"
        "内部カタログ `" + DEFAULT_DATA_CATALOG + "` と `bronze` スキーマを新規作成します。",
        _T4_3,
        "python",
    ),
    (
        "Task 4-4: クレンジング（不正レコード削除）",
        "`DISTANCE IS NULL` または `DISTANCE < 0` のレコードを削除します。\n"
        "複雑な変換はまだ行わず「明らかに使えないデータを除外する」ステップです。"
        "Delta 形式のため削除は削除トランザクションとして記録されます。",
        _T4_4,
        "python",
    ),
    (
        "Task 4-5: Delta バージョニング（タイムトラベル）確認",
        "クレンジング前の **バージョン 0** を `versionAsOf 0` で読み込みます。\n"
        "データを壊しても過去バージョンに復元できることを確認します。",
        _T4_5,
        "python",
    ),
    (
        "Task 5-1: Silver レイヤーへの書き込み",
        "クレンジング済みデータを **Silver** として `delta/silver/airline_sample` に確定・登録します。\n"
        "既存テーブル定義は削除してから再登録するため、再実行しても競合しません。",
        _T5_1,
        "python",
    ),
    (
        "Task 5-2: 航空会社別平均値でエンリッチ",
        "Silver 明細に、航空会社（AIRLINE）ごとの平均出発遅延 / 平均到着遅延 / 平均飛行距離を\n"
        "`LEFT JOIN` で付与します。",
        _T5_2,
        "python",
    ),
    (
        "Task 5-3: レビュー文を UDF で付与",
        "感情分析の対象となるレビュー文を、5 件のサンプルからランダムに選ぶ UDF で\n"
        "`REVIEW` 列として付与します。",
        _T5_3,
        "python",
    ),
    (
        "Task 5-4 (1/2): LLM モデル疎通確認",
        "AIDP から LLM（既定 `" + DEFAULT_LLM_MODEL + "`）を呼び出して疎通を確認します。\n"
        "AIDP では利用可能な生成 AI モデルはリージョンに依存します。"
        "「AIDP 設定ガイド」手順 4（LLM 設定）で登録したモデル名が「LLM モデル名」と一致することを確認してください。",
        _T5_4A,
        "python",
    ),
    (
        "Task 5-4 (2/2): LLM による感情分析",
        "REVIEW 列を LLM に渡し、各行ごとに `SENTIMENT_LABEL`（Positive/Negative/Neutral）と\n"
        "`SENTIMENT_REASON`（理由）を JSON で取得 → クレンジング → `from_json` で展開します。",
        _T5_4B,
        "python",
    ),
    (
        "Task 7-2: Gold スキーマ作成 + 書き込み",
        "エンリッチ済みデータを **Gold** として `delta/gold/airline_sample_avg` に保存し、\n"
        "`gold` スキーマにテーブル登録します。",
        _T7_2,
        "python",
    ),
    (
        "Task 7-3: 列名の大文字化",
        "OAC は可視化時に全カラムが**大文字**である必要があり、小文字だとエラーになります。\n"
        "OAC 連携 / 本番投入前の最後の整形ステップです。",
        _T7_3,
        "python",
    ),
    (
        "Task 7-4: 型キャスト + 列順整理 + 一時ビュー",
        "Oracle テーブルの型定義（NUMBER → Decimal(38,10) / VARCHAR2 → String）に合わせ、\n"
        "列順も `AIRLINE_SAMPLE_GOLD` の定義順に揃えて `df_gold` 一時ビューとして登録します。\n"
        "テーブル DDL は「Lab DB 初期化」タブで先に作成してください。",
        _T7_4,
        "python",
    ),
    (
        "Task 8-3: Gold テーブルへの INSERT（セル言語: SQL）",
        "AI Lakehouse の `GOLD_01.AIRLINE_SAMPLE_GOLD` へ `df_gold` を INSERT します。\n"
        "**Spark のネイティブ INSERT ではなく SQL の INSERT を使う理由**: Spark のネイティブ INSERT は\n"
        "列名を小文字に変換してしまい OAC で可視化エラーになるため。SQL の `INSERT INTO` でこれを回避します。\n"
        "実行前に「AIDP 設定ガイド」手順 7（external catalog リフレッシュ）が完了していること。",
        _T8_3,
        "sql",
    ),
]

# 手作業セル（コンソール操作）の案内
_NOTEBOOK_PREP_MARKDOWN = """コード実行の前に AIDP コンソールで以下を実施します。

1. AIDP コンソール → 左メニュー **Workspace** → 右上 **Create**
   - Workspace name: `airline-workspace_01`
   - Default catalog: 手順 2 で作成した `atp_external_catalog_01`
2. ワークスペースを開き、`+` から新規フォルダ `demo` を作成
3. `Notebook` を作成し、ファイル名を `airlines-notebook.ipynb` に変更
4. **Cluster** → **Create cluster**: Cluster name `my_workspace_cluster_01`（それ以外はデフォルト）
5. クラスター作成完了後、**Attach existing cluster** でアタッチし `(Active)` を確認
6. 各セルの言語が **Python** であること（Task 8-3 のセルのみ **SQL**）

準備ができたら、次のアコーディオンのコードを **タスク番号順** にセルへ貼り付けて実行してください。
"""

_GOLD_REFRESH_MARKDOWN = """**Task 8-2: External Catalog のリフレッシュ**（Notebook Task 8-3 の前置き）

Gold テーブル（`GOLD_01.AIRLINE_SAMPLE_GOLD`）は「Lab DB 初期化」タブで作成済みのはずです。
AIDP 側にまだ見えない場合は、AIDP コンソールで以下を実行します。

1. **Master Catalog** → `airlines_external_adb_gold_01` をクリック
2. 右側のアイコンから **External Catalog をリフレッシュ**
3. `AIRLINE_SAMPLE_GOLD` テーブルが表示されることを確認
   （表示されない場合はブラウザをリフレッシュして再リフレッシュ）

確認できたら、最後のコードブロック（Task 8-3）を実行してください。
"""


def _template_values(namespace: str, bucket: str, model: str) -> dict:
    """コードテンプレートへ埋め込む環境値を解決する（未設定はプレースホルダ維持）."""
    return {
        "NAMESPACE": (namespace or "").strip() or "<namespace>",
        "BUCKET": (bucket or "").strip() or "<bucket>",
        "MODEL": (model or "").strip() or DEFAULT_LLM_MODEL,
        "ATP_CATALOG": _env_or("AIDP_ATP_CATALOG_NAME", DEFAULT_ATP_CATALOG),
        "DATA_CATALOG": _env_or("AIDP_DATA_CATALOG_NAME", DEFAULT_DATA_CATALOG),
        "ADB_CATALOG": _env_or("AIDP_ADB_CATALOG_NAME", DEFAULT_ADB_CATALOG),
        "GOLD_SCHEMA": _env("GOLD_SCHEMA_USER", "GOLD_01").upper() or "GOLD_01",
    }


def render_all_codes(namespace: str, bucket: str, model: str) -> list[str]:
    """全コードブロックを環境値でレンダリングする."""
    values = _template_values(namespace, bucket, model)
    rendered = []
    for _, _, template, _ in _NOTEBOOK_BLOCKS:
        rendered.append(Template(template).safe_substitute(**values))
    return rendered


def _current_values() -> tuple[str, str, str]:
    return (
        _env("OCI_NAMESPACE"),
        _env("BUCKET_NAME"),
        _env_or("AIDP_LLM_MODEL", DEFAULT_LLM_MODEL),
    )


def _save_and_render(namespace: str, bucket: str, model: str) -> tuple:
    """環境値を .env に保存し、全コードブロックを再生成する."""
    _persist_env("OCI_NAMESPACE", namespace)
    _persist_env("BUCKET_NAME", bucket)
    _persist_env("AIDP_LLM_MODEL", model)
    codes = render_all_codes(namespace, bucket, model)
    if (bucket or "").strip() in ("", "TODO") or (namespace or "").strip() == "":
        msg = (
            "✅ 保存しました（namespace / バケットが未設定の場合は、"
            "コード内の `<namespace>` / `<bucket>` を実行前に差し替えてください）"
        )
    else:
        msg = "✅ 環境値を保存し、コードを再生成しました"
    return (msg, *codes)


def build_notebook_code_tab() -> None:
    """AIDP Notebook コード生成タブを構築する."""
    gr.Markdown(
        "**AIDP Notebook 用コード**（前編 Step2 Task 4〜8）\n\n"
        "AIDP の Notebook に貼り付けるコードを、**本 lab の環境値を埋めた状態で**"
        "タスクごとに提供します。各ブロック右上の**コピーボタン**でコピーし、"
        "`airlines-notebook.ipynb` のセルへ貼り付けて **タスク番号順** に実行してください。\n\n"
        "参考: Qiita「【ハンズオン】AI × データ基盤：OCI AI Data Platform で実現する"
        "統合分析パイプラインの構築」 前編 Step2"
    )

    ns_input = gr.Textbox(
        label="Object Storage namespace",
        value=_env("OCI_NAMESPACE"),
        placeholder="例: abc123def456（OCI コンソール → Object Storage の左上）",
    )
    bucket_input = gr.Textbox(
        label="バケット名",
        value=_env("BUCKET_NAME"),
        placeholder="例: aidp-lab-bucket_01",
    )
    model_input = gr.Textbox(
        label="LLM モデル名（AIDP LLM 設定で登録したもの）",
        value=_env_or("AIDP_LLM_MODEL", DEFAULT_LLM_MODEL),
        placeholder=DEFAULT_LLM_MODEL,
    )
    save_btn = gr.Button("保存してコードを再生成", variant="primary")
    save_out = gr.Markdown("")

    code_components = []
    with gr.Accordion("Notebook の準備（前編 Step2 Task 3: コンソール操作）", open=True):
        gr.Markdown(_NOTEBOOK_PREP_MARKDOWN)

    with gr.Accordion("Notebook 実行コード（タスク番号順）", open=True):
        for title, desc, _template, language in _NOTEBOOK_BLOCKS:
            with gr.Accordion(title, open=False):
                gr.Markdown(desc)
                code_components.append(
                    gr.Code(value="", language=language, label="コード")
                )

    with gr.Accordion("Gold テーブルへの投入前に: External Catalog リフレッシュ", open=False):
        gr.Markdown(_GOLD_REFRESH_MARKDOWN)

    initial_codes = render_all_codes(*_current_values())
    for comp, code in zip(code_components, initial_codes):
        comp.value = code

    def _render_only(ns, bk, md):
        codes = render_all_codes(ns, bk, md)
        return tuple(codes)

    save_btn.click(
        fn=_save_and_render,
        inputs=[ns_input, bucket_input, model_input],
        outputs=[save_out, *code_components],
    )
    ns_input.change(fn=_render_only, inputs=[ns_input, bucket_input, model_input], outputs=code_components)
    bucket_input.change(fn=_render_only, inputs=[ns_input, bucket_input, model_input], outputs=code_components)
    model_input.change(fn=_render_only, inputs=[ns_input, bucket_input, model_input], outputs=code_components)
