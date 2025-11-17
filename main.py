import os
import requests
import discord
from discord.ext import tasks
from datetime import datetime, timezone
from dotenv import load_dotenv

# 明示的にローカルの `discord.env` を読み込む（存在すれば）
load_dotenv("discord.env")


def get_required_env(name, cast=str):
    """環境変数を取得して必須チェックを行い、必要なら型変換する。"""
    val = os.getenv(name)
    if val is None:
        print(f"環境変数 `{name}` が設定されていません。`discord.env` を確認するか環境変数を設定してください。")
        raise SystemExit(1)
    try:
        return cast(val)
    except Exception as e:
        print(f"環境変数 `{name}` の値 `{val}` を {cast.__name__} に変換できませんでした: {e}")
        raise SystemExit(1)


TENANT_ID = get_required_env("TENANT_ID")
CLIENT_ID = get_required_env("CLIENT_ID")
CLIENT_SECRET = get_required_env("CLIENT_SECRET")
DISCORD_TOKEN = get_required_env("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = get_required_env("DISCORD_CHANNEL_ID", cast=int)



def is_sane_discord_token(token: str) -> bool:
    """簡易的なトークン妥当性チェック。

    - プレースホルダ（xxxx...）や空文字を弾く
    - あまりに短いトークンも弾く（目安）
    """
    if not token:
        return False
    if token.startswith("xxxxxxxx") or token.lower().startswith("placeholder"):
        return False
    if len(token) < 20:
        return False
    return True

intents = discord.Intents.default()
client = discord.Client(intents=intents)

posted_assignments = set()

# Microsoft Graph のトークン取得
def get_graph_token():
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials"
    }
    res = requests.post(url, data=data)
    return res.json().get("access_token")

# Teams の課題取得
def get_assignments(token):
    url = "https://graph.microsoft.com/v1.0/education/me/assignments"
    headers = {"Authorization": f"Bearer {token}"}
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        print("Error", res.text)
        return []
    return res.json().get("value", [])

# 課題の通知フォーマット
def build_message(a):
    title = a.get("displayName", "タイトル不明")
    due = a.get("dueDateTime")
    if due:
        due_dt = datetime.fromisoformat(due.replace("Z", "+00:00"))
        due_str = due_dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M(UTC)")
    else:
        due_str = "なし"

    return f"📘 **新しい課題が追加されました！**\n" \
           f"**タイトル：** {title}\n" \
           f"**締切：** {due_str}\n"

# 定期的に課題を監視
@tasks.loop(minutes=5)
async def check_assignments():
    token = get_graph_token()
    data = get_assignments(token)

    channel = client.get_channel(DISCORD_CHANNEL_ID)

    for a in data:
        if a["id"] not in posted_assignments:
            posted_assignments.add(a["id"])
            msg = build_message(a)
            await channel.send(msg)

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    check_assignments.start()

client.run(DISCORD_TOKEN)
