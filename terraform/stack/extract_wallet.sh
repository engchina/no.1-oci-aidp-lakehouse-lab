#!/bin/bash
# ADB ウォレット ZIP を展開し、不要ファイルを除去して小さい ZIP に再パックする。
# stdout に {"wallet_content":"<base64>"} のJSONを1行だけ出力する。
# 使用法: extract_wallet.sh <wallet.zip>
set -euo pipefail

ZIP_FILE="${1:-wallet_full.zip}"
WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

unzip -q -o "$ZIP_FILE" -d "$WORK_DIR"

# 不要ファイルを削除（README、Java関連ファイル）
rm -f "$WORK_DIR/README" "$WORK_DIR/keystore.jks" "$WORK_DIR/truststore.jks" \
  "$WORK_DIR/ojdbc.properties" "$WORK_DIR/ewallet.p12"

# 小さいZIPを作成
(cd "$WORK_DIR" && zip -q -r "$WORK_DIR/small.zip" .)

# base64エンコード（改行を除去）
WALLET_CONTENT=$(base64 -w 0 "$WORK_DIR/small.zip" | tr -d '\r\n')

printf '{"wallet_content":"%s"}\n' "$WALLET_CONTENT"
