import streamlit as st
import pandas as pd
from datetime import datetime
from openai import OpenAI

st.title("命名支援ツール")

client = OpenAI()

# 入力フォーム
with st.sidebar:
    st.header("入力条件")
    gender = st.selectbox("性別", ["指定なし", "男", "女"])
    kanji_count = st.selectbox("漢字数", ["指定なし", "1", "2", "3"])
    use_kanji = st.text_input("使いたい漢字（任意）")
    avoid_kanji = st.text_input("避けたい漢字（任意）")
    wish = st.text_area("願い（自由記述）")

# プロンプト生成
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

st.subheader("生成結果")

if st.button("名前を生成（API）"):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500
    )
    output = response.choices[0].message.content
    st.markdown(output)

    # CSV保存
    df = pd.DataFrame([[
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        gender, kanji_count, use_kanji, avoid_kanji, wish, output
    ]], columns=["timestamp", "性別", "漢字数", "使いたい漢字", "避けたい漢字", "願い", "生成候補"])

    filename = f"names_api_{datetime.now().strftime('%Y%m%d')}.csv"
    df.to_csv(filename, index=False, mode="a", header=False, encoding="utf-8-sig")
    st.success(f"候補を {filename} に保存しました！")

# Googleフォームへのリンクを表示
st.markdown("---")
st.markdown("### 評価アンケートはこちら")
st.markdown("[👉 Googleフォームで評価する](https://www.amazon.co.jp/)")


