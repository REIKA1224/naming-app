# ライブラリのインポート
import streamlit as st          # Webアプリを作るためのフレームワーク
import pandas as pd             # 表形式データ（DataFrame）を扱うライブラリ。CSV保存に使用
from datetime import datetime   # 日付・時刻を扱う標準ライブラリ
from openai import OpenAI       # OpenAIのAPIを利用するためのクラス

# その下にタイトル
st.title("AI 命名支援ツール")


# OpenAIのクライアントを初期化
client = OpenAI()

# ------------------------------
# 入力フォーム
# -----------------------------    
        
        st.markdown("### 📋 命名の条件")

        # ジャンル選択
        target_type = st.radio("命名する対象", ["人間", "ペット", "キャラクター"], horizontal=True)

        # 苗字と性別
        col1, col2 = st.columns(2)
        with col1:
            surname = st.text_input("苗字（省略可）", placeholder="例：佐藤")
        with col2:
            gender = st.selectbox("性別", ["指定なし", "男", "女"])

        # 漢字数
        kanji_count = st.selectbox("名前の漢字数", ["指定なし", "1文字", "2文字", "3文字"])

        # 使いたい漢字・避けたい漢字
        col3, col4 = st.columns(2)
        with col3:
            use_kanji = st.text_input("使いたい漢字", placeholder="例：翔、愛")
        with col4:
            avoid_kanji = st.text_input("避けたい漢字", placeholder="例：悪、死")

        # 願いの入力
        wish = st.text_area("どんな願いを込めますか？", placeholder="例：優しくて芯の強い子に育ってほしい")

        # 生成ボタン
        submit_btn = st.button("✨ AIに名前を考えてもらう", use_container_width=True, type="primary")

# --------------------------------------------------
# 2. プロンプト（AIへの指示）の変更
# --------------------------------------------------
if submit_btn:
    if not wish:
        st.warning("「願い」を入力してください！")
    else:
        # 苗字がある場合とない場合でメッセージを変える
        surname_text = f"苗字「{surname}」" if surname else "苗字なし"

        # プロンプト：ランク評価（S/A/B/C）を出すように指示を追加
        prompt = f"""
        あなたはプロの命名アドバイザーです。
        以下の条件に基づいて、素晴らしい名前を3つ提案してください。
        
        また、提案する名前が{surname_text}とつながった時の「響きの良さ」や「字面の美しさ」を総合的に判断し、
        【ランク】（S, A, B, C）をつけてください。
        
        【条件】
        ・性別：{gender}
        ・漢字数：{kanji_count}文字
        ・願い：{wish}
        
        【出力形式】
        必ず以下のフォーマットで出力してください。

        ---
        名前：〇〇（ヨミ）
        ランク：S
        理由：〜〜〜
        ---
        名前：〇〇（ヨミ）
        ランク：A
        理由：〜〜〜
        ---
        """

        # AIに問い合わせ
        with st.spinner("💎 最高の名前を考案中..."):

            # response_content = ... (AIの返事を受け取った後)

            st.success("命名案が完成しました！")
            
            # AIの回答を表示
            import re
    
            st.markdown("### 📝 提案結果")
            st.markdown(response_content) 
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

    # CSVに追記モードで保存
    df.to_csv(filename, index=False, mode="a", header=False, encoding="utf-8-sig")

    # 保存が完了したことをユーザーに通知
    st.success(f"候補を {filename} に保存しました！")
    

# ------------------------------
# 評価アンケートへのリンクを表示
# ------------------------------
st.markdown("---")  # 区切り線を表示
st.markdown("### 評価アンケートはこちら")
st.markdown("[👉 Googleフォームで評価する](https://www.amazon.co.jp/)")
























