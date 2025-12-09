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
# サイドバーではなく、メイン画面上部に折りたたみメニューとして配置
with st.expander("入力条件を開く", expanded=True):
    
    # --------------------------------------------------
    # 1. UI改善 & 苗字・詳細条件の入力
    # --------------------------------------------------
    st.markdown("### 📋 命名の条件")

    # ジャンル選択（横並びにする）
    target_type = st.radio("命名する対象", ["人間", "ペット", "キャラクター"], horizontal=True)

    # 苗字と性別を横並びにする
    col1, col2 = st.columns(2)
    with col1:
        surname = st.text_input("苗字（省略可）", placeholder="例：佐藤")
    with col2:
        gender = st.selectbox("性別", ["指定なし", "男", "女"])

    # 漢字数（スライダーをやめて、セレクトボックスに変更）
    kanji_count = st.selectbox("名前の漢字数", ["指定なし", "1文字", "2文字", "3文字"])

    # 使いたい漢字・避けたい漢字（横並びで見やすく）
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
# --------------------------------------------------
# 2. プロンプト（AIへの指示）の実行と表示
# --------------------------------------------------
if submit_btn:
    if not wish:
        st.warning("「願い」を入力してください！")
    else:
        # 苗字がある場合とない場合でメッセージを変える
        surname_text = f"苗字「{surname}」" if surname else "苗字なし"

        # プロンプト作成
        prompt = f"""
        あなたは辛口かつ的確なプロの命名アドバイザーです。
        以下の条件に基づいて、名前を3つ提案してください。
        
        【重要：評価システム】
        提案する名前と{surname_text}の組み合わせについて、以下の3項目で厳密に採点（各100点満点）し、
        その平均を「総合点」として算出してください。
        AIが考えた名前だからといって満点にせず、客観的に評価してください。

        1. 【語呂】苗字とつなげて呼んだ時のリズム、言いやすさ
        2. 【字面】漢字の並びの美しさ、画数のバランス
        3. 【独創性】ありきたりすぎず、かつキラキラネームすぎないか

        【条件】
        ・対象：{target_type}
        ・性別：{gender}
        ・漢字数：{kanji_count}
        ・使いたい漢字：{use_kanji}
        ・避けたい漢字：{avoid_kanji}
        ・願い：{wish}
        
        【出力形式】
        **太字記号は使わず**、以下の形式で出力すること。

        ---
        名前：〇〇（ヨミ）
        総合ランク：A（88点）
        [内訳]
        ・語呂：90点
        ・字面：85点
        ・独創性：89点
        
        理由：〜〜〜
        ---
        """

        # AIに問い合わせ
        with st.spinner("💎 厳密な基準で選定・採点中..."):
            try:
                # API呼び出し
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                
                # AIの返事を受け取る
                response_content = response.choices[0].message.content

                # 結果表示
                st.success("命名案が完成しました！")
                st.markdown("### 📝 提案結果と分析")
                
                # 青い枠で表示
                st.info(response_content)

                # ------------------------------
                # 生成結果をCSVに保存
                # ------------------------------
                df = pd.DataFrame([[
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    target_type,
                    gender,
                    kanji_count,
                    use_kanji,
                    avoid_kanji,
                    wish,
                    response_content
                ]], columns=["timestamp", "対象", "性別", "漢字数", "使いたい漢字", "避けたい漢字", "願い", "生成候補"])

                filename = f"names_api_{datetime.now().strftime('%Y%m%d')}.csv"
                df.to_csv(filename, index=False, mode="a", header=False, encoding="utf-8-sig")
                
                st.caption(f"※結果は自動的に {filename} に保存されました")
            
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")

# ------------------------------
# 評価アンケートへのリンクを表示
# ------------------------------
st.markdown("---")  # 区切り線を表示
st.markdown("### 評価アンケートはこちら")
st.markdown("[👉 Googleフォームで評価する](https://www.amazon.co.jp/)")






























