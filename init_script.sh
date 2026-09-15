#!/bin/bash
set -euo pipefail

# 全ログをファイルにも出力する
exec > >(tee -a /var/log/init_script.log) 2>&1

echo "OCI AI Data Platform Lab Console のセットアップを初期化中..."

# Configuration
INSTALL_DIR="/u01/aipoc"
APP_DIR="${INSTALL_DIR}/no.1-oci-aidp-lakehouse-lab"
WALLETS_DIR="${INSTALL_DIR}/wallets"
VENV_BIN="${INSTALL_DIR}/.venv/bin"

# Helper function for retrying commands
retry_command() {
    local max_attempts=5
    local timeout=10
    local attempt=1
    local exit_code=0

    while [ $attempt -le $max_attempts ]; do
        echo "Attempt $attempt of $max_attempts: $*"
        "$@" && return 0
        exit_code=$?
        echo "Command failed with exit code $exit_code. Retrying in $timeout seconds..."
        sleep $timeout
        attempt=$((attempt + 1))
        timeout=$((timeout * 2))
    done

    echo "Command failed after $max_attempts attempts."
    return $exit_code
}

cd "$INSTALL_DIR"

# ウォレットを展開（thin mode の wallet_location で使用）
echo "ウォレットを展開中..."
mkdir -p "${WALLETS_DIR}/atp" "${WALLETS_DIR}/lh"
if [ -f "${INSTALL_DIR}/props/wallet_atp.zip" ]; then
    unzip -o -q "${INSTALL_DIR}/props/wallet_atp.zip" -d "${WALLETS_DIR}/atp"
    echo "ATP ウォレット: ${WALLETS_DIR}/atp"
    ls -la "${WALLETS_DIR}/atp"
else
    echo "警告: ${INSTALL_DIR}/props/wallet_atp.zip が見つかりません！"
fi
if [ -f "${INSTALL_DIR}/props/wallet_lh.zip" ]; then
    unzip -o -q "${INSTALL_DIR}/props/wallet_lh.zip" -d "${WALLETS_DIR}/lh"
    echo "Lakehouse ウォレット: ${WALLETS_DIR}/lh"
    ls -la "${WALLETS_DIR}/lh"
else
    echo "警告: ${INSTALL_DIR}/props/wallet_lh.zip が見つかりません！"
fi

# Move to app directory
echo "アプリケーションを設定中..."
cd "$APP_DIR"

dos2unix main.cron || sed -i 's/\r$//' main.cron
crontab main.cron

# Update environment variables
echo "環境変数を設定中..."
install -m 0600 .env.example .env

# Values containing '/', '@', '&', and backslashes are preserved exactly.
source ./scripts/dotenv_util.sh

if [ -f "${INSTALL_DIR}/props/atp.env" ]; then
    ATP_CONNECTION_STRING=$(cat "${INSTALL_DIR}/props/atp.env")
    set_env_value ".env" "ORACLE_26AI_CONNECTION_STRING" "$ATP_CONNECTION_STRING"
else
    echo "警告: ${INSTALL_DIR}/props/atp.env が見つかりません！"
fi

if [ -f "${INSTALL_DIR}/props/lakehouse.env" ]; then
    LH_CONNECTION_STRING=$(cat "${INSTALL_DIR}/props/lakehouse.env")
    set_env_value ".env" "ORACLE_LAKEHOUSE_CONNECTION_STRING" "$LH_CONNECTION_STRING"
else
    echo "警告: ${INSTALL_DIR}/props/lakehouse.env が見つかりません！"
fi

if [ -f "${INSTALL_DIR}/props/admin_web_password.txt" ]; then
    APP_ADMIN_PASSWORD_VALUE=$(cat "${INSTALL_DIR}/props/admin_web_password.txt")
    set_env_value ".env" "APP_ADMIN_PASSWORD" "$APP_ADMIN_PASSWORD_VALUE"
else
    echo "警告: ADMIN Web認証パスワードの設定ファイルが見つかりません！"
fi

if [ -f "${INSTALL_DIR}/props/compartment_id.txt" ]; then
    COMPARTMENT_ID=$(cat "${INSTALL_DIR}/props/compartment_id.txt")
    set_env_value ".env" "OCI_COMPARTMENT_OCID" "$COMPARTMENT_ID"
else
    echo "警告: ${INSTALL_DIR}/props/compartment_id.txt が見つかりません！"
fi

if [ -f "${INSTALL_DIR}/props/aidp_ocid.txt" ]; then
    AIDP_OCID=$(cat "${INSTALL_DIR}/props/aidp_ocid.txt")
    set_env_value ".env" "AIDP_OCID" "$AIDP_OCID"
fi

if [ -f "${INSTALL_DIR}/props/oac_name.txt" ]; then
    OAC_NAME=$(cat "${INSTALL_DIR}/props/oac_name.txt")
    set_env_value ".env" "OAC_NAME" "$OAC_NAME"
fi

if [ -f "${INSTALL_DIR}/props/bucket_name.txt" ]; then
    BUCKET_NAME=$(cat "${INSTALL_DIR}/props/bucket_name.txt")
    set_env_value ".env" "BUCKET_NAME" "$BUCKET_NAME"
fi

if [ -f "${INSTALL_DIR}/props/region.txt" ]; then
    REGION=$(cat "${INSTALL_DIR}/props/region.txt")
    set_env_value ".env" "OCI_REGION" "$REGION"
fi

# ADB 管理タブ用コンテキスト（Lakehouse を主参照とする）
if [ -f "${INSTALL_DIR}/props/lakehouse_name.txt" ]; then
    ADB_NAME=$(cat "${INSTALL_DIR}/props/lakehouse_name.txt")
    set_env_value ".env" "ADB_NAME" "$ADB_NAME"
fi

# Wallet directory setup
set_env_value ".env" "WALLET_ATP_DIR" "${WALLETS_DIR}/atp"
set_env_value ".env" "WALLET_LH_DIR" "${WALLETS_DIR}/lh"

# External IP
echo "アプリケーションを設定中..."
EXTERNAL_IP=$(curl -s -m 10 http://whatismyip.akamai.com/ || echo "")
echo "外部IP: $EXTERNAL_IP"

if [ -n "$EXTERNAL_IP" ]; then
    set_env_value ".env" "EXTERNAL_IP" "$EXTERNAL_IP"
else
    echo "警告: EXTERNAL_IPの検出に失敗しました"
fi

# Python virtualenv
echo "Python仮想環境を作成中..."
if [ ! -d "${INSTALL_DIR}/.venv" ]; then
    retry_command python3 -m venv "${INSTALL_DIR}/.venv"
fi
echo "依存関係をインストール中..."
"${VENV_BIN}/pip" install --upgrade pip
"${VENV_BIN}/pip" install -r requirements.txt

# Run application
echo "アプリケーションを起動中..."
chmod +x main.sh
nohup ./main.sh > /var/log/no1-aidp-lab.log 2>&1 &

echo "初期化が完了しました。"
