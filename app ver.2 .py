# ライブラリのインポート
import streamlit as st          # Webアプリを作るためのフレームワーク
import pandas as pd             # 表形式データ（DataFrame）を扱うライブラリ。CSV保存に使用
from datetime import datetime   # 日付・時刻を扱う標準ライブラリ
from openai import OpenAI       # OpenAIのAPIを利用するためのクラス

# タイトルをアプリ画面に表示
st.title("命名支援ツール")

# OpenAIのクライアントを初期化（環境変数に保存したAPIキーを利用）
client = OpenAI()

# ------------------------------
# 入力フォーム（サイドバーに配置）
# ------------------------------
with st.sidebar:
    st.header("入力条件")  # サイドバーに見出しを表示

    # 性別をプルダウンで選択
    gender = st.selectbox("性別", ["指定なし", "男", "女"])

    # 漢字数をプルダウンで選択
    kanji_count = st.selectbox("漢字数", ["指定なし", "1", "2", "3"])

    # 使いたい漢字を自由入力
    use_kanji = st.text_input("使いたい漢字（任意）")

    # 避けたい漢字を自由入力
    avoid_kanji = st.text_input("避けたい漢字（任意）")

    # 名前に込めたい願いを文章で入力
    wish = st.text_area("願い（自由記述）")

# ------------------------------
# AIに送るプロンプトの作成
# ------------------------------
prompt = f"""
あなたは日本語の名前生成に詳しいアシスタントです。
次の条件に合う自然な名前候補を3〜5個提案してください。

【指定条件】
・性別：{gender}
・漢字数：{kanji_count}
・使いたい漢字：{use_kanji}
・避けたい漢字：{avoid_kanji}

【願い】
{wish}

【出力形式】
名前：〇〇（カタカナ）
理由：〜〜〜
"""

# ------------------------------
# 生成結果を表示するセクション
# ------------------------------
st.subheader("生成結果")

# 「名前を生成（API）」ボタンが押されたときの処理
if st.button("名前を生成（API）"):
    # OpenAIのチャットモデルにプロンプトを送信
    response = client.chat.completions.create(
        model="gpt-4o-mini",                        # 使用するAIモデル
        messages=[{"role": "user", "content": prompt}],  # ユーザー入力としてプロンプトを渡す
        max_tokens=500                             # 応答の最大トークン数（出力文字数の上限）
    )

    # AIから返ってきたテキストを取得
    output = response.choices[0].message.content

    # 生成結果を画面に表示（Markdown形式で整形）
    st.markdown(output)

    # ------------------------------
    # 生成結果をCSVに保存
    # ------------------------------
    df = pd.DataFrame([[
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # 実行時刻
        gender,                                        # 入力した性別
        kanji_count,                                   # 入力した漢字数
        use_kanji,                                     # 入力した使いたい漢字
        avoid_kanji,                                   # 入力した避けたい漢字
        wish,                                          # 入力した願い
        output                                         # AIが生成した名前候補
    ]], columns=["timestamp", "性別", "漢字数", "使いたい漢字", "避けたい漢字", "願い", "生成候補"])

    # ファイル名を実行日ごとに変更（例：names_api_20250907.csv）
    filename = f"names_api_{datetime.now().strftime('%Y%m%d')}.csv"

    # CSVに追記モードで保存（utf-8-sigでExcelでも文字化けしない）
    df.to_csv(filename, index=False, mode="a", header=False, encoding="utf-8-sig")

    # 保存が完了したことをユーザーに通知
    st.success(f"候補を {filename} に保存しました！")

# ------------------------------
# 評価アンケートへのリンクを表示
# ------------------------------
st.markdown("---")  # 区切り線を表示
st.markdown("### 評価アンケートはこちら")
st.markdown("[👉 Googleフォームで評価する](https://www.amazon.co.jp/)")




